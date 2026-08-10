"""Manuscript export and preview APIs."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from app.api.deps import CurrentUser, DbSession, OptionalUser, enforce_rate_limit, require_csrf
from app.schemas.export import ExportPreviewRequest, ExportRunRequest
from app.services.authorization import get_owned_project
from app.services.export import service as export_service

router = APIRouter(tags=["exports"])


@router.get("/projects/{project_id}/exports/meta")
async def export_meta(
    project_id: UUID,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    await get_owned_project(session, project_id=project_id, user=user)
    return export_service.meta_payload()


@router.post(
    "/projects/{project_id}/exports/preview",
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def export_preview(
    project_id: UUID,
    payload: ExportPreviewRequest,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    project = await get_owned_project(session, project_id=project_id, user=user)
    options: dict[str, Any] = {
        "affiliations": payload.affiliations,
        "back_matter": payload.back_matter,
    }
    if payload.authors is not None:
        options["authors"] = [a.model_dump() for a in payload.authors]
    return await export_service.preview_manuscript(
        session,
        project=project,
        template_id=payload.template_id,
        page=payload.page,
        options={k: v for k, v in options.items() if v is not None},
    )


@router.post(
    "/projects/{project_id}/exports/run",
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def run_export(
    project_id: UUID,
    payload: ExportRunRequest,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    project = await get_owned_project(session, project_id=project_id, user=user)
    options: dict[str, Any] = {}
    if payload.authors is not None:
        options["authors"] = [a.model_dump() for a in payload.authors]
    if payload.affiliations is not None:
        options["affiliations"] = payload.affiliations
    if payload.back_matter is not None:
        options["back_matter"] = payload.back_matter
    job = await export_service.create_export_job(
        session,
        project=project,
        user=user,
        template_id=payload.template_id,
        outputs=payload.outputs,
        acknowledged_warnings=payload.acknowledged_warnings,
        options=options,
        idempotency_key=payload.idempotency_key,
        process_sync=payload.process_sync,
    )
    return export_service.job_to_dict(job)


@router.get("/projects/{project_id}/exports/jobs")
async def list_export_jobs(
    project_id: UUID,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    await get_owned_project(session, project_id=project_id, user=user)
    jobs = await export_service.list_jobs(session, project_id=project_id)
    return {"jobs": [export_service.job_to_dict(j) for j in jobs]}


@router.get("/projects/{project_id}/exports/jobs/{job_id}")
async def get_export_job(
    project_id: UUID,
    job_id: UUID,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    await get_owned_project(session, project_id=project_id, user=user)
    job = await export_service.get_job(session, project_id=project_id, job_id=job_id)
    return export_service.job_to_dict(job)


@router.get("/projects/{project_id}/exports/history")
async def export_download_history(
    project_id: UUID,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    await get_owned_project(session, project_id=project_id, user=user)
    history = await export_service.download_history(session, project_id=project_id, user_id=user.id)
    return {"downloads": history}


@router.post(
    "/projects/{project_id}/exports/artifacts/{artifact_id}/download",
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def create_artifact_download(
    project_id: UUID,
    artifact_id: UUID,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    project = await get_owned_project(session, project_id=project_id, user=user)
    return await export_service.create_download_grant(
        session, project=project, user=user, artifact_id=artifact_id
    )


@router.get("/exports/download/{token}")
async def redeem_export_download(
    token: str,
    session: DbSession,
    user: OptionalUser,
) -> Response:
    artifact, data = await export_service.redeem_download_token(session, token=token, user=user)
    headers = {
        "Content-Disposition": f'attachment; filename="{artifact.filename}"',
        "X-Export-Artifact-Kind": artifact.kind.value,
    }
    return Response(content=data, media_type=artifact.content_type, headers=headers)
