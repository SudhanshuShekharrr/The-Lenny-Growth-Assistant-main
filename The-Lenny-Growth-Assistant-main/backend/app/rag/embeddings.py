"""
Thin wrapper around Ollama's embeddings API.

Kept separate from the LLM chat client (added in the agent-layer step) since
embeddings and chat generation are called independently and may even use
different models.
"""

import logging
import httpx

from app.config import get_settings

logger = logging.getLogger("lenny.rag.embeddings")


class EmbeddingError(Exception):
    """Raised when an embedding request fails after retries."""


async def embed_text(text: str, retries: int = 3, timeout: float = 30.0) -> list[float]:
    """
    Calls Ollama's /api/embeddings endpoint for a single piece of text.
    Retries on transient failures (timeouts, connection errors) since
    ingestion runs unattended and Ollama can be briefly warming up a model.
    """
    settings = get_settings()
    url = f"{settings.ollama_base_url}/api/embeddings"
    payload = {"model": settings.ollama_embed_model, "prompt": text}

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                embedding = data.get("embedding")
                if not embedding:
                    raise EmbeddingError(f"No embedding in response: {data}")
                return embedding
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            logger.warning("Embedding attempt %d/%d failed: %s", attempt, retries, exc)

    raise EmbeddingError(f"Embedding failed after {retries} attempts: {last_error}")