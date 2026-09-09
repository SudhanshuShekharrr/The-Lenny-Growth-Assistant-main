"""
Async PostgreSQL connection pool (asyncpg).

A single shared pool lives on `app.state.db_pool` for the process lifetime
(created/closed via the FastAPI lifespan handler in main.py). Session/message
models added in a later step will pull connections from this pool rather than
opening their own.
"""

import asyncpg
import logging
from app.config import Settings

logger = logging.getLogger("lenny.db")


async def create_pool(settings: Settings) -> asyncpg.Pool:
    return await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=1,
        max_size=10,
        command_timeout=10,
    )


async def close_pool(pool: asyncpg.Pool | None) -> None:
    if pool is not None:
        await pool.close()


async def check_db_connection(pool: asyncpg.Pool | None) -> bool:
    """Used by /health/ready to confirm the DB is actually reachable."""
    if pool is None:
        return False
    try:
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return True
    except Exception as exc:  # noqa: BLE001 — deliberately broad for a health probe
        logger.error("DB connection check failed: %s", exc)
        return False
