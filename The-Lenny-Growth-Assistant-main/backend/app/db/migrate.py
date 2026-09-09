"""
Minimal migration runner.

Applies every .sql file in db/migrations/ (relative to repo root) in
filename order, tracking what's already been applied in a `schema_migrations`
table. Run with: python -m app.db.migrate

Kept intentionally simple (no Alembic) — swap for a real migration tool
later if the schema grows complex enough to need rollbacks.
"""

import asyncio
import os
import sys
from pathlib import Path

import asyncpg

from app.config import get_settings


MIGRATIONS_DIR = Path(os.environ.get("MIGRATIONS_DIR", "/app/db/migrations"))


async def ensure_migrations_table(conn: asyncpg.Connection) -> None:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            filename TEXT PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


async def get_applied(conn: asyncpg.Connection) -> set[str]:
    rows = await conn.fetch("SELECT filename FROM schema_migrations")
    return {r["filename"] for r in rows}


async def run_migrations() -> None:
    settings = get_settings()
    if not settings.database_url:
        print("DATABASE_URL is not set. Aborting.", file=sys.stderr)
        sys.exit(1)

    if not MIGRATIONS_DIR.exists():
        print(f"Migrations dir not found: {MIGRATIONS_DIR}", file=sys.stderr)
        sys.exit(1)

    sql_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not sql_files:
        print("No migration files found.")
        return

    conn = await asyncpg.connect(settings.database_url)
    try:
        await ensure_migrations_table(conn)
        applied = await get_applied(conn)

        for path in sql_files:
            if path.name in applied:
                print(f"skip  {path.name} (already applied)")
                continue

            print(f"apply {path.name} ...")
            sql = path.read_text(encoding="utf-8")
            async with conn.transaction():
                await conn.execute(sql)
                await conn.execute(
                    "INSERT INTO schema_migrations (filename) VALUES ($1)", path.name
                )
            print(f"done  {path.name}")

        print("All migrations applied.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_migrations())