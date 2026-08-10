"""Guided engagement: milestones, daily goals, notifications, analytics, progress."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import AnalyticsEventType, DailyGoalType, MilestoneType, NotificationKind

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.user import User


class NotificationPreference(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """User-controlled notification preferences. Writing reminders off by default."""

    __tablename__ = "notification_preferences"
    __table_args__ = (UniqueConstraint("user_id", name="uq_notification_preferences_user"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Map of NotificationKind.value -> bool
    preferences: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=dict,
    )

    user: Mapped[User] = relationship()


class ProjectMilestone(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "project_milestones"
    __table_args__ = (
        UniqueConstraint("project_id", "milestone_type", name="uq_project_milestone_type"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    milestone_type: Mapped[MilestoneType] = mapped_column(
        Enum(
            MilestoneType,
            name="milestone_type",
            values_callable=lambda e: [i.value for i in e],
        ),
        nullable=False,
    )
    achieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    meta: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=dict,
    )

    project: Mapped[Project] = relationship()


class DailyGoal(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "daily_goals"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "user_id", "goal_date", name="uq_daily_goal_project_user_date"
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    goal_type: Mapped[DailyGoalType] = mapped_column(
        Enum(
            DailyGoalType,
            name="daily_goal_type",
            values_callable=lambda e: [i.value for i in e],
        ),
        nullable=False,
    )
    goal_date: Mapped[date] = mapped_column(Date, nullable=False)
    task_sequence: Mapped[list[Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=list,
    )
    completed_step_ids: Mapped[list[Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=list,
    )
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    project: Mapped[Project] = relationship()
    user: Mapped[User] = relationship()


class ProgressEvent(Base, UUIDPrimaryKeyMixin):
    """Records why the completion score changed (no manuscript text)."""

    __tablename__ = "progress_events"

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    previous_percent: Mapped[int] = mapped_column(Integer, nullable=False)
    new_percent: Mapped[int] = mapped_column(Integer, nullable=False)
    component_scores: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=dict,
    )
    deltas: Mapped[list[Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=list,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    project: Mapped[Project] = relationship()


class AnalyticsEvent(Base, UUIDPrimaryKeyMixin):
    """Privacy-conscious product analytics — never store manuscript content."""

    __tablename__ = "analytics_events"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    event_type: Mapped[AnalyticsEventType] = mapped_column(
        Enum(
            AnalyticsEventType,
            name="analytics_event_type",
            values_callable=lambda e: [i.value for i in e],
        ),
        nullable=False,
        index=True,
    )
    # Allowed: counts, IDs (opaque), booleans, plan names — never titles/text/filenames
    properties: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class InAppNotification(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """User-visible notifications for retention and job completion."""

    __tablename__ = "in_app_notifications"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    kind: Mapped[NotificationKind] = mapped_column(
        Enum(
            NotificationKind,
            name="notification_kind",
            values_callable=lambda e: [i.value for i in e],
        ),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    action_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=dict,
    )
