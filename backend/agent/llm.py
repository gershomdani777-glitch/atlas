from __future__ import annotations

"""Stage 2 (Interpret) — the reasoning layer. Calls Google Gemini with
structured output bound to ThesisCandidateList so the model can only ever
*propose* a fixed-schema thesis, never issue a raw buy/sell instruction.

On any failure (missing key, timeout, rate limit, malformed structured
output) this returns an empty candidate list and degraded=True rather than
raising — the rest of the 7-stage loop (regime classification, risk
throttling, outcome tracking, adaptation) must keep running on quant-only
logic even when the LLM is unavailable, per the PRD's resilience NFR.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

from langchain_google_genai import ChatGoogleGenerativeAI

from config import settings

from . import memory
from .state import AgentState, ThesisCandidate, ThesisCandidateList

logger = logging.getLogger("atlas.llm")

_llm = None
_executor = ThreadPoolExecutor(max_workers=2)

SYSTEM_PROMPT = """You are the interpretation layer of ATLAS, an autonomous paper-trading agent.

Your ONLY job is to PROPOSE candidate trade theses. You never size positions
and you never execute trades — a separate deterministic risk engine decides
whether to accept, reject, or resize every thesis you propose.

For each asset in the provided market snapshot:
- Ground your thesis strictly in the supplied market data and, where given,
  your own past (thesis -> outcome) history for that asset.
- If no defensible thesis exists, set direction to "no_action" rather than
  forcing a speculative call.
- expected_edge_bps is your estimate of gross expected edge in basis points
  before costs; confidence is 0.0-1.0.
- Do not fabricate news or information not present in the snapshot.

Respond with one ThesisCandidate per asset in the snapshot."""


def _get_llm() -> ChatGoogleGenerativeAI:
    global _llm
    if _llm is None:
        _llm = ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.google_api_key,
            temperature=0.4,
        )
    return _llm


def _build_prompt(state: AgentState, memory_by_asset: dict[str, list[dict]]) -> str:
    lines = ["Current market snapshot:\n"]
    for symbol, asset in state["assets"].items():
        if asset.stale:
            lines.append(f"- {symbol.upper()}: STALE DATA, skip unless you can justify no_action.")
            continue
        lines.append(
            f"- {symbol.upper()}: price={asset.price}, volatility={asset.volatility:.4f}, "
            f"trend={asset.trend:.2f}, liquidity={asset.liquidity:.2f}, regime={asset.regime}, "
            f"spread_bps={asset.spread_bps:.1f}"
        )
        matches = memory_by_asset.get(symbol, [])
        for match in matches:
            lines.append(f"    past: \"{match['thesis_text']}\" -> {match['outcome_summary']}")
    return "\n".join(lines)


def get_thesis_candidates(state: AgentState) -> tuple[list[ThesisCandidate], bool]:
    if not settings.google_api_key:
        logger.info("GOOGLE_API_KEY not set; interpret() degrading to no candidates this cycle.")
        state["memory_context"] = {}
        return [], True

    queries = {
        symbol: f"{symbol} regime={asset.regime} trend={asset.trend:.2f} volatility={asset.volatility:.4f}"
        for symbol, asset in state["assets"].items()
        if not asset.stale
    }
    # One batched embedding call for every active asset this cycle, not one
    # call per asset — the free-tier daily quota doesn't forgive N-per-cycle.
    memory_by_asset = memory.retrieve_similar_batch(queries)
    state["memory_context"] = memory_by_asset

    prompt = _build_prompt(state, memory_by_asset)

    try:
        llm = _get_llm().with_structured_output(ThesisCandidateList)
        future = _executor.submit(llm.invoke, [("system", SYSTEM_PROMPT), ("human", prompt)])
        result = future.result(timeout=settings.llm_timeout_seconds)
        candidates = result.candidates if isinstance(result, ThesisCandidateList) else []
        known_assets = set(state["assets"].keys())
        normalized = []
        for c in candidates:
            if c.asset.lower() in known_assets:
                c.asset = c.asset.lower()  # Gemini often echoes the symbol back uppercased
                normalized.append(c)
        return normalized, False
    except FutureTimeoutError:
        logger.warning("Gemini interpret() call timed out after %ss; no new theses this cycle.", settings.llm_timeout_seconds)
        return [], True
    except Exception as exc:
        logger.warning("Gemini interpret() call failed: %s; no new theses this cycle.", exc)
        return [], True
