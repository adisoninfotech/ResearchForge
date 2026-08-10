"""Manuscript version snapshots, preview, restore, and diff."""

from __future__ import annotations

from difflib import unified_diff
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ConflictError, NotFoundError
from app.core.time import utcnow
from app.models.enums import AuditAction, SectionStatus, SectionType, VersionAuthorType
from app.models.manuscript import Manuscript, ManuscriptSection, ManuscriptVersion
from app.services.audit import record_audit


async def _next_version_number(db: AsyncSession, manuscript_id: UUID) -> int:
    current = await db.scalar(
        select(func.max(ManuscriptVersion.version_number)).where(
            ManuscriptVersion.manuscript_id == manuscript_id
        )
    )
    return int(current or 0) + 1


def build_snapshot(sections: list[ManuscriptSection]) -> dict[str, Any]:
    ordered = sorted(sections, key=lambda s: s.position)
    return {
        "sections": [
            {
                "id": str(s.id),
                "section_type": s.section_type.value,
                "title": s.title,
                "position": s.position,
                "structured_content": s.structured_content,
                "plain_text": s.plain_text,
                "word_count": s.word_count,
                "status": s.status.value,
            }
            for s in ordered
        ]
    }


async def create_snapshot(
    db: AsyncSession,
    *,
    manuscript_id: UUID,
    change_summary: str,
    created_by_type: VersionAuthorType,
    created_by_user_id: UUID | None,
    model_metadata: dict[str, Any] | None = None,
    is_named: bool = False,
) -> ManuscriptVersion:
    manuscript = await db.scalar(
        select(Manuscript)
        .where(Manuscript.id == manuscript_id)
        .options(selectinload(Manuscript.sections))
    )
    if manuscript is None:
        raise NotFoundError("Manuscript not found")

    version = ManuscriptVersion(
        manuscript_id=manuscript_id,
        version_number=await _next_version_number(db, manuscript_id),
        snapshot=build_snapshot(list(manuscript.sections)),
        change_summary=change_summary[:500],
        created_by_type=created_by_type,
        created_by_user_id=created_by_user_id,
        model_metadata=model_metadata,
        is_named=is_named,
        created_at=utcnow(),
    )
    db.add(version)
    try:
        await db.flush()
        manuscript.current_version_id = version.id
        await db.flush()
    except IntegrityError as exc:
        # Concurrent autosaves can race on version_number; client should reload.
        raise ConflictError(
            "Concurrent save conflict — reload and retry",
            details={"manuscript_id": str(manuscript_id)},
        ) from exc
    if created_by_user_id:
        await record_audit(
            db,
            action=AuditAction.VERSION_CREATED,
            user_id=created_by_user_id,
            metadata={
                "manuscript_id": str(manuscript_id),
                "version_id": str(version.id),
                "version_number": version.version_number,
            },
        )
    return version


async def list_versions(db: AsyncSession, *, manuscript_id: UUID) -> list[ManuscriptVersion]:
    result = await db.scalars(
        select(ManuscriptVersion)
        .where(ManuscriptVersion.manuscript_id == manuscript_id)
        .order_by(ManuscriptVersion.version_number.desc())
    )
    return list(result.all())


async def get_version(
    db: AsyncSession,
    *,
    manuscript_id: UUID,
    version_id: UUID,
) -> ManuscriptVersion:
    version = await db.get(ManuscriptVersion, version_id)
    if version is None or version.manuscript_id != manuscript_id:
        raise NotFoundError("Version not found")
    return version


async def restore_version(
    db: AsyncSession,
    *,
    manuscript_id: UUID,
    version_id: UUID,
    user_id: UUID,
) -> ManuscriptVersion:
    manuscript = await db.scalar(
        select(Manuscript)
        .where(Manuscript.id == manuscript_id)
        .options(selectinload(Manuscript.sections))
    )
    if manuscript is None:
        raise NotFoundError("Manuscript not found")
    source = await get_version(db, manuscript_id=manuscript_id, version_id=version_id)

    # Snapshot current state before restore
    await create_snapshot(
        db,
        manuscript_id=manuscript_id,
        change_summary=f"Pre-restore checkpoint before v{source.version_number}",
        created_by_type=VersionAuthorType.SYSTEM,
        created_by_user_id=user_id,
    )

    snapshot_sections = source.snapshot.get("sections", [])
    by_id = {str(s.id): s for s in manuscript.sections}
    by_type: dict[str, ManuscriptSection] = {}
    for existing_section in manuscript.sections:
        if existing_section.section_type != SectionType.CUSTOM:
            by_type[existing_section.section_type.value] = existing_section
    now = utcnow()
    restored_ids: set[str] = set()
    restored_type_keys: set[str] = set()
    for item in snapshot_sections:
        key = str(item.get("section_type") or SectionType.CUSTOM.value)
        try:
            section_type = SectionType(key)
        except ValueError:
            section_type = SectionType.CUSTOM
        content = item.get("structured_content") or {"type": "doc", "content": []}
        plain = str(item.get("plain_text") or "")
        target: ManuscriptSection | None = None
        item_id = item.get("id")
        if item_id and str(item_id) in by_id:
            target = by_id[str(item_id)]
        elif section_type != SectionType.CUSTOM:
            target = by_type.get(section_type.value)
        if target is None:
            db.add(
                ManuscriptSection(
                    manuscript_id=manuscript_id,
                    section_type=section_type,
                    title=str(item.get("title") or key),
                    position=int(item.get("position") or 0),
                    structured_content=content,
                    plain_text=plain,
                    word_count=int(item.get("word_count") or 0),
                    status=SectionStatus(str(item.get("status") or SectionStatus.DRAFT.value)),
                    revision_number=1,
                    updated_at=now,
                )
            )
        else:
            restored_ids.add(str(target.id))
            if section_type != SectionType.CUSTOM:
                restored_type_keys.add(section_type.value)
            target.title = str(item.get("title") or target.title)
            target.position = int(item.get("position") or target.position)
            target.structured_content = content
            target.plain_text = plain
            target.word_count = int(item.get("word_count") or 0)
            target.status = SectionStatus(str(item.get("status") or target.status.value))
            target.revision_number += 1
            target.updated_at = now
    # Clear sections that exist now but were absent from the restored snapshot
    for existing in manuscript.sections:
        if str(existing.id) in restored_ids:
            continue
        if (
            existing.section_type != SectionType.CUSTOM
            and existing.section_type.value in restored_type_keys
        ):
            continue
        existing.structured_content = {"type": "doc", "content": []}
        existing.plain_text = ""
        existing.word_count = 0
        existing.status = SectionStatus.EMPTY
        existing.revision_number += 1
        existing.updated_at = now
    await db.flush()

    restored = await create_snapshot(
        db,
        manuscript_id=manuscript_id,
        change_summary=f"Restored from version {source.version_number}",
        created_by_type=VersionAuthorType.USER,
        created_by_user_id=user_id,
        is_named=False,
    )
    await record_audit(
        db,
        action=AuditAction.VERSION_RESTORED,
        user_id=user_id,
        metadata={
            "manuscript_id": str(manuscript_id),
            "from_version_id": str(version_id),
            "new_version_id": str(restored.id),
        },
    )
    return restored


def compare_versions(a: ManuscriptVersion, b: ManuscriptVersion) -> dict[str, Any]:
    def flatten(snapshot: dict[str, Any]) -> str:
        parts: list[str] = []
        for section in snapshot.get("sections", []):
            parts.append(f"# {section.get('title')}")
            parts.append(str(section.get("plain_text") or ""))
            parts.append("")
        return "\n".join(parts)

    left = flatten(a.snapshot).splitlines()
    right = flatten(b.snapshot).splitlines()
    diff = list(
        unified_diff(
            left,
            right,
            fromfile=f"v{a.version_number}",
            tofile=f"v{b.version_number}",
            lineterm="",
        )
    )
    return {
        "from_version": a.version_number,
        "to_version": b.version_number,
        "unified_diff": diff,
        "from_text": "\n".join(left),
        "to_text": "\n".join(right),
    }


def version_to_dict(version: ManuscriptVersion) -> dict[str, Any]:
    return {
        "id": str(version.id),
        "manuscript_id": str(version.manuscript_id),
        "version_number": version.version_number,
        "change_summary": version.change_summary,
        "created_by_type": version.created_by_type.value,
        "created_by_user_id": (
            str(version.created_by_user_id) if version.created_by_user_id else None
        ),
        "model_metadata": version.model_metadata,
        "is_named": version.is_named,
        "created_at": version.created_at.isoformat(),
    }
