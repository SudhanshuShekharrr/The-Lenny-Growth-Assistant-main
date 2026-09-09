"""
Smoke tests for Step 1 foundation. Run with: pytest

Kept minimal — this step is scaffolding, not feature logic. More meaningful
tests (retrieval, agent routing, persistence) land in later steps once
those features exist, per the assignment's "Tests" deliverable.
"""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.mark.asyncio
async def test_health_endpoint_returns_ok():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "lenny-growth-assistant-backend"


@pytest.mark.asyncio
async def test_unknown_route_returns_structured_404():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/does-not-exist")

    assert response.status_code == 404
    body = response.json()
    assert "detail" in body or "error" in body
