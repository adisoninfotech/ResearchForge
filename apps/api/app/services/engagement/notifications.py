"""User-controlled notification preferences and in-app notices."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utcnow
from app.models.engagement import InAppNotification, NotificationPreference
from app.models.enums import NotificationKind
from app.models.user import User

DEFAULT_PREFERENCES: dict[str, bool] = {
    NotificationKind.DRAFT_SCHEDULED_DELETION.value: True,
    NotificationKind.TRASH_EXPIRATION.value: True,
    NotificationKind.COLLABORATOR_ACTIVITY.value: False,  # placeholder
    NotificationKind.EXPORT_COMPLETED.value: True,
    NotificationKind.SIMILARITY_REPORT_COMPLETED.value: True,
    NotificationKind.SUBMISSION_DATE_APPROACHING.value: True,
    NotificationKind.WEEKLY_PROJECT_SUMMARY.value: False,
    NotificationKind.WRITING_REMINDERS.value: False,  # off unless enabled
}

KIND_LABELS: dict[str, str] = {
    NotificationKind.DRAFT_SCHEDULED_DELETION.value: "Draft scheduled for deletion",
    NotificationKind.TRASH_EXPIRATION.value: "Trash expiration",
    NotificationKind.COLLABORATOR_ACTIVITY.value: "Collaborator activity (placeholder)",
    NotificationKind.EXPORT_COMPLETED.value: "Export completed",
    NotificationKind.SIMILARITY_REPORT_COMPLETED.value: "Similarity report completed",
    NotificationKind.SUBMISSION_DATE_APPROACHING.value: "Submission date approaching",
    NotificationKind.WEEKLY_PROJECT_SUMMARY.value: "Weekly project summary",
    NotificationKind.WRITING_REMINDERS.value: "Writing reminders",
}


def _merged(prefs: dict[str, Any] | None) -> dict[str, bool]:
    out = dict(DEFAULT_PREFERENCES)
    if prefs:
        for key, val in prefs.items():
            if key in out:
                out[key] = bool(val)
    return out


async def get_preferences(db: AsyncSession, *, user: User) -> dict[str, Any]:
    row = await db.scalar(
        select(NotificationPreference).where(NotificationPreference.user_id == user.id)
    )
    prefs = _merged(row.preferences if row else None)
    return {
        "preferences": prefs,
        "labels": KIND_LABELS,
        "writing_reminders_default_off": True,
        "note": "Writing reminders are never sent unless you enable them.",
    }


async def update_preferences(
    db: AsyncSession,
    *,
    user: User,
    preferences: dict[str, bool],
) -> dict[str, Any]:
    row = await db.scalar(
        select(NotificationPreference).where(NotificationPreference.user_id == user.id)
    )
    merged = _merged(row.preferences if row else None)
    for key, val in preferences.items():
        if key in DEFAULT_PREFERENCES:
            merged[key] = bool(val)
    if row is None:
        row = NotificationPreference(user_id=user.id, preferences=merged)
        db.add(row)
    else:
        row.preferences = merged
    await db.flush()
    return await get_preferences(db, user=user)


async def is_enabled(db: AsyncSession, *, user_id: UUID, kind: NotificationKind) -> bool:
    row = await db.scalar(
        select(NotificationPreference).where(NotificationPreference.user_id == user_id)
    )
    return _merged(row.preferences if row else None).get(kind.value, False)


async def create_notification(
    db: AsyncSession,
    *,
    user_id: UUID,
    kind: NotificationKind,
    title: str,
    body: str,
    project_id: UUID | None = None,
    action_url: str | None = None,
    meta: dict[str, Any] | None = None,
) -> InAppNotification | None:
    if not await is_enabled(db, user_id=user_id, kind=kind):
        return None
    note = InAppNotification(
        user_id=user_id,
        project_id=project_id,
        kind=kind,
        title=title,
        body=body,
        action_url=action_url,
        meta=meta or {},
        read=False,
    )
    db.add(note)
    await db.flush()
    return note


async def list_notifications(
    db: AsyncSession, *, user_id: UUID, limit: int = 50
) -> list[dict[str, Any]]:
    rows = (
        await db.scalars(
            select(InAppNotification)
            .where(InAppNotification.user_id == user_id)
            .order_by(InAppNotification.created_at.desc())
            .limit(limit)
        )
    ).all()
    return [
        {
            "id": str(n.id),
            "kind": n.kind.value,
            "title": n.title,
            "body": n.body,
            "read": n.read,
            "project_id": str(n.project_id) if n.project_id else None,
            "action_url": n.action_url,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in rows
    ]


async def mark_read(db: AsyncSession, *, user_id: UUID, notification_id: UUID) -> bool:
    row = await db.scalar(
        select(InAppNotification).where(
            InAppNotification.id == notification_id,
            InAppNotification.user_id == user_id,
        )
    )
    if row is None:
        return False
    row.read = True
    row.updated_at = utcnow()
    await db.flush()
    return True
