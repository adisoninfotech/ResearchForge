"""Celery tasks for durable background jobs."""

from __future__ import annotations

import asyncio
from typing import Any

from app.workers.celery_app import celery_app


@celery_app.task(name="researchforge.ping")
def ping() -> dict[str, str]:
    return {"status": "ok", "task": "ping"}


@celery_app.task(name="researchforge.transfer_guest_draft_async")
def transfer_guest_draft_async(project_id: str) -> dict[str, Any]:
    """Placeholder durable job hook for post-transfer processing."""
    return {"status": "accepted", "project_id": project_id}


async def _run_cleanup(dry_run: bool) -> dict[str, Any]:
    from app.db.session import AsyncSessionLocal
    from app.services.retention import run_scheduled_cleanup

    async with AsyncSessionLocal() as session:
        result = await run_scheduled_cleanup(session, dry_run=dry_run)
        await session.commit()
        return result


@celery_app.task(name="researchforge.scheduled_project_cleanup")
def scheduled_project_cleanup(dry_run: bool = False) -> dict[str, Any]:
    """Idempotent trash purge + inactive-draft policy + deletion notices."""
    return asyncio.run(_run_cleanup(dry_run=dry_run))


@celery_app.task(name="researchforge.notify_pending_deletions")
def notify_pending_deletions(dry_run: bool = False) -> dict[str, Any]:
    async def _run() -> dict[str, Any]:
        from app.db.session import AsyncSessionLocal
        from app.services.retention import notify_upcoming_deletions

        async with AsyncSessionLocal() as session:
            notices = await notify_upcoming_deletions(session, dry_run=dry_run)
            await session.commit()
            return {"notices": notices, "dry_run": dry_run}

    return asyncio.run(_run())


@celery_app.task(
    name="researchforge.run_ai_job",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
)
def run_ai_job(self, job_id: str) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    async def _run() -> dict[str, Any]:
        from uuid import UUID

        from app.db.session import AsyncSessionLocal
        from app.services.ai.jobs import execute_ai_job, job_to_dict

        async with AsyncSessionLocal() as session:
            job = await execute_ai_job(session, job_id=UUID(job_id))
            await session.commit()
            return job_to_dict(job)

    return asyncio.run(_run())


@celery_app.task(
    name="researchforge.process_project_file",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
)
def process_project_file(self, file_id: str) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    async def _run() -> dict[str, Any]:
        from uuid import UUID

        from sqlalchemy import select

        from app.db.session import AsyncSessionLocal
        from app.models.project_file import FileProcessingJob
        from app.services.files.processing import process_file_job
        from app.services.files.upload import file_to_dict

        async with AsyncSessionLocal() as session:
            file = await process_file_job(session, file_id=UUID(file_id))
            job = await session.scalar(
                select(FileProcessingJob)
                .where(FileProcessingJob.project_file_id == file.id)
                .order_by(FileProcessingJob.created_at.desc())
            )
            if job is not None:
                job.celery_task_id = getattr(self.request, "id", None)
            await session.commit()
            return file_to_dict(file)

    return asyncio.run(_run())


@celery_app.task(
    name="researchforge.run_export_job",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
)
def run_export_job(self, job_id: str) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    async def _run() -> dict[str, Any]:
        from uuid import UUID

        from app.db.session import AsyncSessionLocal
        from app.services.export import service as export_service

        async with AsyncSessionLocal() as session:
            job = await export_service.execute_export_job(session, job_id=UUID(job_id))
            await session.commit()
            return export_service.job_to_dict(job)

    return asyncio.run(_run())
