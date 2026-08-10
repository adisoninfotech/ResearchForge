"""Manuscript creation, section autosave, reordering, and completeness."""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppError, ConflictError, NotFoundError, ValidationAppError
from app.core.time import utcnow
from app.models.enums import (
    SectionStatus,
    SectionType,
    VersionAuthorType,
)
from app.models.manuscript import Manuscript, ManuscriptSection
from app.models.project import Project
from app.models.user import User
from app.services import versions as version_service

DEFAULT_SECTIONS: list[tuple[SectionType, str]] = [
    (SectionType.ABSTRACT, "Abstract"),
    (SectionType.KEYWORDS, "Keywords"),
    (SectionType.INTRODUCTION, "Introduction"),
    (SectionType.RELATED_WORK, "Related Work"),
    (SectionType.METHODOLOGY, "Methodology"),
    (SectionType.RESULTS, "Results"),
    (SectionType.DISCUSSION, "Discussion"),
    (SectionType.LIMITATIONS, "Limitations"),
    (SectionType.CONCLUSION, "Conclusion"),
    (SectionType.REFERENCES, "References"),
]


def _word_count(text: str) -> int:
    words = re.findall(r"\b\w+\b", text)
    return len(words)


def _plain_from_structured(content: dict[str, Any]) -> str:
    if "plain_text" in content and isinstance(content["plain_text"], str):
        return content["plain_text"]

    # TipTap JSON doc walk
    def walk(node: Any) -> str:
        if isinstance(node, dict):
            if node.get("type") == "text":
                return str(node.get("text", ""))
            parts = [walk(child) for child in node.get("content", [])]
            return " ".join(p for p in parts if p)
        if isinstance(node, list):
            return " ".join(walk(item) for item in node)
        return ""

    return walk(content.get("doc") or content).strip()


def _section_status(word_count: int) -> SectionStatus:
    if word_count <= 0:
        return SectionStatus.EMPTY
    if word_count < 40:
        return SectionStatus.DRAFT
    return SectionStatus.COMPLETE


async def ensure_manuscript(db: AsyncSession, *, project: Project) -> Manuscript:
    existing = await db.scalar(
        select(Manuscript)
        .where(Manuscript.project_id == project.id)
        .options(selectinload(Manuscript.sections), selectinload(Manuscript.versions))
    )
    if existing:
        return existing

    now = utcnow()
    manuscript = Manuscript(project_id=project.id, schema_version=1)
    db.add(manuscript)
    await db.flush()

    for index, (section_type, title) in enumerate(DEFAULT_SECTIONS):
        db.add(
            ManuscriptSection(
                manuscript_id=manuscript.id,
                section_type=section_type,
                title=title,
                position=index,
                structured_content={"type": "doc", "content": [{"type": "paragraph"}]},
                plain_text="",
                word_count=0,
                status=SectionStatus.EMPTY,
                revision_number=1,
                updated_at=now,
            )
        )
    await db.flush()

    await version_service.create_snapshot(
        db,
        manuscript_id=manuscript.id,
        change_summary="Initial manuscript structure",
        created_by_type=VersionAuthorType.SYSTEM,
        created_by_user_id=None,
        is_named=False,
    )
    await db.refresh(manuscript, attribute_names=["sections", "versions", "current_version_id"])
    return manuscript


async def get_manuscript_for_project(
    db: AsyncSession,
    *,
    project: Project,
) -> Manuscript:
    manuscript = await db.scalar(
        select(Manuscript)
        .where(Manuscript.project_id == project.id)
        .options(selectinload(Manuscript.sections), selectinload(Manuscript.versions))
    )
    if manuscript is None:
        return await ensure_manuscript(db, project=project)
    return manuscript


async def save_section(
    db: AsyncSession,
    *,
    project: Project,
    user: User,
    section_id: UUID,
    structured_content: dict[str, Any],
    expected_revision: int,
    title: str | None = None,
    create_snapshot: bool = False,
    snapshot_summary: str | None = None,
    author_type: VersionAuthorType = VersionAuthorType.USER,
    model_metadata: dict[str, Any] | None = None,
) -> ManuscriptSection:
    manuscript = await get_manuscript_for_project(db, project=project)
    section = next((s for s in manuscript.sections if s.id == section_id), None)
    if section is None:
        raise NotFoundError("Section not found")

    if section.revision_number != expected_revision:
        raise ConflictError(
            "Section was modified elsewhere",
            details={
                "section_id": str(section_id),
                "server_revision": section.revision_number,
                "client_revision": expected_revision,
                "server_plain_text": section.plain_text,
                "server_structured_content": section.structured_content,
                "server_updated_at": section.updated_at.isoformat(),
            },
        )

    plain = _plain_from_structured(structured_content)
    words = _word_count(plain)
    section.structured_content = structured_content
    section.plain_text = plain
    section.word_count = words
    section.status = _section_status(words)
    section.revision_number += 1
    section.updated_at = utcnow()
    if title is not None:
        section.title = title.strip() or section.title

    project.last_activity_at = utcnow()
    project.updated_at = utcnow()
    from app.models.enums import AnalyticsEventType
    from app.services.engagement.analytics import track as track_analytics
    from app.services.engagement.progress import refresh_project_completion

    previous_components = None
    snap = await refresh_project_completion(
        db, project=project, previous_components=previous_components
    )
    if section.status == SectionStatus.COMPLETE:
        await track_analytics(
            db,
            event_type=AnalyticsEventType.SECTION_COMPLETED,
            user_id=user.id,
            project_id=project.id,
            properties={"section_type": section.section_type.value},
        )

    if create_snapshot:
        await version_service.create_snapshot(
            db,
            manuscript_id=manuscript.id,
            change_summary=snapshot_summary or f"Autosave snapshot · {section.title}",
            created_by_type=author_type,
            created_by_user_id=user.id,
            model_metadata=model_metadata,
        )

    await db.flush()
    await db.refresh(section)
    # Expose latest weighted percent via section save callers
    section._engagement_percent = snap.percent  # type: ignore[attr-defined]
    return section


async def reorder_sections(
    db: AsyncSession,
    *,
    project: Project,
    ordered_section_ids: list[UUID],
) -> list[ManuscriptSection]:
    manuscript = await get_manuscript_for_project(db, project=project)
    by_id = {section.id: section for section in manuscript.sections}
    if set(ordered_section_ids) != set(by_id):
        raise ValidationAppError("Section order must include every section exactly once")

    # Two-phase update avoids unique(position) collisions.
    for offset, section_id in enumerate(ordered_section_ids):
        by_id[section_id].position = 10_000 + offset
    await db.flush()
    for position, section_id in enumerate(ordered_section_ids):
        by_id[section_id].position = position
    project.last_activity_at = utcnow()
    await db.flush()
    return sorted(manuscript.sections, key=lambda s: s.position)


async def add_custom_section(
    db: AsyncSession,
    *,
    project: Project,
    title: str,
) -> ManuscriptSection:
    manuscript = await get_manuscript_for_project(db, project=project)
    position = max((s.position for s in manuscript.sections), default=-1) + 1
    section = ManuscriptSection(
        manuscript_id=manuscript.id,
        section_type=SectionType.CUSTOM,
        title=title.strip() or "Custom section",
        position=position,
        structured_content={"type": "doc", "content": [{"type": "paragraph"}]},
        plain_text="",
        word_count=0,
        status=SectionStatus.EMPTY,
        revision_number=1,
        updated_at=utcnow(),
    )
    db.add(section)
    project.last_activity_at = utcnow()
    await db.flush()
    await db.refresh(section)
    return section


def compute_completion(sections: list[ManuscriptSection]) -> int:
    if not sections:
        return 0
    complete = sum(1 for s in sections if s.status == SectionStatus.COMPLETE)
    return round(100 * complete / len(sections))


def manuscript_to_dict(manuscript: Manuscript) -> dict[str, Any]:
    sections = sorted(manuscript.sections, key=lambda s: s.position)
    total_words = sum(s.word_count for s in sections)
    return {
        "id": str(manuscript.id),
        "project_id": str(manuscript.project_id),
        "current_version_id": (
            str(manuscript.current_version_id) if manuscript.current_version_id else None
        ),
        "schema_version": manuscript.schema_version,
        "completion_percent": compute_completion(sections),
        "total_word_count": total_words,
        "sections": [section_to_dict(s) for s in sections],
    }


def section_to_dict(section: ManuscriptSection) -> dict[str, Any]:
    return {
        "id": str(section.id),
        "section_type": section.section_type.value,
        "title": section.title,
        "position": section.position,
        "structured_content": section.structured_content,
        "plain_text": section.plain_text,
        "word_count": section.word_count,
        "status": section.status.value,
        "revision_number": section.revision_number,
        "updated_at": section.updated_at.isoformat(),
        "etag": f'W/"{section.id}:{section.revision_number}"',
    }


class OfflineNotSupportedError(AppError):
    def __init__(self) -> None:
        super().__init__("Offline sync rejected", code="offline_rejected", status_code=409)
