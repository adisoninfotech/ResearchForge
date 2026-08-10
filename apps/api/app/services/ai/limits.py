"""Per-user and per-project AI job limits."""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.core.time import utcnow
from app.models.ai_job import AIJob
from app.models.enums import AIJobStatus


async def enforce_ai_limits(
    db: AsyncSession,
    *,
    owner_id: UUID,
    project_id: UUID | None,
    settings: Settings | None = None,
) -> None:
    settings = settings or get_settings()
    now = utcnow()
    day_ago = now - timedelta(days=1)
    hour_ago = now - timedelta(hours=1)

    user_count = await db.scalar(
        select(func.count())
        .select_from(AIJob)
        .where(
            AIJob.owner_id == owner_id,
            AIJob.created_at >= day_ago,
            AIJob.status != AIJobStatus.CANCELLED,
        )
    )
    if int(user_count or 0) >= settings.ai_user_daily_job_limit:
        raise AppError(
            "Daily AI generation limit reached",
            code="ai_user_limit",
            status_code=429,
        )

    if project_id is not None:
        project_count = await db.scalar(
            select(func.count())
            .select_from(AIJob)
            .where(
                AIJob.project_id == project_id,
                AIJob.created_at >= hour_ago,
                AIJob.status != AIJobStatus.CANCELLED,
            )
        )
        if int(project_count or 0) >= settings.ai_project_hourly_job_limit:
            raise AppError(
                "Project AI generation limit reached",
                code="ai_project_limit",
                status_code=429,
            )
