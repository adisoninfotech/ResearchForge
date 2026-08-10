"""Export job orchestration — validate, render from canonical, package, authorize downloads."""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.dataset import AnalysisRun, Dataset, Figure, ReproducibilityManifest, Table
from app.models.enums import (
    ExportArtifactKind,
    ExportJobStatus,
    ExportTemplateId,
    FindingResolutionAction,
)
from app.models.export import (
    TEMPLATE_COMPATIBILITY_WARNING,
    ExportArtifact,
    ExportDownload,
    ExportJob,
)
from app.models.manuscript import Manuscript
from app.models.project import Project
from app.models.project_file import ProjectFile
from app.models.reference import Reference
from app.models.similarity import SimilarityFinding, SimilarityReport
from app.models.user import User
from app.services.export.canonical import CanonicalManuscript, build_canonical
from app.services.export.docx_render import render_docx
from app.services.export.html_render import render_html
from app.services.export.latex_render import render_bibtex, render_latex
from app.services.export.package import (
    build_dataset_manifest_zip,
    build_figures_zip,
    build_overleaf_zip,
    build_submission_package,
)
from app.services.export.pdf_render import pdf_available, render_pdf, render_text_pdf
from app.services.export.provenance import build_provenance_manifest
from app.services.export.templates import get_template, list_templates
from app.services.export.validate import partition_issues, validate_canonical
from app.services.similarity import service as similarity_service
from app.services.storage import get_object_bytes, put_object_trusted

DEFAULT_OUTPUTS = [
    ExportArtifactKind.DOCX.value,
    ExportArtifactKind.LATEX.value,
    ExportArtifactKind.PDF.value,
    ExportArtifactKind.OVERLEAF_ZIP.value,
    ExportArtifactKind.BIBTEX.value,
    ExportArtifactKind.FIGURES_ZIP.value,
    ExportArtifactKind.DATASET_MANIFEST_ZIP.value,
    ExportArtifactKind.SIMILARITY_REPORT_PDF.value,
    ExportArtifactKind.SUBMISSION_PACKAGE.value,
    ExportArtifactKind.HTML_PREVIEW.value,
    ExportArtifactKind.PROVENANCE_MANIFEST.value,
    ExportArtifactKind.CANONICAL_JSON.value,
]


def _utcnow() -> datetime:
    return datetime.now(UTC)


def job_to_dict(job: ExportJob, *, include_artifacts: bool = True) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": str(job.id),
        "project_id": str(job.project_id),
        "status": job.status.value,
        "template_id": job.template_id.value,
        "template_version": job.template_version,
        "template_warning": TEMPLATE_COMPATIBILITY_WARNING,
        "requested_outputs": job.requested_outputs,
        "validation_issues": job.validation_issues,
        "acknowledged_warnings": job.acknowledged_warnings,
        "manuscript_version_number": job.manuscript_version_number,
        "content_sha256": job.content_sha256,
        "error_message": job.error_message,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "created_at": job.created_at.isoformat() if job.created_at else None,
    }
    if include_artifacts:
        payload["artifacts"] = [artifact_to_dict(a) for a in (job.artifacts or [])]
    return payload


def artifact_to_dict(artifact: ExportArtifact) -> dict[str, Any]:
    return {
        "id": str(artifact.id),
        "kind": artifact.kind.value,
        "filename": artifact.filename,
        "content_type": artifact.content_type,
        "size_bytes": artifact.size_bytes,
        "sha256": artifact.sha256,
        "meta": artifact.meta,
        "created_at": artifact.created_at.isoformat() if artifact.created_at else None,
    }


async def _load_manuscript(db: AsyncSession, project_id: UUID) -> Manuscript:
    ms = await db.scalar(
        select(Manuscript)
        .where(Manuscript.project_id == project_id)
        .options(selectinload(Manuscript.sections), selectinload(Manuscript.versions))
    )
    if ms is None:
        raise NotFoundError("Manuscript not found")
    return ms


async def _unresolved_similarity_count(db: AsyncSession, project_id: UUID) -> int:
    report = await db.scalar(
        select(SimilarityReport)
        .where(SimilarityReport.project_id == project_id)
        .order_by(SimilarityReport.created_at.desc())
        .limit(1)
    )
    if report is None:
        return 0
    findings = (
        await db.scalars(
            select(SimilarityFinding)
            .where(SimilarityFinding.report_id == report.id)
            .options(selectinload(SimilarityFinding.resolution))
        )
    ).all()
    count = 0
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
            count += 1
    return count


async def build_canonical_for_project(
    db: AsyncSession,
    *,
    project: Project,
    template_id: str,
    options: dict[str, Any] | None = None,
) -> CanonicalManuscript:
    options = options or {}
    # Re-load project with relationships needed for async-safe access
    project_loaded = await db.scalar(
        select(Project)
        .where(Project.id == project.id)
        .options(selectinload(Project.facts), selectinload(Project.owner))
    )
    if project_loaded is None:
        raise NotFoundError("Project not found")
    project = project_loaded
    ms = await _load_manuscript(db, project.id)
    tpl = get_template(template_id)
    refs = (
        await db.scalars(
            select(Reference)
            .where(Reference.project_id == project.id)
            .options(selectinload(Reference.authors), selectinload(Reference.identifiers))
            .order_by(Reference.created_at.asc())
        )
    ).all()
    ref_payload: list[dict[str, Any]] = []
    for ref in refs:
        ref_authors = [a.full_name for a in sorted(ref.authors, key=lambda x: x.position)]
        key = (ref.doi or ref.title or str(ref.id))[:40]
        key = "".join(ch if ch.isalnum() else "_" for ch in key) or str(ref.id)[:8]
        ref_payload.append(
            {
                "key": key,
                "title": ref.title,
                "authors": ref_authors,
                "year": ref.year,
                "venue": ref.venue,
                "doi": ref.doi,
                "url": ref.url,
                "verification_status": ref.verification_status.value,
            }
        )

    figures = (
        await db.scalars(
            select(Figure).where(Figure.project_id == project.id).order_by(Figure.number)
        )
    ).all()
    tables = (
        await db.scalars(select(Table).where(Table.project_id == project.id).order_by(Table.number))
    ).all()

    draft: dict[str, Any] = (
        dict(project.draft_content) if isinstance(project.draft_content, dict) else {}
    )
    project_authors = project.authors if isinstance(project.authors, list) else []
    manuscript_authors: list[dict[str, Any]] = [
        a
        for a in (options.get("authors") or project_authors or draft.get("authors") or [])
        if isinstance(a, dict)
    ]
    affiliations: list[dict[str, Any]] = [
        a
        for a in (options.get("affiliations") or draft.get("affiliations") or [])
        if isinstance(a, dict)
    ]
    if not manuscript_authors and project.owner is not None:
        manuscript_authors = [
            {
                "name": str(project.owner.display_name or project.owner.email),
                "corresponding": True,
            }
        ]
    elif not manuscript_authors:
        owner = await db.get(User, project.owner_id)
        if owner:
            manuscript_authors = [
                {
                    "name": str(owner.display_name or owner.email),
                    "corresponding": True,
                }
            ]

    raw_back = options.get("back_matter") or draft.get("back_matter") or {}
    back_matter: dict[str, Any] = dict(raw_back) if isinstance(raw_back, dict) else {}
    # pull ethics fact if present
    for fact in project.facts or []:
        if fact.category.value == "ethics" and not back_matter.get("ethics"):
            back_matter["ethics"] = fact.value

    body_text = " ".join(s.plain_text for s in ms.sections).lower()
    synth = project.contains_synthetic_data or any(
        "synthetic" in (f.provenance_label or "").lower() for f in figures
    )
    simulated = any("simul" in (f.provenance_label or "").lower() for f in figures)
    disclosures = {
        "contains_synthetic_data": synth,
        "contains_simulated_results": simulated,
        "synthetic_disclosed_in_text": "synthetic" in body_text,
        "simulated_disclosed_in_text": "simul" in body_text,
    }

    sections_payload = [
        {
            "id": str(s.id),
            "section_type": s.section_type.value,
            "title": s.title,
            "position": s.position,
            "structured_content": s.structured_content,
            "plain_text": s.plain_text,
            "model_generated": False,
        }
        for s in ms.sections
    ]

    version_number = None
    if ms.current_version_id:
        for v in ms.versions:
            if v.id == ms.current_version_id:
                version_number = v.version_number
                break

    return build_canonical(
        project_id=project.id,
        title=project.title,
        template_id=tpl.id.value,
        template_version=tpl.version,
        manuscript_version=version_number,
        authors=manuscript_authors,
        affiliations=affiliations,
        sections=sections_payload,
        references=ref_payload,
        figures=[
            {
                "id": str(f.id),
                "stable_id": f.stable_id,
                "number": f.number,
                "title": f.title,
                "caption": f.caption,
                "alt_text": f.alt_text,
                "storage_png": f.storage_png,
                "provenance_label": f.provenance_label,
                "is_conceptual": f.is_conceptual,
                "filename": f"{f.stable_id}.png",
            }
            for f in figures
        ],
        tables=[
            {
                "id": str(t.id),
                "stable_id": t.stable_id,
                "number": t.number,
                "title": t.title,
                "caption": t.caption,
                "headers": t.headers,
                "rows": t.rows,
                "provenance_label": t.provenance_label,
            }
            for t in tables
        ],
        back_matter=back_matter,
        disclosures=disclosures,
        meta={"research_field": project.research_field},
    )


async def create_export_job(
    db: AsyncSession,
    *,
    project: Project,
    user: User,
    template_id: str = ExportTemplateId.GENERIC_ACADEMIC.value,
    outputs: list[str] | None = None,
    acknowledged_warnings: list[str] | None = None,
    options: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
    process_sync: bool | None = None,
) -> ExportJob:
    settings = get_settings()
    if process_sync is None:
        process_sync = settings.app_env == "test"

    if idempotency_key:
        existing = await db.scalar(
            select(ExportJob).where(
                ExportJob.project_id == project.id,
                ExportJob.owner_id == user.id,
                ExportJob.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            await db.refresh(existing, attribute_names=["artifacts"])
            return existing

    tpl = get_template(template_id)
    job = ExportJob(
        project_id=project.id,
        owner_id=user.id,
        status=ExportJobStatus.QUEUED,
        template_id=ExportTemplateId(tpl.id.value),
        template_version=tpl.version,
        requested_outputs=list(outputs or DEFAULT_OUTPUTS),
        options=options or {},
        acknowledged_warnings=list(acknowledged_warnings or []),
        idempotency_key=idempotency_key,
    )
    db.add(job)
    await db.flush()
    from app.observability.metrics import EXPORT_JOBS, metrics

    metrics.incr(EXPORT_JOBS, labels={"status": "queued", "template": tpl.id.value})

    if process_sync:
        await execute_export_job(db, job_id=job.id)
        await db.refresh(job, attribute_names=["artifacts"])
    else:
        from app.workers.tasks import run_export_job

        run_export_job.delay(str(job.id))
    return job


async def execute_export_job(db: AsyncSession, *, job_id: UUID) -> ExportJob:
    job = await db.scalar(
        select(ExportJob).where(ExportJob.id == job_id).options(selectinload(ExportJob.artifacts))
    )
    if job is None:
        raise NotFoundError("Export job not found")
    if job.status == ExportJobStatus.COMPLETED and job.artifacts:
        return job  # retry-safe

    project = await db.scalar(
        select(Project)
        .where(Project.id == job.project_id)
        .options(selectinload(Project.facts), selectinload(Project.owner))
    )
    if project is None:
        raise NotFoundError("Project not found")

    job.status = ExportJobStatus.VALIDATING
    job.started_at = job.started_at or _utcnow()
    await db.flush()

    try:
        manuscript = await build_canonical_for_project(
            db,
            project=project,
            template_id=job.template_id.value,
            options=job.options,
        )
        unresolved = await _unresolved_similarity_count(db, project.id)
        issues = validate_canonical(manuscript, unresolved_similarity=unresolved)
        job.validation_issues = [i.to_dict() for i in issues]
        job.content_sha256 = manuscript.content_sha256()
        job.manuscript_version_number = manuscript.manuscript_version

        ack = set(job.acknowledged_warnings or [])
        _blocking, _warnings, can_proceed = partition_issues(issues, ack)
        if not can_proceed:
            job.status = ExportJobStatus.BLOCKED
            job.error_message = "Critical validation issues must be fixed before export."
            job.completed_at = _utcnow()
            await db.flush()
            return job

        job.status = ExportJobStatus.RENDERING
        await db.flush()
        await _render_and_store(db, job=job, project=project, manuscript=manuscript)
        job.status = ExportJobStatus.COMPLETED
        job.completed_at = _utcnow()
        job.error_message = None
        await db.flush()
        await db.refresh(job, attribute_names=["artifacts"])
        from app.models.enums import AnalyticsEventType, NotificationKind
        from app.services.engagement.analytics import track as track_analytics
        from app.services.engagement.notifications import create_notification

        await track_analytics(
            db,
            event_type=AnalyticsEventType.EXPORT_REQUESTED,
            user_id=job.owner_id,
            project_id=job.project_id,
            properties={"status": "completed", "template": job.template_id.value},
        )
        await create_notification(
            db,
            user_id=job.owner_id,
            project_id=job.project_id,
            kind=NotificationKind.EXPORT_COMPLETED,
            title="Export completed",
            body="Your manuscript export finished. Download artifacts from the Export panel.",
            action_url=f"/projects/{job.project_id}#export",
        )
        return job
    except Exception as exc:
        job.status = ExportJobStatus.FAILED
        job.error_message = str(exc)[:1000]
        job.completed_at = _utcnow()
        await db.flush()
        raise


async def _store_artifact(
    db: AsyncSession,
    *,
    job: ExportJob,
    kind: ExportArtifactKind,
    filename: str,
    content_type: str,
    data: bytes,
    meta: dict[str, Any] | None = None,
) -> ExportArtifact:
    digest = hashlib.sha256(data).hexdigest()
    key = f"projects/{job.project_id}/exports/{job.id}/{filename}"
    put_object_trusted(key=key, body=data, content_type=content_type)
    artifact = ExportArtifact(
        job_id=job.id,
        project_id=job.project_id,
        kind=kind,
        filename=filename,
        content_type=content_type,
        storage_key=key,
        size_bytes=len(data),
        sha256=digest,
        meta=meta or {},
    )
    db.add(artifact)
    await db.flush()
    return artifact


async def _render_and_store(
    db: AsyncSession,
    *,
    job: ExportJob,
    project: Project,
    manuscript: CanonicalManuscript,
) -> None:
    requested = set(job.requested_outputs or DEFAULT_OUTPUTS)
    job.status = ExportJobStatus.PACKAGING

    # Clear prior artifacts for retry-safety
    for old in list(job.artifacts or []):
        await db.delete(old)
    await db.flush()

    canonical_bytes = json.dumps(manuscript.to_dict(), indent=2, default=str).encode("utf-8")
    if ExportArtifactKind.CANONICAL_JSON.value in requested:
        await _store_artifact(
            db,
            job=job,
            kind=ExportArtifactKind.CANONICAL_JSON,
            filename="manuscript.canonical.json",
            content_type="application/json",
            data=canonical_bytes,
        )

    html_payload = render_html(manuscript)
    if ExportArtifactKind.HTML_PREVIEW.value in requested:
        await _store_artifact(
            db,
            job=job,
            kind=ExportArtifactKind.HTML_PREVIEW,
            filename="preview.html",
            content_type="text/html; charset=utf-8",
            data=html_payload["html"].encode("utf-8"),
            meta={
                "page_count": html_payload["page_count"],
                "template_warning": html_payload["template_warning"],
            },
        )

    latex = render_latex(manuscript)
    if ExportArtifactKind.LATEX.value in requested:
        await _store_artifact(
            db,
            job=job,
            kind=ExportArtifactKind.LATEX,
            filename="main.tex",
            content_type="application/x-tex",
            data=latex.encode("utf-8"),
        )

    bib = render_bibtex(manuscript)
    if ExportArtifactKind.BIBTEX.value in requested:
        await _store_artifact(
            db,
            job=job,
            kind=ExportArtifactKind.BIBTEX,
            filename="references.bib",
            content_type="text/x-bibtex",
            data=bib.encode("utf-8"),
        )

    docx = render_docx(manuscript)
    if ExportArtifactKind.DOCX.value in requested:
        await _store_artifact(
            db,
            job=job,
            kind=ExportArtifactKind.DOCX,
            filename="manuscript.docx",
            content_type=(
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ),
            data=docx,
        )

    pdf_meta: dict[str, Any] = {"available": pdf_available()}
    pdf_bytes: bytes | None = None
    if ExportArtifactKind.PDF.value in requested:
        try:
            pdf_bytes, pdf_meta = render_pdf(manuscript)
            await _store_artifact(
                db,
                job=job,
                kind=ExportArtifactKind.PDF,
                filename="manuscript.pdf",
                content_type="application/pdf",
                data=pdf_bytes,
                meta=pdf_meta,
            )
        except RuntimeError as exc:
            pdf_meta = {"available": False, "error": str(exc)}

    # Figures
    figure_bytes: dict[str, bytes] = {}
    figure_manifest: list[dict[str, Any]] = []
    for fig in manuscript.figures:
        fname = fig.filename or f"figure_{fig.number}.png"
        entry = {
            "id": fig.id,
            "number": fig.number,
            "caption": fig.caption,
            "provenance_label": fig.provenance_label,
            "filename": fname,
        }
        if fig.storage_key:
            try:
                data = get_object_bytes(fig.storage_key)
                figure_bytes[fname] = data
                figure_bytes[fig.id] = data
                entry["included"] = True
            except FileNotFoundError:
                entry["included"] = False
        else:
            entry["included"] = False
        figure_manifest.append(entry)

    if ExportArtifactKind.FIGURES_ZIP.value in requested:
        named_figures = {
            (fig.filename or f"figure_{fig.number}.png"): figure_bytes[fig.id]
            for fig in manuscript.figures
            if fig.id in figure_bytes
        }
        await _store_artifact(
            db,
            job=job,
            kind=ExportArtifactKind.FIGURES_ZIP,
            filename="figures.zip",
            content_type="application/zip",
            data=build_figures_zip(named_figures, figure_manifest),
        )

    if ExportArtifactKind.OVERLEAF_ZIP.value in requested:
        await _store_artifact(
            db,
            job=job,
            kind=ExportArtifactKind.OVERLEAF_ZIP,
            filename="overleaf_package.zip",
            content_type="application/zip",
            data=build_overleaf_zip(manuscript, figure_bytes=figure_bytes),
        )

    # Dataset / reproducibility
    datasets = (await db.scalars(select(Dataset).where(Dataset.project_id == project.id))).all()
    runs = (await db.scalars(select(AnalysisRun).where(AnalysisRun.project_id == project.id))).all()
    manifests = (
        await db.scalars(
            select(ReproducibilityManifest).where(ReproducibilityManifest.project_id == project.id)
        )
    ).all()
    dataset_rows: list[dict[str, Any]] = [
        {
            "id": str(d.id),
            "name": d.name,
            "provenance_type": d.provenance_type.value
            if hasattr(d.provenance_type, "value")
            else str(d.provenance_type),
        }
        for d in datasets
    ]
    dataset_payload: dict[str, Any] = {
        "datasets": dataset_rows,
        "analysis_run_ids": [str(r.id) for r in runs],
        "reproducibility_manifests": [m.manifest_json for m in manifests if m.manifest_json],
        "synthetic_status": manuscript.disclosures,
    }
    if ExportArtifactKind.DATASET_MANIFEST_ZIP.value in requested:
        await _store_artifact(
            db,
            job=job,
            kind=ExportArtifactKind.DATASET_MANIFEST_ZIP,
            filename="dataset_reproducibility.zip",
            content_type="application/zip",
            data=build_dataset_manifest_zip(dataset_payload),
        )

    # Similarity report PDF
    sim_pdf: bytes | None = None
    report = await db.scalar(
        select(SimilarityReport)
        .where(SimilarityReport.project_id == project.id)
        .order_by(SimilarityReport.created_at.desc())
        .limit(1)
    )
    if report is not None and ExportArtifactKind.SIMILARITY_REPORT_PDF.value in requested:
        full = await similarity_service.get_report(db, project_id=project.id, report_id=report.id)
        text = (
            similarity_service.export_report_text(full)
            if full is not None
            else "No similarity report body."
        )
        sim_pdf = render_text_pdf("Similarity and citation-risk report", text)
        await _store_artifact(
            db,
            job=job,
            kind=ExportArtifactKind.SIMILARITY_REPORT_PDF,
            filename="similarity_report.pdf",
            content_type="application/pdf",
            data=sim_pdf,
        )

    files = (
        await db.scalars(select(ProjectFile).where(ProjectFile.project_id == project.id))
    ).all()
    citation_verification = {
        "total": len(manuscript.references),
        "verified": sum(1 for r in manuscript.references if r.verification_status == "verified"),
        "unverified": sum(1 for r in manuscript.references if r.verification_status != "verified"),
    }
    provenance = build_provenance_manifest(
        manuscript=manuscript,
        package_versions={
            "researchforge_api": "0.1.0",
            "canonical_schema": manuscript.schema_version,
            "template": f"{manuscript.template_id}@{manuscript.template_version}",
            "pdf_engine": str(pdf_meta.get("engine") or "unavailable"),
        },
        source_documents=[
            {"id": str(f.id), "filename": f.original_filename, "kind": f.kind.value} for f in files
        ],
        datasets=dataset_rows,
        figures=figure_manifest,
        analysis_run_ids=[str(r.id) for r in runs],
        citation_verification=citation_verification,
        model_generated_sections=[s.id for s in manuscript.sections if s.model_generated],
        export_job_id=job.id,
    )
    if ExportArtifactKind.PROVENANCE_MANIFEST.value in requested:
        await _store_artifact(
            db,
            job=job,
            kind=ExportArtifactKind.PROVENANCE_MANIFEST,
            filename="provenance_manifest.json",
            content_type="application/json",
            data=json.dumps(provenance, indent=2, default=str).encode("utf-8"),
        )

    if ExportArtifactKind.SUBMISSION_PACKAGE.value in requested:
        package_files: dict[str, bytes] = {
            "manuscript.docx": docx,
            "main.tex": latex.encode("utf-8"),
            "references.bib": bib.encode("utf-8"),
            "preview.html": html_payload["html"].encode("utf-8"),
            "manuscript.canonical.json": canonical_bytes,
        }
        if pdf_bytes:
            package_files["manuscript.pdf"] = pdf_bytes
        if sim_pdf:
            package_files["similarity_report.pdf"] = sim_pdf
        for fname, data in figure_bytes.items():
            if fname.endswith(".png") or fname.endswith(".svg"):
                package_files[f"figures/{fname}"] = data
        await _store_artifact(
            db,
            job=job,
            kind=ExportArtifactKind.SUBMISSION_PACKAGE,
            filename="submission_package.zip",
            content_type="application/zip",
            data=build_submission_package(files=package_files, provenance=provenance),
        )


async def list_jobs(db: AsyncSession, *, project_id: UUID, limit: int = 20) -> list[ExportJob]:
    result = await db.scalars(
        select(ExportJob)
        .where(ExportJob.project_id == project_id)
        .options(selectinload(ExportJob.artifacts))
        .order_by(ExportJob.created_at.desc())
        .limit(limit)
    )
    return list(result)


async def get_job(db: AsyncSession, *, project_id: UUID, job_id: UUID) -> ExportJob:
    job = await db.scalar(
        select(ExportJob)
        .where(ExportJob.id == job_id, ExportJob.project_id == project_id)
        .options(selectinload(ExportJob.artifacts))
    )
    if job is None:
        raise NotFoundError("Export job not found")
    return job


async def preview_manuscript(
    db: AsyncSession,
    *,
    project: Project,
    template_id: str,
    page: int = 1,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    manuscript = await build_canonical_for_project(
        db, project=project, template_id=template_id, options=options
    )
    unresolved = await _unresolved_similarity_count(db, project.id)
    issues = validate_canonical(manuscript, unresolved_similarity=unresolved)
    html = render_html(manuscript, template_id=template_id, page=page)
    overflow = [i.to_dict() for i in issues if "overflow" in i.code]
    return {
        "canonical_schema_version": manuscript.schema_version,
        "template_id": template_id,
        "template_warning": TEMPLATE_COMPATIBILITY_WARNING,
        "templates": list_templates(),
        "html": html["html"],
        "page": html["page"],
        "page_count": html["page_count"],
        "validation_issues": [i.to_dict() for i in issues],
        "figure_table_overflow_warnings": overflow,
        "references_preview": [
            {
                "order": r.order,
                "key": r.key,
                "title": r.title,
                "authors": r.authors,
                "year": r.year,
                "verification_status": r.verification_status,
            }
            for r in manuscript.references
        ],
        "figure_numbering": [
            {"id": f.id, "number": f.number, "caption": f.caption} for f in manuscript.figures
        ],
        "table_numbering": [
            {"id": t.id, "number": t.number, "caption": t.caption} for t in manuscript.tables
        ],
        "pdf_available": pdf_available(),
    }


async def create_download_grant(
    db: AsyncSession,
    *,
    project: Project,
    user: User,
    artifact_id: UUID,
) -> dict[str, Any]:
    settings = get_settings()
    artifact = await db.scalar(
        select(ExportArtifact).where(
            ExportArtifact.id == artifact_id,
            ExportArtifact.project_id == project.id,
        )
    )
    if artifact is None:
        raise NotFoundError("Export artifact not found")
    job = await db.get(ExportJob, artifact.job_id)
    if job is None or job.owner_id != user.id:
        raise ForbiddenError("Not authorized to download this export")

    expire_seconds = settings.export_download_expire_seconds
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    grant = ExportDownload(
        job_id=artifact.job_id,
        artifact_id=artifact.id,
        user_id=user.id,
        token_hash=token_hash,
        expires_at=_utcnow() + timedelta(seconds=expire_seconds),
    )
    db.add(grant)
    await db.flush()

    # Do not return raw storage_url — clients must redeem the authenticated token path.
    return {
        "download_token": token,
        "expires_in": expire_seconds,
        "expires_at": grant.expires_at.isoformat(),
        "artifact": artifact_to_dict(artifact),
        "download_path": f"/api/v1/exports/download/{token}",
    }


async def redeem_download_token(
    db: AsyncSession,
    *,
    token: str,
    user: User | None,
) -> tuple[ExportArtifact, bytes]:
    if user is None:
        raise ForbiddenError("Authentication required to download complete manuscripts")
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    grant = await db.scalar(select(ExportDownload).where(ExportDownload.token_hash == token_hash))
    if grant is None or grant.revoked:
        raise NotFoundError("Download link not found")
    if grant.user_id != user.id:
        raise ForbiddenError("Download link is not authorized for this user")
    if grant.expires_at.replace(tzinfo=UTC) < _utcnow():
        raise ForbiddenError("Download link has expired")
    if grant.downloaded_at is not None:
        raise ForbiddenError("Download link has already been used")
    artifact = await db.get(ExportArtifact, grant.artifact_id)
    if artifact is None:
        raise NotFoundError("Export artifact not found")
    grant.downloaded_at = _utcnow()
    await db.flush()
    return artifact, get_object_bytes(artifact.storage_key)


async def download_history(
    db: AsyncSession, *, project_id: UUID, user_id: UUID, limit: int = 50
) -> list[dict[str, Any]]:
    rows = (
        await db.scalars(
            select(ExportDownload)
            .join(ExportArtifact, ExportArtifact.id == ExportDownload.artifact_id)
            .where(
                ExportDownload.user_id == user_id,
                ExportArtifact.project_id == project_id,
            )
            .options(selectinload(ExportDownload.artifact))
            .order_by(ExportDownload.created_at.desc())
            .limit(limit)
        )
    ).all()
    return [
        {
            "id": str(d.id),
            "artifact_id": str(d.artifact_id),
            "artifact_kind": d.artifact.kind.value if d.artifact else None,
            "filename": d.artifact.filename if d.artifact else None,
            "created_at": d.created_at.isoformat() if d.created_at else None,
            "expires_at": d.expires_at.isoformat(),
            "downloaded_at": d.downloaded_at.isoformat() if d.downloaded_at else None,
            "expired": d.expires_at.replace(tzinfo=UTC) < _utcnow(),
        }
        for d in rows
    ]


def meta_payload() -> dict[str, Any]:
    return {
        "templates": list_templates(),
        "template_warning": TEMPLATE_COMPATIBILITY_WARNING,
        "outputs": [k.value for k in ExportArtifactKind],
        "pdf_available": pdf_available(),
        "guest_restriction": "Guests cannot download complete manuscripts.",
        "certification_note": (
            "ResearchForge does not claim official publisher certification unless "
            "officially licensed or approved."
        ),
    }
