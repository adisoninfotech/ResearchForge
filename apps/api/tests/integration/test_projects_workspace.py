"""Project workspace: autosave, versions, trash, retention, isolation."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from app.core.time import utcnow
from app.models.enums import ProjectStatus
from app.models.project import Project
from app.services.retention import is_purge_eligible, purge_project, run_scheduled_cleanup
from httpx import AsyncClient


def _csrf(client: AsyncClient) -> str:
    token = client.cookies.get("rf_csrf")
    assert token
    return token


async def _register(client: AsyncClient, email: str) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "display_name": "User"},
    )
    assert response.status_code == 200, response.text


def _doc(text: str) -> dict:
    return {
        "type": "doc",
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
        "plain_text": text,
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_guest_cannot_save_project_apis(client: AsyncClient) -> None:
    create = await client.post("/api/v1/projects", json={"title": "Nope"})
    assert create.status_code in {401, 403}

    save = await client.put(
        f"/api/v1/projects/{uuid4()}/sections/{uuid4()}",
        json={"structured_content": _doc("x"), "expected_revision": 1},
    )
    assert save.status_code in {401, 403}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_logged_in_user_can_create_and_autosave(client: AsyncClient) -> None:
    await _register(client, "saver@example.com")
    headers = {"X-CSRF-Token": _csrf(client)}

    created = await client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "title": "Transformer Survey",
            "research_field": "NLP",
            "target_publisher": "ACL",
            "status": "active",
        },
    )
    assert created.status_code == 200, created.text
    project = created.json()
    assert project["slug"]
    assert project["status"] == "active"

    manuscript = await client.get(f"/api/v1/projects/{project['id']}/manuscript")
    assert manuscript.status_code == 200
    body = manuscript.json()
    assert len(body["sections"]) >= 10
    section = body["sections"][0]

    saved = await client.put(
        f"/api/v1/projects/{project['id']}/sections/{section['id']}",
        headers={**headers, "If-Match": section["etag"]},
        json={
            "structured_content": _doc("This abstract describes a novel contribution to research."),
            "expected_revision": section["revision_number"],
            "reason": "autosave",
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["section"]["revision_number"] == section["revision_number"] + 1
    assert saved.json()["section"]["word_count"] > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_editing_conflict(client: AsyncClient) -> None:
    await _register(client, "conflict@example.com")
    headers = {"X-CSRF-Token": _csrf(client)}
    project = (
        await client.post(
            "/api/v1/projects",
            headers=headers,
            json={"title": "Conflict Paper"},
        )
    ).json()
    manuscript = (await client.get(f"/api/v1/projects/{project['id']}/manuscript")).json()
    section = manuscript["sections"][0]

    first = await client.put(
        f"/api/v1/projects/{project['id']}/sections/{section['id']}",
        headers=headers,
        json={
            "structured_content": _doc("First writer content here with enough words for status."),
            "expected_revision": section["revision_number"],
            "reason": "shortcut",
        },
    )
    assert first.status_code == 200

    stale = await client.put(
        f"/api/v1/projects/{project['id']}/sections/{section['id']}",
        headers=headers,
        json={
            "structured_content": _doc("Stale writer should lose"),
            "expected_revision": section["revision_number"],
            "reason": "autosave",
        },
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "conflict"
    assert "server_revision" in stale.json()["error"]["details"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_version_restore_creates_new_version(client: AsyncClient) -> None:
    await _register(client, "versions@example.com")
    headers = {"X-CSRF-Token": _csrf(client)}
    project = (
        await client.post(
            "/api/v1/projects",
            headers=headers,
            json={"title": "Versioned Paper"},
        )
    ).json()
    manuscript = (await client.get(f"/api/v1/projects/{project['id']}/manuscript")).json()
    section = manuscript["sections"][0]

    await client.put(
        f"/api/v1/projects/{project['id']}/sections/{section['id']}",
        headers=headers,
        json={
            "structured_content": _doc("Original meaningful content for snapshot creation path."),
            "expected_revision": 1,
            "reason": "shortcut",
            "create_snapshot": True,
        },
    )
    versions = (await client.get(f"/api/v1/projects/{project['id']}/versions")).json()
    assert len(versions) >= 2
    target = versions[-1]

    # Edit again
    manuscript = (await client.get(f"/api/v1/projects/{project['id']}/manuscript")).json()
    section = next(s for s in manuscript["sections"] if s["id"] == section["id"])
    await client.put(
        f"/api/v1/projects/{project['id']}/sections/{section['id']}",
        headers=headers,
        json={
            "structured_content": _doc("Changed content after the original snapshot was taken."),
            "expected_revision": section["revision_number"],
            "reason": "shortcut",
        },
    )

    before = len((await client.get(f"/api/v1/projects/{project['id']}/versions")).json())
    restored = await client.post(
        f"/api/v1/projects/{project['id']}/versions/{target['id']}/restore",
        headers=headers,
    )
    assert restored.status_code == 200, restored.text
    after = (await client.get(f"/api/v1/projects/{project['id']}/versions")).json()
    assert len(after) > before
    assert after[0]["change_summary"].startswith("Restored from version")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_isolation(client: AsyncClient) -> None:
    await _register(client, "owner@example.com")
    headers = {"X-CSRF-Token": _csrf(client)}
    project = (
        await client.post(
            "/api/v1/projects",
            headers=headers,
            json={"title": "Private Only"},
        )
    ).json()
    client.cookies.clear()
    await _register(client, "intruder@example.com")
    other_headers = {"X-CSRF-Token": _csrf(client)}
    get = await client.get(f"/api/v1/projects/{project['id']}")
    assert get.status_code == 404
    trash = await client.post(
        f"/api/v1/projects/{project['id']}/trash",
        headers=other_headers,
    )
    assert trash.status_code == 404


@pytest.mark.integration
@pytest.mark.asyncio
async def test_trash_restore_and_permanent_delete(client: AsyncClient) -> None:
    await _register(client, "trash@example.com")
    headers = {"X-CSRF-Token": _csrf(client)}
    project = (
        await client.post(
            "/api/v1/projects",
            headers=headers,
            json={"title": "Trashable"},
        )
    ).json()

    trashed = await client.post(f"/api/v1/projects/{project['id']}/trash", headers=headers)
    assert trashed.status_code == 200
    assert trashed.json()["status"] == "trash"
    assert trashed.json()["purge_after"] is not None

    restored = await client.post(f"/api/v1/projects/{project['id']}/restore", headers=headers)
    assert restored.status_code == 200
    # Restores prior status (create default is draft)
    assert restored.json()["status"] == "draft"
    assert restored.json()["purge_after"] is None

    await client.post(f"/api/v1/projects/{project['id']}/trash", headers=headers)
    deleted = await client.post(
        f"/api/v1/projects/{project['id']}/permanent-delete",
        headers=headers,
        json={"confirmation": "DELETE"},
    )
    assert deleted.status_code == 200
    assert deleted.json()["purged"] is True
    missing = await client.get(f"/api/v1/projects/{project['id']}")
    assert missing.status_code == 404


@pytest.mark.integration
@pytest.mark.asyncio
async def test_legal_hold_blocks_purge(client: AsyncClient, db_engine) -> None:
    await _register(client, "hold@example.com")
    headers = {"X-CSRF-Token": _csrf(client)}
    project = (
        await client.post(
            "/api/v1/projects",
            headers=headers,
            json={"title": "Held"},
        )
    ).json()
    await client.patch(
        f"/api/v1/projects/{project['id']}",
        headers=headers,
        json={"legal_hold": True},
    )
    trash = await client.post(f"/api/v1/projects/{project['id']}/trash", headers=headers)
    assert trash.status_code == 403

    # Force trash+purge eligibility via DB then ensure purge skips legal hold
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    project_uuid = UUID(project["id"])
    async with factory() as session:
        row = await session.get(Project, project_uuid)
        assert row is not None
        row.legal_hold = True
        row.status = ProjectStatus.TRASH
        row.purge_after = utcnow() - timedelta(days=1)
        await session.commit()
        assert is_purge_eligible(row) is False
        result = await purge_project(session, project=row, dry_run=False)
        assert result["skipped"] is True
        assert result["reason"] == "legal_hold"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_purge_eligibility_and_idempotent_cleanup(client: AsyncClient, db_engine) -> None:
    await _register(client, "purge@example.com")
    headers = {"X-CSRF-Token": _csrf(client)}
    project = (
        await client.post(
            "/api/v1/projects",
            headers=headers,
            json={"title": "Purge Me"},
        )
    ).json()
    await client.post(f"/api/v1/projects/{project['id']}/trash", headers=headers)

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    project_uuid = UUID(project["id"])
    async with factory() as session:
        row = await session.get(Project, project_uuid)
        assert row is not None
        row.purge_after = utcnow() - timedelta(hours=1)
        await session.commit()
        assert is_purge_eligible(row) is True

        with patch("app.services.retention.delete_prefix", return_value=True) as mocked:
            first = await run_scheduled_cleanup(session, dry_run=False)
            await session.commit()
            assert any(r.get("purged") for r in first["purge_results"])
            mocked.assert_called()

        second = await run_scheduled_cleanup(session, dry_run=False)
        await session.commit()
        # Second run finds nothing (already deleted) — idempotent
        assert second["purge_results"] == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_object_deletion_called_on_purge(client: AsyncClient, db_engine) -> None:
    await _register(client, "objects@example.com")
    headers = {"X-CSRF-Token": _csrf(client)}
    project = (
        await client.post(
            "/api/v1/projects",
            headers=headers,
            json={"title": "With Objects"},
        )
    ).json()
    await client.post(f"/api/v1/projects/{project['id']}/trash", headers=headers)

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    project_uuid = UUID(project["id"])
    async with factory() as session:
        row = await session.get(Project, project_uuid)
        assert row is not None
        with patch("app.services.retention.delete_prefix", return_value=True) as mocked:
            result = await purge_project(session, project=row, dry_run=False)
            await session.commit()
            assert result["purged"] is True
            mocked.assert_called_once_with(f"projects/{project['id']}/")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_project_authors_persist_and_max_six(client: AsyncClient) -> None:
    await _register(client, "authors@example.com")
    headers = {"X-CSRF-Token": _csrf(client)}
    created = await client.post(
        "/api/v1/projects",
        headers=headers,
        json={"title": "Author Paper", "status": "active"},
    )
    assert created.status_code == 200, created.text
    project = created.json()
    assert len(project["authors"]) == 1
    assert project["authors"][0]["name"]
    assert project["authors"][0]["corresponding"] is True

    six = [
        {
            "name": f"Author {i}",
            "affiliation": f"Lab {i}",
            "email": f"a{i}@example.com",
            "corresponding": i == 0,
        }
        for i in range(6)
    ]
    updated = await client.patch(
        f"/api/v1/projects/{project['id']}",
        headers=headers,
        json={"authors": six},
    )
    assert updated.status_code == 200, updated.text
    assert len(updated.json()["authors"]) == 6
    assert updated.json()["authors"][0]["name"] == "Author 0"

    too_many = [*six, {"name": "Author 6", "corresponding": False}]
    rejected = await client.patch(
        f"/api/v1/projects/{project['id']}",
        headers=headers,
        json={"authors": too_many},
    )
    assert rejected.status_code == 422, rejected.text

    fetched = await client.get(f"/api/v1/projects/{project['id']}")
    assert fetched.status_code == 200
    assert len(fetched.json()["authors"]) == 6


@pytest.mark.integration
@pytest.mark.asyncio
async def test_purge_aborts_when_storage_delete_fails(client: AsyncClient, db_engine) -> None:
    await _register(client, "storagefail@example.com")
    headers = {"X-CSRF-Token": _csrf(client)}
    project = (
        await client.post(
            "/api/v1/projects",
            headers=headers,
            json={"title": "Keep On Storage Fail"},
        )
    ).json()
    await client.post(f"/api/v1/projects/{project['id']}/trash", headers=headers)

    from app.models.project import Project
    from app.services.retention import purge_project
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    project_uuid = UUID(project["id"])
    async with factory() as session:
        row = await session.get(Project, project_uuid)
        assert row is not None
        with patch("app.services.retention.delete_prefix", return_value=False):
            result = await purge_project(session, project=row, dry_run=False)
            await session.commit()
            assert result["purged"] is False
            assert result["reason"] == "storage_delete_failed"
        still = await session.get(Project, project_uuid)
        assert still is not None
