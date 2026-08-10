"""Engagement system integration tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


def _csrf(client: AsyncClient) -> str:
    token = client.cookies.get("rf_csrf")
    assert token
    return token


async def _register(client: AsyncClient, email: str) -> None:
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "display_name": "Engage User"},
    )
    assert r.status_code == 200, r.text


async def _project(client: AsyncClient) -> dict:
    headers = {"X-CSRF-Token": _csrf(client)}
    created = await client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "title": "Engagement Study",
            "status": "active",
            "research_problem": "How do widgets reduce latency?",
            "proposed_contribution": "A measured widget pipeline",
        },
    )
    assert created.status_code == 200, created.text
    return created.json()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_progress_milestones_goals_and_questions(client: AsyncClient) -> None:
    await _register(client, "engage1@example.com")
    project = await _project(client)
    headers = {"X-CSRF-Token": _csrf(client)}

    home = await client.get(f"/api/v1/projects/{project['id']}/engagement/home")
    assert home.status_code == 200, home.text
    body = home.json()
    assert body["progress"]["not_word_count_based"] is True
    assert "components" in body["progress"]
    assert body["next_recommended_action"]
    assert len(body["milestones"]) == 9
    assert body["retention"]["message"]
    assert body["engagement_principles"]["no_manipulative_patterns"] is True

    # Answer guided questions → facts + completion change
    ans = await client.post(
        f"/api/v1/projects/{project['id']}/engagement/questions/answer",
        headers=headers,
        json={
            "category": "dataset",
            "key": "dataset_used",
            "value": "Public widget traces",
        },
    )
    assert ans.status_code == 200, ans.text
    assert "completion_percent" in ans.json()

    for cat, key, value in (
        ("dataset", "dataset_source", "Open repository"),
        ("dataset", "dataset_provenance", "real"),
        ("dataset", "dataset_size", "1000"),
        ("ethics", "ethics_statement", "N/A"),
        ("ethics", "conflict_of_interest", "None"),
        ("ethics", "data_availability", "On request"),
        ("evaluation", "limitations", "Single domain"),
        ("problem", "research_problem", "Latency"),
        ("contribution", "novel_contribution", "Pipeline"),
    ):
        r = await client.post(
            f"/api/v1/projects/{project['id']}/engagement/questions/answer",
            headers=headers,
            json={"category": cat, "key": key, "value": value},
        )
        assert r.status_code == 200, r.text

    progress = await client.get(f"/api/v1/projects/{project['id']}/engagement/progress")
    assert progress.status_code == 200
    comps = progress.json()["progress"]["components"]
    assert comps["problem_defined"]["complete"] is True
    assert comps["contribution_defined"]["complete"] is True

    milestones = await client.get(f"/api/v1/projects/{project['id']}/engagement/milestones")
    assert milestones.status_code == 200
    achieved = {m["type"]: m["achieved"] for m in milestones.json()["milestones"]}
    assert achieved["research_plan_approved"] is True

    goal = await client.post(
        f"/api/v1/projects/{project['id']}/engagement/goals",
        headers=headers,
        json={"goal_type": "verify_references"},
    )
    assert goal.status_code == 200, goal.text
    assert goal.json()["goal"]["task_sequence"]
    assert "does not estimate" in goal.json()["goal"]["disclaimer"].lower()

    step_id = goal.json()["goal"]["task_sequence"][0]["id"]
    stepped = await client.post(
        f"/api/v1/projects/{project['id']}/engagement/goals/steps",
        headers=headers,
        json={"step_id": step_id},
    )
    assert stepped.status_code == 200
    assert step_id in stepped.json()["goal"]["completed_step_ids"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_notification_preferences_and_retention_keep(client: AsyncClient) -> None:
    await _register(client, "engage2@example.com")
    project = await _project(client)
    headers = {"X-CSRF-Token": _csrf(client)}

    prefs = await client.get("/api/v1/account/notifications/preferences")
    assert prefs.status_code == 200
    assert prefs.json()["preferences"]["writing_reminders"] is False
    assert "unless you enable" in prefs.json()["note"].lower()

    updated = await client.put(
        "/api/v1/account/notifications/preferences",
        headers=headers,
        json={
            "preferences": {
                "writing_reminders": True,
                "export_completed": False,
                "weekly_project_summary": True,
            }
        },
    )
    assert updated.status_code == 200
    assert updated.json()["preferences"]["writing_reminders"] is True
    assert updated.json()["preferences"]["export_completed"] is False

    keep = await client.post(
        f"/api/v1/projects/{project['id']}/engagement/retention/actions",
        headers=headers,
        json={"action": "keep"},
    )
    assert keep.status_code == 200, keep.text
    assert keep.json()["project"]["retention_policy"] == "keep"

    archive = await client.post(
        f"/api/v1/projects/{project['id']}/engagement/retention/actions",
        headers=headers,
        json={"action": "archive"},
    )
    assert archive.status_code == 200
    assert archive.json()["project"]["status"] == "archived"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_engagement_isolation(client: AsyncClient) -> None:
    await _register(client, "engageowner@example.com")
    project = await _project(client)
    headers = {"X-CSRF-Token": _csrf(client)}
    await client.post("/api/v1/auth/logout", headers=headers)
    await _register(client, "engageintruder@example.com")
    other = {"X-CSRF-Token": _csrf(client)}
    denied = await client.get(
        f"/api/v1/projects/{project['id']}/engagement/home",
        headers=other,
    )
    assert denied.status_code == 404
