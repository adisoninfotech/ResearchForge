"""Export pipeline integration tests."""

from __future__ import annotations

import hashlib
import zipfile
from datetime import UTC, datetime, timedelta
from io import BytesIO
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select


def _csrf(client: AsyncClient) -> str:
    token = client.cookies.get("rf_csrf")
    assert token
    return token


async def _register(client: AsyncClient, email: str) -> None:
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "display_name": "Export User"},
    )
    assert r.status_code == 200, r.text


async def _project(client: AsyncClient, title: str = "Export Project") -> dict:
    headers = {"X-CSRF-Token": _csrf(client)}
    created = await client.post(
        "/api/v1/projects",
        headers=headers,
        json={"title": title, "status": "active", "research_field": "NLP"},
    )
    assert created.status_code == 200, created.text
    return created.json()


async def _seed_section(client: AsyncClient, project_id: str, text: str) -> None:
    headers = {"X-CSRF-Token": _csrf(client)}
    ms = await client.get(f"/api/v1/projects/{project_id}/manuscript")
    assert ms.status_code == 200
    section = ms.json()["sections"][0]
    saved = await client.put(
        f"/api/v1/projects/{project_id}/sections/{section['id']}",
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
    assert saved.status_code == 200, saved.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_export_pipeline_artifacts_and_download(client: AsyncClient) -> None:
    await _register(client, "exporter@example.com")
    project = await _project(client)
    await _seed_section(
        client,
        project["id"],
        "Results use synthetic data for illustration. See related work.",
    )
    headers = {"X-CSRF-Token": _csrf(client)}

    meta = await client.get(f"/api/v1/projects/{project['id']}/exports/meta")
    assert meta.status_code == 200
    assert "compatible starting templates" in meta.json()["template_warning"].lower()
    assert len(meta.json()["templates"]) == 4

    preview = await client.post(
        f"/api/v1/projects/{project['id']}/exports/preview",
        headers=headers,
        json={
            "template_id": "acm",
            "page": 1,
            "authors": [{"name": "Grace Hopper", "corresponding": True}],
            "back_matter": {
                "funding": "Grant X",
                "conflict_of_interest": "None",
                "data_availability": "On request",
            },
        },
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert "html" in body
    assert body["template_warning"]
    assert body["page_count"] >= 1

    run = await client.post(
        f"/api/v1/projects/{project['id']}/exports/run",
        headers=headers,
        json={
            "template_id": "generic_academic",
            "process_sync": True,
            "idempotency_key": "export-1",
            "authors": [{"name": "Grace Hopper", "corresponding": True}],
            "back_matter": {
                "funding": "Grant X",
                "conflict_of_interest": "None",
                "data_availability": "On request",
            },
            "acknowledged_warnings": [
                "synthetic_data_disclosure",
                "missing_required_statement",
                "unverified_reference",
                "unresolved_similarity_findings",
            ],
        },
    )
    assert run.status_code == 200, run.text
    job = run.json()
    assert job["status"] == "completed", job
    kinds = {a["kind"] for a in job["artifacts"]}
    assert "docx" in kinds
    assert "latex" in kinds
    assert "bibtex" in kinds
    assert "overleaf_zip" in kinds
    assert "submission_package" in kinds
    assert "provenance_manifest" in kinds
    assert "canonical_json" in kinds
    assert "pdf" in kinds

    # Idempotent retry returns same job
    again = await client.post(
        f"/api/v1/projects/{project['id']}/exports/run",
        headers=headers,
        json={
            "template_id": "generic_academic",
            "process_sync": True,
            "idempotency_key": "export-1",
            "authors": [{"name": "Grace Hopper"}],
        },
    )
    assert again.status_code == 200
    assert again.json()["id"] == job["id"]

    jobs = await client.get(f"/api/v1/projects/{project['id']}/exports/jobs")
    assert jobs.status_code == 200
    assert jobs.json()["jobs"]

    docx_art = next(a for a in job["artifacts"] if a["kind"] == "docx")
    grant = await client.post(
        f"/api/v1/projects/{project['id']}/exports/artifacts/{docx_art['id']}/download",
        headers=headers,
    )
    assert grant.status_code == 200, grant.text
    token = grant.json()["download_token"]
    assert grant.json()["expires_in"] > 0
    assert "/exports/download/" in grant.json()["download_path"]

    downloaded = await client.get(f"/api/v1/exports/download/{token}")
    assert downloaded.status_code == 200
    assert downloaded.content[:2] == b"PK"

    history = await client.get(f"/api/v1/projects/{project['id']}/exports/history")
    assert history.status_code == 200
    assert history.json()["downloads"]

    overleaf = next(a for a in job["artifacts"] if a["kind"] == "overleaf_zip")
    g2 = await client.post(
        f"/api/v1/projects/{project['id']}/exports/artifacts/{overleaf['id']}/download",
        headers=headers,
    )
    zbytes = (await client.get(f"/api/v1/exports/download/{g2.json()['download_token']}")).content
    with zipfile.ZipFile(BytesIO(zbytes)) as zf:
        names = zf.namelist()
        assert "main.tex" in names
        assert "references.bib" in names

    # User isolation
    await client.post("/api/v1/auth/logout", headers=headers)
    await _register(client, "exportintruder@example.com")
    other = {"X-CSRF-Token": _csrf(client)}
    denied = await client.get(
        f"/api/v1/projects/{project['id']}/exports/jobs",
        headers=other,
    )
    assert denied.status_code == 404
    stolen = await client.get(f"/api/v1/exports/download/{token}", headers=other)
    assert stolen.status_code in {403, 404}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_export_blocks_critical_validation(client: AsyncClient, db_engine) -> None:
    await _register(client, "exportblock@example.com")
    project = await _project(client)
    headers = {"X-CSRF-Token": _csrf(client)}

    # Insert a figure with missing file to force critical failure
    from app.models.dataset import Figure
    from app.models.enums import FigureKind
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        session.add(
            Figure(
                project_id=UUID(project["id"]),
                stable_id="fig_missing_export",
                number=1,
                kind=FigureKind.CONCEPTUAL,
                title="Missing asset",
                caption="",
                alt_text="",
                is_conceptual=False,
                storage_png=None,
                provenance_label="synthetic",
            )
        )
        await session.commit()

    run = await client.post(
        f"/api/v1/projects/{project['id']}/exports/run",
        headers=headers,
        json={
            "process_sync": True,
            "authors": [{"name": "Blocked Author"}],
            "idempotency_key": "block-critical",
        },
    )
    assert run.status_code == 200, run.text
    job = run.json()
    assert job["status"] == "blocked"
    codes = {i["code"] for i in job["validation_issues"]}
    assert "missing_figure_file" in codes or "missing_caption" in codes


@pytest.mark.integration
@pytest.mark.asyncio
async def test_expiring_download_link(client: AsyncClient, db_engine) -> None:
    await _register(client, "exportexpire@example.com")
    project = await _project(client)
    await _seed_section(client, project["id"], "Plain original text without citations.")
    headers = {"X-CSRF-Token": _csrf(client)}
    run = await client.post(
        f"/api/v1/projects/{project['id']}/exports/run",
        headers=headers,
        json={
            "process_sync": True,
            "authors": [{"name": "Test Author"}],
            "back_matter": {
                "funding": "N/A",
                "conflict_of_interest": "None",
                "data_availability": "N/A",
            },
            "acknowledged_warnings": [
                "synthetic_data_disclosure",
                "missing_required_statement",
                "unverified_reference",
            ],
            "outputs": ["docx", "canonical_json", "html_preview"],
        },
    )
    assert run.status_code == 200, run.text
    job = run.json()
    assert job["status"] == "completed", job
    art = next(a for a in job["artifacts"] if a["kind"] == "docx")
    grant = await client.post(
        f"/api/v1/projects/{project['id']}/exports/artifacts/{art['id']}/download",
        headers=headers,
    )
    assert grant.status_code == 200
    token = grant.json()["download_token"]
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

    from app.models.export import ExportDownload
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        row = await session.scalar(
            select(ExportDownload).where(ExportDownload.token_hash == token_hash)
        )
        assert row is not None
        row.expires_at = datetime.now(UTC) - timedelta(seconds=5)
        await session.commit()

    expired = await client.get(f"/api/v1/exports/download/{token}")
    assert expired.status_code == 403
