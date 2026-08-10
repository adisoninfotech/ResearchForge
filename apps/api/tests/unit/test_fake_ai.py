"""Unit tests for deterministic fake AI provider."""

from __future__ import annotations

import pytest
from app.services.ai.fake import FakeAIProvider


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fake_outline_is_deterministic_shape() -> None:
    provider = FakeAIProvider()
    result = await provider.generate_outline(
        title="Sample Paper",
        research_area="NLP",
        research_problem="Grounding citations",
        proposed_contribution="A retrieval pipeline",
        target_format="IEEE",
        max_sections=4,
    )
    assert result.provider == "fake"
    assert result.title == "Sample Paper"
    assert len(result.sections) == 4
    assert result.is_preview is True
    assert "guarantee" not in result.disclaimer.lower()
