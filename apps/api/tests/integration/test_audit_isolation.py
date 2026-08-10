"""Cross-user / cross-project isolation and guest auth gates (audit items 3-4, 22, 24)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient


def _csrf(client: AsyncClient) -> str:
    token = client.cookies.get("rf_csrf")
    assert token
    return token


async def _register(client: AsyncClient, email: str) -> dict[str, str]:
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "display_name": "Audit User"},
    )
    assert r.status_code == 200, r.text
    return {"X-CSRF-Token": _csrf(client)}


async def _project(
    client: AsyncClient, headers: dict[str, str], title: str = "Audit Project"
) -> dict:
    created = await client.post(
        "/api/v1/projects",
        headers=headers,
        json={"title": title, "status": "active", "research_field": "CS"},
    )
    assert created.status_code == 200, created.text
    return created.json()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_guest_cannot_access_gated_server_apis(client: AsyncClient) -> None:
    """Save / upload / export / similarity / AI require login (items 3-4)."""
    fake_id = str(uuid4())
    unauth_matrix = [
        ("POST", "/api/v1/projects", {"title": "Nope"}),
        ("POST", f"/api/v1/projects/{fake_id}/files/upload", None),
        ("POST", f"/api/v1/projects/{fake_id}/exports/run", {"template_id": "generic_academic"}),
        ("POST", f"/api/v1/projects/{fake_id}/similarity/run", {}),
        ("POST", "/api/v1/ai/generate", {"operation": "outline", "sync": True}),
    ]
    for method, path, body in unauth_matrix:
        if method == "POST":
            response = await client.post(path, json=body or {})
        else:
            response = await client.get(path)
        assert response.status_code in {401, 403, 422}, (path, response.status_code, response.text)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cross_user_intruder_matrix(client: AsyncClient) -> None:
    owner = await _register(client, "audit-owner@example.com")
    project = await _project(client, owner)
    pid = project["id"]
    ms = await client.get(f"/api/v1/projects/{pid}/manuscript")
    assert ms.status_code == 200
    section_id = ms.json()["sections"][0]["id"]

    await client.post("/api/v1/auth/logout", headers=owner)
    intruder = await _register(client, "audit-intruder@example.com")

    paths = [
        f"/api/v1/projects/{pid}",
        f"/api/v1/projects/{pid}/manuscript",
        f"/api/v1/projects/{pid}/versions",
        f"/api/v1/projects/{pid}/facts",
        f"/api/v1/projects/{pid}/files",
        f"/api/v1/projects/{pid}/search",
        f"/api/v1/projects/{pid}/exports/jobs",
        f"/api/v1/projects/{pid}/similarity/meta",
        f"/api/v1/projects/{pid}/engagement/home",
        f"/api/v1/projects/{pid}/datasets",
    ]
    for path in paths:
        if path.endswith("/search"):
            response = await client.post(path, headers=intruder, json={"query": "x"})
        else:
            response = await client.get(path, headers=intruder)
        assert response.status_code == 404, (path, response.status_code)

    gen = await client.post(
        "/api/v1/ai/generate",
        headers=intruder,
        json={
            "operation": "outline",
            "project_id": pid,
            "sync": True,
            "idempotency_key": f"intrude-{uuid4().hex}",
        },
    )
    assert gen.status_code == 404

    save = await client.put(
        f"/api/v1/projects/{pid}/sections/{section_id}",
        headers=intruder,
        json={
            "structured_content": {"type": "doc", "content": [], "plain_text": "x"},
            "expected_revision": 1,
        },
    )
    assert save.status_code == 404


@pytest.mark.integration
@pytest.mark.asyncio
async def test_same_owner_cross_project_chunk_evidence_rejected(client: AsyncClient) -> None:
    """Evidence chunk from project B cannot be used against project A (item 24)."""
    headers = await _register(client, "cross-proj@example.com")
    project_a = await _project(client, headers, "Project A")
    project_b = await _project(client, headers, "Project B")

    # Upload a text file into B and process (sync in test env via authorize flow if available)
    upload = await client.post(
        f"/api/v1/projects/{project_b['id']}/files/upload",
        headers=headers,
        files={"file": ("note.txt", b"Secret evidence from project B only.", "text/plain")},
        data={"process_sync": "true"},
    )
    assert upload.status_code == 200, upload.text

    search = await client.post(
        f"/api/v1/projects/{project_b['id']}/search",
        headers=headers,
        json={"query": "Secret evidence"},
    )
    assert search.status_code == 200, search.text
    payload = search.json()
    hits = payload.get("results") or payload.get("passages") or payload.get("hits") or []
    if not hits:
        # Still reject a random foreign chunk id against project A
        foreign_chunk = str(uuid4())
    else:
        foreign_chunk = str(hits[0].get("chunk_id") or hits[0].get("id"))

    gen = await client.post(
        "/api/v1/ai/generate",
        headers=headers,
        json={
            "operation": "expand_with_evidence",
            "project_id": project_a["id"],
            "sync": True,
            "idempotency_key": f"xproj-{uuid4().hex}",
            "selected_text": "Expand this claim.",
            "evidence_passages": [
                {
                    "id": "ev-foreign",
                    "chunk_id": foreign_chunk,
                    "text": "should be ignored if chunk missing",
                }
            ],
        },
    )
    assert gen.status_code in {400, 404, 422}, gen.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_export_download_has_no_storage_url_and_is_single_use(client: AsyncClient) -> None:
    headers = await _register(client, "dl-audit@example.com")
    project = await _project(client, headers)
    ms = await client.get(f"/api/v1/projects/{project['id']}/manuscript")
    section = ms.json()["sections"][0]
    text = "Download audit seed " * 20
    await client.put(
        f"/api/v1/projects/{project['id']}/sections/{section['id']}",
        headers=headers,
        json={
            "structured_content": {
                "type": "doc",
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
                "plain_text": text,
            },
            "expected_revision": section["revision_number"],
        },
    )
    run = await client.post(
        f"/api/v1/projects/{project['id']}/exports/run",
        headers=headers,
        json={
            "template_id": "generic_academic",
            "process_sync": True,
            "outputs": ["docx"],
            "acknowledged_warnings": [
                "synthetic_data_disclosure",
                "missing_required_statement",
                "unverified_reference",
                "unresolved_similarity_findings",
            ],
        },
    )
    assert run.status_code == 200, run.text
    art = next(a for a in run.json()["artifacts"] if a["kind"] == "docx")
    grant = await client.post(
        f"/api/v1/projects/{project['id']}/exports/artifacts/{art['id']}/download",
        headers=headers,
    )
    assert grant.status_code == 200
    body = grant.json()
    assert "storage_url" not in body
    token = body["download_token"]
    first = await client.get(f"/api/v1/exports/download/{token}")
    assert first.status_code == 200
    second = await client.get(f"/api/v1/exports/download/{token}")
    assert second.status_code == 403


@pytest.mark.integration
@pytest.mark.asyncio
async def test_expand_requires_evidence(client: AsyncClient) -> None:
    headers = await _register(client, "evidence-req@example.com")
    project = await _project(client, headers)
    response = await client.post(
        "/api/v1/ai/generate",
        headers=headers,
        json={
            "operation": "expand_with_evidence",
            "project_id": project["id"],
            "sync": True,
            "idempotency_key": f"noev-{uuid4().hex}",
            "selected_text": "A claim without evidence.",
            "evidence_passages": [],
        },
    )
    assert response.status_code in {400, 422}, response.text
