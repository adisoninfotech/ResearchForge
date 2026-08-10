"""Manuscript editor, autosave, versions, and research facts APIs."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession, enforce_rate_limit, require_csrf
from app.core.config import get_settings
from app.models.enums import AuditAction, VersionAuthorType
from app.models.manuscript import Manuscript
from app.schemas.projects import (
    CustomSectionRequest,
    FactUpsertRequest,
    NamedVersionRequest,
    SectionReorderRequest,
    SectionSaveRequest,
)
from app.services import facts as fact_service
from app.services import manuscripts as manuscript_service
from app.services import versions as version_service
from app.services.audit import record_audit
from app.services.authorization import get_owned_project

router = APIRouter(prefix="/projects/{project_id}", tags=["manuscripts"])


async def _load_manuscript(session: DbSession, project_id: UUID, user: CurrentUser) -> Manuscript:
    project = await get_owned_project(session, project_id=project_id, user=user)
    return await manuscript_service.get_manuscript_for_project(session, project=project)


@router.get("/manuscript")
async def get_manuscript(
    project_id: UUID,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    manuscript = await _load_manuscript(session, project_id, user)
    return manuscript_service.manuscript_to_dict(manuscript)


@router.put(
    "/sections/{section_id}",
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def save_section(
    project_id: UUID,
    section_id: UUID,
    payload: SectionSaveRequest,
    session: DbSession,
    user: CurrentUser,
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> dict[str, Any]:
    project = await get_owned_project(session, project_id=project_id, user=user)
    expected = payload.expected_revision
    if if_match:
        # ETag form: W/"uuid:revision"
        from app.core.exceptions import ValidationAppError

        try:
            raw = if_match.strip().removeprefix("W/").strip('"')
            _, rev = raw.rsplit(":", 1)
            expected = int(rev)
        except ValueError as exc:
            raise ValidationAppError(
                'Malformed If-Match header; expected W/"section-id:revision"'
            ) from exc

    settings = get_settings()
    manuscript = await manuscript_service.get_manuscript_for_project(session, project=project)
    current = next((s for s in manuscript.sections if s.id == section_id), None)
    words_before = current.word_count if current else 0

    reason = (payload.reason or "autosave").lower()
    if reason in {"before_ai", "after_ai"}:
        author_type = VersionAuthorType.AI
    else:
        author_type = VersionAuthorType.USER
    model_metadata = {"reason": reason} if author_type == VersionAuthorType.AI else None

    section = await manuscript_service.save_section(
        session,
        project=project,
        user=user,
        section_id=section_id,
        structured_content=payload.structured_content,
        expected_revision=expected,
        title=payload.title,
        create_snapshot=False,
        author_type=author_type,
        model_metadata=model_metadata,
    )

    meaningful = (
        payload.create_snapshot
        or reason in {"before_ai", "after_ai", "shortcut", "section_change"}
        or abs(section.word_count - words_before) >= settings.autosave_snapshot_min_words_delta
    )
    if meaningful:
        await version_service.create_snapshot(
            session,
            manuscript_id=manuscript.id,
            change_summary=payload.snapshot_summary
            or f"{reason.replace('_', ' ').title()} · {section.title}",
            created_by_type=author_type,
            created_by_user_id=user.id,
            model_metadata=model_metadata,
            is_named=False,
        )

    await record_audit(
        session,
        action=AuditAction.MANUSCRIPT_SAVED,
        user_id=user.id,
        metadata={
            "project_id": str(project_id),
            "section_id": str(section_id),
            "revision": section.revision_number,
            "reason": reason,
        },
    )
    return {
        "section": manuscript_service.section_to_dict(section),
        "completion_percent": project.completion_percent,
        "last_activity_at": (
            project.last_activity_at.isoformat() if project.last_activity_at else None
        ),
    }


@router.post(
    "/sections/reorder",
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def reorder_sections(
    project_id: UUID,
    payload: SectionReorderRequest,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    project = await get_owned_project(session, project_id=project_id, user=user)
    sections = await manuscript_service.reorder_sections(
        session,
        project=project,
        ordered_section_ids=payload.ordered_section_ids,
    )
    return {"sections": [manuscript_service.section_to_dict(s) for s in sections]}


@router.post(
    "/sections",
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def add_custom_section(
    project_id: UUID,
    payload: CustomSectionRequest,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    project = await get_owned_project(session, project_id=project_id, user=user)
    section = await manuscript_service.add_custom_section(
        session, project=project, title=payload.title
    )
    return {"section": manuscript_service.section_to_dict(section)}


@router.get("/versions")
async def list_versions(
    project_id: UUID,
    session: DbSession,
    user: CurrentUser,
) -> list[dict[str, Any]]:
    manuscript = await _load_manuscript(session, project_id, user)
    versions = await version_service.list_versions(session, manuscript_id=manuscript.id)
    return [version_service.version_to_dict(v) for v in versions]


@router.get("/versions/compare")
async def compare_versions(
    project_id: UUID,
    session: DbSession,
    user: CurrentUser,
    from_version_id: UUID,
    to_version_id: UUID,
) -> dict[str, Any]:
    manuscript = await _load_manuscript(session, project_id, user)
    left = await version_service.get_version(
        session, manuscript_id=manuscript.id, version_id=from_version_id
    )
    right = await version_service.get_version(
        session, manuscript_id=manuscript.id, version_id=to_version_id
    )
    return version_service.compare_versions(left, right)


@router.get("/versions/{version_id}")
async def get_version(
    project_id: UUID,
    version_id: UUID,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    manuscript = await _load_manuscript(session, project_id, user)
    version = await version_service.get_version(
        session, manuscript_id=manuscript.id, version_id=version_id
    )
    data = version_service.version_to_dict(version)
    data["snapshot"] = version.snapshot
    return data


@router.post(
    "/versions",
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def create_named_version(
    project_id: UUID,
    payload: NamedVersionRequest,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    manuscript = await _load_manuscript(session, project_id, user)
    version = await version_service.create_snapshot(
        session,
        manuscript_id=manuscript.id,
        change_summary=payload.change_summary,
        created_by_type=VersionAuthorType.USER,
        created_by_user_id=user.id,
        is_named=True,
    )
    return version_service.version_to_dict(version)


@router.post(
    "/versions/{version_id}/restore",
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def restore_version(
    project_id: UUID,
    version_id: UUID,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    manuscript = await _load_manuscript(session, project_id, user)
    restored = await version_service.restore_version(
        session,
        manuscript_id=manuscript.id,
        version_id=version_id,
        user_id=user.id,
    )
    # Reload sections after restore
    reloaded = await session.scalar(
        select(Manuscript)
        .where(Manuscript.id == manuscript.id)
        .options(selectinload(Manuscript.sections))
    )
    assert reloaded is not None
    return {
        "version": version_service.version_to_dict(restored),
        "manuscript": manuscript_service.manuscript_to_dict(reloaded),
    }


@router.get("/facts")
async def list_facts(
    project_id: UUID,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    await get_owned_project(session, project_id=project_id, user=user)
    facts = await fact_service.list_facts(session, project_id=project_id)
    return {
        "template": fact_service.completeness_template(),
        "facts": [fact_service.fact_to_public(f) for f in facts],
    }


@router.put(
    "/facts",
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def upsert_fact(
    project_id: UUID,
    payload: FactUpsertRequest,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    project = await get_owned_project(session, project_id=project_id, user=user)
    fact = await fact_service.upsert_fact(
        session,
        project=project,
        category=payload.category,
        key=payload.key,
        value=payload.value,
        verification_status=payload.verification_status,
    )
    return {"fact": fact_service.fact_to_public(fact)}
