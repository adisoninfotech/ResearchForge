"""Prominent retention actions: keep, archive, export, delete now."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ValidationAppError
from app.core.time import utcnow
from app.models.enums import ProjectStatus, RetentionPolicy
from app.models.project import Project
from app.models.user import User
from app.services import retention as retention_service


async def retention_status(db: AsyncSession, *, project: Project, user: User) -> dict[str, Any]:
    settings = get_settings()
    activity = project.last_activity_at or project.updated_at
    inactive_days = None
    if user.subscription_plan.value == "free" and project.status == ProjectStatus.DRAFT:
        inactive_days = settings.free_inactive_draft_days
    return {
        "retention_policy": project.retention_policy.value,
        "status": project.status.value,
        "last_activity_at": activity.isoformat() if activity else None,
        "trash_at": project.trash_at.isoformat() if project.trash_at else None,
        "purge_after": project.purge_after.isoformat() if project.purge_after else None,
        "legal_hold": project.legal_hold,
        "inactive_draft_days": inactive_days,
        "trash_retention_days": settings.trash_retention_days,
        "deletion_notice_days": settings.deletion_notice_days,
        "actions": {
            "keep": "Mark project as keep and restore from trash if needed",
            "archive": "Archive the project without deleting content",
            "export": "Generate an export before any deletion",
            "delete_now": "Permanently delete now (irreversible)",
        },
        "message": (
            "Retention information: inactive free-plan drafts and trashed projects may be "
            "deleted on a schedule. You will be notified before automatic deletion when "
            "notifications are enabled."
        ),
    }


async def keep_project(db: AsyncSession, *, project: Project, user: User) -> Project:
    """One-click keep: restore from trash if needed and set KEEP policy."""
    if project.status == ProjectStatus.TRASH:
        await retention_service.restore_from_trash(db, project=project, user=user)
    project.retention_policy = RetentionPolicy.KEEP
    project.purge_after = None
    project.last_activity_at = utcnow()
    await db.flush()
    await db.refresh(project)
    return project


async def archive_project(db: AsyncSession, *, project: Project) -> Project:
    if project.status == ProjectStatus.TRASH:
        raise ValidationAppError("Restore the project before archiving")
    project.status = ProjectStatus.ARCHIVED
    project.last_activity_at = utcnow()
    await db.flush()
    await db.refresh(project)
    return project


async def delete_now(db: AsyncSession, *, project: Project, user: User) -> dict[str, Any]:
    return await retention_service.permanently_delete(
        db, project=project, user=user, confirm="DELETE"
    )
