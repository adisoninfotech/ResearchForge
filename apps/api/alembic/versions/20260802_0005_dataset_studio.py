"""dataset studio tables

Revision ID: 20260802_0005
Revises: 20260802_0004
Create Date: 2026-08-02 21:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260802_0005"
down_revision: Union[str, None] = "20260802_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

dataset_provenance_type = sa.Enum(
    "uploaded_real",
    "publicly_sourced",
    "synthetic",
    "simulated_experiment",
    "calculated_result",
    "user_entered",
    name="dataset_provenance_type",
)
dataset_column_type = sa.Enum(
    "integer",
    "float",
    "boolean",
    "category",
    "string",
    "datetime",
    name="dataset_column_type",
)
dataset_column_override_type = sa.Enum(
    "integer",
    "float",
    "boolean",
    "category",
    "string",
    "datetime",
    name="dataset_column_override_type",
)
analysis_operation = sa.Enum(
    "descriptive",
    "correlation",
    "missing_values",
    "group_comparison",
    "confidence_intervals",
    "t_test",
    "mann_whitney",
    "anova",
    "chi_square",
    "simple_regression",
    "classification_metrics",
    "confusion_matrix",
    "roc_curve",
    "precision_recall",
    name="analysis_operation",
)
analysis_run_status = sa.Enum(
    "queued",
    "running",
    "completed",
    "failed",
    name="analysis_run_status",
)
figure_kind = sa.Enum(
    "bar",
    "line",
    "scatter",
    "histogram",
    "box",
    "correlation_heatmap",
    "confusion_matrix",
    "roc_curve",
    "precision_recall",
    "conceptual",
    name="figure_kind",
)
table_kind = sa.Enum(
    "dataset_summary",
    "descriptive_stats",
    "performance_comparison",
    "hyperparameters",
    "ablation",
    "statistical_test",
    name="table_kind",
)


def upgrade() -> None:
    bind = op.get_bind()
    for enum in (
        dataset_provenance_type,
        dataset_column_type,
        dataset_column_override_type,
        analysis_operation,
        analysis_run_status,
        figure_kind,
        table_kind,
    ):
        enum.create(bind, checkfirst=True)

    json_type = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")

    op.create_table(
        "datasets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("provenance_type", dataset_provenance_type, nullable=False),
        sa.Column("synthetic", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("source_description", sa.Text(), nullable=True),
        sa.Column("license", sa.String(255), nullable=True),
        sa.Column("provenance_label", sa.Text(), nullable=False),
        sa.Column("label_locked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("current_version_id", sa.Uuid(), nullable=True),
        sa.Column("creation_parameters", json_type, nullable=True),
        sa.Column("random_seed", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_datasets_project_id", "datasets", ["project_id"])

    op.create_table(
        "dataset_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("dataset_id", sa.Uuid(), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(1024), nullable=False, unique=True),
        sa.Column("original_storage_key", sa.String(1024), nullable=True),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("column_count", sa.Integer(), nullable=False),
        sa.Column("schema_json", json_type, nullable=False),
        sa.Column("is_immutable_original", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("dataset_id", "version_number", name="uq_dataset_version"),
    )
    op.create_index("ix_dataset_versions_dataset_id", "dataset_versions", ["dataset_id"])
    op.create_index("ix_dataset_versions_project_id", "dataset_versions", ["project_id"])

    op.create_table(
        "dataset_columns",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("version_id", sa.Uuid(), sa.ForeignKey("dataset_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("inferred_type", dataset_column_type, nullable=False),
        sa.Column("override_type", dataset_column_override_type, nullable=True),
        sa.Column("nullable_ratio", sa.Float(), nullable=False),
        sa.Column("unique_count", sa.Integer(), nullable=False),
        sa.Column("stats_json", json_type, nullable=True),
        sa.UniqueConstraint("version_id", "name", name="uq_dataset_column_name"),
    )
    op.create_index("ix_dataset_columns_version_id", "dataset_columns", ["version_id"])

    op.create_table(
        "dataset_profiles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("version_id", sa.Uuid(), sa.ForeignKey("dataset_versions.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("missing_summary", json_type, nullable=False),
        sa.Column("duplicate_row_count", sa.Integer(), nullable=False),
        sa.Column("descriptive_stats", json_type, nullable=False),
        sa.Column("pii_warnings", json_type, nullable=False),
        sa.Column("preview_rows", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_dataset_profiles_project_id", "dataset_profiles", ["project_id"])

    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dataset_version_id", sa.Uuid(), sa.ForeignKey("dataset_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("operation", analysis_operation, nullable=False),
        sa.Column("status", analysis_run_status, nullable=False),
        sa.Column("parameters", json_type, nullable=False),
        sa.Column("package_versions", json_type, nullable=False),
        sa.Column("random_seed", sa.Integer(), nullable=True),
        sa.Column("code_representation", sa.Text(), nullable=False),
        sa.Column("results", json_type, nullable=True),
        sa.Column("warnings", json_type, nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_analysis_runs_project_id", "analysis_runs", ["project_id"])
    op.create_index("ix_analysis_runs_dataset_version_id", "analysis_runs", ["dataset_version_id"])

    op.create_table(
        "analysis_artifacts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("analysis_run_id", sa.Uuid(), sa.ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.String(1024), nullable=True),
        sa.Column("content_json", json_type, nullable=True),
        sa.Column("media_type", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_analysis_artifacts_analysis_run_id", "analysis_artifacts", ["analysis_run_id"])
    op.create_index("ix_analysis_artifacts_project_id", "analysis_artifacts", ["project_id"])

    op.create_table(
        "figures",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stable_id", sa.String(64), nullable=False, unique=True),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("kind", figure_kind, nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("caption", sa.Text(), nullable=False),
        sa.Column("alt_text", sa.Text(), nullable=False),
        sa.Column("x_label", sa.String(255), nullable=True),
        sa.Column("y_label", sa.String(255), nullable=True),
        sa.Column("journal_preset", sa.String(64), nullable=False),
        sa.Column("dataset_version_id", sa.Uuid(), sa.ForeignKey("dataset_versions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("analysis_run_id", sa.Uuid(), sa.ForeignKey("analysis_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_reference", sa.Text(), nullable=False),
        sa.Column("provenance_label", sa.Text(), nullable=False),
        sa.Column("is_conceptual", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("storage_png", sa.String(1024), nullable=True),
        sa.Column("storage_svg", sa.String(1024), nullable=True),
        sa.Column("storage_pdf", sa.String(1024), nullable=True),
        sa.Column("parameters", json_type, nullable=False),
        sa.Column("reproducibility", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_figures_project_id", "figures", ["project_id"])

    op.create_table(
        "tables",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stable_id", sa.String(64), nullable=False, unique=True),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("kind", table_kind, nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("caption", sa.Text(), nullable=False),
        sa.Column("dataset_version_id", sa.Uuid(), sa.ForeignKey("dataset_versions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("analysis_run_id", sa.Uuid(), sa.ForeignKey("analysis_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_reference", sa.Text(), nullable=False),
        sa.Column("provenance_label", sa.Text(), nullable=False),
        sa.Column("headers", json_type, nullable=False),
        sa.Column("rows", json_type, nullable=False),
        sa.Column("parameters", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_tables_project_id", "tables", ["project_id"])

    op.create_table(
        "reproducibility_manifests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=True),
        sa.Column("analysis_run_id", sa.Uuid(), sa.ForeignKey("analysis_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("figure_id", sa.Uuid(), sa.ForeignKey("figures.id", ondelete="SET NULL"), nullable=True),
        sa.Column("table_id", sa.Uuid(), sa.ForeignKey("tables.id", ondelete="SET NULL"), nullable=True),
        sa.Column("manifest_json", json_type, nullable=False),
        sa.Column("provenance_label", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_reproducibility_manifests_project_id", "reproducibility_manifests", ["project_id"])

    op.create_table(
        "manuscript_asset_refs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("section_id", sa.Uuid(), nullable=False),
        sa.Column("asset_type", sa.String(16), nullable=False),
        sa.Column("asset_stable_id", sa.String(64), nullable=False),
        sa.Column("cross_ref", sa.String(64), nullable=False),
        sa.Column("caption", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("provenance", sa.Text(), nullable=False),
        sa.Column("alt_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "project_id",
            "asset_type",
            "asset_stable_id",
            "section_id",
            name="uq_manuscript_asset_ref",
        ),
    )
    op.create_index("ix_manuscript_asset_refs_project_id", "manuscript_asset_refs", ["project_id"])
    op.create_index("ix_manuscript_asset_refs_section_id", "manuscript_asset_refs", ["section_id"])


def downgrade() -> None:
    op.drop_table("manuscript_asset_refs")
    op.drop_table("reproducibility_manifests")
    op.drop_table("tables")
    op.drop_table("figures")
    op.drop_table("analysis_artifacts")
    op.drop_table("analysis_runs")
    op.drop_table("dataset_profiles")
    op.drop_table("dataset_columns")
    op.drop_table("dataset_versions")
    op.drop_table("datasets")
    bind = op.get_bind()
    for enum in (
        table_kind,
        figure_kind,
        analysis_run_status,
        analysis_operation,
        dataset_column_override_type,
        dataset_column_type,
        dataset_provenance_type,
    ):
        enum.drop(bind, checkfirst=True)
