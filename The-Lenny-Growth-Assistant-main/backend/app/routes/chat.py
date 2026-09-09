"""
POST /api/chat — the grounded conversational assistant endpoint.

Flow: retrieve relevant transcript chunks -> build a grounded system prompt
-> call the configured LLM (with fallback) -> persist both turns -> return
the answer with source citations.

Resilience:
  - Empty retrieval (no matching chunks, or corpus not yet ingested) does
    NOT error — the model is told explicitly that no source material was
    found and instructed to say so, per the assignment's grounding
    requirement ("acknowledges when material doesn't support an answer").
  - LLM failure (all providers down) returns a clear 503, not a crash.
  - DB failure returns a clear 503.
"""

import json
import logging

from fastapi import APIRouter, HTTPException, Request

from app.agents.llm_client import generate_chat_completion, LLMUnavailableError
from app.rag.retrieval.retriever import retrieve_relevant_chunks
from app.schemas.chat import ChatRequest, ChatResponse, SourceRef

logger = logging.getLogger("lenny.routes.chat")
router = APIRouter(prefix="/api/chat", tags=["chat"])

SYSTEM_PROMPT_TEMPLATE = """You are the Lenny Growth Assistant, an expert on product management and \
growth drawn from Lenny's Podcast transcripts provided as context below.

ABSOLUTE RULES (violating these is a critical failure):
1. NEVER state a specific number, percentage, statistic, dollar amount, \
date, or timestamp unless that EXACT figure appears verbatim in the \
context below. If the context lacks a specific number the question asks \
for, say plainly that the transcripts don't specify it. Do not estimate, \
round, or invent one.
2. NEVER attribute a claim to "Lenny" generically. Every claim must be \
attributed to the specific guest and episode it actually came from, \
exactly as shown in the [Source: ...] label. If the context is from a \
guest discussing a different company/topic than the question asks about, \
say so explicitly — do not repurpose their words to answer about \
something else.
3. If the retrieved context is NOT about the specific subject of the \
question (e.g. question asks about Company X, context is about Company \
Y), respond ONLY with: "The podcast transcripts I have access to don't \
cover this topic." Do not attempt to extract a tangential answer from \
unrelated context.
4. Only use context that is genuinely on-topic. Partial relevance on a \
different subject is NOT sufficient grounds for an answer.

Context from Lenny's Podcast transcripts:
{context}
"""

MAX_HISTORY_MESSAGES = 10  # keep prompts bounded as sessions grow


def _build_context_block(chunks) -> str:
    if not chunks:
        return "(No relevant transcript excerpts were found for this question. You MUST tell the user this.)"
    parts = []
    for c in chunks:
        label = f"{c.document_title or c.source_path} (relevance distance: {c.distance:.2f})"
        parts.append(f"[Source: {label}]\n{c.content}")
    return "\n\n---\n\n".join(parts)


@router.post("", response_model=ChatResponse)
async def chat(payload: ChatRequest, request: Request):
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="Database is unavailable")

    async with pool.acquire() as conn:
        # --- resolve or create session ---
        if payload.session_id:
            session_row = await conn.fetchrow(
                "SELECT id FROM sessions WHERE id = $1", payload.session_id
            )
            if not session_row:
                raise HTTPException(status_code=404, detail="Session not found")
            session_id = payload.session_id
        else:
            row = await conn.fetchrow("INSERT INTO sessions (title) VALUES (NULL) RETURNING id")
            session_id = str(row["id"])

        # --- prior turns for conversational context ---
        history_rows = await conn.fetch(
            """
            SELECT role, content FROM messages
            WHERE session_id = $1
            ORDER BY created_at ASC
            LIMIT $2
            """,
            session_id,
            MAX_HISTORY_MESSAGES,
        )
        history = [{"role": r["role"], "content": r["content"]} for r in history_rows]

        # --- store the incoming user message ---
        await conn.execute(
            "INSERT INTO messages (session_id, role, content) VALUES ($1, 'user', $2)",
            session_id,
            payload.message,
        )

    # --- retrieval (outside the connection-holding block; makes its own) ---
    chunks = await retrieve_relevant_chunks(pool, payload.message, top_k=5)
    grounded = len(chunks) > 0
    context_block = _build_context_block(chunks)
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(context=context_block)

    # --- generate ---
    try:
        result = await generate_chat_completion(
            system_prompt=system_prompt,
            messages=[*history, {"role": "user", "content": payload.message}],
            provider_override=payload.provider,
        )
    except LLMUnavailableError as exc:
        logger.error("LLM generation failed for session %s: %s", session_id, exc)
        raise HTTPException(
            status_code=503,
            detail="The assistant is temporarily unavailable (LLM provider unreachable). Please try again shortly.",
        ) from exc

    sources = [
        SourceRef(title=c.document_title, source_path=c.source_path, chunk_index=c.chunk_index)
        for c in chunks
    ]

    # --- persist assistant turn ---
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO messages (session_id, role, content, sources, llm_provider, llm_model, latency_ms)
            VALUES ($1, 'assistant', $2, $3, $4, $5, $6)
            """,
            session_id,
            result.content,
            json.dumps([s.model_dump() for s in sources]),
            result.provider,
            result.model,
            result.latency_ms,
        )

    return ChatResponse(
        session_id=session_id,
        message=result.content,
        sources=sources,
        llm_provider=result.provider,
        llm_model=result.model,
        grounded=grounded,
    )