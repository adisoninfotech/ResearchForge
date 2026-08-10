"""User data export (portability) — account + owned project content."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import AuditAction, ProjectStatus
from app.models.manuscript import Manuscript
from app.models.project import Project
from app.models.project_fact import ProjectFact
from app.models.project_file import ProjectFile
from app.models.user import User
from app.services.audit import record_audit


async def build_user_export(
    db: AsyncSession,
    *,
    user: User,
    ip_hash: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    """Assemble a portable JSON export of the authenticated user's data."""
    projects = list(
        (
            await db.scalars(
                select(Project).where(
                    Project.owner_id == user.id,
                    Project.status != ProjectStatus.TRASH,
                )
            )
        ).all()
    )

    project_payloads: list[dict[str, Any]] = []
    for project in projects:
        facts = list(
            (
                await db.scalars(select(ProjectFact).where(ProjectFact.project_id == project.id))
            ).all()
        )
        files = list(
            (
                await db.scalars(select(ProjectFile).where(ProjectFile.project_id == project.id))
            ).all()
        )
        manuscript_data: dict[str, Any] | None = None
        manuscript = await db.scalar(
            select(Manuscript)
            .where(Manuscript.project_id == project.id)
            .options(selectinload(Manuscript.sections))
        )
        if manuscript is not None:
            sections = sorted(
                manuscript.sections or [],
                key=lambda s: (s.position, str(s.id)),
            )
            manuscript_data = {
                "id": str(manuscript.id),
                "schema_version": manuscript.schema_version,
                "sections": [
                    {
                        "id": str(sec.id),
                        "section_type": sec.section_type.value,
                        "title": sec.title,
                        "position": sec.position,
                        "plain_text": sec.plain_text,
                        "structured_content": sec.structured_content,
                        "word_count": sec.word_count,
                        "status": sec.status.value,
                    }
                    for sec in sections
                ],
            }

        project_payloads.append(
            {
                "id": str(project.id),
                "title": project.title,
                "slug": project.slug,
                "status": project.status.value,
                "is_private": project.is_private,
                "research_field": project.research_field,
                "paper_type": project.paper_type,
                "created_at": project.created_at.isoformat() if project.created_at else None,
                "facts": [
                    {
                        "id": str(f.id),
                        "category": f.category.value,
                        "key": f.key,
                        "value": f.value,
                        "source_type": f.source_type.value,
                    }
                    for f in facts
                ],
                "files": [
                    {
                        "id": str(f.id),
                        "original_filename": f.original_filename,
                        "kind": f.kind.value,
                        "size_bytes": f.size_bytes,
                        "status": f.status.value,
                        "content_sha256": f.content_sha256,
                    }
                    for f in files
                ],
                "manuscript": manuscript_data,
            }
        )

    await record_audit(
        db,
        action=AuditAction.EXPORT_ACCOUNT_DATA,
        user_id=user.id,
        ip_hash=ip_hash,
        user_agent=user_agent,
        metadata={"project_count": len(project_payloads)},
    )

    return {
        "export_version": "1.0",
        "user": {
            "id": str(user.id),
            "email": user.email,
            "display_name": user.display_name,
            "subscription_plan": user.subscription_plan.value,
            "training_opt_in": user.training_opt_in,
            "email_verified_at": (
                user.email_verified_at.isoformat() if user.email_verified_at else None
            ),
            "created_at": user.created_at.isoformat() if user.created_at else None,
        },
        "projects": project_payloads,
        "notes": (
            "Binary file contents are not inlined; re-download from the product if needed. "
            "Password hashes and session tokens are never exported."
        ),
    }
