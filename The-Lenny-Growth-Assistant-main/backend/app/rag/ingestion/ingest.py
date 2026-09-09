"""
Ingestion orchestrator: clone -> parse -> chunk -> embed -> store.

Run with: python -m app.rag.ingestion.ingest [--limit N]

Refresh behavior: re-running this script re-clones the repo and re-checks
every transcript's content_hash. Unchanged documents are skipped entirely
(no re-embedding cost); changed or new documents are (re-)ingested — old
chunks for a changed document are deleted and replaced.
"""

import argparse
import asyncio
import logging
import sys

import asyncpg

from app.config import get_settings
from app.rag.embeddings import embed_text, EmbeddingError
from app.rag.ingestion.chunker import chunk_text
from app.rag.ingestion.loader import load_all_transcripts

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
logger = logging.getLogger("lenny.rag.ingest")


async def get_existing_hash(conn: asyncpg.Connection, source_path: str) -> str | None:
    row = await conn.fetchrow(
        "SELECT content_hash FROM documents WHERE source_path = $1", source_path
    )
    return row["content_hash"] if row else None


async def upsert_document(conn: asyncpg.Connection, transcript, existing_id: str | None) -> str:
    if existing_id:
        await conn.execute(
            """
            UPDATE documents
            SET title = $1,
                published_at = $2,
                content_hash = $3,
                ingested_at = now()
            WHERE id = $4
            """,
            transcript.title,
            transcript.publish_date,
            transcript.content_hash,
            existing_id,
        )
        await conn.execute("DELETE FROM chunks WHERE document_id = $1", existing_id)
        return existing_id

    row = await conn.fetchrow(
        """
        INSERT INTO documents (source_path, title, published_at, content_hash)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (source_path) DO UPDATE
            SET title = EXCLUDED.title,
                published_at = EXCLUDED.published_at,
                content_hash = EXCLUDED.content_hash,
                ingested_at = now()
        RETURNING id
        """,
        transcript.source_path,
        transcript.title,
        transcript.publish_date,
        transcript.content_hash,
    )
    return str(row["id"])


async def ingest_transcript(conn: asyncpg.Connection, transcript, stats: dict) -> None:
    existing_row = await conn.fetchrow(
        "SELECT id, content_hash FROM documents WHERE source_path = $1", transcript.source_path
    )

    if existing_row and existing_row["content_hash"] == transcript.content_hash:
        stats["skipped"] += 1
        return

    document_id = await upsert_document(
        conn, transcript, str(existing_row["id"]) if existing_row else None
    )

    chunks = chunk_text(transcript.body)
    logger.info("[%s] %d chunks to embed", transcript.source_path, len(chunks))

    for idx, chunk_content in enumerate(chunks):
        try:
            embedding = await embed_text(chunk_content)
        except EmbeddingError as exc:
            # Resilience: one bad chunk shouldn't kill the whole ingestion run.
            logger.error("[%s] chunk %d embedding failed, skipping: %s", transcript.source_path, idx, exc)
            stats["chunk_failures"] += 1
            continue

        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
        await conn.execute(
            """
            INSERT INTO chunks (document_id, chunk_index, content, embedding, token_count)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (document_id, chunk_index) DO UPDATE
                SET content = EXCLUDED.content, embedding = EXCLUDED.embedding
            """,
            document_id,
            idx,
            chunk_content,
            embedding_str,
            len(chunk_content.split()),
        )

    stats["ingested"] += 1


async def run(limit: int | None) -> None:
    settings = get_settings()
    if not settings.database_url:
        logger.error("DATABASE_URL not set. Aborting.")
        sys.exit(1)

    logger.info("Loading transcripts (limit=%s)...", limit)
    transcripts = load_all_transcripts(limit=limit)

    if not transcripts:
        logger.warning("No transcripts loaded — nothing to ingest.")
        return

    conn = await asyncpg.connect(settings.database_url)
    stats = {"ingested": 0, "skipped": 0, "chunk_failures": 0}
    try:
        for i, transcript in enumerate(transcripts, start=1):
            logger.info("(%d/%d) %s", i, len(transcripts), transcript.source_path)
            try:
                async with conn.transaction():
                    await ingest_transcript(conn, transcript, stats)
            except Exception as exc:  # noqa: BLE001
                # Resilience: one bad document shouldn't kill the whole run.
                logger.error("Failed to ingest %s: %s", transcript.source_path, exc)
    finally:
        await conn.close()

    logger.info(
        "Ingestion complete. ingested=%d skipped_unchanged=%d chunk_failures=%d",
        stats["ingested"], stats["skipped"], stats["chunk_failures"],
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest Lenny's Podcast transcripts into the RAG store.")
    parser.add_argument("--limit", type=int, default=None, help="Only ingest the first N transcripts (for testing).")
    args = parser.parse_args()
    asyncio.run(run(args.limit))