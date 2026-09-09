"""
Vector similarity retrieval over ingested transcript chunks.

Uses pgvector's cosine distance operator (<=>) directly via asyncpg —
no ORM needed for a single query like this. Returns chunks ordered by
relevance along with the source document metadata needed for citation
display in the UI (title, source_path).
"""

import logging
from dataclasses import dataclass

import asyncpg

from app.rag.embeddings import embed_text, EmbeddingError

logger = logging.getLogger("lenny.rag.retriever")


@dataclass
class RetrievedChunk:
    content: str
    chunk_index: int
    document_title: str | None
    source_path: str
    distance: float  # lower = more similar (cosine distance)


async def retrieve_relevant_chunks(
    pool: asyncpg.Pool, query: str, top_k: int = 5
) -> list[RetrievedChunk]:
    """
    Embeds the query and returns the top_k most similar chunks.
    Returns an empty list (not an error) if:
      - the corpus is empty (no chunks ingested yet)
      - the embedding call fails (Ollama down) — logged, not raised, so a
        chat request degrades to an ungrounded answer rather than a 500.
    """
    try:
        query_embedding = await embed_text(query)
    except EmbeddingError as exc:
        logger.error("Query embedding failed, returning no context: %s", exc)
        return []

    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT c.content, c.chunk_index, d.title, d.source_path,
                       (c.embedding <=> $1::vector) AS distance
                FROM chunks c
                JOIN documents d ON d.id = c.document_id
                ORDER BY c.embedding <=> $1::vector
                LIMIT $2
                """,
                embedding_str,
                top_k,
            )
    except Exception as exc:  # noqa: BLE001
        logger.error("Retrieval query failed: %s", exc)
        return []

    # Cosine distance threshold: chunks above this are too dissimilar to be
    # genuinely relevant. Filtering here prevents feeding irrelevant context
    # to the LLM, which otherwise tends to hallucinate confident-sounding
    # answers from weak matches instead of admitting no good match exists.
    MAX_RELEVANT_DISTANCE = 0.40

    relevant = [row for row in rows if row["distance"] <= MAX_RELEVANT_DISTANCE]

    return [
        RetrievedChunk(
            content=row["content"],
            chunk_index=row["chunk_index"],
            document_title=row["title"],
            source_path=row["source_path"],
            distance=row["distance"],
        )
        for row in relevant
    ]