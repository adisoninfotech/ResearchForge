"""API v1 router aggregation."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    account,
    ai,
    auth,
    datasets,
    discovery,
    engagement,
    exports,
    files,
    guest,
    manuscripts,
    projects,
    similarity,
)

api_v1_router = APIRouter()
api_v1_router.include_router(auth.router)
api_v1_router.include_router(account.router)
api_v1_router.include_router(guest.router)
api_v1_router.include_router(projects.router)
api_v1_router.include_router(manuscripts.router)
api_v1_router.include_router(files.router)
api_v1_router.include_router(datasets.router)
api_v1_router.include_router(similarity.router)
api_v1_router.include_router(exports.router)
api_v1_router.include_router(engagement.router)
api_v1_router.include_router(ai.router)
api_v1_router.include_router(discovery.router)
