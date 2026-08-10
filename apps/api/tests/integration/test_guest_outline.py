"""Guest outline endpoint uses fake AI in tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.integration
@pytest.mark.asyncio
async def test_guest_outline_preview(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/guest/outline",
        json={
            "title": "Evidence-Aware Drafting",
            "research_area": "HCI",
            "target_format": "ACM",
            "research_problem": "Authors struggle to ground claims",
            "proposed_contribution": "A workspace that preserves provenance",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert "browser" in body["storage_hint"].lower()
    assert "save" in body["gated_actions"]
    assert body["outline"]["provider"] == "fake"
    assert len(body["outline"]["sections"]) >= 1
