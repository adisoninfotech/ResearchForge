"""HTTP tests for health endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_endpoint(client: AsyncClient) -> None:
    response = await client.get("/health/live")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert response.headers.get("X-Request-ID")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ready_endpoint_shape(client: AsyncClient) -> None:
    response = await client.get("/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"ok", "degraded", "error"}
    names = {c["name"] for c in body["components"]}
    assert names == {"database", "redis", "object_storage"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_openapi_available(client: AsyncClient) -> None:
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"] == "ResearchForge"
