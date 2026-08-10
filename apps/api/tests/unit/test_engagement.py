"""Unit tests for engagement progress, analytics sanitization, goals."""

from __future__ import annotations

import pytest
from app.services.engagement.analytics import sanitize_properties
from app.services.engagement.goals import GOAL_DISCLAIMER, GOAL_SEQUENCES
from app.services.engagement.progress import COMPONENT_WEIGHTS
from app.services.engagement.questions import MISSING_FACT_PLACEHOLDER, facts_for_ai


@pytest.mark.unit
def test_completion_weights_sum_to_100() -> None:
    assert sum(COMPONENT_WEIGHTS.values()) == 100
    assert "problem_defined" in COMPONENT_WEIGHTS
    assert COMPONENT_WEIGHTS["evidence_attached"] >= 8


@pytest.mark.unit
def test_analytics_strips_forbidden_content() -> None:
    clean = sanitize_properties(
        {
            "title": "Secret Paper Title",
            "filename": "data.csv",
            "operation": "t_test",
            "count": 3,
            "manuscript_text": "long prose that must never be stored",
            "citation": "Smith 2020",
            "plan": "free",
        }
    )
    assert "title" not in clean
    assert "filename" not in clean
    assert "manuscript_text" not in clean
    assert "citation" not in clean
    assert clean["operation"] == "t_test"
    assert clean["count"] == 3
    assert clean["plan"] == "free"


@pytest.mark.unit
def test_facts_for_ai_never_invents_missing() -> None:
    out = facts_for_ai({"problem:research_problem": "Latency in widgets"})
    assert out["problem:research_problem"] == "Latency in widgets"
    assert out["dataset:dataset_used"] == MISSING_FACT_PLACEHOLDER
    instruction = out["_instruction"].lower()
    assert "do not invent" in instruction or "never substitute" in instruction


@pytest.mark.unit
def test_daily_goal_sequences_have_no_time_promises() -> None:
    assert "does not estimate" in GOAL_DISCLAIMER.lower()
    for steps in GOAL_SEQUENCES.values():
        blob = " ".join(s["label"] for s in steps).lower()
        assert "minute" not in blob
        assert "hour" not in blob
        assert "quickly" not in blob
