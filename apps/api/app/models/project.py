"""Project ORM model — private by default; ownership via owner_id."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

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
from app.models.enums import ProjectStatus, RetentionPolicy

if TYPE_CHECKING:
    from app.models.manuscript import Manuscript
    from app.models.project_fact import ProjectFact
    from app.models.user import User


class Project(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "guest_conversion_key",
            name="uq_projects_owner_guest_conversion_key",
        ),
        UniqueConstraint("owner_id", "slug", name="uq_projects_owner_slug"),
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    slug: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    research_field: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Legacy guest-compat field; mirrored into research_field when set.
    research_area: Mapped[str | None] = mapped_column(String(255), nullable=True)
    paper_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    target_publisher: Mapped[str | None] = mapped_column(String(255), nullable=True)
    target_template: Mapped[str | None] = mapped_column(String(100), nullable=True)
    target_format: Mapped[str | None] = mapped_column(String(100), nullable=True)
    target_word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    intended_submission_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    research_problem: Mapped[str | None] = mapped_column(Text, nullable=True)
    proposed_contribution: Mapped[str | None] = mapped_column(Text, nullable=True)
    outline: Mapped[list[object] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
    )
    draft_content: Mapped[dict[str, object] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
    )
    authors: Mapped[list[object]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=list,
    )
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus, name="project_status", values_callable=lambda e: [i.value for i in e]),
        nullable=False,
        default=ProjectStatus.DRAFT,
        server_default=ProjectStatus.DRAFT.value,
        index=True,
    )
    retention_policy: Mapped[RetentionPolicy] = mapped_column(
        Enum(
            RetentionPolicy,
            name="retention_policy",
            values_callable=lambda e: [i.value for i in e],
        ),
        nullable=False,
        default=RetentionPolicy.PLAN_DEFAULT,
        server_default=RetentionPolicy.PLAN_DEFAULT.value,
    )
    last_activity_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    trash_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    purge_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status_before_trash: Mapped[str | None] = mapped_column(String(32), nullable=True)
    deletion_notice_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    legal_hold: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_private: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    contains_synthetic_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    transferred_from_guest: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    guest_conversion_key: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    completion_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    owner: Mapped[User] = relationship(back_populates="projects")
    manuscript: Mapped[Manuscript | None] = relationship(
        back_populates="project",
        uselist=False,
        cascade="all, delete-orphan",
    )
    facts: Mapped[list[ProjectFact]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
