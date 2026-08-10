"""Celery application for durable background jobs."""

from __future__ import annotations

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "researchforge",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "project-retention-cleanup-hourly": {
            "task": "researchforge.scheduled_project_cleanup",
            "schedule": 3600.0,
            "kwargs": {"dry_run": False},
        },
        "pending-deletion-notices-daily": {
            "task": "researchforge.notify_pending_deletions",
            "schedule": 86400.0,
            "kwargs": {"dry_run": False},
        },
    },
)
