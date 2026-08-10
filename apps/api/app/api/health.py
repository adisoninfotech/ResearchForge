"""Liveness and readiness probes, plus Prometheus metrics."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Response

from app.core.config import get_settings
from app.db.session import check_database, engine
from app.observability.metrics import DB_POOL, metrics
from app.schemas.health import LiveResponse, ReadyComponent, ReadyResponse
from app.services.redis_client import check_redis
from app.services.storage import check_object_storage

router = APIRouter(tags=["health"])


def _refresh_db_pool_metrics() -> None:
    pool = engine.sync_engine.pool
    size = getattr(pool, "size", None)
    checked_in = getattr(pool, "checkedin", None)
    checked_out = getattr(pool, "checkedout", None)
    overflow = getattr(pool, "overflow", None)
    if callable(size):
        metrics.set_gauge(DB_POOL, float(size()), labels={"state": "size"})
    if callable(checked_in):
        metrics.set_gauge(DB_POOL, float(checked_in()), labels={"state": "checked_in"})
    if callable(checked_out):
        metrics.set_gauge(DB_POOL, float(checked_out()), labels={"state": "checked_out"})
    if callable(overflow):
        metrics.set_gauge(DB_POOL, float(overflow()), labels={"state": "overflow"})


@router.get("/health/live", response_model=LiveResponse)
async def live() -> LiveResponse:
    settings = get_settings()
    return LiveResponse(service=settings.app_name)


@router.get("/health/ready", response_model=ReadyResponse)
async def ready() -> ReadyResponse:
    components = [
        ReadyComponent(name="database", status="ok" if await check_database() else "error"),
        ReadyComponent(name="redis", status="ok" if await check_redis() else "error"),
        ReadyComponent(
            name="object_storage",
            status="ok" if check_object_storage() else "error",
        ),
    ]
    errors = sum(1 for c in components if c.status == "error")
    overall: Literal["ok", "degraded", "error"]
    if errors == 0:
        overall = "ok"
    elif errors == len(components):
        overall = "error"
    else:
        overall = "degraded"
    return ReadyResponse(status=overall, components=components)


@router.get("/metrics", include_in_schema=False)
async def prometheus_metrics() -> Response:
    """Prometheus text exposition. Values never include manuscript content."""
    _refresh_db_pool_metrics()
    body = metrics.render_prometheus()
    return Response(content=body, media_type="text/plain; version=0.0.4; charset=utf-8")
