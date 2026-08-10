"""document rendering and export pipeline

Revision ID: 20260802_0007
Revises: 20260802_0006
Create Date: 2026-08-02 23:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260802_0007"
down_revision: Union[str, None] = "20260802_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

export_job_status = sa.Enum(
    "queued",
    "validating",
    "rendering",
    "packaging",
    "completed",
    "failed",
    "blocked",
    "cancelled",
    name="export_job_status",
)
export_artifact_kind = sa.Enum(
    "docx",
    "latex",
    "pdf",
    "overleaf_zip",
    "bibtex",
    "figures_zip",
    "dataset_manifest_zip",
    "similarity_report_pdf",
    "submission_package",
    "html_preview",
    "provenance_manifest",
    "canonical_json",
    name="export_artifact_kind",
)
export_template_id = sa.Enum(
    "generic_academic",
    "ieee_two_column",
    "springer_lncs",
    "acm",
    name="export_template_id",
)


def upgrade() -> None:
    bind = op.get_bind()
    for enum in (export_job_status, export_artifact_kind, export_template_id):
        enum.create(bind, checkfirst=True)

    json_type = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")

    op.create_table(
        "export_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", export_job_status, nullable=False),
        sa.Column("template_id", export_template_id, nullable=False),
        sa.Column("template_version", sa.String(32), nullable=False),
        sa.Column("requested_outputs", json_type, nullable=False),
        sa.Column("options", json_type, nullable=False),
        sa.Column("validation_issues", json_type, nullable=False),
        sa.Column("acknowledged_warnings", json_type, nullable=False),
        sa.Column("manuscript_version_number", sa.Integer(), nullable=True),
        sa.Column("content_sha256", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_export_jobs_project_id", "export_jobs", ["project_id"])
    op.create_index("ix_export_jobs_owner_id", "export_jobs", ["owner_id"])
    op.create_index("ix_export_jobs_idempotency_key", "export_jobs", ["idempotency_key"])

    op.create_table(
        "export_artifacts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("export_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", export_artifact_kind, nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(128), nullable=False),
        sa.Column("storage_key", sa.String(1024), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=True),
        sa.Column("meta", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_export_artifacts_job_id", "export_artifacts", ["job_id"])
    op.create_index("ix_export_artifacts_project_id", "export_artifacts", ["project_id"])

    op.create_table(
        "export_downloads",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("export_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "artifact_id",
            sa.Uuid(),
            sa.ForeignKey("export_artifacts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("downloaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_export_downloads_job_id", "export_downloads", ["job_id"])
    op.create_index("ix_export_downloads_artifact_id", "export_downloads", ["artifact_id"])
    op.create_index("ix_export_downloads_user_id", "export_downloads", ["user_id"])
    op.create_index("ix_export_downloads_token_hash", "export_downloads", ["token_hash"], unique=True)


def downgrade() -> None:
    op.drop_table("export_downloads")
    op.drop_table("export_artifacts")
    op.drop_table("export_jobs")
    bind = op.get_bind()
    for enum in (export_template_id, export_artifact_kind, export_job_status):
        enum.drop(bind, checkfirst=True)
