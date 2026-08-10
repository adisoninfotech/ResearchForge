"""Orchestrate similarity jobs, reports, resolutions, and rewrites."""

from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings, get_settings
from app.core.exceptions import NotFoundError, ValidationAppError
from app.core.time import utcnow
from app.models.enums import (
    FindingResolutionAction,
    SimilarityFindingClass,
    SimilarityJobStatus,
    SimilaritySourceKind,
)
from app.models.manuscript import Manuscript
from app.models.project import Project
from app.models.project_file import ExtractedDocument, ProjectFile
from app.models.similarity import (
    HUMAN_REVIEW_DISCLAIMER,
    SAFE_OVERLAP_SUMMARY,
    FindingResolution,
    ReportCoverage,
    SimilarityFinding,
    SimilarityJob,
    SimilarityReport,
    SimilaritySource,
)
from app.models.user import User
from app.services.similarity.classify import classify_match
from app.services.similarity.engine import SourceDoc, compare_texts
from app.services.similarity.providers import get_licensed_provider
from app.services.similarity.thresholds import (
    ALGORITHM_VERSIONS,
    COVERAGE_LIMITATIONS,
    get_profile,
)


def job_to_dict(job: SimilarityJob) -> dict[str, Any]:
    return {
        "id": str(job.id),
        "project_id": str(job.project_id),
        "status": job.status.value,
        "threshold_profile": job.threshold_profile,
        "options": job.options,
        "algorithm_versions": job.algorithm_versions,
        "error_message": job.error_message,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "report_id": str(job.report.id) if job.report else None,
    }


def report_to_dict(
    report: SimilarityReport,
    *,
    include_findings: bool = True,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    filters = filters or {}
    findings = list(report.__dict__.get("findings") or [])
    if filters.get("exclude_bibliography"):
        findings = [
            f
            for f in findings
            if f.classification != SimilarityFindingClass.BIBLIOGRAPHY_OR_TITLE_MATCH
        ]
    if filters.get("exclude_quotations"):
        findings = [
            f for f in findings if f.classification != SimilarityFindingClass.PROPER_QUOTATION
        ]
    if filters.get("exclude_common"):
        findings = [
            f
            for f in findings
            if f.classification != SimilarityFindingClass.COMMON_TECHNICAL_PHRASE
        ]
    if filters.get("classification"):
        findings = [f for f in findings if f.classification.value == filters["classification"]]

    payload: dict[str, Any] = {
        "id": str(report.id),
        "job_id": str(report.job_id),
        "project_id": str(report.project_id),
        "summary_text": report.summary_text,
        "risk_level": report.risk_level,
        "section_summaries": report.section_summaries,
        "method_explanations": report.method_explanations,
        "footer": report.footer,
        "finding_counts": report.finding_counts,
        "content_sha256": report.content_sha256,
        "coverage": None,
        "sources": [
            {
                "id": str(s.id),
                "kind": s.kind.value,
                "label": s.label,
                "checked": s.checked,
                "unavailable_reason": s.unavailable_reason,
                "metadata": s.metadata_json,
            }
            for s in list(report.__dict__.get("sources") or [])
        ],
    }
    cov = report.__dict__.get("coverage")
    if cov is not None:
        payload["coverage"] = {
            "sources_checked": cov.sources_checked,
            "sources_not_checked": cov.sources_not_checked,
            "limitations": cov.limitations,
            "open_corpus_enabled": cov.open_corpus_enabled,
            "licensed_provider_status": cov.licensed_provider_status,
        }
    if include_findings:
        payload["findings"] = [finding_to_dict(f) for f in findings]
    return payload


def finding_to_dict(finding: SimilarityFinding) -> dict[str, Any]:
    res = finding.__dict__.get("resolution")
    return {
        "id": str(finding.id),
        "section_id": str(finding.section_id) if finding.section_id else None,
        "classification": finding.classification.value,
        "manuscript_text": finding.manuscript_text,
        "manuscript_start": finding.manuscript_start,
        "manuscript_end": finding.manuscript_end,
        "source_text": finding.source_text,
        "source_start": finding.source_start,
        "source_end": finding.source_end,
        "source_id": str(finding.source_id) if finding.source_id else None,
        "methods": finding.methods,
        "scores": finding.scores,
        "citation_present": finding.citation_present,
        "citation_keys": finding.citation_keys,
        "recommended_action": finding.recommended_action,
        "explanation": finding.explanation,
        "resolution": (
            {
                "action": res.action.value,
                "note": res.note,
                "rewrite_original": res.rewrite_original,
                "rewrite_proposed": res.rewrite_proposed,
                "rewrite_accepted": res.rewrite_accepted,
                "rewrite_diff": res.rewrite_diff,
            }
            if res is not None
            else None
        ),
    }


async def create_and_run_job(
    db: AsyncSession,
    *,
    project: Project,
    user: User,
    options: dict[str, Any] | None = None,
    settings: Settings | None = None,
) -> SimilarityJob:
    settings = settings or get_settings()
    opts = dict(options or {})
    profile_name = str(opts.get("threshold_profile") or "default")
    job = SimilarityJob(
        project_id=project.id,
        owner_id=user.id,
        status=SimilarityJobStatus.RUNNING,
        options=opts,
        threshold_profile=profile_name,
        algorithm_versions=ALGORITHM_VERSIONS,
        started_at=utcnow(),
    )
    db.add(job)
    await db.flush()
    try:
        await _execute_job(db, job=job, project=project, user=user, settings=settings)
        job.status = SimilarityJobStatus.COMPLETED
        job.completed_at = utcnow()
        from app.models.enums import AnalyticsEventType, NotificationKind
        from app.services.engagement.analytics import track as track_analytics
        from app.services.engagement.notifications import create_notification

        await track_analytics(
            db,
            event_type=AnalyticsEventType.SIMILARITY_REPORT_COMPLETED,
            user_id=user.id,
            project_id=project.id,
            properties={"profile": job.threshold_profile},
        )
        await create_notification(
            db,
            user_id=user.id,
            project_id=project.id,
            kind=NotificationKind.SIMILARITY_REPORT_COMPLETED,
            title="Similarity report completed",
            body=(
                "An advisory overlap review is ready. It does not guarantee originality; "
                "human review is required."
            ),
            action_url=f"/projects/{project.id}",
        )
    except ValidationAppError:
        job.status = SimilarityJobStatus.FAILED
        job.error_message = "Similarity check failed"
        job.completed_at = utcnow()
        await db.flush()
        raise
    except Exception:
        job.status = SimilarityJobStatus.FAILED
        job.error_message = "Similarity check failed"
        job.completed_at = utcnow()
        await db.flush()
        raise ValidationAppError("Similarity check failed") from None
    await db.flush()
    loaded = await get_job(db, project_id=project.id, job_id=job.id)
    assert loaded is not None
    return loaded


async def _execute_job(
    db: AsyncSession,
    *,
    job: SimilarityJob,
    project: Project,
    user: User,
    settings: Settings,
) -> None:
    profile = get_profile(job.threshold_profile)
    manuscript = await db.scalar(
        select(Manuscript)
        .where(Manuscript.project_id == project.id)
        .options(selectinload(Manuscript.sections))
    )
    if manuscript is None:
        raise ValidationAppError("Manuscript not found")

    sources: list[SourceDoc] = []
    unavailable_files: list[ProjectFile] = []

    # Uploaded reference / project documents with extracted text
    file_rows = list(
        (
            await db.scalars(
                select(ProjectFile).where(
                    ProjectFile.project_id == project.id,
                    ProjectFile.exclude_from_ai.is_(False),
                )
            )
        ).all()
    )
    for pf in file_rows:
        extracted = await db.scalar(
            select(ExtractedDocument).where(ExtractedDocument.project_file_id == pf.id)
        )
        if extracted is None or not extracted.plain_text.strip():
            unavailable_files.append(pf)
            continue
        kind = (
            SimilaritySourceKind.UPLOADED_REFERENCE
            if pf.kind.value in {"pdf", "docx", "bibtex", "ris", "txt", "markdown"}
            else SimilaritySourceKind.PROJECT_DOCUMENT
        )
        sources.append(
            SourceDoc(
                key=f"file:{pf.id}",
                label=pf.original_filename,
                text=extracted.plain_text,
                kind=kind.value,
                metadata={"file_id": str(pf.id)},
                project_file_id=str(pf.id),
            )
        )

    # Internal duplication: other sections
    sections = sorted(manuscript.sections, key=lambda s: s.position)
    for section in sections:
        for other in sections:
            if other.id == section.id:
                continue
            if not (other.plain_text or "").strip():
                continue
            sources.append(
                SourceDoc(
                    key=f"section:{other.id}",
                    label=f"Internal section: {other.title}",
                    text=other.plain_text,
                    kind="internal_section",
                    metadata={"section_id": str(other.id)},
                    section_id=str(other.id),
                )
            )

    # Authorized prior manuscripts (same owner, opted-in via options)
    prior_ids = list(job.options.get("authorized_prior_project_ids") or [])
    for prior_id in prior_ids:
        try:
            pid = UUID(str(prior_id))
        except ValueError:
            continue
        prior = await db.scalar(
            select(Project).where(Project.id == pid, Project.owner_id == user.id)
        )
        if prior is None:
            continue
        prior_ms = await db.scalar(
            select(Manuscript)
            .where(Manuscript.project_id == prior.id)
            .options(selectinload(Manuscript.sections))
        )
        if prior_ms is None:
            continue
        text = "\n\n".join(s.plain_text or "" for s in prior_ms.sections)
        sources.append(
            SourceDoc(
                key=f"prior:{prior.id}",
                label=f"Authorized prior manuscript: {prior.title}",
                text=text,
                kind="authorized_prior_manuscript",
                metadata={"project_id": str(prior.id)},
            )
        )

    # Optional open-license corpus (admin-provided snippets in settings/options)
    open_corpus = list(
        job.options.get("open_license_corpus")
        or getattr(settings, "similarity_open_corpus", None)
        or []
    )
    for idx, item in enumerate(open_corpus):
        if isinstance(item, dict) and item.get("text"):
            sources.append(
                SourceDoc(
                    key=f"corpus:{idx}",
                    label=str(item.get("label") or f"Open corpus {idx + 1}"),
                    text=str(item["text"]),
                    kind="open_license_corpus",
                    metadata={"license": item.get("license")},
                )
            )

    licensed = get_licensed_provider(settings)
    licensed_result = await licensed.check(
        manuscript_text="\n\n".join(s.plain_text or "" for s in sections)
    )

    all_findings: list[dict[str, Any]] = []
    section_summaries: list[dict[str, Any]] = []

    for section in sections:
        text = section.plain_text or ""
        if not text.strip():
            section_summaries.append(
                {
                    "section_id": str(section.id),
                    "title": section.title,
                    "finding_count": 0,
                    "risk_level": "none",
                }
            )
            continue
        # Compare against non-internal sources + internals from other sections
        section_sources = [
            s
            for s in sources
            if not (s.kind == "internal_section" and s.section_id == str(section.id))
        ]
        raw = await compare_texts(
            manuscript_text=text,
            sources=section_sources,
            profile=profile,
            section_title=section.title,
        )
        classified: list[dict[str, Any]] = []
        for match in raw:
            cls, action, explanation = classify_match(match, profile)
            classified.append(
                {
                    "section_id": section.id,
                    "classification": cls,
                    "match": match,
                    "recommended_action": action,
                    "explanation": explanation,
                }
            )
        all_findings.extend(classified)
        section_summaries.append(
            {
                "section_id": str(section.id),
                "title": section.title,
                "finding_count": len(classified),
                "risk_level": _section_risk(classified),
            }
        )

    risk = _overall_risk(all_findings)
    summary = (
        SAFE_OVERLAP_SUMMARY
        if risk in {"none", "low"} and not _has_actionable(all_findings)
        else (
            "Potential textual overlap or citation-risk items were identified "
            "within the sources checked. Review each finding; human judgment is required."
        )
    )

    report = SimilarityReport(
        job_id=job.id,
        project_id=project.id,
        summary_text=summary,
        risk_level=risk,
        section_summaries=section_summaries,
        method_explanations={
            "exact_phrase": "Long shared word sequences",
            "word_ngram": "Overlapping word n-grams (Jaccard)",
            "char_ngram": "Overlapping character n-grams (Jaccard)",
            "minhash": "MinHash candidate discovery",
            "embedding": "Embedding cosine similarity",
            "reranker": "Reranker confirmation (identity or configured)",
            "note": (
                "Scores are method-specific; there is no single unexplained overall percentage."
            ),
        },
        footer={
            "disclaimer": HUMAN_REVIEW_DISCLAIMER,
            "safe_summary_language": SAFE_OVERLAP_SUMMARY,
            "date": utcnow().isoformat(),
            "algorithm_versions": ALGORITHM_VERSIONS,
            "threshold_profile": profile.name,
            "threshold_values": profile.__dict__,
            "sources_checked_summary": (
                "Coverage details are listed below; this check does not cover the open web "
                "or proprietary plagiarism databases unless a licensed provider is configured."
            ),
            "sources_not_checked_summary": licensed_result.message,
            "coverage_limitations": list(COVERAGE_LIMITATIONS),
        },
        finding_counts={},
        content_sha256="",
    )
    db.add(report)
    await db.flush()

    # Persist sources
    key_to_source_id: dict[str, UUID] = {}
    checked_labels: list[dict[str, Any]] = []
    not_checked: list[dict[str, Any]] = list(licensed_result.sources_not_checked)

    seen_keys: set[str] = set()
    for src in sources:
        if src.key in seen_keys:
            continue
        seen_keys.add(src.key)
        try:
            kind = SimilaritySourceKind(src.kind)
        except ValueError:
            kind = SimilaritySourceKind.PROJECT_DOCUMENT
        row = SimilaritySource(
            report_id=report.id,
            kind=kind,
            label=src.label,
            project_file_id=UUID(src.project_file_id) if src.project_file_id else None,
            section_id=UUID(src.section_id) if src.section_id else None,
            metadata_json=src.metadata,
            checked=True,
        )
        db.add(row)
        await db.flush()
        key_to_source_id[src.key] = row.id
        checked_labels.append({"label": src.label, "kind": kind.value})

    for pf in unavailable_files:
        db.add(
            SimilaritySource(
                report_id=report.id,
                kind=SimilaritySourceKind.PROJECT_DOCUMENT,
                label=pf.original_filename,
                project_file_id=pf.id,
                checked=False,
                unavailable_reason="No extracted text available",
                metadata_json={"file_id": str(pf.id)},
            )
        )
        not_checked.append(
            {
                "label": pf.original_filename,
                "reason": "No extracted text available",
            }
        )

    for item in licensed_result.sources_not_checked:
        db.add(
            SimilaritySource(
                report_id=report.id,
                kind=SimilaritySourceKind.LICENSED_PROVIDER,
                label=str(item.get("label") or "Licensed provider"),
                checked=False,
                unavailable_reason=str(item.get("reason") or licensed_result.message),
                metadata_json=item,
            )
        )

    counts: dict[str, int] = {}
    for item in all_findings:
        match = item["match"]
        cls = item["classification"]
        counts[cls.value] = counts.get(cls.value, 0) + 1
        finding = SimilarityFinding(
            report_id=report.id,
            project_id=project.id,
            section_id=item["section_id"],
            classification=cls,
            manuscript_text=match.manuscript_text,
            manuscript_start=match.manuscript_start,
            manuscript_end=match.manuscript_end,
            source_text=match.source_text,
            source_start=match.source_start,
            source_end=match.source_end,
            source_id=key_to_source_id.get(match.source_key),
            methods=match.methods,
            scores=match.scores,
            citation_present=match.citation_present,
            citation_keys=match.citation_keys,
            recommended_action=item["recommended_action"],
            explanation=item["explanation"],
        )
        db.add(finding)
        await db.flush()
        db.add(
            FindingResolution(
                finding_id=finding.id,
                action=FindingResolutionAction.UNRESOLVED,
            )
        )

    report.finding_counts = counts
    coverage = ReportCoverage(
        report_id=report.id,
        sources_checked=checked_labels,
        sources_not_checked=not_checked,
        limitations=COVERAGE_LIMITATIONS,
        open_corpus_enabled=bool(open_corpus),
        licensed_provider_status=licensed_result.status,
    )
    db.add(coverage)

    fingerprint = {
        "project_id": str(project.id),
        "profile": profile.name,
        "sections": [
            {"id": str(s.id), "text": s.plain_text or "", "rev": s.revision_number}
            for s in sections
        ],
        "source_keys": sorted(seen_keys),
        "counts": counts,
    }
    report.content_sha256 = hashlib.sha256(
        json.dumps(fingerprint, sort_keys=True).encode()
    ).hexdigest()
    report.footer["sources_checked"] = checked_labels
    report.footer["sources_not_checked"] = not_checked
    await db.flush()


def _has_actionable(items: list[dict[str, Any]]) -> bool:
    actionable = {
        SimilarityFindingClass.EXACT_TEXTUAL_OVERLAP,
        SimilarityFindingClass.NEAR_TEXTUAL_OVERLAP,
        SimilarityFindingClass.CITATION_POTENTIALLY_REQUIRED,
        SimilarityFindingClass.EXCESSIVE_SIMILARITY_DESPITE_CITATION,
        SimilarityFindingClass.SELF_OVERLAP,
        SimilarityFindingClass.INTERNAL_DUPLICATION,
        SimilarityFindingClass.NEEDS_HUMAN_REVIEW,
    }
    return any(i["classification"] in actionable for i in items)


def _section_risk(items: list[dict[str, Any]]) -> str:
    if not items:
        return "none"
    if _has_actionable(items):
        classes = {i["classification"] for i in items}
        if SimilarityFindingClass.EXACT_TEXTUAL_OVERLAP in classes:
            return "high"
        if SimilarityFindingClass.EXCESSIVE_SIMILARITY_DESPITE_CITATION in classes:
            return "high"
        return "medium"
    return "low"


def _overall_risk(items: list[dict[str, Any]]) -> str:
    levels = [_section_risk([i]) for i in items] or ["none"]
    if "high" in levels:
        return "high"
    if "medium" in levels:
        return "medium"
    if "low" in levels:
        return "low"
    return "none"


async def get_job(db: AsyncSession, *, project_id: UUID, job_id: UUID) -> SimilarityJob | None:
    row = await db.scalar(
        select(SimilarityJob)
        .where(SimilarityJob.id == job_id, SimilarityJob.project_id == project_id)
        .options(selectinload(SimilarityJob.report))
    )
    return row if isinstance(row, SimilarityJob) else None


async def get_report(
    db: AsyncSession, *, project_id: UUID, report_id: UUID
) -> SimilarityReport | None:
    row = await db.scalar(
        select(SimilarityReport)
        .where(SimilarityReport.id == report_id, SimilarityReport.project_id == project_id)
        .options(
            selectinload(SimilarityReport.findings).selectinload(SimilarityFinding.resolution),
            selectinload(SimilarityReport.sources),
            selectinload(SimilarityReport.coverage),
        )
    )
    return row if isinstance(row, SimilarityReport) else None


async def resolve_finding(
    db: AsyncSession,
    *,
    project_id: UUID,
    finding_id: UUID,
    user: User,
    action: FindingResolutionAction,
    note: str | None = None,
) -> SimilarityFinding:
    finding = await db.scalar(
        select(SimilarityFinding)
        .where(SimilarityFinding.id == finding_id, SimilarityFinding.project_id == project_id)
        .options(selectinload(SimilarityFinding.resolution))
    )
    if finding is None:
        raise NotFoundError("Finding not found")
    res = finding.resolution
    if res is None:
        res = FindingResolution(finding_id=finding.id)
        db.add(res)
    res.action = action
    res.note = note
    res.resolved_by_id = user.id
    res.resolved_at = utcnow()
    await db.flush()
    await db.refresh(finding, attribute_names=["resolution"])
    return finding


def make_diff(original: str, proposed: str) -> list[dict[str, str]]:
    """Simple line-oriented diff for UI."""
    import difflib

    rows: list[dict[str, str]] = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(
        a=original.split(), b=proposed.split()
    ).get_opcodes():
        rows.append(
            {
                "op": tag,
                "original": " ".join(original.split()[i1:i2]),
                "proposed": " ".join(proposed.split()[j1:j2]),
            }
        )
    return rows


async def propose_rewrite(
    db: AsyncSession,
    *,
    project_id: UUID,
    finding_id: UUID,
    user: User,
) -> SimilarityFinding:
    """Meaning-preserving rewrite proposal — not evasion-oriented."""
    finding = await db.scalar(
        select(SimilarityFinding)
        .where(SimilarityFinding.id == finding_id, SimilarityFinding.project_id == project_id)
        .options(selectinload(SimilarityFinding.resolution))
    )
    if finding is None:
        raise NotFoundError("Finding not found")

    original = finding.manuscript_text
    # Deterministic local rewrite for tests / offline: clarify + keep meaning
    proposed = _local_meaning_preserving_rewrite(original, finding)
    res = finding.resolution
    if res is None:
        res = FindingResolution(finding_id=finding.id)
        db.add(res)
        await db.flush()
    res.rewrite_original = original
    res.rewrite_proposed = proposed
    res.rewrite_diff = make_diff(original, proposed)
    res.rewrite_accepted = False
    res.action = FindingResolutionAction.NEEDS_REVIEW
    res.note = (
        "Proposed rewrite aims to express the author's supported understanding clearly "
        "and cite the source where needed — not to evade overlap detection."
    )
    res.resolved_by_id = user.id
    await db.flush()
    await db.refresh(finding, attribute_names=["resolution"])
    return finding


def _local_meaning_preserving_rewrite(original: str, finding: SimilarityFinding) -> str:
    text = " ".join(original.split())
    cite = ""
    if finding.source_text and not finding.citation_present:
        cite = " (see cited source)"
    elif finding.citation_keys:
        cite = f" {finding.citation_keys[0]}"
    return (
        f"In our own framing, {text[0].lower() + text[1:] if text else text}"
        f"{cite}. "
        "This wording is intended to reflect our understanding of the supporting material."
    )


async def accept_rewrite(
    db: AsyncSession,
    *,
    project: Project,
    user: User,
    finding_id: UUID,
    accepted_text: str | None = None,
) -> dict[str, Any]:
    from app.models.enums import VersionAuthorType
    from app.services import manuscripts as manuscript_service

    finding = await db.scalar(
        select(SimilarityFinding)
        .where(SimilarityFinding.id == finding_id, SimilarityFinding.project_id == project.id)
        .options(selectinload(SimilarityFinding.resolution))
    )
    if finding is None:
        raise NotFoundError("Finding not found")
    res = finding.resolution
    if res is None or not res.rewrite_proposed:
        raise ValidationAppError("No rewrite proposal available")
    final = accepted_text if accepted_text is not None else res.rewrite_proposed
    res.rewrite_accepted = True
    res.action = FindingResolutionAction.REWRITTEN
    res.resolved_by_id = user.id
    res.resolved_at = utcnow()

    if finding.section_id is not None:
        manuscript = await manuscript_service.get_manuscript_for_project(db, project=project)
        section = next((s for s in manuscript.sections if s.id == finding.section_id), None)
        if section is not None:
            plain = section.plain_text or ""
            start, end = finding.manuscript_start, finding.manuscript_end
            if 0 <= start < end <= len(plain):
                new_plain = plain[:start] + final + plain[end:]
            else:
                new_plain = plain.replace(finding.manuscript_text, final, 1)
            structured = {
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": new_plain}],
                    }
                ],
                "plain_text": new_plain,
            }
            await manuscript_service.save_section(
                db,
                project=project,
                user=user,
                section_id=section.id,
                structured_content=structured,
                expected_revision=section.revision_number,
                create_snapshot=False,
                author_type=VersionAuthorType.USER,
            )
    await db.flush()
    return {"finding_id": str(finding.id), "accepted_text": final, "status": "rewritten"}


def export_report_text(report: SimilarityReport) -> str:
    lines = [
        "ResearchForge Similarity & Citation-Risk Report",
        f"Date: {report.footer.get('date')}",
        f"Risk level: {report.risk_level}",
        "",
        report.summary_text,
        "",
        "Coverage limitations:",
    ]
    cov = report.__dict__.get("coverage")
    if cov:
        for item in cov.limitations:
            lines.append(f"- {item}")
        lines.append("")
        lines.append("Sources checked:")
        for s in cov.sources_checked:
            lines.append(f"- {s.get('label')} ({s.get('kind')})")
        lines.append("")
        lines.append("Sources not checked:")
        for s in cov.sources_not_checked:
            lines.append(f"- {s.get('label')}: {s.get('reason')}")
    lines.extend(
        [
            "",
            f"Threshold profile: {report.footer.get('threshold_profile')}",
            f"Algorithm versions: {report.footer.get('algorithm_versions')}",
            "",
            report.footer.get("disclaimer") or HUMAN_REVIEW_DISCLAIMER,
        ]
    )
    return "\n".join(lines) + "\n"
