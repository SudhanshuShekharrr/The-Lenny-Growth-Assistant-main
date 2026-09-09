"""
Session management endpoints.

A session is just a container for message history + independent context.
No auth in scope for this step — sessions are created freely and identified
by their UUID.
"""

import json
import logging

from fastapi import APIRouter, HTTPException, Request

from app.schemas.chat import SessionCreateResponse, MessageOut, SourceRef

logger = logging.getLogger("lenny.routes.sessions")
router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("", response_model=SessionCreateResponse, status_code=201)
async def create_session(request: Request):
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="Database is unavailable")

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO sessions (title) VALUES (NULL) RETURNING id"
        )
    return SessionCreateResponse(session_id=str(row["id"]))


@router.get("/{session_id}/messages", response_model=list[MessageOut])
async def get_session_messages(session_id: str, request: Request):
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="Database is unavailable")

    async with pool.acquire() as conn:
        session_row = await conn.fetchrow("SELECT id FROM sessions WHERE id = $1", session_id)
        if not session_row:
            raise HTTPException(status_code=404, detail="Session not found")

        rows = await conn.fetch(
            """
            SELECT role, content, sources, created_at
            FROM messages
            WHERE session_id = $1
            ORDER BY created_at ASC
            """,
            session_id,
        )

    return [
        MessageOut(
            role=row["role"],
            content=row["content"],
            sources=[SourceRef(**s) for s in json.loads(row["sources"])],
            created_at=row["created_at"].isoformat(),
        )
        for row in rows
    ]