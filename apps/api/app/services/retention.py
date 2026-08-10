"""Trash, retention policies, and idempotent purge cleanup."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings, get_settings
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationAppError
from app.core.logging import get_logger
from app.core.time import ensure_utc, utcnow
from app.models.enums import AuditAction, ProjectStatus, RetentionPolicy, SubscriptionPlan
from app.models.project import Project
from app.models.user import User
from app.services.audit import record_audit
from app.services.email import send_pending_deletion_email
from app.services.storage import delete_prefix

logger = get_logger(__name__)


def trash_retention_days(
    settings: Settings | None = None,
    *,
    policy: RetentionPolicy | None = None,
) -> int:
    settings = settings or get_settings()
    if policy == RetentionPolicy.TRASH_30:
        return 30
    return settings.trash_retention_days


def inactive_draft_days_for_plan(
    plan: SubscriptionPlan,
    settings: Settings,
    *,
    policy: RetentionPolicy | None = None,
) -> int | None:
    if policy == RetentionPolicy.INACTIVE_DRAFT_90:
        return 90
    if plan == SubscriptionPlan.FREE:
        return settings.free_inactive_draft_days
    # Paid plans: abstraction — no automatic inactive-draft purge by default
    return settings.paid_inactive_draft_days


def compute_purge_after_for_trash(
    settings: Settings | None = None,
    *,
    policy: RetentionPolicy | None = None,
) -> Any:
    settings = settings or get_settings()
    return utcnow() + timedelta(days=trash_retention_days(settings, policy=policy))


async def move_to_trash(
    db: AsyncSession,
    *,
    project: Project,
    user: User,
    settings: Settings | None = None,
) -> Project:
    settings = settings or get_settings()
    if project.legal_hold:
        raise ForbiddenError("Project is under legal hold and cannot be trashed for purge")
    now = utcnow()
    if project.status != ProjectStatus.TRASH:
        project.status_before_trash = project.status.value
    project.status = ProjectStatus.TRASH
    project.trash_at = now
    project.purge_after = compute_purge_after_for_trash(settings, policy=project.retention_policy)
    project.deletion_notice_sent_at = None
    project.last_activity_at = now
    await record_audit(
        db,
        action=AuditAction.PROJECT_TRASHED,
        user_id=user.id,
        metadata={"project_id": str(project.id), "purge_after": project.purge_after.isoformat()},
    )
    await db.flush()
    await db.refresh(project)
    return project


async def restore_from_trash(
    db: AsyncSession,
    *,
    project: Project,
    user: User,
) -> Project:
    if project.status != ProjectStatus.TRASH:
        raise ValidationAppError("Project is not in trash")
    restored = ProjectStatus.ACTIVE
    if project.status_before_trash:
        try:
            restored = ProjectStatus(project.status_before_trash)
        except ValueError:
            restored = ProjectStatus.ACTIVE
        if restored == ProjectStatus.TRASH:
            restored = ProjectStatus.ACTIVE
    project.status = restored
    project.trash_at = None
    project.purge_after = None
    project.status_before_trash = None
    project.deletion_notice_sent_at = None
    project.last_activity_at = utcnow()
    await record_audit(
        db,
        action=AuditAction.PROJECT_RESTORED,
        user_id=user.id,
        metadata={"project_id": str(project.id), "restored_status": restored.value},
    )
    await db.flush()
    await db.refresh(project)
    return project


async def empty_trash(db: AsyncSession, *, user: User, settings: Settings | None = None) -> int:
    settings = settings or get_settings()
    rows = await db.scalars(
        select(Project).where(
            Project.owner_id == user.id,
            Project.status == ProjectStatus.TRASH,
            Project.legal_hold.is_(False),
        )
    )
    count = 0
    for project in rows.all():
        await purge_project(db, project=project, settings=settings, dry_run=False)
        count += 1
    return count


def is_purge_eligible(project: Project, *, now: Any | None = None) -> bool:
    now = now or utcnow()
    if project.legal_hold:
        return False
    if project.status != ProjectStatus.TRASH:
        return False
    if project.purge_after is None:
        return False
    return ensure_utc(project.purge_after) <= now


async def list_purge_candidates(db: AsyncSession) -> list[Project]:
    now = utcnow()
    rows = await db.scalars(
        select(Project).where(
            Project.status == ProjectStatus.TRASH,
            Project.legal_hold.is_(False),
            Project.purge_after.is_not(None),
            Project.purge_after <= now,
        )
    )
    return list(rows.all())


async def purge_project(
    db: AsyncSession,
    *,
    project: Project,
    settings: Settings | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Idempotent purge: object storage prefix + DB row + audit."""
    settings = settings or get_settings()
    project_id = project.id
    result: dict[str, Any] = {
        "project_id": str(project_id),
        "dry_run": dry_run,
        "purged": False,
        "skipped": False,
        "reason": None,
    }

    # Re-load for idempotency
    fresh = await db.get(Project, project_id)
    if fresh is None:
        result["skipped"] = True
        result["reason"] = "already_deleted"
        return result
    if fresh.legal_hold:
        result["skipped"] = True
        result["reason"] = "legal_hold"
        return result
    if fresh.status != ProjectStatus.TRASH and not dry_run:
        # Allow explicit permanent delete path to set trash first
        pass

    if dry_run:
        result["purged"] = True
        result["reason"] = "dry_run"
        return result

    prefix = f"projects/{project_id}/"
    storage_ok = delete_prefix(prefix)
    if not storage_ok:
        logger.error(
            "purge_storage_delete_failed",
            project_id=str(project_id),
            storage_prefix=prefix,
        )
        result["skipped"] = True
        result["reason"] = "storage_delete_failed"
        result["storage_deleted"] = False
        await record_audit(
            db,
            action=AuditAction.PROJECT_PURGED,
            user_id=fresh.owner_id,
            metadata={
                "project_id": str(project_id),
                "storage_prefix": prefix,
                "storage_deleted": False,
                "db_deleted": False,
            },
        )
        return result

    owner_id = fresh.owner_id
    await db.delete(fresh)
    await db.flush()
    await record_audit(
        db,
        action=AuditAction.PROJECT_PURGED,
        user_id=owner_id,
        metadata={
            "project_id": str(project_id),
            "storage_prefix": prefix,
            "storage_deleted": True,
            "db_deleted": True,
        },
    )
    result["purged"] = True
    result["storage_deleted"] = True
    return result


async def permanently_delete(
    db: AsyncSession,
    *,
    project: Project,
    user: User,
    confirm: str,
    settings: Settings | None = None,
) -> dict[str, Any]:
    if confirm != "DELETE":
        raise ValidationAppError('Confirmation must be the string "DELETE"')
    if project.legal_hold:
        raise ForbiddenError("Project is under legal hold and cannot be permanently deleted")
    if project.owner_id != user.id:
        raise NotFoundError("Project not found")
    # Move to trash semantics then purge immediately
    project.status = ProjectStatus.TRASH
    project.trash_at = utcnow()
    project.purge_after = utcnow()
    await db.flush()
    return await purge_project(db, project=project, settings=settings, dry_run=False)


async def apply_inactive_draft_policy(
    db: AsyncSession,
    *,
    settings: Settings | None = None,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    """Mark eligible inactive free-plan drafts for trash (does not purge immediately)."""
    settings = settings or get_settings()
    results: list[dict[str, Any]] = []
    now = utcnow()
    rows = await db.scalars(
        select(Project)
        .join(User, User.id == Project.owner_id)
        .where(
            Project.status == ProjectStatus.DRAFT,
            Project.legal_hold.is_(False),
            User.subscription_plan == SubscriptionPlan.FREE,
        )
        .options(selectinload(Project.owner))
    )
    for project in rows.all():
        days = inactive_draft_days_for_plan(
            project.owner.subscription_plan,
            settings,
            policy=project.retention_policy,
        )
        if days is None:
            continue
        activity = project.last_activity_at or project.updated_at
        if ensure_utc(activity) > now - timedelta(days=days):
            continue
        if project.retention_policy == RetentionPolicy.KEEP:
            continue
        entry = {
            "project_id": str(project.id),
            "action": "trash_inactive_draft",
            "dry_run": dry_run,
        }
        if not dry_run:
            project.status_before_trash = project.status.value
            project.status = ProjectStatus.TRASH
            project.trash_at = now
            project.purge_after = compute_purge_after_for_trash(
                settings, policy=project.retention_policy
            )
            project.deletion_notice_sent_at = None
            await record_audit(
                db,
                action=AuditAction.PROJECT_TRASHED,
                user_id=project.owner_id,
                metadata={"project_id": str(project.id), "reason": "inactive_draft_policy"},
            )
        results.append(entry)
    await db.flush()
    return results


async def notify_upcoming_deletions(
    db: AsyncSession,
    *,
    settings: Settings | None = None,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    """Email abstraction: warn owners before scheduled permanent deletion."""
    settings = settings or get_settings()
    now = utcnow()
    window_end = now + timedelta(days=settings.deletion_notice_days)
    rows = await db.scalars(
        select(Project)
        .where(
            Project.status == ProjectStatus.TRASH,
            Project.legal_hold.is_(False),
            Project.purge_after.is_not(None),
            Project.purge_after > now,
            Project.purge_after <= window_end,
        )
        .options(selectinload(Project.owner))
    )
    notified: list[dict[str, Any]] = []
    for project in rows.all():
        # Dedupe: only one warning email/notification per trash cycle
        if project.deletion_notice_sent_at is not None:
            continue
        entry = {
            "project_id": str(project.id),
            "owner_email": project.owner.email,
            "purge_after": project.purge_after.isoformat() if project.purge_after else None,
            "dry_run": dry_run,
        }
        if not dry_run and project.purge_after is not None:
            await send_pending_deletion_email(
                to=project.owner.email,
                project_title=project.title,
                purge_after_iso=project.purge_after.isoformat(),
                settings=settings,
            )
            from app.models.enums import NotificationKind
            from app.services.engagement.notifications import create_notification

            await create_notification(
                db,
                user_id=project.owner_id,
                project_id=project.id,
                kind=NotificationKind.TRASH_EXPIRATION,
                title="Project scheduled for deletion",
                body=(
                    "A project in trash is approaching permanent deletion. "
                    "You can keep, archive, export, or delete now from the project home."
                ),
                action_url=f"/projects/{project.id}",
            )
            project.deletion_notice_sent_at = now
        notified.append(entry)
    await db.flush()
    return notified


async def run_scheduled_cleanup(
    db: AsyncSession,
    *,
    settings: Settings | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    settings = settings or get_settings()
    notices = await notify_upcoming_deletions(db, settings=settings, dry_run=dry_run)
    inactive = await apply_inactive_draft_policy(db, settings=settings, dry_run=dry_run)
    candidates = await list_purge_candidates(db)
    purged: list[dict[str, Any]] = []
    for project in candidates:
        purged.append(await purge_project(db, project=project, settings=settings, dry_run=dry_run))
    return {
        "deletion_notices": notices,
        "inactive_drafts": inactive,
        "purge_results": purged,
        "dry_run": dry_run,
    }
