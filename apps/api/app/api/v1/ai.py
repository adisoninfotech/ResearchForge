"""AI generation jobs, SSE progress, and proposal review APIs."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.api.deps import AppSettings, CurrentUser, DbSession, enforce_rate_limit, require_csrf
from app.core.exceptions import AppError, ValidationAppError
from app.core.time import utcnow
from app.models.enums import AIOperation
from app.models.project_fact import ProjectFact
from app.schemas.ai import AIGenerateRequest, AIJobPublic, ProposalDecisionRequest
from app.services import manuscripts as manuscript_service
from app.services.ai import jobs as job_service
from app.services.authorization import get_owned_project

router = APIRouter(prefix="/ai", tags=["ai"])


def _parse_operation(value: str) -> AIOperation:
    try:
        return AIOperation(value)
    except ValueError as exc:
        raise ValidationAppError(f"Unsupported AI operation: {value}") from exc


async def _resolve_evidence_passages(
    session: DbSession,
    *,
    project_id: UUID,
    passages: list[Any],
) -> list[dict[str, Any]]:
    """Load chunk text from DB when chunk_id is provided; reject foreign chunks."""
    from app.models.project_file import DocumentChunk

    resolved: list[dict[str, Any]] = []
    for passage in passages:
        data = passage.model_dump() if hasattr(passage, "model_dump") else dict(passage)
        chunk_id = data.get("chunk_id")
        if chunk_id:
            chunk = await session.scalar(
                select(DocumentChunk).where(
                    DocumentChunk.id == chunk_id,
                    DocumentChunk.project_id == project_id,
                )
            )
            if chunk is None:
                raise ValidationAppError(
                    "Evidence chunk not found in this project",
                    details={"chunk_id": str(chunk_id)},
                )
            resolved.append(
                {
                    "id": data.get("id") or str(chunk.id),
                    "text": chunk.text,
                    "chunk_id": str(chunk.id),
                    "source_label": data.get("source_label") or chunk.evidence_key,
                    "is_synthetic": bool(data.get("is_synthetic")),
                }
            )
        else:
            text = str(data.get("text") or "").strip()
            if not text:
                continue
            resolved.append(
                {
                    "id": str(data.get("id") or f"pasted-{len(resolved) + 1}"),
                    "text": text,
                    "source_label": data.get("source_label"),
                    "is_synthetic": bool(data.get("is_synthetic")),
                }
            )
    return resolved


async def _build_variables(
    session: DbSession,
    user: CurrentUser,
    payload: AIGenerateRequest,
) -> dict[str, Any]:
    variables: dict[str, Any] = {
        "section_type": payload.section_type or "",
        "section_title": payload.section_title or "",
        "section_goal": payload.section_goal or "",
        "selected_text": payload.selected_text or "",
        "existing_text": payload.existing_text or "",
        "evidence_passages": [e.model_dump() for e in payload.evidence_passages],
        "constraints": list(payload.constraints),
        "length_hint": payload.length_hint or "shorter",
        "max_sections": 8,
        "contains_synthetic_data": False,
        "target_format": None,
        "project_facts": {},
        "manuscript_context": {},
        "title": "",
        "research_field": "",
        "research_problem": "",
        "proposed_contribution": "",
    }
    if payload.project_id is None:
        return variables

    project = await get_owned_project(session, project_id=payload.project_id, user=user)
    variables.update(
        {
            "title": project.title,
            "research_field": project.research_field or project.research_area or "",
            "research_problem": project.research_problem or "",
            "proposed_contribution": project.proposed_contribution or "",
            "target_format": project.target_template or project.target_format or "",
            "contains_synthetic_data": project.contains_synthetic_data,
        }
    )
    variables["evidence_passages"] = await _resolve_evidence_passages(
        session,
        project_id=project.id,
        passages=payload.evidence_passages,
    )
    facts = await session.scalars(select(ProjectFact).where(ProjectFact.project_id == project.id))
    from app.services.engagement.questions import facts_for_ai

    variables["project_facts"] = facts_for_ai(
        {f"{f.category.value}:{f.key}": f.value for f in facts.all()}
    )
    manuscript = await manuscript_service.get_manuscript_for_project(session, project=project)
    variables["manuscript_context"] = {
        s.section_type.value: s.plain_text for s in manuscript.sections if s.plain_text
    }
    if payload.section_id:
        section = next((s for s in manuscript.sections if s.id == payload.section_id), None)
        if section:
            variables["section_type"] = section.section_type.value
            variables["section_title"] = section.title
            if not variables["existing_text"]:
                variables["existing_text"] = section.plain_text
    return variables


@router.get("/health")
async def ai_health(settings: AppSettings) -> dict[str, Any]:
    from app.services.ai.factory import get_llm_client

    client = get_llm_client(settings)
    return await client.health_check()


@router.post(
    "/generate",
    response_model=AIJobPublic,
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def generate(
    payload: AIGenerateRequest,
    session: DbSession,
    user: CurrentUser,
    settings: AppSettings,
) -> dict[str, Any]:
    operation = _parse_operation(payload.operation)
    variables = await _build_variables(session, user, payload)
    evidence = variables.get("evidence_passages") or []
    if operation == AIOperation.EXPAND_WITH_EVIDENCE and not evidence:
        raise ValidationAppError(
            "Expand with evidence requires at least one evidence passage or project chunk"
        )
    if operation == AIOperation.DRAFT_SECTION and not evidence:
        constraints = list(variables.get("constraints") or [])
        constraints.append(
            "No evidence passages were supplied; mark unsupported claims in warnings "
            "and do not invent citations or experimental results."
        )
        variables["constraints"] = constraints
    request_payload = {
        "variables": variables,
        "section_id": str(payload.section_id) if payload.section_id else None,
        "selected_text": payload.selected_text,
        "existing_text": payload.existing_text,
        "evidence_passages": evidence,
    }
    job, created = await job_service.create_ai_job(
        session,
        user=user,
        operation=operation,
        project_id=payload.project_id,
        request_payload=request_payload,
        idempotency_key=payload.idempotency_key,
        settings=settings,
    )
    if created:
        if payload.sync or settings.app_env == "test":
            job = await job_service.execute_ai_job(session, job_id=job.id, settings=settings)
        else:
            from app.workers.tasks import run_ai_job

            async_result = run_ai_job.delay(str(job.id))
            job.celery_task_id = async_result.id
            await session.flush()
    return job_service.job_to_dict(job)


@router.get("/jobs/{job_id}", response_model=AIJobPublic)
async def get_job(job_id: UUID, session: DbSession, user: CurrentUser) -> dict[str, Any]:
    job = await job_service.get_owned_job(session, job_id=job_id, user=user)
    return job_service.job_to_dict(job)


@router.post(
    "/jobs/{job_id}/cancel",
    response_model=AIJobPublic,
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def cancel_job(job_id: UUID, session: DbSession, user: CurrentUser) -> dict[str, Any]:
    job = await job_service.get_owned_job(session, job_id=job_id, user=user)
    job = await job_service.request_cancel(session, job=job, user=user)
    return job_service.job_to_dict(job)


@router.get("/jobs/{job_id}/events")
async def job_events(
    job_id: UUID,
    session: DbSession,
    user: CurrentUser,
) -> StreamingResponse:
    """Server-Sent Events stream for job progress."""

    async def event_stream() -> Any:
        last_len = 0
        for _ in range(120):
            job = await job_service.get_owned_job(session, job_id=job_id, user=user)
            events = job.progress_events or []
            if len(events) > last_len:
                for event in events[last_len:]:
                    yield f"event: progress\ndata: {json.dumps(event)}\n\n"
                last_len = len(events)
            payload = {
                "status": job.status.value,
                "progress": job.progress,
                "error_code": job.error_code,
            }
            yield f"event: status\ndata: {json.dumps(payload)}\n\n"
            if job.status.value in {"completed", "failed", "cancelled"}:
                yield f"event: done\ndata: {json.dumps(job_service.job_to_dict(job))}\n\n"
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post(
    "/proposals/{proposal_id}/accept",
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def accept_proposal(
    proposal_id: UUID,
    payload: ProposalDecisionRequest,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    proposal = await job_service.accept_proposal(
        session,
        user=user,
        proposal_id=proposal_id,
        accepted_text=payload.accepted_text,
    )
    return {
        "id": str(proposal.id),
        "status": proposal.status.value,
        "accepted_text": proposal.accepted_text,
        "decided_at": proposal.decided_at.isoformat() if proposal.decided_at else None,
        "model_metadata": proposal.model_metadata,
    }


@router.post(
    "/proposals/{proposal_id}/reject",
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def reject_proposal(
    proposal_id: UUID,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    proposal = await job_service.reject_proposal(session, user=user, proposal_id=proposal_id)
    return {
        "id": str(proposal.id),
        "status": proposal.status.value,
        "decided_at": proposal.decided_at.isoformat() if proposal.decided_at else None,
    }


@router.get("/proposals/{proposal_id}")
async def get_proposal(
    proposal_id: UUID,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    from app.models.ai_job import AIProposal

    proposal = await session.get(AIProposal, proposal_id)
    if proposal is None:
        raise AppError("Proposal not found", code="not_found", status_code=404)
    await get_owned_project(session, project_id=proposal.project_id, user=user)
    return {
        "id": str(proposal.id),
        "job_id": str(proposal.job_id),
        "project_id": str(proposal.project_id),
        "section_id": str(proposal.section_id) if proposal.section_id else None,
        "status": proposal.status.value,
        "original_text": proposal.original_text,
        "proposed_text": proposal.proposed_text,
        "proposed_structured": proposal.proposed_structured,
        "model_metadata": proposal.model_metadata,
        "accepted_text": proposal.accepted_text,
        "created_at": (
            proposal.created_at.isoformat() if proposal.created_at else utcnow().isoformat()
        ),
    }
