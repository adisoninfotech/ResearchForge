"""AI job lifecycle: create, progress, cancel, idempotency."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError, ForbiddenError, NotFoundError
from app.core.time import utcnow
from app.models.ai_job import AIJob, AIProposal
from app.models.enums import AIJobStatus, AIOperation, AIProposalStatus, VersionAuthorType
from app.models.project import Project
from app.models.user import User
from app.services import versions as version_service
from app.services.ai.credits import reserve_credits, settle_credits
from app.services.ai.factory import get_llm_client
from app.services.ai.limits import enforce_ai_limits
from app.services.ai.orchestrator import run_structured_operation
from app.services.authorization import get_owned_project


def job_to_dict(job: AIJob) -> dict[str, Any]:
    return {
        "id": str(job.id),
        "project_id": str(job.project_id) if job.project_id else None,
        "operation": job.operation.value,
        "status": job.status.value,
        "progress": job.progress,
        "progress_events": job.progress_events or [],
        "result_payload": job.result_payload,
        "error_code": job.error_code,
        "error_message": job.error_message,
        "idempotency_key": job.idempotency_key,
        "prompt_template_id": job.prompt_template_id,
        "prompt_version": job.prompt_version,
        "model_name": job.model_name,
        "cancel_requested": job.cancel_requested,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "proposal_id": str(job.proposal.id) if job.proposal else None,
    }


async def _append_progress(db: AsyncSession, job: AIJob, message: str, progress: int) -> None:
    events = list(job.progress_events or [])
    events.append({"at": utcnow().isoformat(), "message": message, "progress": progress})
    job.progress_events = events
    job.progress = progress
    await db.flush()


async def create_ai_job(
    db: AsyncSession,
    *,
    user: User,
    operation: AIOperation,
    project_id: UUID | None,
    request_payload: dict[str, Any],
    idempotency_key: str | None,
    settings: Settings | None = None,
) -> tuple[AIJob, bool]:
    settings = settings or get_settings()

    if idempotency_key:
        existing = await db.scalar(
            select(AIJob)
            .where(AIJob.owner_id == user.id, AIJob.idempotency_key == idempotency_key)
            .options(selectinload(AIJob.proposal))
        )
        if existing is not None:
            return existing, False

    project: Project | None = None
    if project_id is not None:
        project = await get_owned_project(db, project_id=project_id, user=user)
        if not project.ai_enabled:
            raise ForbiddenError(
                "AI is disabled for this project",
                details={"code": "ai_disabled_project"},
            )

    await enforce_ai_limits(db, owner_id=user.id, project_id=project_id, settings=settings)
    reservation = reserve_credits(user, operation)

    job = AIJob(
        owner_id=user.id,
        project_id=project_id,
        operation=operation,
        status=AIJobStatus.QUEUED,
        progress=0,
        progress_events=[{"at": utcnow().isoformat(), "message": "queued", "progress": 0}],
        request_payload=request_payload,
        idempotency_key=idempotency_key,
        credits_reserved=reservation.amount,
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)
    return job, True


async def request_cancel(db: AsyncSession, *, job: AIJob, user: User) -> AIJob:
    if job.owner_id != user.id:
        raise NotFoundError("AI job not found")
    if job.status in {AIJobStatus.COMPLETED, AIJobStatus.FAILED, AIJobStatus.CANCELLED}:
        return job
    job.cancel_requested = True
    if job.status == AIJobStatus.QUEUED:
        job.status = AIJobStatus.CANCELLED
        job.completed_at = utcnow()
        await _append_progress(db, job, "cancelled", job.progress)
    else:
        await _append_progress(db, job, "cancel requested", job.progress)
    await db.flush()
    return job


async def get_owned_job(db: AsyncSession, *, job_id: UUID, user: User) -> AIJob:
    job = await db.scalar(
        select(AIJob).where(AIJob.id == job_id).options(selectinload(AIJob.proposal))
    )
    if job is None or job.owner_id != user.id:
        raise NotFoundError("AI job not found")
    return job


def _proposal_texts(
    operation: AIOperation,
    payload: dict[str, Any],
    request: dict[str, Any],
) -> tuple[str, str]:
    original = str(request.get("selected_text") or request.get("existing_text") or "")
    if operation == AIOperation.DRAFT_SECTION:
        proposed = str(payload.get("plain_text") or "")
        if not proposed:
            blocks = payload.get("content_blocks") or []
            proposed = " ".join(
                str(b.get("text", "")) for b in blocks if isinstance(b, dict)
            ).strip()
        return original, proposed
    if operation in {
        AIOperation.REWRITE_CLARITY,
        AIOperation.SHORTEN,
        AIOperation.EXPAND_WITH_EVIDENCE,
    }:
        return (
            str(payload.get("original_text") or original),
            str(payload.get("transformed_text") or ""),
        )
    if operation == AIOperation.GENERATE_ABSTRACT:
        return original, str(payload.get("abstract") or "")
    if operation == AIOperation.GENERATE_LIMITATIONS:
        items = payload.get("limitations") or []
        return original, "\n".join(f"- {item}" for item in items)
    return original, ""


async def execute_ai_job(
    db: AsyncSession,
    *,
    job_id: UUID,
    settings: Settings | None = None,
) -> AIJob:
    settings = settings or get_settings()
    job = await db.scalar(
        select(AIJob).where(AIJob.id == job_id).options(selectinload(AIJob.proposal))
    )
    if job is None:
        raise NotFoundError("AI job not found")
    if job.status == AIJobStatus.CANCELLED or job.cancel_requested:
        job.status = AIJobStatus.CANCELLED
        job.completed_at = utcnow()
        await db.flush()
        return job

    user = await db.get(User, job.owner_id)
    if user is None:
        raise NotFoundError("User not found")

    if job.project_id is not None:
        project = await db.get(Project, job.project_id)
        if project is None or not project.ai_enabled:
            job.status = AIJobStatus.FAILED
            job.error_code = "ai_disabled_project"
            job.error_message = "AI is disabled for this project"
            job.completed_at = utcnow()
            await db.flush()
            return job

    job.status = AIJobStatus.RUNNING
    job.started_at = utcnow()
    await _append_progress(db, job, "running", 10)

    cancel_event = asyncio.Event()
    if job.cancel_requested:
        cancel_event.set()

    client = get_llm_client(settings)
    training_eligible = bool(user.training_opt_in)
    variables = dict(job.request_payload.get("variables") or job.request_payload)

    try:
        await _append_progress(db, job, "calling model", 40)
        # Re-check cancel from DB mid-flight via event; worker may set cancel_requested
        fresh = await db.get(AIJob, job.id)
        if fresh and fresh.cancel_requested:
            cancel_event.set()

        result = await run_structured_operation(
            client=client,
            operation=job.operation,
            variables=variables,
            training_eligible=training_eligible,
            cancel_event=cancel_event,
            settings=settings,
        )
        await _append_progress(db, job, "validating output", 80)

        job.result_payload = {
            "operation": job.operation.value,
            "result": result.payload,
            "provenance": result.provenance.model_dump(),
            "repaired": result.repaired,
        }
        job.prompt_template_id = result.provenance.prompt_template_id
        job.prompt_version = result.provenance.prompt_version
        job.model_name = result.provenance.model
        job.status = AIJobStatus.COMPLETED
        job.completed_at = utcnow()
        await _append_progress(db, job, "completed", 100)
        settle_credits(reserve_credits(user, job.operation), success=True)

        # Create editable proposal for content-changing ops (never auto-write manuscript)
        if job.project_id and job.operation in {
            AIOperation.DRAFT_SECTION,
            AIOperation.REWRITE_CLARITY,
            AIOperation.SHORTEN,
            AIOperation.EXPAND_WITH_EVIDENCE,
            AIOperation.GENERATE_ABSTRACT,
            AIOperation.GENERATE_LIMITATIONS,
        }:
            original, proposed = _proposal_texts(job.operation, result.payload, job.request_payload)
            section_id = job.request_payload.get("section_id")
            proposal = AIProposal(
                job_id=job.id,
                project_id=job.project_id,
                section_id=UUID(section_id) if section_id else None,
                status=AIProposalStatus.PENDING,
                original_text=original,
                proposed_text=proposed,
                proposed_structured=result.payload,
                model_metadata={
                    "provenance": result.provenance.model_dump(),
                    "warnings": result.payload.get("warnings") or [],
                    "missing_information": result.payload.get("missing_information") or [],
                    "evidence_references": result.payload.get("evidence_references")
                    or result.payload.get("evidence_ids")
                    or [],
                },
            )
            db.add(proposal)

        claims = result.payload.get("claims") or []
        if job.project_id and claims:
            from app.services.files.evidence import store_claims_from_ai

            section_id = job.request_payload.get("section_id")
            await store_claims_from_ai(
                db,
                project_id=job.project_id,
                section_id=UUID(section_id) if section_id else None,
                claims=claims,
                model_metadata={
                    "model": result.provenance.model,
                    "prompt_template_id": result.provenance.prompt_template_id,
                    "prompt_version": result.provenance.prompt_version,
                    "operation": job.operation.value,
                },
            )
        await db.flush()
        await db.refresh(job, attribute_names=["proposal"])
        return job
    except AppError as exc:
        if exc.code == "ai_cancelled":
            job.status = AIJobStatus.CANCELLED
            job.error_code = exc.code
            job.error_message = exc.message
        else:
            job.status = AIJobStatus.FAILED
            job.error_code = exc.code
            job.error_message = exc.message
        job.completed_at = utcnow()
        await _append_progress(db, job, job.status.value, job.progress)
        settle_credits(reserve_credits(user, job.operation), success=False)
        await db.flush()
        return job
    except Exception:
        job.status = AIJobStatus.FAILED
        job.error_code = "ai_internal_error"
        job.error_message = "AI job failed"
        job.completed_at = utcnow()
        await _append_progress(db, job, "failed", job.progress)
        settle_credits(reserve_credits(user, job.operation), success=False)
        await db.flush()
        return job


async def accept_proposal(
    db: AsyncSession,
    *,
    user: User,
    proposal_id: UUID,
    accepted_text: str | None = None,
    create_version: bool = True,
) -> AIProposal:
    proposal = await db.get(AIProposal, proposal_id)
    if proposal is None:
        raise NotFoundError("Proposal not found")
    project = await get_owned_project(db, project_id=proposal.project_id, user=user)
    if proposal.status != AIProposalStatus.PENDING:
        raise AppError("Proposal is not pending", code="proposal_not_pending", status_code=409)

    final_text = accepted_text if accepted_text is not None else proposal.proposed_text
    proposal.accepted_text = final_text
    proposal.status = (
        AIProposalStatus.PARTIALLY_ACCEPTED
        if accepted_text is not None and accepted_text != proposal.proposed_text
        else AIProposalStatus.ACCEPTED
    )
    proposal.decided_at = utcnow()

    # Apply to section only after explicit accept
    if proposal.section_id is not None:
        from app.services import manuscripts as manuscript_service

        manuscript = await manuscript_service.get_manuscript_for_project(db, project=project)
        section = next((s for s in manuscript.sections if s.id == proposal.section_id), None)
        if section is None:
            raise NotFoundError("Section not found")
        structured = {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": final_text}],
                }
            ],
            "plain_text": final_text,
        }
        await manuscript_service.save_section(
            db,
            project=project,
            user=user,
            section_id=section.id,
            structured_content=structured,
            expected_revision=section.revision_number,
            create_snapshot=False,
            author_type=VersionAuthorType.AI,
            model_metadata=proposal.model_metadata,
        )
        if create_version:
            await version_service.create_snapshot(
                db,
                manuscript_id=manuscript.id,
                change_summary=f"Accepted AI proposal ({proposal.status.value})",
                created_by_type=VersionAuthorType.AI,
                created_by_user_id=user.id,
                model_metadata=proposal.model_metadata,
                is_named=False,
            )
    await db.flush()
    await db.refresh(proposal)
    return proposal


async def reject_proposal(
    db: AsyncSession,
    *,
    user: User,
    proposal_id: UUID,
) -> AIProposal:
    proposal = await db.get(AIProposal, proposal_id)
    if proposal is None:
        raise NotFoundError("Proposal not found")
    await get_owned_project(db, project_id=proposal.project_id, user=user)
    if proposal.status != AIProposalStatus.PENDING:
        raise AppError("Proposal is not pending", code="proposal_not_pending", status_code=409)
    proposal.status = AIProposalStatus.REJECTED
    proposal.decided_at = utcnow()
    await db.flush()
    await db.refresh(proposal)
    return proposal
