from __future__ import annotations

"""Outcome-conditioned memory: embed thesis+outcome text into pgvector and
retrieve the top-k most similar past situations for a given asset before
the next Interpret call. Every call is best-effort — a failure here must
never break the agent cycle, only degrade it to "no memory context"."""

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


def retrieve_similar(asset_symbol: str, query_text: str, k: int | None = None) -> list[dict]:
    """Top-k similar (thesis, outcome) pairs for `asset_symbol`. Returns []
    on any failure (no API key, embedding error, no rows yet) rather than
    raising, so interpret() can always proceed with an empty memory context."""
    k = k or settings.memory_top_k
    embedding = embed_text(query_text)
    if embedding is None:
        return []

    try:
        with get_session() as session:
            asset = repository.get_asset_by_symbol(session, asset_symbol)
            if asset is None:
                return []
            rows = repository.query_similar_memories(session, asset.id, embedding, k)
            return [{"thesis_text": r.thesis_text, "outcome_summary": r.outcome_summary} for r in rows]
    except Exception as exc:
        logger.warning("Memory retrieval failed for %s: %s", asset_symbol, exc)
        return []


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
