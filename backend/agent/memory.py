from __future__ import annotations

"""Outcome-conditioned memory: embed thesis+outcome text into pgvector and
retrieve the top-k most similar past situations for a given asset before
the next Interpret call. Every call is best-effort — a failure here must
never break the agent cycle, only degrade it to "no memory context".

Retrieval is batched across all assets into a single Gemini embedding call
per cycle (`retrieve_similar_batch`) rather than one call per asset — on a
free-tier daily quota, N separate network calls where one batched call
would do is pure waste."""

import logging

from langchain_google_genai import GoogleGenerativeAIEmbeddings

from config import settings
from db import repository
from db.session import get_session

logger = logging.getLogger("atlas.memory")

_embeddings: GoogleGenerativeAIEmbeddings | None = None


def _get_embeddings_client() -> GoogleGenerativeAIEmbeddings | None:
    global _embeddings
    if not settings.google_api_key:
        return None
    if _embeddings is None:
        _embeddings = GoogleGenerativeAIEmbeddings(
            model=settings.gemini_embedding_model,
            google_api_key=settings.google_api_key,
        )
    return _embeddings


def embed_text(text: str) -> list[float] | None:
    client = _get_embeddings_client()
    if client is None:
        return None
    try:
        return client.embed_query(text)
    except Exception as exc:
        logger.warning("Embedding call failed: %s", exc)
        return None


def retrieve_similar_batch(queries: dict[str, str], k: int | None = None) -> dict[str, list[dict]]:
    """queries: {asset_symbol: query_text}. Returns {asset_symbol: [{thesis_text,
    outcome_summary}, ...]}. One embedding API call for every asset in
    `queries`, not one call each — the whole point of this function over
    calling `embed_text` in a loop."""
    if not queries:
        return {}

    k = k or settings.memory_top_k
    client = _get_embeddings_client()
    if client is None:
        return {}

    symbols = list(queries.keys())
    try:
        embeddings = client.embed_documents(list(queries.values()))
    except Exception as exc:
        logger.warning("Batched embedding call failed for %d assets: %s", len(symbols), exc)
        return {}

    results: dict[str, list[dict]] = {}
    try:
        with get_session() as session:
            for symbol, embedding in zip(symbols, embeddings):
                asset = repository.get_asset_by_symbol(session, symbol)
                if asset is None:
                    continue
                rows = repository.query_similar_memories(session, asset.id, embedding, k)
                results[symbol] = [{"thesis_text": r.thesis_text, "outcome_summary": r.outcome_summary} for r in rows]
    except Exception as exc:
        logger.warning("Memory retrieval failed after embedding: %s", exc)
        return {}

    return results


def embed_and_store(record: dict) -> None:
    """record: {asset, thesis_text, outcome_summary, regime}. Best-effort;
    swallows failures so a persistence-loop failure here can't break the
    rest of the cycle's persistence."""
    embedding = embed_text(f"{record['thesis_text']} -> {record['outcome_summary']}")
    if embedding is None:
        return
    try:
        with get_session() as session:
            asset = repository.get_asset_by_symbol(session, record["asset"])
            if asset is None:
                return
            repository.record_memory_embedding(
                session,
                asset_id=asset.id,
                thesis_text=record["thesis_text"],
                outcome_summary=record["outcome_summary"],
                regime=record["regime"],
                embedding=embedding,
            )
    except Exception as exc:
        logger.warning("Failed to store memory embedding for %s: %s", record.get("asset"), exc)
