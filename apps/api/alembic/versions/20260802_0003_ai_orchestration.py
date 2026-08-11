"""ai jobs proposals and project ai_enabled

Revision ID: 20260802_0003
Revises: 20260802_0002
Create Date: 2026-08-02 18:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260802_0003"
down_revision: Union[str, None] = "20260802_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ai_job_status = postgresql.ENUM(
    "queued",
    "running",
    "completed",
    "failed",
    "cancelled",
    name="ai_job_status",
    create_type=False,
)
ai_operation = postgresql.ENUM(
    "outline",
    "section_questions",
    "draft_section",
    "rewrite_clarity",
    "shorten",
    "expand_with_evidence",
    "missing_information",
    "generate_abstract",
    "generate_limitations",
    "consistency_review",
    name="ai_operation",
    create_type=False,
)
ai_proposal_status = postgresql.ENUM(
    "pending",
    "accepted",
    "partially_accepted",
    "rejected",
    "superseded",
    name="ai_proposal_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    for enum in (ai_job_status, ai_operation, ai_proposal_status):
        enum.create(bind, checkfirst=True)

    op.add_column(
        "projects",
        sa.Column("ai_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )

    json_type = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")

    op.create_table(
        "ai_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("operation", ai_operation, nullable=False),
        sa.Column("status", ai_job_status, nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("progress_events", json_type, nullable=False),
        sa.Column("request_payload", json_type, nullable=False),
        sa.Column("result_payload", json_type, nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("celery_task_id", sa.String(length=255), nullable=True),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("credits_reserved", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("prompt_template_id", sa.String(length=100), nullable=True),
        sa.Column("prompt_version", sa.String(length=40), nullable=True),
        sa.Column("model_name", sa.String(length=255), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_ai_jobs_owner_idempotency"),
    )
    op.create_index("ix_ai_jobs_owner_id", "ai_jobs", ["owner_id"])
    op.create_index("ix_ai_jobs_project_id", "ai_jobs", ["project_id"])
    op.create_index("ix_ai_jobs_status", "ai_jobs", ["status"])

    op.create_table(
        "ai_proposals",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "job_id",
            sa.Uuid(),
            sa.ForeignKey("ai_jobs.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("section_id", sa.Uuid(), nullable=True),
        sa.Column("status", ai_proposal_status, nullable=False),
        sa.Column("original_text", sa.Text(), nullable=False),
        sa.Column("proposed_text", sa.Text(), nullable=False),
        sa.Column("proposed_structured", json_type, nullable=True),
        sa.Column("model_metadata", json_type, nullable=True),
        sa.Column("accepted_text", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
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
    )
    op.create_index("ix_ai_proposals_project_id", "ai_proposals", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_proposals_project_id", table_name="ai_proposals")
    op.drop_table("ai_proposals")
    op.drop_index("ix_ai_jobs_status", table_name="ai_jobs")
    op.drop_index("ix_ai_jobs_project_id", table_name="ai_jobs")
    op.drop_index("ix_ai_jobs_owner_id", table_name="ai_jobs")
    op.drop_table("ai_jobs")
    op.drop_column("projects", "ai_enabled")
    bind = op.get_bind()
    for enum in (ai_proposal_status, ai_operation, ai_job_status):
        enum.drop(bind, checkfirst=True)
