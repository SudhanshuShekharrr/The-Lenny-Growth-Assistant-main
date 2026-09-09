"""
One-off debug script: shows raw similarity distances for a query against
the ingested corpus. Not part of the app — just for calibrating the
retrieval distance threshold. Safe to delete after use, or keep for
future debugging.

Run with: docker compose exec backend python app/debug_retrieval.py
"""

import asyncio
import asyncpg

from app.config import get_settings
from app.rag.embeddings import embed_text

QUERY = "What are some principles for building a culture of excellence at a company?"


async def main():
    settings = get_settings()
    embedding = await embed_text(QUERY)
    embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

    conn = await asyncpg.connect(settings.database_url)
    rows = await conn.fetch(
        """
        SELECT d.title, c.chunk_index, (c.embedding <=> $1::vector) AS distance
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        ORDER BY c.embedding <=> $1::vector
        LIMIT 10
        """,
        embedding_str,
    )
    for row in rows:
        print(f"{row['distance']:.4f}  {row['title']}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())