"""Secure upload, references, retrieval, provenance, and deletion cascade."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _csrf(client: AsyncClient) -> str:
    token = client.cookies.get("rf_csrf")
    assert token
    return token


async def _register(client: AsyncClient, email: str) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "display_name": "File User"},
    )
    assert response.status_code == 200, response.text


async def _project(client: AsyncClient, title: str = "Evidence Project") -> dict:
    headers = {"X-CSRF-Token": _csrf(client)}
    created = await client.post(
        "/api/v1/projects",
        headers=headers,
        json={"title": title, "status": "active", "research_field": "Systems"},
    )
    assert created.status_code == 200, created.text
    return created.json()


async def _upload(
    client: AsyncClient,
    project_id: str,
    *,
    filename: str,
    content: bytes,
    content_type: str = "application/octet-stream",
) -> dict:
    headers = {"X-CSRF-Token": _csrf(client)}
    response = await client.post(
        f"/api/v1/projects/{project_id}/files/upload",
        headers=headers,
        files={"file": (filename, content, content_type)},
        data={"process_sync": "true"},
    )
    return {"status_code": response.status_code, "json": response.json(), "text": response.text}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_authorize_and_upload_txt(client: AsyncClient) -> None:
    await _register(client, "upload1@example.com")
    project = await _project(client)
    headers = {"X-CSRF-Token": _csrf(client)}
    auth = await client.post(
        f"/api/v1/projects/{project['id']}/files/authorize",
        headers=headers,
    )
    assert auth.status_code == 200
    assert auth.json()["authorized"] is True
    body = (FIXTURES / "sample_notes.txt").read_bytes()
    uploaded = await _upload(
        client,
        project["id"],
        filename="sample_notes.txt",
        content=body,
        content_type="text/plain",
    )
    assert uploaded["status_code"] == 200, uploaded["text"]
    assert uploaded["json"]["status"] == "ready"
    # Heading-led notes are classified by content signature (markdown), not client type
    assert uploaded["json"]["kind"] in {"txt", "markdown"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_mime_spoofing_rejected_or_corrected(client: AsyncClient) -> None:
    await _register(client, "spoof@example.com")
    project = await _project(client)
    # Claim PDF MIME but send plaintext with .exe-style payload disguised as .pdf
    bad = await _upload(
        client,
        project["id"],
        filename="notes.pdf",
        content=b"not a real pdf payload",
        content_type="application/pdf",
    )
    assert bad["status_code"] == 422

    # Real PDF signature wins over claimed image/png
    pdf_bytes = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
    ok = await _upload(
        client,
        project["id"],
        filename="figure.png",
        content=pdf_bytes,
        content_type="image/png",
    )
    # May fail extraction but must be detected as pdf if accepted, or fail signature path
    assert ok["status_code"] in {200, 422}
    if ok["status_code"] == 200:
        assert ok["json"]["kind"] == "pdf"
        assert ok["json"]["detected_mime"] == "application/pdf"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_oversized_file_rejected(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _register(client, "big@example.com")
    project = await _project(client)
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "max_upload_bytes", 64)
    oversized = await _upload(
        client,
        project["id"],
        filename="big.txt",
        content=b"x" * 128,
        content_type="text/plain",
    )
    assert oversized["status_code"] == 422
    assert "maximum size" in oversized["json"]["error"]["message"].lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_malicious_filename_sanitized(client: AsyncClient) -> None:
    await _register(client, "evilname@example.com")
    project = await _project(client)
    uploaded = await _upload(
        client,
        project["id"],
        filename="../../etc/passwd\x00evil.txt",
        content=b"safe notes about widgets",
        content_type="text/plain",
    )
    assert uploaded["status_code"] == 200, uploaded["text"]
    assert ".." not in uploaded["json"]["original_filename"]
    assert "/" not in uploaded["json"]["original_filename"]
    assert "\x00" not in uploaded["json"]["original_filename"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_duplicate_upload_conflict(client: AsyncClient) -> None:
    await _register(client, "dup@example.com")
    project = await _project(client)
    content = b"unique duplicate fixture content for sha256"
    first = await _upload(client, project["id"], filename="a.txt", content=content)
    assert first["status_code"] == 200
    second = await _upload(client, project["id"], filename="b.txt", content=content)
    assert second["status_code"] == 409
    assert second["json"]["error"]["code"] == "conflict"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_unauthorized_file_access(client: AsyncClient) -> None:
    await _register(client, "owner@example.com")
    project = await _project(client)
    uploaded = await _upload(
        client,
        project["id"],
        filename="private.txt",
        content=b"owner only notes",
    )
    assert uploaded["status_code"] == 200
    file_id = uploaded["json"]["id"]

    await client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": _csrf(client)})
    await _register(client, "intruder@example.com")
    headers = {"X-CSRF-Token": _csrf(client)}
    denied = await client.get(
        f"/api/v1/projects/{project['id']}/files/{file_id}",
        headers=headers,
    )
    assert denied.status_code == 404


@pytest.mark.integration
@pytest.mark.asyncio
async def test_extraction_failure_and_retry(client: AsyncClient) -> None:
    await _register(client, "retry@example.com")
    project = await _project(client)
    # Signature is PDF but body is corrupt → processing fails without leaking paths
    uploaded = await _upload(
        client,
        project["id"],
        filename="broken.pdf",
        content=b"%PDF-1.4\n%corrupt",
        content_type="application/pdf",
    )
    assert uploaded["status_code"] == 200, uploaded["text"]
    assert uploaded["json"]["status"] == "failed"
    assert uploaded["json"]["error_message"]
    err = uploaded["json"]["error_message"] or ""
    assert err == "Extraction or indexing failed. Check the file and retry."
    assert "\\" not in err
    assert "/" not in err

    headers = {"X-CSRF-Token": _csrf(client)}
    retry = await client.post(
        f"/api/v1/projects/{project['id']}/files/{uploaded['json']['id']}/retry",
        headers=headers,
    )
    assert retry.status_code == 200
    assert retry.json()["status"] in {"failed", "ready"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_bibtex_import_and_deduplication(client: AsyncClient) -> None:
    await _register(client, "bib@example.com")
    project = await _project(client)
    bib = (FIXTURES / "sample.bib").read_text(encoding="utf-8")
    headers = {"X-CSRF-Token": _csrf(client)}
    imported = await client.post(
        f"/api/v1/projects/{project['id']}/references/import",
        headers=headers,
        json={"text": bib, "format": "bibtex"},
    )
    assert imported.status_code == 200, imported.text
    refs = imported.json()["references"]
    assert any(r.get("doi") == "10.1234/toy.2020.widgets" for r in refs)
    incomplete = [r for r in refs if r.get("needs_user_correction")]
    assert incomplete, "Missing title must request correction"

    again = await client.post(
        f"/api/v1/projects/{project['id']}/references/import",
        headers=headers,
        json={"text": bib, "format": "bibtex"},
    )
    assert again.status_code == 200
    listed = await client.get(f"/api/v1/projects/{project['id']}/references")
    assert listed.status_code == 200
    dois = [r["doi"] for r in listed.json() if r.get("doi")]
    assert dois.count("10.1234/toy.2020.widgets") == 1

    export = await client.get(f"/api/v1/projects/{project['id']}/references/export/bibtex")
    assert export.status_code == 200
    assert "toy2020widgets" in export.text or "A Toy Study" in export.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_hybrid_retrieval_provenance_and_isolation(client: AsyncClient) -> None:
    await _register(client, "searcha@example.com")
    project_a = await _project(client, "Project A")
    notes = (FIXTURES / "sample_notes.txt").read_bytes()
    uploaded = await _upload(
        client,
        project_a["id"],
        filename="sample_notes.txt",
        content=notes,
    )
    assert uploaded["status_code"] == 200
    assert uploaded["json"]["status"] == "ready"

    headers = {"X-CSRF-Token": _csrf(client)}
    search = await client.post(
        f"/api/v1/projects/{project_a['id']}/search",
        headers=headers,
        json={"query": "widget latency", "limit": 5},
    )
    assert search.status_code == 200, search.text
    results = search.json()["results"]
    assert results
    hit = results[0]
    assert hit["source_file_id"] == uploaded["json"]["id"]
    assert hit["chunk_id"]
    assert hit["evidence_key"]
    assert "page" in hit
    assert "char_start" in hit
    assert "section" in hit
    assert "reference_id" in hit

    # Pin evidence
    manuscript = await client.get(f"/api/v1/projects/{project_a['id']}/manuscript")
    section_id = manuscript.json()["sections"][0]["id"]
    pinned = await client.post(
        f"/api/v1/projects/{project_a['id']}/evidence",
        headers=headers,
        json={
            "chunk_id": hit["chunk_id"],
            "section_id": section_id,
            "relation": "supports",
            "note": "Useful for intro",
        },
    )
    assert pinned.status_code == 200, pinned.text

    # Isolation: other user cannot search this project
    await client.post("/api/v1/auth/logout", headers=headers)
    await _register(client, "searchb@example.com")
    other_headers = {"X-CSRF-Token": _csrf(client)}
    denied = await client.post(
        f"/api/v1/projects/{project_a['id']}/search",
        headers=other_headers,
        json={"query": "widget latency"},
    )
    assert denied.status_code == 404


@pytest.mark.integration
@pytest.mark.asyncio
async def test_signed_url_expiration_and_deletion_cascade(client: AsyncClient) -> None:
    await _register(client, "purgefiles@example.com")
    project = await _project(client)
    uploaded = await _upload(
        client,
        project["id"],
        filename="sample_notes.txt",
        content=(FIXTURES / "sample_notes.txt").read_bytes(),
    )
    assert uploaded["status_code"] == 200
    file_id = uploaded["json"]["id"]
    detail = await client.get(f"/api/v1/projects/{project['id']}/files/{file_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert "expires_in=" in body["download_url"]
    assert body["signed_url_expires_in"] == 900

    headers = {"X-CSRF-Token": _csrf(client)}
    await client.post(
        f"/api/v1/projects/{project['id']}/references/import",
        headers=headers,
        json={
            "text": (FIXTURES / "sample.bib").read_text(encoding="utf-8"),
            "format": "bibtex",
        },
    )

    from app.services.storage import _MEMORY_STORE

    keys_before = [k for k in _MEMORY_STORE if project["id"] in k]
    assert keys_before

    deleted = await client.post(
        f"/api/v1/projects/{project['id']}/permanent-delete",
        headers=headers,
        json={"confirmation": "DELETE"},
    )
    assert deleted.status_code == 200, deleted.text
    keys_after = [k for k in _MEMORY_STORE if project["id"] in k]
    assert keys_after == []

    gone = await client.get(f"/api/v1/projects/{project['id']}")
    assert gone.status_code == 404


@pytest.mark.integration
@pytest.mark.asyncio
async def test_exclude_source_from_ai_and_remove_evidence(client: AsyncClient) -> None:
    await _register(client, "exclude@example.com")
    project = await _project(client)
    uploaded = await _upload(
        client,
        project["id"],
        filename="sample_notes.txt",
        content=(FIXTURES / "sample_notes.txt").read_bytes(),
    )
    assert uploaded["status_code"] == 200
    headers = {"X-CSRF-Token": _csrf(client)}
    patched = await client.patch(
        f"/api/v1/projects/{project['id']}/files/{uploaded['json']['id']}",
        headers=headers,
        json={"exclude_from_ai": True},
    )
    assert patched.status_code == 200
    assert patched.json()["exclude_from_ai"] is True

    search = await client.post(
        f"/api/v1/projects/{project['id']}/search",
        headers=headers,
        json={"query": "latency"},
    )
    assert search.status_code == 200
    assert search.json()["results"] == []

    # Re-enable and pin/remove evidence without deleting source
    await client.patch(
        f"/api/v1/projects/{project['id']}/files/{uploaded['json']['id']}",
        headers=headers,
        json={"exclude_from_ai": False},
    )
    search2 = await client.post(
        f"/api/v1/projects/{project['id']}/search",
        headers=headers,
        json={"query": "latency"},
    )
    chunk_id = search2.json()["results"][0]["chunk_id"]
    pin = await client.post(
        f"/api/v1/projects/{project['id']}/evidence",
        headers=headers,
        json={"chunk_id": chunk_id, "relation": "background"},
    )
    link_id = pin.json()["id"]
    removed = await client.delete(
        f"/api/v1/projects/{project['id']}/evidence/{link_id}",
        headers=headers,
    )
    assert removed.status_code == 200
    still = await client.get(f"/api/v1/projects/{project['id']}/files/{uploaded['json']['id']}")
    assert still.status_code == 200
