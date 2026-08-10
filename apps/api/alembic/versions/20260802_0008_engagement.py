"""guided ethical engagement system

Revision ID: 20260802_0008
Revises: 20260802_0007
Create Date: 2026-08-02 24:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260802_0008"
down_revision: Union[str, None] = "20260802_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

milestone_type = sa.Enum(
    "research_plan_approved",
    "first_section_completed",
    "dataset_added",
    "first_analysis_completed",
    "all_citations_verified",
    "all_figures_resolved",
    "integrity_review_completed",
    "first_full_draft_completed",
    "submission_package_generated",
    name="milestone_type",
)
daily_goal_type = sa.Enum(
    "complete_a_section",
    "verify_references",
    "analyze_a_dataset",
    "resolve_similarity_findings",
    "create_figures",
    "prepare_export",
    name="daily_goal_type",
)
notification_kind = sa.Enum(
    "draft_scheduled_for_deletion",
    "trash_expiration",
    "collaborator_activity",
    "export_completed",
    "similarity_report_completed",
    "submission_date_approaching",
    "weekly_project_summary",
    "writing_reminders",
    name="notification_kind",
)
analytics_event_type = sa.Enum(
    "account_created",
    "project_created",
    "section_completed",
    "export_requested",
    "draft_converted_from_guest",
    "similarity_report_completed",
    "dataset_analyzed",
    name="analytics_event_type",
)


def upgrade() -> None:
    bind = op.get_bind()
    for enum in (milestone_type, daily_goal_type, notification_kind, analytics_event_type):
        enum.create(bind, checkfirst=True)

    json_type = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")

    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("preferences", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", name="uq_notification_preferences_user"),
    )
    op.create_index("ix_notification_preferences_user_id", "notification_preferences", ["user_id"])

    op.create_table(
        "project_milestones",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("milestone_type", milestone_type, nullable=False),
        sa.Column("achieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("meta", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "milestone_type", name="uq_project_milestone_type"),
    )
    op.create_index("ix_project_milestones_project_id", "project_milestones", ["project_id"])

    op.create_table(
        "daily_goals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("goal_type", daily_goal_type, nullable=False),
        sa.Column("goal_date", sa.Date(), nullable=False),
        sa.Column("task_sequence", json_type, nullable=False),
        sa.Column("completed_step_ids", json_type, nullable=False),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "project_id", "user_id", "goal_date", name="uq_daily_goal_project_user_date"
        ),
    )
    op.create_index("ix_daily_goals_project_id", "daily_goals", ["project_id"])
    op.create_index("ix_daily_goals_user_id", "daily_goals", ["user_id"])

    op.create_table(
        "progress_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("previous_percent", sa.Integer(), nullable=False),
        sa.Column("new_percent", sa.Integer(), nullable=False),
        sa.Column("component_scores", json_type, nullable=False),
        sa.Column("deltas", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_progress_events_project_id", "progress_events", ["project_id"])

    op.create_table(
        "analytics_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_type", analytics_event_type, nullable=False),
        sa.Column("properties", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_analytics_events_user_id", "analytics_events", ["user_id"])
    op.create_index("ix_analytics_events_project_id", "analytics_events", ["project_id"])
    op.create_index("ix_analytics_events_event_type", "analytics_events", ["event_type"])

    op.create_table(
        "in_app_notifications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True),
        sa.Column("kind", notification_kind, nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("read", sa.Boolean(), nullable=False),
        sa.Column("action_url", sa.String(500), nullable=True),
        sa.Column("meta", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_in_app_notifications_user_id", "in_app_notifications", ["user_id"])
    op.create_index("ix_in_app_notifications_project_id", "in_app_notifications", ["project_id"])


def downgrade() -> None:
    op.drop_table("in_app_notifications")
    op.drop_table("analytics_events")
    op.drop_table("progress_events")
    op.drop_table("daily_goals")
    op.drop_table("project_milestones")
    op.drop_table("notification_preferences")
    bind = op.get_bind()
    for enum in (analytics_event_type, notification_kind, daily_goal_type, milestone_type):
        enum.drop(bind, checkfirst=True)
