"""
GET /health        — liveness: process is up. Always 200.
GET /health/ready   — readiness: verifies DB (and Ollama, informationally)
                      are actually reachable, not just that the process started.

Kept separate so a slow/unreachable dependency doesn't flap the liveness probe.
"""

from datetime import datetime, timezone
import httpx
from fastapi import APIRouter, Request, Response

from app.config import get_settings
from app.db.session import check_db_connection

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "lenny-growth-assistant-backend",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health/ready")
async def ready(request: Request, response: Response):
    settings = get_settings()
    pool = getattr(request.app.state, "db_pool", None)
    db_ok = await check_db_connection(pool)

    # Ollama check is informational, not fatal — see resilience notes in README.
    ollama_ok: bool | None = None
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            ollama_ok = resp.status_code == 200
    except Exception:  # noqa: BLE001
        ollama_ok = False

    all_critical_ok = db_ok
    response.status_code = 200 if all_critical_ok else 503

    return {
        "status": "ready" if all_critical_ok else "not_ready",
        "checks": {"database": db_ok, "ollama": ollama_ok},
        "llmProvider": settings.llm_provider,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
