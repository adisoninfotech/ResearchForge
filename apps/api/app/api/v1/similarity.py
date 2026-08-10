"""Similarity and citation-risk checker APIs."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, enforce_rate_limit, require_csrf
from app.core.exceptions import NotFoundError, ValidationAppError
from app.models.enums import FindingResolutionAction
from app.models.similarity import SimilarityJob
from app.schemas.similarity import (
    FindingResolveRequest,
    RewriteAcceptRequest,
    SimilarityRunRequest,
)
from app.services.authorization import get_owned_project
from app.services.similarity import service as similarity_service
from app.services.similarity.thresholds import COVERAGE_LIMITATIONS, PROFILES

router = APIRouter(prefix="/projects/{project_id}/similarity", tags=["similarity"])


@router.get("/meta")
async def similarity_meta(
    project_id: UUID,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    await get_owned_project(session, project_id=project_id, user=user)
    return {
        "language": {
            "safe_summary": (
                "No significant textual overlap was identified within the sources checked."
            ),
            "forbidden_claims": [
                "Zero plagiarism",
                "Plagiarism-free guarantee",
                "Guaranteed originality",
                "Equivalent to Turnitin or iThenticate",
            ],
        },
        "threshold_profiles": {name: profile.__dict__ for name, profile in PROFILES.items()},
        "coverage_limitations": COVERAGE_LIMITATIONS,
    }


@router.post(
    "/run",
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def run_similarity(
    project_id: UUID,
    payload: SimilarityRunRequest,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    project = await get_owned_project(session, project_id=project_id, user=user)
    job = await similarity_service.create_and_run_job(
        session,
        project=project,
        user=user,
        options=payload.model_dump(mode="json"),
    )
    result = similarity_service.job_to_dict(job)
    if job.report is not None:
        full = await similarity_service.get_report(
            session, project_id=project_id, report_id=job.report.id
        )
        if full is not None:
            result["report"] = similarity_service.report_to_dict(
                full,
                filters={
                    "exclude_bibliography": payload.exclude_bibliography,
                    "exclude_quotations": payload.exclude_quotations,
                    "exclude_common": payload.exclude_common_phrases,
                },
            )
    return result


@router.get("/jobs")
async def list_jobs(
    project_id: UUID,
    session: DbSession,
    user: CurrentUser,
) -> list[dict[str, Any]]:
    await get_owned_project(session, project_id=project_id, user=user)
    rows = await session.scalars(
        select(SimilarityJob)
        .where(SimilarityJob.project_id == project_id)
        .order_by(SimilarityJob.created_at.desc())
    )
    return [similarity_service.job_to_dict(j) for j in rows.all()]


@router.get("/jobs/{job_id}")
async def get_job(
    project_id: UUID,
    job_id: UUID,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    await get_owned_project(session, project_id=project_id, user=user)
    job = await similarity_service.get_job(session, project_id=project_id, job_id=job_id)
    if job is None:
        raise NotFoundError("Similarity job not found")
    return similarity_service.job_to_dict(job)


@router.get("/reports/{report_id}")
async def get_report(
    project_id: UUID,
    report_id: UUID,
    session: DbSession,
    user: CurrentUser,
    exclude_bibliography: bool = Query(default=False),
    exclude_quotations: bool = Query(default=False),
    exclude_common: bool = Query(default=False),
    classification: str | None = Query(default=None),
) -> dict[str, Any]:
    await get_owned_project(session, project_id=project_id, user=user)
    report = await similarity_service.get_report(
        session, project_id=project_id, report_id=report_id
    )
    if report is None:
        raise NotFoundError("Similarity report not found")
    return similarity_service.report_to_dict(
        report,
        filters={
            "exclude_bibliography": exclude_bibliography,
            "exclude_quotations": exclude_quotations,
            "exclude_common": exclude_common,
            "classification": classification,
        },
    )


@router.get("/reports/{report_id}/download")
async def download_report(
    project_id: UUID,
    report_id: UUID,
    session: DbSession,
    user: CurrentUser,
) -> PlainTextResponse:
    await get_owned_project(session, project_id=project_id, user=user)
    report = await similarity_service.get_report(
        session, project_id=project_id, report_id=report_id
    )
    if report is None:
        raise NotFoundError("Similarity report not found")
    return PlainTextResponse(
        similarity_service.export_report_text(report),
        media_type="text/plain",
        headers={
            "Content-Disposition": f'attachment; filename="similarity-report-{report_id}.txt"'
        },
    )


@router.post(
    "/findings/{finding_id}/resolve",
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def resolve_finding(
    project_id: UUID,
    finding_id: UUID,
    payload: FindingResolveRequest,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    await get_owned_project(session, project_id=project_id, user=user)
    try:
        action = FindingResolutionAction(payload.action)
    except ValueError as exc:
        raise ValidationAppError("Invalid resolution action") from exc
    finding = await similarity_service.resolve_finding(
        session,
        project_id=project_id,
        finding_id=finding_id,
        user=user,
        action=action,
        note=payload.note,
    )
    return similarity_service.finding_to_dict(finding)


@router.post(
    "/findings/{finding_id}/rewrite",
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def propose_rewrite(
    project_id: UUID,
    finding_id: UUID,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    await get_owned_project(session, project_id=project_id, user=user)
    finding = await similarity_service.propose_rewrite(
        session, project_id=project_id, finding_id=finding_id, user=user
    )
    return similarity_service.finding_to_dict(finding)


@router.post(
    "/findings/{finding_id}/rewrite/accept",
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def accept_rewrite(
    project_id: UUID,
    finding_id: UUID,
    payload: RewriteAcceptRequest,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    project = await get_owned_project(session, project_id=project_id, user=user)
    result = await similarity_service.accept_rewrite(
        session,
        project=project,
        user=user,
        finding_id=finding_id,
        accepted_text=payload.accepted_text,
    )
    # Rerun check for the project after acceptance
    job = await similarity_service.create_and_run_job(
        session, project=project, user=user, options={"threshold_profile": "default"}
    )
    result["rerun_job_id"] = str(job.id)
    result["rerun_report_id"] = str(job.report.id) if job.report else None
    return result
