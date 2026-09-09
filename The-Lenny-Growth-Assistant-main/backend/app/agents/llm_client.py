"""
LLM provider abstraction: Ollama (local, mandatory) and Anthropic (cloud,
optional), selected via LLM_PROVIDER with graceful fallback.

Fallback behavior (documented per assignment requirement):
  - If LLM_PROVIDER=anthropic/openai but the call fails (missing key, API
    error, timeout), we log the failure and fall back to Ollama rather than
    erroring the whole request — Ollama is the one provider guaranteed to be
    present for the demo.
  - If LLM_PROVIDER=ollama and Ollama itself is unreachable, we raise
    LLMUnavailableError so the chat endpoint can return a clear 503 instead
    of hanging or crashing.
"""

import logging
import time
from dataclasses import dataclass

import httpx

from app.config import get_settings

logger = logging.getLogger("lenny.agents.llm_client")


class LLMUnavailableError(Exception):
    """Raised when no configured provider could produce a completion."""


@dataclass
class ChatResult:
    content: str
    provider: str
    model: str
    latency_ms: int


async def _call_ollama(system_prompt: str, messages: list[dict], timeout: float = 180.0, max_tokens: int | None = None) -> ChatResult:
    settings = get_settings()
    url = f"{settings.ollama_base_url}/api/chat"
    payload = {
        "model": settings.ollama_model,
        "messages": [{"role": "system", "content": system_prompt}, *messages],
        "stream": False,
    }
    if max_tokens:
        payload["options"] = {"num_predict": max_tokens}

    start = time.monotonic()
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()

    latency_ms = int((time.monotonic() - start) * 1000)
    content = data.get("message", {}).get("content", "")
    if not content:
        raise LLMUnavailableError(f"Ollama returned an empty response: {data}")

    return ChatResult(content=content, provider="ollama", model=settings.ollama_model, latency_ms=latency_ms)


async def _call_anthropic(system_prompt: str, messages: list[dict], timeout: float = 60.0, max_tokens: int | None = None) -> ChatResult:
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise LLMUnavailableError("ANTHROPIC_API_KEY is not set")

    # Imported lazily so the anthropic package is only required if this
    # provider is actually used.
    import anthropic

    start = time.monotonic()
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    response = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=max_tokens or 1500,
        system=system_prompt,
        messages=messages,
        timeout=timeout,
    )
    latency_ms = int((time.monotonic() - start) * 1000)

    content = "".join(block.text for block in response.content if block.type == "text")
    if not content:
        raise LLMUnavailableError("Anthropic returned an empty response")

    return ChatResult(content=content, provider="anthropic", model=settings.anthropic_model, latency_ms=latency_ms)


async def generate_chat_completion(
    system_prompt: str, messages: list[dict], max_tokens: int | None = None, provider_override: str | None = None
) -> ChatResult:
    """
    Main entry point used by the chat endpoint. Routes to the configured
    provider; falls back to Ollama if a cloud provider is configured but
    fails. Raises LLMUnavailableError only if every available path fails.
    """
    settings = get_settings()
    provider = provider_override or settings.llm_provider

    if provider == "anthropic":
        try:
            return await _call_anthropic(system_prompt, messages ,max_tokens=max_tokens)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Anthropic call failed (%s), falling back to Ollama", exc)
            return await _call_ollama(system_prompt, messages ,max_tokens=max_tokens)

    if provider == "openai":
        # OpenAI wiring intentionally deferred — Anthropic and Ollama cover
        # the assignment's "at least one cloud provider" + mandatory local
        # requirement. Falls back to Ollama directly.
        logger.warning("LLM_PROVIDER=openai is not yet implemented, using Ollama")
        return await _call_ollama(system_prompt, messages ,max_tokens=max_tokens)

    # Default / explicit "ollama"
    try:
        return await _call_ollama(system_prompt, messages ,max_tokens=max_tokens)
    except Exception as exc:  # noqa: BLE001
        logger.error("Ollama call failed and no fallback provider available: %s", exc)
        raise LLMUnavailableError(f"Ollama is unavailable: {exc}") from exc