"""Machine-readable export provenance manifest."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.services.export.canonical import SCHEMA_VERSION, CanonicalManuscript

MANIFEST_VERSION = "1.0.0"


def build_provenance_manifest(
    *,
    manuscript: CanonicalManuscript,
    package_versions: dict[str, str],
    source_documents: list[dict[str, Any]],
    datasets: list[dict[str, Any]],
    figures: list[dict[str, Any]],
    analysis_run_ids: list[str],
    citation_verification: dict[str, Any],
    model_generated_sections: list[str],
    export_job_id: UUID | str | None = None,
) -> dict[str, Any]:
    return {
        "manifest_version": MANIFEST_VERSION,
        "canonical_schema_version": SCHEMA_VERSION,
        "project_id": manuscript.project_id,
        "manuscript_version": manuscript.manuscript_version,
        "export_timestamp": datetime.now(UTC).isoformat(),
        "export_job_id": str(export_job_id) if export_job_id else None,
        "template_id": manuscript.template_id,
        "template_version": manuscript.template_version,
        "content_sha256": manuscript.content_sha256(),
        "model_generated_sections": model_generated_sections,
        "source_document_references": source_documents,
        "dataset_provenance": datasets,
        "figure_provenance": figures,
        "synthetic_data_status": {
            "contains_synthetic_data": bool(
                (manuscript.disclosures or {}).get("contains_synthetic_data")
            ),
            "contains_simulated_results": bool(
                (manuscript.disclosures or {}).get("contains_simulated_results")
            ),
            "disclosures": manuscript.disclosures,
        },
        "analysis_run_ids": analysis_run_ids,
        "package_versions": package_versions,
        "citation_verification_status": citation_verification,
    }
