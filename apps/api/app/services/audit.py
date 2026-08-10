"""Audit event helpers."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utcnow
from app.models.audit_event import AuditEvent
from app.models.enums import AuditAction


async def record_audit(
    session: AsyncSession,
    *,
    action: AuditAction,
    user_id: UUID | None = None,
    ip_hash: str | None = None,
    user_agent: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        user_id=user_id,
        action=action,
        ip_hash=ip_hash,
        user_agent=(user_agent or "")[:512] or None,
        metadata_json=metadata,
        created_at=utcnow(),
    )
    session.add(event)
    await session.flush()
    return event
