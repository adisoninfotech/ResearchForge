"""Ethical research milestones — celebrate real progress, not vanity metrics."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.time import utcnow
from app.models.dataset import AnalysisRun, Dataset, Figure
from app.models.engagement import ProjectMilestone
from app.models.enums import (
    AnalysisRunStatus,
    ExportArtifactKind,
    ExportJobStatus,
    MilestoneType,
    ReferenceVerificationStatus,
    SectionStatus,
)
from app.models.export import ExportArtifact, ExportJob
from app.models.manuscript import Manuscript
from app.models.project import Project
from app.models.project_fact import ProjectFact
from app.models.reference import Reference
from app.models.similarity import SimilarityReport
from app.services.engagement.progress import compute_progress

MILESTONE_LABELS: dict[str, str] = {
    MilestoneType.RESEARCH_PLAN_APPROVED.value: "Research plan approved",
    MilestoneType.FIRST_SECTION_COMPLETED.value: "First section completed",
    MilestoneType.DATASET_ADDED.value: "Dataset added",
    MilestoneType.FIRST_ANALYSIS_COMPLETED.value: "First analysis completed",
    MilestoneType.ALL_CITATIONS_VERIFIED.value: "All citations verified",
    MilestoneType.ALL_FIGURES_RESOLVED.value: "All figures resolved",
    MilestoneType.INTEGRITY_REVIEW_COMPLETED.value: "Integrity review completed",
    MilestoneType.FIRST_FULL_DRAFT_COMPLETED.value: "First full draft completed",
    MilestoneType.SUBMISSION_PACKAGE_GENERATED.value: "Submission package generated",
}


async def _achieve(
    db: AsyncSession,
    *,
    project_id: UUID,
    milestone: MilestoneType,
    meta: dict[str, Any] | None = None,
) -> ProjectMilestone | None:
    existing = await db.scalar(
        select(ProjectMilestone).where(
            ProjectMilestone.project_id == project_id,
            ProjectMilestone.milestone_type == milestone,
        )
    )
    if existing is not None:
        return None
    row = ProjectMilestone(
        project_id=project_id,
        milestone_type=milestone,
        achieved_at=utcnow(),
        meta=meta or {},
    )
    db.add(row)
    await db.flush()
    return row


async def refresh_milestones(db: AsyncSession, *, project: Project) -> list[ProjectMilestone]:
    """Evaluate and create newly earned milestones (idempotent)."""
    newly: list[ProjectMilestone] = []

    facts = (
        await db.scalars(select(ProjectFact).where(ProjectFact.project_id == project.id))
    ).all()
    fact_keys = {f"{f.category.value}:{f.key}" for f in facts if f.value not in (None, "", [])}
    if "problem:research_problem" in fact_keys and "contribution:novel_contribution" in fact_keys:
        m = await _achieve(
            db, project_id=project.id, milestone=MilestoneType.RESEARCH_PLAN_APPROVED
        )
        if m:
            newly.append(m)

    manuscript = await db.scalar(
        select(Manuscript)
        .where(Manuscript.project_id == project.id)
        .options(selectinload(Manuscript.sections))
    )
    if manuscript and any(s.status == SectionStatus.COMPLETE for s in manuscript.sections):
        m = await _achieve(
            db, project_id=project.id, milestone=MilestoneType.FIRST_SECTION_COMPLETED
        )
        if m:
            newly.append(m)

    ds_count = await db.scalar(select(Dataset.id).where(Dataset.project_id == project.id).limit(1))
    if ds_count is not None:
        m = await _achieve(db, project_id=project.id, milestone=MilestoneType.DATASET_ADDED)
        if m:
            newly.append(m)

    analysis = await db.scalar(
        select(AnalysisRun.id)
        .where(
            AnalysisRun.project_id == project.id,
            AnalysisRun.status == AnalysisRunStatus.COMPLETED,
        )
        .limit(1)
    )
    if analysis is not None:
        m = await _achieve(
            db, project_id=project.id, milestone=MilestoneType.FIRST_ANALYSIS_COMPLETED
        )
        if m:
            newly.append(m)

    refs = (await db.scalars(select(Reference).where(Reference.project_id == project.id))).all()
    if refs and all(r.verification_status == ReferenceVerificationStatus.VERIFIED for r in refs):
        m = await _achieve(
            db, project_id=project.id, milestone=MilestoneType.ALL_CITATIONS_VERIFIED
        )
        if m:
            newly.append(m)

    figures = (await db.scalars(select(Figure).where(Figure.project_id == project.id))).all()
    if figures and all(
        f.is_conceptual or (f.storage_png and (f.caption or "").strip()) for f in figures
    ):
        m = await _achieve(db, project_id=project.id, milestone=MilestoneType.ALL_FIGURES_RESOLVED)
        if m:
            newly.append(m)

    report = await db.scalar(
        select(SimilarityReport.id).where(SimilarityReport.project_id == project.id).limit(1)
    )
    progress = await compute_progress(db, project=project)
    if report is not None and progress.similarity_findings_open == 0:
        m = await _achieve(
            db, project_id=project.id, milestone=MilestoneType.INTEGRITY_REVIEW_COMPLETED
        )
        if m:
            newly.append(m)

    if manuscript and manuscript.sections:
        non_ref = [s for s in manuscript.sections if s.section_type.value not in {"keywords"}]
        if non_ref and all(s.status == SectionStatus.COMPLETE for s in non_ref):
            m = await _achieve(
                db, project_id=project.id, milestone=MilestoneType.FIRST_FULL_DRAFT_COMPLETED
            )
            if m:
                newly.append(m)

    package = await db.scalar(
        select(ExportArtifact.id)
        .join(ExportJob, ExportJob.id == ExportArtifact.job_id)
        .where(
            ExportJob.project_id == project.id,
            ExportJob.status == ExportJobStatus.COMPLETED,
            ExportArtifact.kind == ExportArtifactKind.SUBMISSION_PACKAGE,
        )
        .limit(1)
    )
    if package is not None:
        m = await _achieve(
            db, project_id=project.id, milestone=MilestoneType.SUBMISSION_PACKAGE_GENERATED
        )
        if m:
            newly.append(m)

    await db.flush()
    return newly


async def list_milestones(db: AsyncSession, *, project_id: UUID) -> list[dict[str, Any]]:
    rows = (
        await db.scalars(
            select(ProjectMilestone)
            .where(ProjectMilestone.project_id == project_id)
            .order_by(ProjectMilestone.achieved_at.asc())
        )
    ).all()
    achieved = {r.milestone_type.value: r for r in rows}
    out: list[dict[str, Any]] = []
    for mtype in MilestoneType:
        row = achieved.get(mtype.value)
        out.append(
            {
                "type": mtype.value,
                "label": MILESTONE_LABELS[mtype.value],
                "achieved": row is not None,
                "achieved_at": row.achieved_at.isoformat() if row else None,
            }
        )
    return out
