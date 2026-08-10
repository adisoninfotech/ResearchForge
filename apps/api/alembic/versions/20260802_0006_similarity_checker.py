"""similarity and citation-risk checker

Revision ID: 20260802_0006
Revises: 20260802_0005
Create Date: 2026-08-02 22:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260802_0006"
down_revision: Union[str, None] = "20260802_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

similarity_job_status = sa.Enum(
    "queued", "running", "completed", "failed", "cancelled", name="similarity_job_status"
)
similarity_finding_class = sa.Enum(
    "exact_textual_overlap",
    "near_textual_overlap",
    "semantic_similarity",
    "proper_quotation",
    "properly_cited_paraphrase",
    "citation_potentially_required",
    "excessive_similarity_despite_citation",
    "common_technical_phrase",
    "bibliography_or_title_match",
    "self_overlap",
    "internal_duplication",
    "needs_human_review",
    name="similarity_finding_class",
)
finding_resolution_action = sa.Enum(
    "unresolved",
    "false_positive",
    "added_citation",
    "rewritten",
    "accepted_technical_language",
    "needs_review",
    name="finding_resolution_action",
)
similarity_source_kind = sa.Enum(
    "uploaded_reference",
    "project_document",
    "authorized_prior_manuscript",
    "open_license_corpus",
    "internal_section",
    "licensed_provider",
    name="similarity_source_kind",
)


def upgrade() -> None:
    bind = op.get_bind()
    for enum in (
        similarity_job_status,
        similarity_finding_class,
        finding_resolution_action,
        similarity_source_kind,
    ):
        enum.create(bind, checkfirst=True)

    json_type = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")

    op.create_table(
        "similarity_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", similarity_job_status, nullable=False),
        sa.Column("options", json_type, nullable=False),
        sa.Column("threshold_profile", sa.String(64), nullable=False),
        sa.Column("algorithm_versions", json_type, nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_similarity_jobs_project_id", "similarity_jobs", ["project_id"])
    op.create_index("ix_similarity_jobs_owner_id", "similarity_jobs", ["owner_id"])

    op.create_table(
        "similarity_reports",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("similarity_jobs.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("risk_level", sa.String(32), nullable=False),
        sa.Column("section_summaries", json_type, nullable=False),
        sa.Column("method_explanations", json_type, nullable=False),
        sa.Column("footer", json_type, nullable=False),
        sa.Column("finding_counts", json_type, nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_similarity_reports_project_id", "similarity_reports", ["project_id"])

    op.create_table(
        "similarity_sources",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("report_id", sa.Uuid(), sa.ForeignKey("similarity_reports.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", similarity_source_kind, nullable=False),
        sa.Column("label", sa.String(500), nullable=False),
        sa.Column("project_file_id", sa.Uuid(), nullable=True),
        sa.Column("manuscript_id", sa.Uuid(), nullable=True),
        sa.Column("section_id", sa.Uuid(), nullable=True),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("checked", sa.Boolean(), nullable=False),
        sa.Column("unavailable_reason", sa.Text(), nullable=True),
    )
    op.create_index("ix_similarity_sources_report_id", "similarity_sources", ["report_id"])

    op.create_table(
        "report_coverage",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("report_id", sa.Uuid(), sa.ForeignKey("similarity_reports.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("sources_checked", json_type, nullable=False),
        sa.Column("sources_not_checked", json_type, nullable=False),
        sa.Column("limitations", json_type, nullable=False),
        sa.Column("open_corpus_enabled", sa.Boolean(), nullable=False),
        sa.Column("licensed_provider_status", sa.String(64), nullable=False),
    )

    op.create_table(
        "similarity_findings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("report_id", sa.Uuid(), sa.ForeignKey("similarity_reports.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("section_id", sa.Uuid(), nullable=True),
        sa.Column("classification", similarity_finding_class, nullable=False),
        sa.Column("manuscript_text", sa.Text(), nullable=False),
        sa.Column("manuscript_start", sa.Integer(), nullable=False),
        sa.Column("manuscript_end", sa.Integer(), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("source_start", sa.Integer(), nullable=True),
        sa.Column("source_end", sa.Integer(), nullable=True),
        sa.Column("source_id", sa.Uuid(), sa.ForeignKey("similarity_sources.id", ondelete="SET NULL"), nullable=True),
        sa.Column("methods", json_type, nullable=False),
        sa.Column("scores", json_type, nullable=False),
        sa.Column("citation_present", sa.Boolean(), nullable=False),
        sa.Column("citation_keys", json_type, nullable=False),
        sa.Column("recommended_action", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("excluded_by_filter", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_similarity_findings_report_id", "similarity_findings", ["report_id"])
    op.create_index("ix_similarity_findings_project_id", "similarity_findings", ["project_id"])

    op.create_table(
        "finding_resolutions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("finding_id", sa.Uuid(), sa.ForeignKey("similarity_findings.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("action", finding_resolution_action, nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("rewrite_original", sa.Text(), nullable=True),
        sa.Column("rewrite_proposed", sa.Text(), nullable=True),
        sa.Column("rewrite_accepted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("rewrite_diff", json_type, nullable=True),
        sa.Column("resolved_by_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("finding_resolutions")
    op.drop_table("similarity_findings")
    op.drop_table("report_coverage")
    op.drop_table("similarity_sources")
    op.drop_table("similarity_reports")
    op.drop_table("similarity_jobs")
    bind = op.get_bind()
    for enum in (
        similarity_source_kind,
        finding_resolution_action,
        similarity_finding_class,
        similarity_job_status,
    ):
        enum.drop(bind, checkfirst=True)
