"""manuscripts versions facts retention

Revision ID: 20260802_0002
Revises: 20260322_0001
Create Date: 2026-08-02 17:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260802_0002"
down_revision: Union[str, None] = "20260322_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

project_status = postgresql.ENUM(
    "draft", "active", "archived", "trash", name="project_status", create_type=False
)
retention_policy = postgresql.ENUM(
    "keep",
    "trash_30",
    "inactive_draft_90",
    "plan_default",
    name="retention_policy",
    create_type=False,
)
section_type = postgresql.ENUM(
    "abstract",
    "keywords",
    "introduction",
    "related_work",
    "methodology",
    "results",
    "discussion",
    "limitations",
    "conclusion",
    "references",
    "custom",
    name="section_type",
    create_type=False,
)
section_status = postgresql.ENUM(
    "empty", "draft", "complete", name="section_status", create_type=False
)
version_author_type = postgresql.ENUM(
    "user", "ai", "system", name="version_author_type", create_type=False
)
fact_category = postgresql.ENUM(
    "problem",
    "contribution",
    "dataset",
    "experiment",
    "evaluation",
    "ethics",
    "other",
    name="fact_category",
    create_type=False,
)
fact_source_type = postgresql.ENUM(
    "user", "ai", "import", "system", name="fact_source_type", create_type=False
)
fact_verification_status = postgresql.ENUM(
    "unverified",
    "verified",
    "disputed",
    name="fact_verification_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    for enum in (
        project_status,
        retention_policy,
        section_type,
        section_status,
        version_author_type,
        fact_category,
        fact_source_type,
        fact_verification_status,
    ):
        enum.create(bind, checkfirst=True)

    op.add_column("projects", sa.Column("slug", sa.String(length=160), nullable=True))
    op.add_column("projects", sa.Column("research_field", sa.String(length=255), nullable=True))
    op.add_column("projects", sa.Column("paper_type", sa.String(length=100), nullable=True))
    op.add_column("projects", sa.Column("target_publisher", sa.String(length=255), nullable=True))
    op.add_column("projects", sa.Column("target_template", sa.String(length=100), nullable=True))
    op.add_column("projects", sa.Column("target_word_count", sa.Integer(), nullable=True))
    op.add_column("projects", sa.Column("intended_submission_date", sa.Date(), nullable=True))
    op.add_column(
        "projects",
        sa.Column("status", project_status, nullable=False, server_default="draft"),
    )
    op.add_column(
        "projects",
        sa.Column(
            "retention_policy",
            retention_policy,
            nullable=False,
            server_default="plan_default",
        ),
    )
    op.add_column("projects", sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("projects", sa.Column("trash_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("projects", sa.Column("purge_after", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "projects",
        sa.Column("legal_hold", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "projects",
        sa.Column("completion_percent", sa.Integer(), nullable=False, server_default="0"),
    )

    op.execute(
        "UPDATE projects SET research_field = research_area "
        "WHERE research_field IS NULL AND research_area IS NOT NULL"
    )
    op.execute(
        "UPDATE projects SET target_template = target_format "
        "WHERE target_template IS NULL AND target_format IS NOT NULL"
    )
    dialect = bind.dialect.name
    if dialect == "postgresql":
        op.execute(
            "UPDATE projects SET slug = lower(substr(replace(title, ' ', '-'), 1, 80)) "
            "|| '-' || substr(replace(id::text, '-', ''), 1, 8) "
            "WHERE slug IS NULL"
        )
        op.execute("UPDATE projects SET slug = 'project-legacy' WHERE slug IS NULL OR slug = ''")
        op.alter_column("projects", "slug", nullable=False)
    else:
        op.execute(
            "UPDATE projects SET slug = lower(substr(replace(title, ' ', '-'), 1, 80)) "
            "|| '-' || substr(replace(cast(id as char), '-', ''), 1, 8) "
            "WHERE slug IS NULL"
        )
        op.execute(
            "UPDATE projects SET slug = 'project-legacy' WHERE slug IS NULL OR slug = ''"
        )
        # SQLite cannot ALTER COLUMN SET NOT NULL; app always writes slug on create.

    op.create_index("ix_projects_slug", "projects", ["slug"])
    op.create_index("ix_projects_status", "projects", ["status"])
    if dialect == "postgresql":
        op.create_unique_constraint("uq_projects_owner_slug", "projects", ["owner_id", "slug"])

    json_type = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")

    op.create_table(
        "manuscripts",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("current_version_id", sa.Uuid(), nullable=True),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.UniqueConstraint("project_id"),
    )
    op.create_index("ix_manuscripts_project_id", "manuscripts", ["project_id"])

    op.create_table(
        "manuscript_versions",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "manuscript_id",
            sa.Uuid(),
            sa.ForeignKey("manuscripts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("snapshot", json_type, nullable=False),
        sa.Column("change_summary", sa.String(length=500), nullable=False),
        sa.Column("created_by_type", version_author_type, nullable=False),
        sa.Column(
            "created_by_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("model_metadata", json_type, nullable=True),
        sa.Column("is_named", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("manuscript_id", "version_number", name="uq_manuscript_version_number"),
    )
    op.create_index("ix_manuscript_versions_manuscript_id", "manuscript_versions", ["manuscript_id"])

    op.create_foreign_key(
        "fk_manuscripts_current_version",
        "manuscripts",
        "manuscript_versions",
        ["current_version_id"],
        ["id"],
    )

    op.create_table(
        "manuscript_sections",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "manuscript_id",
            sa.Uuid(),
            sa.ForeignKey("manuscripts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("section_type", section_type, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("structured_content", json_type, nullable=False),
        sa.Column("plain_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", section_status, nullable=False, server_default="empty"),
        sa.Column("revision_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("manuscript_id", "position", name="uq_section_manuscript_position"),
    )
    op.create_index("ix_manuscript_sections_manuscript_id", "manuscript_sections", ["manuscript_id"])

    op.create_table(
        "project_facts",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", fact_category, nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", json_type, nullable=True),
        sa.Column("source_type", fact_source_type, nullable=False, server_default="user"),
        sa.Column(
            "verification_status",
            fact_verification_status,
            nullable=False,
            server_default="unverified",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "category", "key", name="uq_project_fact_key"),
    )
    op.create_index("ix_project_facts_project_id", "project_facts", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_project_facts_project_id", table_name="project_facts")
    op.drop_table("project_facts")
    op.drop_index("ix_manuscript_sections_manuscript_id", table_name="manuscript_sections")
    op.drop_table("manuscript_sections")
    op.drop_constraint("fk_manuscripts_current_version", "manuscripts", type_="foreignkey")
    op.drop_index("ix_manuscript_versions_manuscript_id", table_name="manuscript_versions")
    op.drop_table("manuscript_versions")
    op.drop_index("ix_manuscripts_project_id", table_name="manuscripts")
    op.drop_table("manuscripts")
    op.drop_constraint("uq_projects_owner_slug", "projects", type_="unique")
    op.drop_index("ix_projects_status", table_name="projects")
    op.drop_index("ix_projects_slug", table_name="projects")
    for col in (
        "completion_percent",
        "legal_hold",
        "purge_after",
        "trash_at",
        "last_activity_at",
        "retention_policy",
        "status",
        "intended_submission_date",
        "target_word_count",
        "target_template",
        "target_publisher",
        "paper_type",
        "research_field",
        "slug",
    ):
        op.drop_column("projects", col)

    bind = op.get_bind()
    for enum in (
        fact_verification_status,
        fact_source_type,
        fact_category,
        version_author_type,
        section_status,
        section_type,
        retention_policy,
        project_status,
    ):
        enum.drop(bind, checkfirst=True)
