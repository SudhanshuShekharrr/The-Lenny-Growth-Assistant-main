"""
POST /api/artifacts — generates a Markdown document or a complete HTML/CSS
snippet based on the current conversation, per assignment requirement 4.3.

The LLM is instructed to return exactly one fenced code block (```markdown
or ```html) and nothing else, which we parse out. Grounded the same way as
chat: relevant transcript chunks are retrieved and included as context so
generated artifacts are backed by real source material where applicable.
"""

import logging
import re

from fastapi import APIRouter, HTTPException, Request

from app.agents.llm_client import generate_chat_completion, LLMUnavailableError
from app.rag.retrieval.retriever import retrieve_relevant_chunks
from app.schemas.artifact import ArtifactRequest, ArtifactResponse

logger = logging.getLogger("lenny.routes.artifacts")
router = APIRouter(prefix="/api/artifacts", tags=["artifacts"])

ARTIFACT_SYSTEM_PROMPT = """You generate a single downloadable artifact (a Markdown \
document OR a complete, self-contained HTML/CSS snippet) based on the \
conversation context and the user's instruction below.

Rules:
- Output EXACTLY ONE fenced code block, tagged either ```markdown or ```html.
- Output NOTHING else — no explanation before or after the code block.
- If the instruction and context support it, ground factual claims in the \
provided transcript excerpts. If asked for something the context doesn't \
support, still produce the artifact but do not invent facts as if they \
came from the podcast.
- If html: produce a complete, self-contained snippet (inline <style> is \
fine; no external network requests, no <script> that calls out to \
external URLs).

Context from Lenny's Podcast transcripts (may be empty):
{context}

User's instruction: {instruction}
"""

FENCE_PATTERN = re.compile(r"```(markdown|html)\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)


def _extract_artifact(raw_text: str) -> tuple[str, str]:
    match = FENCE_PATTERN.search(raw_text)
    if not match:
        # Fallback: treat the whole response as markdown rather than failing outright.
        return "markdown", raw_text.strip()
    artifact_type = match.group(1).lower()
    content = match.group(2).strip()
    return artifact_type, content


@router.post("", response_model=ArtifactResponse)
async def generate_artifact(payload: ArtifactRequest, request: Request):
    pool = request.app.state.db_pool
    if pool is None:
        raise HTTPException(status_code=503, detail="Database is unavailable")

    chunks = await retrieve_relevant_chunks(pool, payload.instruction, top_k=5)
    context_block = (
        "\n\n---\n\n".join(f"[Source: {c.document_title or c.source_path}]\n{c.content}" for c in chunks)
        if chunks
        else "(no relevant transcript excerpts found)"
    )

    system_prompt = ARTIFACT_SYSTEM_PROMPT.format(context=context_block, instruction=payload.instruction)

    try:
        result = await generate_chat_completion(
            system_prompt=system_prompt,
            messages=[{"role": "user", "content": payload.instruction}],
        )
    except LLMUnavailableError as exc:
        logger.error("Artifact generation failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="The assistant is temporarily unavailable. Please try again shortly.",
        ) from exc

    artifact_type, content = _extract_artifact(result.content)
    title = payload.instruction[:60] + ("..." if len(payload.instruction) > 60 else "")

    return ArtifactResponse(artifact_type=artifact_type, title=title, content=content)