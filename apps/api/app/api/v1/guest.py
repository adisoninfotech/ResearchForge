"""Guest preview endpoints — no durable guest manuscript storage on the server."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import AppSettings, CurrentUser, DbSession, enforce_rate_limit, require_csrf
from app.schemas.guest import (
    GuestOutlineRequest,
    GuestOutlineResponse,
    GuestTransferRequest,
    GuestTransferResponse,
)
from app.services import projects as project_service
from app.services.ai import get_ai_provider

router = APIRouter(prefix="/guest", tags=["guest"])


@router.post(
    "/outline",
    response_model=GuestOutlineResponse,
    dependencies=[Depends(enforce_rate_limit)],
)
async def generate_guest_outline(
    payload: GuestOutlineRequest,
    settings: AppSettings,
) -> GuestOutlineResponse:
    provider = get_ai_provider(settings)
    outline = await provider.generate_outline(
        title=payload.title,
        research_area=payload.research_area,
        research_problem=payload.research_problem,
        proposed_contribution=payload.proposed_contribution,
        target_format=payload.target_format,
        max_sections=settings.guest_outline_max_sections,
    )
    return GuestOutlineResponse(outline=outline)


@router.post(
    "/transfer",
    response_model=GuestTransferResponse,
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
    deprecated=True,
)
async def transfer_guest_draft(
    payload: GuestTransferRequest,
    session: DbSession,
    user: CurrentUser,
) -> GuestTransferResponse:
    """Deprecated alias — prefer POST /projects/from-guest."""
    project, created = await project_service.convert_guest_draft(
        session,
        user=user,
        payload=payload,
    )
    return GuestTransferResponse(
        project=project_service.project_to_public(project),
        created=created,
        message=(
            "Guest draft saved as a new project"
            if created
            else "Guest draft was already converted (idempotent)"
        ),
    )
