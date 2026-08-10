"""Authenticated project endpoints with ownership checks."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, DbSession, enforce_rate_limit, require_csrf
from app.schemas.guest import GuestTransferRequest, GuestTransferResponse
from app.schemas.projects import (
    PermanentDeleteRequest,
    ProjectCreateRequest,
    ProjectPublic,
    ProjectUpdateRequest,
)
from app.services import projects as project_service
from app.services import retention as retention_service
from app.services.authorization import get_owned_project

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectPublic])
async def list_projects(
    session: DbSession,
    user: CurrentUser,
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    sort: str = Query(default="last_edited"),
) -> list[ProjectPublic]:
    rows = await project_service.list_user_projects(
        session, user=user, status=status, q=q, sort=sort
    )
    return [project_service.project_to_public(p) for p in rows]


@router.post(
    "",
    response_model=ProjectPublic,
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def create_project(
    payload: ProjectCreateRequest,
    session: DbSession,
    user: CurrentUser,
) -> ProjectPublic:
    project = await project_service.create_project(session, user=user, payload=payload)
    return project_service.project_to_public(project)


@router.post(
    "/from-guest",
    response_model=GuestTransferResponse,
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def convert_guest_draft(
    payload: GuestTransferRequest,
    session: DbSession,
    user: CurrentUser,
) -> GuestTransferResponse:
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


@router.post(
    "/trash/empty",
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def empty_trash(session: DbSession, user: CurrentUser) -> dict[str, int]:
    count = await retention_service.empty_trash(session, user=user)
    return {"purged": count}


@router.get("/{project_id}", response_model=ProjectPublic)
async def get_project(
    project_id: UUID,
    session: DbSession,
    user: CurrentUser,
) -> ProjectPublic:
    project = await get_owned_project(session, project_id=project_id, user=user)
    return project_service.project_to_public(project)


@router.patch(
    "/{project_id}",
    response_model=ProjectPublic,
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def update_project(
    project_id: UUID,
    payload: ProjectUpdateRequest,
    session: DbSession,
    user: CurrentUser,
) -> ProjectPublic:
    project = await get_owned_project(session, project_id=project_id, user=user)
    updated = await project_service.update_project(
        session, project=project, user=user, payload=payload
    )
    return project_service.project_to_public(updated)


@router.post(
    "/{project_id}/trash",
    response_model=ProjectPublic,
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def trash_project(
    project_id: UUID,
    session: DbSession,
    user: CurrentUser,
) -> ProjectPublic:
    project = await get_owned_project(session, project_id=project_id, user=user)
    trashed = await retention_service.move_to_trash(session, project=project, user=user)
    return project_service.project_to_public(trashed)


@router.post(
    "/{project_id}/restore",
    response_model=ProjectPublic,
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def restore_project(
    project_id: UUID,
    session: DbSession,
    user: CurrentUser,
) -> ProjectPublic:
    project = await get_owned_project(session, project_id=project_id, user=user)
    restored = await retention_service.restore_from_trash(session, project=project, user=user)
    return project_service.project_to_public(restored)


@router.post(
    "/{project_id}/permanent-delete",
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def permanent_delete(
    project_id: UUID,
    payload: PermanentDeleteRequest,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, object]:
    project = await get_owned_project(session, project_id=project_id, user=user)
    return await retention_service.permanently_delete(
        session,
        project=project,
        user=user,
        confirm=payload.confirmation,
    )
