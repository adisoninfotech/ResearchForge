"""Weighted completion — not word-count based."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.time import utcnow
from app.models.dataset import AnalysisRun, Dataset, Figure, Table
from app.models.engagement import ProgressEvent
from app.models.enums import (
    AnalysisRunStatus,
    FindingResolutionAction,
    ReferenceVerificationStatus,
    SectionStatus,
    SectionType,
)
from app.models.evidence import ClaimProvenance, EvidenceLink
from app.models.manuscript import Manuscript
from app.models.project import Project
from app.models.project_fact import ProjectFact
from app.models.reference import Reference
from app.models.similarity import SimilarityFinding, SimilarityReport
from app.services.facts import fact_map

# Weights sum to 100
COMPONENT_WEIGHTS: dict[str, int] = {
    "problem_defined": 8,
    "contribution_defined": 8,
    "evidence_attached": 10,
    "methodology_complete": 10,
    "dataset_provenance_present": 8,
    "analysis_complete": 8,
    "results_supported": 10,
    "limitations_included": 8,
    "citations_verified": 8,
    "figures_resolved": 6,
    "tables_resolved": 6,
    "integrity_warnings_addressed": 5,
    "required_journal_statements_complete": 5,
}

COMPONENT_LABELS: dict[str, str] = {
    "problem_defined": "Problem defined",
    "contribution_defined": "Contribution defined",
    "evidence_attached": "Evidence attached",
    "methodology_complete": "Methodology complete",
    "dataset_provenance_present": "Dataset provenance present",
    "analysis_complete": "Analysis complete",
    "results_supported": "Results supported",
    "limitations_included": "Limitations included",
    "citations_verified": "Citations verified",
    "figures_resolved": "Figures resolved",
    "tables_resolved": "Tables resolved",
    "integrity_warnings_addressed": "Integrity warnings addressed",
    "required_journal_statements_complete": "Required journal statements complete",
}


@dataclass
class ProgressSnapshot:
    percent: int
    components: dict[str, dict[str, Any]] = field(default_factory=dict)
    sections_completed: int = 0
    sections_total: int = 0
    missing_evidence: int = 0
    unsupported_claims: int = 0
    unverified_references: int = 0
    dataset_status: str = "none"
    figures_needed: int = 0
    tables_needed: int = 0
    similarity_findings_open: int = 0
    next_action: str = "Define the research problem"
    next_action_code: str = "problem_defined"

    def to_dict(self) -> dict[str, Any]:
        return {
            "percent": self.percent,
            "components": self.components,
            "sections_completed": self.sections_completed,
            "sections_total": self.sections_total,
            "missing_evidence": self.missing_evidence,
            "unsupported_claims": self.unsupported_claims,
            "unverified_references": self.unverified_references,
            "dataset_status": self.dataset_status,
            "figures_needed": self.figures_needed,
            "tables_needed": self.tables_needed,
            "similarity_findings_open": self.similarity_findings_open,
            "next_action": self.next_action,
            "next_action_code": self.next_action_code,
            "weight_basis": "weighted_research_components",
            "not_word_count_based": True,
        }


def _fact_truthy(facts: dict[str, Any], *keys: str) -> bool:
    for key in keys:
        val = facts.get(key)
        if val is None:
            continue
        if isinstance(val, str) and val.strip():
            return True
        if isinstance(val, (int, float, bool)) and val != 0 and val is not False:
            return True
        if isinstance(val, (list, dict)) and val:
            return True
    return False


def _score(ok: bool, weight: int) -> dict[str, Any]:
    return {
        "complete": ok,
        "weight": weight,
        "earned": weight if ok else 0,
        "label": "",
    }


async def compute_progress(db: AsyncSession, *, project: Project) -> ProgressSnapshot:
    facts_rows = await db.scalars(select(ProjectFact).where(ProjectFact.project_id == project.id))
    facts = fact_map(list(facts_rows.all()))

    manuscript = await db.scalar(
        select(Manuscript)
        .where(Manuscript.project_id == project.id)
        .options(selectinload(Manuscript.sections))
    )
    sections = list(manuscript.sections) if manuscript else []
    sections_completed = sum(1 for s in sections if s.status == SectionStatus.COMPLETE)
    sections_total = len(sections)

    def section_complete(stype: SectionType) -> bool:
        return any(s.section_type == stype and s.status == SectionStatus.COMPLETE for s in sections)

    evidence_count = await db.scalar(
        select(func.count()).select_from(EvidenceLink).where(EvidenceLink.project_id == project.id)
    )
    claims = (
        await db.scalars(select(ClaimProvenance).where(ClaimProvenance.project_id == project.id))
    ).all()
    unsupported = sum(
        1
        for c in claims
        if c.support_status.value in {"unsupported", "citation_missing", "conflicting_evidence"}
    )
    missing_evidence = max(0, unsupported)

    refs = (await db.scalars(select(Reference).where(Reference.project_id == project.id))).all()
    unverified = sum(
        1
        for r in refs
        if r.verification_status
        in {ReferenceVerificationStatus.UNVERIFIED, ReferenceVerificationStatus.NEEDS_CORRECTION}
    )
    citations_ok = bool(refs) and unverified == 0

    datasets = (await db.scalars(select(Dataset).where(Dataset.project_id == project.id))).all()
    if not datasets:
        dataset_status = "none"
    elif any(d.provenance_type.value in {"synthetic", "simulated_experiment"} for d in datasets):
        dataset_status = "synthetic_or_simulated"
    else:
        dataset_status = "present"
    dataset_ok = bool(datasets) and (
        _fact_truthy(facts, "dataset:dataset_source", "dataset:dataset_provenance")
        or all(bool(d.provenance_label) for d in datasets)
    )

    analyses = (
        await db.scalars(
            select(AnalysisRun).where(
                AnalysisRun.project_id == project.id,
                AnalysisRun.status == AnalysisRunStatus.COMPLETED,
            )
        )
    ).all()
    analysis_ok = bool(analyses)

    figures = (await db.scalars(select(Figure).where(Figure.project_id == project.id))).all()
    tables = (await db.scalars(select(Table).where(Table.project_id == project.id))).all()
    figures_needed = sum(
        1 for f in figures if not f.is_conceptual and not f.storage_png and not f.caption
    )
    # "needed" also when methodology/results complete but no figures yet
    if section_complete(SectionType.RESULTS) and not figures:
        figures_needed = max(figures_needed, 1)
    tables_needed = 1 if section_complete(SectionType.RESULTS) and not tables else 0
    figures_ok = (not figures and not section_complete(SectionType.RESULTS)) or (
        bool(figures)
        and all(f.is_conceptual or f.storage_png for f in figures)
        and all((f.caption or "").strip() for f in figures)
    )
    tables_ok = (not tables and not section_complete(SectionType.RESULTS)) or (
        bool(tables) and all((t.caption or "").strip() for t in tables)
    )

    report = await db.scalar(
        select(SimilarityReport)
        .where(SimilarityReport.project_id == project.id)
        .order_by(SimilarityReport.created_at.desc())
        .limit(1)
    )
    open_findings = 0
    if report is not None:
        findings = (
            await db.scalars(
                select(SimilarityFinding)
                .where(SimilarityFinding.report_id == report.id)
                .options(selectinload(SimilarityFinding.resolution))
            )
        ).all()
        for finding in findings:
            action = (
                finding.resolution.action
                if finding.resolution is not None
                else FindingResolutionAction.UNRESOLVED
            )
            if action in {
                FindingResolutionAction.UNRESOLVED,
                FindingResolutionAction.NEEDS_REVIEW,
            }:
                open_findings += 1
    integrity_ok = report is None or open_findings == 0

    # Require core journal statements (ethics/funding + COI + data availability)
    statements_ok = (
        (_fact_truthy(facts, "ethics:ethics_statement") or _fact_truthy(facts, "ethics:funding"))
        and _fact_truthy(facts, "ethics:data_availability")
        and _fact_truthy(facts, "ethics:conflict_of_interest")
    )

    components_raw: dict[str, bool] = {
        "problem_defined": _fact_truthy(facts, "problem:research_problem")
        or bool((project.research_problem or "").strip()),
        "contribution_defined": _fact_truthy(facts, "contribution:novel_contribution")
        or bool((project.proposed_contribution or "").strip()),
        "evidence_attached": int(evidence_count or 0) > 0,
        "methodology_complete": section_complete(SectionType.METHODOLOGY)
        or _fact_truthy(facts, "experiment:experiment_configuration"),
        "dataset_provenance_present": bool(dataset_ok),
        "analysis_complete": analysis_ok or _fact_truthy(facts, "evaluation:evaluation_metrics"),
        "results_supported": section_complete(SectionType.RESULTS) and unsupported == 0,
        "limitations_included": section_complete(SectionType.LIMITATIONS)
        or _fact_truthy(facts, "evaluation:limitations"),
        "citations_verified": citations_ok,
        "figures_resolved": figures_ok,
        "tables_resolved": tables_ok,
        "integrity_warnings_addressed": integrity_ok,
        "required_journal_statements_complete": statements_ok,
    }

    components: dict[str, dict[str, Any]] = {}
    earned = 0
    for key, weight in COMPONENT_WEIGHTS.items():
        ok = components_raw[key]
        entry = _score(ok, weight)
        entry["label"] = COMPONENT_LABELS[key]
        components[key] = entry
        earned += entry["earned"]

    percent = min(100, max(0, earned))

    # Next recommended incomplete component (stable order)
    next_action = "Review project readiness"
    next_code = "ready"
    for key in COMPONENT_WEIGHTS:
        if not components[key]["complete"]:
            next_action = f"Next: {COMPONENT_LABELS[key]}"
            next_code = key
            break

    return ProgressSnapshot(
        percent=percent,
        components=components,
        sections_completed=sections_completed,
        sections_total=sections_total,
        missing_evidence=missing_evidence,
        unsupported_claims=unsupported,
        unverified_references=unverified,
        dataset_status=dataset_status,
        figures_needed=figures_needed,
        tables_needed=tables_needed,
        similarity_findings_open=open_findings,
        next_action=next_action,
        next_action_code=next_code,
    )


async def refresh_project_completion(
    db: AsyncSession,
    *,
    project: Project,
    previous_components: dict[str, Any] | None = None,
) -> ProgressSnapshot:
    """Recompute weighted completion, persist percent, and record score deltas."""
    snap = await compute_progress(db, project=project)
    previous = project.completion_percent
    project.completion_percent = snap.percent
    project.last_activity_at = utcnow()

    deltas: list[dict[str, Any]] = []
    if previous_components:
        for key, entry in snap.components.items():
            prev = previous_components.get(key) or {}
            if bool(prev.get("complete")) != bool(entry["complete"]):
                deltas.append(
                    {
                        "component": key,
                        "label": entry["label"],
                        "from_complete": bool(prev.get("complete")),
                        "to_complete": bool(entry["complete"]),
                        "weight": entry["weight"],
                        "reason": (
                            f"{entry['label']} marked complete (+{entry['weight']}%)"
                            if entry["complete"]
                            else f"{entry['label']} no longer complete (-{entry['weight']}%)"
                        ),
                    }
                )
    elif previous != snap.percent:
        deltas.append(
            {
                "component": "overall",
                "label": "Overall completion",
                "from_complete": None,
                "to_complete": None,
                "weight": snap.percent - previous,
                "reason": f"Completion changed from {previous}% to {snap.percent}%",
            }
        )

    if previous != snap.percent or deltas:
        db.add(
            ProgressEvent(
                project_id=project.id,
                previous_percent=previous,
                new_percent=snap.percent,
                component_scores=snap.components,
                deltas=deltas
                or [
                    {
                        "component": "overall",
                        "label": "Overall completion",
                        "reason": f"Completion is {snap.percent}%",
                        "weight": 0,
                    }
                ],
                created_at=utcnow(),
            )
        )
    await db.flush()
    return snap


async def latest_progress_explanation(
    db: AsyncSession, *, project_id: UUID
) -> dict[str, Any] | None:
    event = await db.scalar(
        select(ProgressEvent)
        .where(ProgressEvent.project_id == project_id)
        .order_by(ProgressEvent.created_at.desc())
        .limit(1)
    )
    if event is None:
        return None
    return {
        "previous_percent": event.previous_percent,
        "new_percent": event.new_percent,
        "deltas": event.deltas,
        "created_at": event.created_at.isoformat(),
        "summary": "; ".join(
            str(d.get("reason") or "") for d in (event.deltas or []) if d.get("reason")
        ),
    }
