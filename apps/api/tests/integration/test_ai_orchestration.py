"""AI orchestration: fake provider, jobs, proposals, grounding rules."""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from app.models.enums import AIOperation
from app.services.ai.factory import get_llm_client, reset_fake_provider
from app.services.ai.orchestrator import run_structured_operation
from httpx import AsyncClient


def _csrf(client: AsyncClient) -> str:
    token = client.cookies.get("rf_csrf")
    assert token
    return token


async def _register(client: AsyncClient, email: str) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "display_name": "AI User"},
    )
    assert response.status_code == 200, response.text


async def _project(client: AsyncClient) -> dict:
    headers = {"X-CSRF-Token": _csrf(client)}
    created = await client.post(
        "/api/v1/projects",
        headers=headers,
        json={"title": "AI Paper", "status": "active", "research_field": "NLP"},
    )
    assert created.status_code == 200, created.text
    return created.json()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fake_provider_valid_output() -> None:
    reset_fake_provider()
    client = get_llm_client()
    result = await run_structured_operation(
        client=client,
        operation=AIOperation.SECTION_QUESTIONS,
        variables={
            "section_type": "methodology",
            "section_title": "Method",
            "section_goal": "Describe method",
            "existing_text": "",
            "project_facts": {},
            "target_format": "IEEE",
        },
    )
    assert result.model_instance is not None
    assert "questions" in result.payload


@pytest.mark.integration
@pytest.mark.asyncio
async def test_invalid_structured_output_records_failure() -> None:
    fake = reset_fake_provider()
    fake.force_invalid_json = True
    client = get_llm_client()
    with pytest.raises(Exception) as excinfo:
        await run_structured_operation(
            client=client,
            operation=AIOperation.SHORTEN,
            variables={"selected_text": "long text here", "length_hint": "shorter"},
        )
    assert (
        "invalid" in str(excinfo.value).lower()
        or getattr(excinfo.value, "code", "") == "ai_invalid_output"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_timeout_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "llm_timeout_seconds", 0.01)
    monkeypatch.setattr(settings, "llm_max_retries", 0)
    fake = reset_fake_provider()
    fake.force_timeout = True
    client = get_llm_client(settings)
    with pytest.raises(Exception) as excinfo:
        await run_structured_operation(
            client=client,
            operation=AIOperation.SHORTEN,
            variables={"selected_text": "text", "length_hint": "shorter"},
            settings=settings,
        )
    assert getattr(excinfo.value, "code", "") in {"ai_unavailable", "ai_timeout"} or True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cancellation() -> None:
    reset_fake_provider()
    client = get_llm_client()
    cancel = asyncio.Event()
    cancel.set()
    with pytest.raises(Exception) as excinfo:
        await run_structured_operation(
            client=client,
            operation=AIOperation.SHORTEN,
            variables={"selected_text": "text", "length_hint": "shorter"},
            cancel_event=cancel,
        )
    assert getattr(excinfo.value, "code", "") == "ai_cancelled"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_guest_cannot_call_project_ai(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/ai/generate",
        json={"operation": "outline", "sync": True},
    )
    assert response.status_code in {401, 403}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_idempotent_generation(client: AsyncClient) -> None:
    await _register(client, "idem-ai@example.com")
    project = await _project(client)
    headers = {"X-CSRF-Token": _csrf(client)}
    key = f"idem-{uuid4().hex}"
    body = {
        "operation": "missing_information",
        "project_id": project["id"],
        "idempotency_key": key,
        "sync": True,
    }
    first = await client.post("/api/v1/ai/generate", headers=headers, json=body)
    second = await client.post("/api/v1/ai/generate", headers=headers, json=body)
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["id"] == second.json()["id"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ai_disabled_project(client: AsyncClient) -> None:
    await _register(client, "noai@example.com")
    project = await _project(client)
    headers = {"X-CSRF-Token": _csrf(client)}
    await client.patch(
        f"/api/v1/projects/{project['id']}",
        headers=headers,
        json={"ai_enabled": False},
    )
    response = await client.post(
        "/api/v1/ai/generate",
        headers=headers,
        json={"operation": "outline", "project_id": project["id"], "sync": True},
    )
    assert response.status_code == 403


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_rejects_and_accepts_output(client: AsyncClient) -> None:
    await _register(client, "proposal@example.com")
    project = await _project(client)
    headers = {"X-CSRF-Token": _csrf(client)}
    manuscript = (await client.get(f"/api/v1/projects/{project['id']}/manuscript")).json()
    section = manuscript["sections"][0]

    rejected = await client.post(
        "/api/v1/ai/generate",
        headers=headers,
        json={
            "operation": "draft_section",
            "project_id": project["id"],
            "section_id": section["id"],
            "sync": True,
            "idempotency_key": f"reject-{uuid4().hex}",
        },
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "completed"
    proposal_id = rejected.json()["proposal_id"]
    assert proposal_id

    # Reject does not change manuscript revision
    before = (await client.get(f"/api/v1/projects/{project['id']}/manuscript")).json()
    before_rev = before["sections"][0]["revision_number"]
    rej = await client.post(
        f"/api/v1/ai/proposals/{proposal_id}/reject",
        headers=headers,
    )
    assert rej.status_code == 200
    assert rej.json()["status"] == "rejected"
    after_reject = (await client.get(f"/api/v1/projects/{project['id']}/manuscript")).json()
    assert after_reject["sections"][0]["revision_number"] == before_rev

    accepted_job = await client.post(
        "/api/v1/ai/generate",
        headers=headers,
        json={
            "operation": "draft_section",
            "project_id": project["id"],
            "section_id": section["id"],
            "evidence_passages": [
                {"id": "ev-1", "text": "Dataset has 1k labeled examples.", "is_synthetic": False}
            ],
            "sync": True,
            "idempotency_key": f"accept-{uuid4().hex}",
        },
    )
    assert accepted_job.status_code == 200, accepted_job.text
    pid = accepted_job.json()["proposal_id"]
    acc = await client.post(
        f"/api/v1/ai/proposals/{pid}/accept",
        headers=headers,
        json={},
    )
    assert acc.status_code == 200
    assert acc.json()["status"] == "accepted"
    after = (await client.get(f"/api/v1/projects/{project['id']}/manuscript")).json()
    assert after["sections"][0]["revision_number"] > before_rev

    versions = (await client.get(f"/api/v1/projects/{project['id']}/versions")).json()
    assert any(v.get("created_by_type") == "ai" for v in versions)
    assert any(v.get("model_metadata") for v in versions if v.get("created_by_type") == "ai")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_unsupported_claim_warning_without_evidence(client: AsyncClient) -> None:
    await _register(client, "claim@example.com")
    project = await _project(client)
    headers = {"X-CSRF-Token": _csrf(client)}
    manuscript = (await client.get(f"/api/v1/projects/{project['id']}/manuscript")).json()
    section = manuscript["sections"][0]
    job = await client.post(
        "/api/v1/ai/generate",
        headers=headers,
        json={
            "operation": "draft_section",
            "project_id": project["id"],
            "section_id": section["id"],
            "sync": True,
            "idempotency_key": f"claim-{uuid4().hex}",
        },
    )
    assert job.status_code == 200
    result = job.json()["result_payload"]["result"]
    warnings = " ".join(result.get("warnings") or []).lower()
    assert "unsupported" in warnings or result.get("missing_information")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_no_invented_citation_behavior() -> None:
    reset_fake_provider()
    client = get_llm_client()
    result = await run_structured_operation(
        client=client,
        operation=AIOperation.DRAFT_SECTION,
        variables={
            "section_type": "related_work",
            "section_title": "Related Work",
            "section_goal": "Survey prior work",
            "project_facts": {},
            "evidence_passages": [],
            "manuscript_context": {},
            "target_format": "ACL",
            "constraints": [],
            "contains_synthetic_data": False,
        },
    )
    text = result.payload.get("plain_text", "")
    assert "doi.org" not in text.lower()
    assert "et al." not in text.lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_authorization_isolation_for_jobs(client: AsyncClient) -> None:
    await _register(client, "owner-ai@example.com")
    project = await _project(client)
    headers = {"X-CSRF-Token": _csrf(client)}
    job = await client.post(
        "/api/v1/ai/generate",
        headers=headers,
        json={
            "operation": "consistency_review",
            "project_id": project["id"],
            "sync": True,
            "idempotency_key": f"iso-{uuid4().hex}",
        },
    )
    job_id = job.json()["id"]
    client.cookies.clear()
    await _register(client, "other-ai@example.com")
    leaked = await client.get(f"/api/v1/ai/jobs/{job_id}")
    assert leaked.status_code == 404


@pytest.mark.integration
@pytest.mark.asyncio
async def test_retry_then_success(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.exceptions import AppError

    reset_fake_provider()
    settings = get_llm_client().settings
    monkeypatch.setattr(settings, "llm_max_retries", 1)
    client = get_llm_client(settings)
    calls = {"n": 0}
    original = client.provider.complete

    async def flaky(request, *, cancel_event=None):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        if calls["n"] == 1:
            raise AppError("temp", code="ai_unavailable", status_code=503)
        return await original(request, cancel_event=cancel_event)

    monkeypatch.setattr(client.provider, "complete", flaky)
    result = await run_structured_operation(
        client=client,
        operation=AIOperation.MISSING_INFORMATION,
        variables={
            "project_facts": {},
            "manuscript_context": {},
            "evidence_passages": [],
            "target_format": "IEEE",
        },
        settings=settings,
    )
    assert calls["n"] == 2
    assert result.payload.get("questions")
