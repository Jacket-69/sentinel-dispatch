"""Smoke test de la API — verifica /healthz y /readyz."""

import pytest
from httpx import ASGITransport, AsyncClient

from sentinel_dispatch.api.main import app


@pytest.mark.asyncio
async def test_healthz_returns_alive() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"


@pytest.mark.asyncio
async def test_readyz_returns_ready() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/readyz")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
