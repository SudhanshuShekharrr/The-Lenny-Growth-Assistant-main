"""
Routing tests — verify the LLM provider abstraction selects/falls back
between providers correctly. Mocked at the module level so these tests
run fast and don't depend on Ollama or a real Anthropic API key being
available — exactly what "routing" tests should isolate (the decision
logic), separate from "does the network call itself work" (covered by
manual testing against the live stack).
"""

import pytest
from unittest.mock import AsyncMock, patch

from app.agents import llm_client
from app.agents.llm_client import ChatResult, LLMUnavailableError


@pytest.mark.asyncio
async def test_default_provider_routes_to_ollama():
    with patch.object(llm_client, "_call_ollama", new=AsyncMock(return_value=ChatResult(
        content="hi", provider="ollama", model="llama3.2:1b", latency_ms=10
    ))) as mock_ollama:
        result = await llm_client.generate_chat_completion("system", [{"role": "user", "content": "hi"}])
        assert result.provider == "ollama"
        mock_ollama.assert_called_once()


@pytest.mark.asyncio
async def test_anthropic_failure_falls_back_to_ollama():
    with patch.object(llm_client, "_call_anthropic", new=AsyncMock(side_effect=Exception("no api key"))), \
         patch.object(llm_client, "_call_ollama", new=AsyncMock(return_value=ChatResult(
             content="fallback answer", provider="ollama", model="llama3.2:1b", latency_ms=15
         ))) as mock_ollama:
        result = await llm_client.generate_chat_completion(
            "system", [{"role": "user", "content": "hi"}], provider_override="anthropic"
        )
        assert result.provider == "ollama"
        assert result.content == "fallback answer"
        mock_ollama.assert_called_once()


@pytest.mark.asyncio
async def test_ollama_failure_raises_llm_unavailable_when_no_fallback():
    with patch.object(llm_client, "_call_ollama", new=AsyncMock(side_effect=Exception("connection refused"))):
        with pytest.raises(LLMUnavailableError):
            await llm_client.generate_chat_completion("system", [{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_provider_override_takes_precedence():
    with patch.object(llm_client, "_call_anthropic", new=AsyncMock(return_value=ChatResult(
        content="claude answer", provider="anthropic", model="claude-sonnet-4-6", latency_ms=20
    ))) as mock_anthropic:
        result = await llm_client.generate_chat_completion(
            "system", [{"role": "user", "content": "hi"}], provider_override="anthropic"
        )
        assert result.provider == "anthropic"
        mock_anthropic.assert_called_once()