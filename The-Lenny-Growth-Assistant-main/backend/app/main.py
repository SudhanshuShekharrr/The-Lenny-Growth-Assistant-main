"""
Application entry point.

Step 1 scope: server bootstrapping, middleware, health checks, and DB
connectivity only. Session/chat routes, the agent layer, and RAG
ingestion/retrieval are intentionally NOT wired up yet — they land in
later steps on top of this foundation (see README "Roadmap").

Run directly with: uvicorn app.main:app --reload
"""

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.cors import CORSMiddleware

from app.config import get_settings, validate_settings
from app.db.session import create_pool, close_pool
from app.middleware.request_id import RequestIdMiddleware
from app.middleware.error_handlers import (
    http_exception_handler,
    validation_exception_handler,
    unhandled_exception_handler,
)
from app.routes.health import router as health_router
from app.routes.chat import router as chat_router
from app.routes.sessions import router as sessions_router
from app.routes.artifacts import router as artifacts_router
from app.routes.content import router as content_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("lenny.startup")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    problems = validate_settings(settings)
    if problems:
        logger.error("Invalid configuration:")
        for p in problems:
            logger.error("  - %s", p)
        sys.exit(1)

    logger.info("Lenny Growth Assistant backend starting...")
    logger.info("Environment: %s", settings.env)
    logger.info("LLM provider: %s", settings.llm_provider)

    # Resilience requirement: an unreachable database must not crash the whole
    # process. We try to connect, but if it fails we log loudly and start the
    # app anyway with a null pool — /health still returns 200 (liveness), and
    # /health/ready correctly reports 503/not_ready until the DB comes back.
    try:
        app.state.db_pool = await create_pool(settings)
        logger.info("Database pool created.")
    except Exception as exc:  # noqa: BLE001 — deliberately broad at startup boundary
        logger.error("Could not connect to database at startup: %s", exc)
        logger.error("Starting anyway in degraded mode — /health/ready will report not_ready.")
        app.state.db_pool = None

    yield

    logger.info("Shutting down...")
    await close_pool(getattr(app.state, "db_pool", None))
    logger.info("Database pool closed.")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Lenny Growth Assistant API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.cors_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIdMiddleware)

    # Registered against Starlette's base HTTPException (not just fastapi's
    # subclass) because Starlette's own routing raises the base class directly
    # for things like unmatched routes — using only the subclass would miss those.
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    app.include_router(health_router)

    app.include_router(chat_router)
    app.include_router(sessions_router)
    app.include_router(artifacts_router)
    app.include_router(content_router)

    # Future mount points (kept as comments so the intended shape is explicit):
    # app.include_router(session_router, prefix="/api/sessions")
    # app.include_router(chat_router, prefix="/api/chat")
    # app.include_router(artifact_router, prefix="/api/artifacts")

    return app


app = create_app()
