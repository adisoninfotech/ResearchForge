"""Durable AI job and proposal models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
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
from app.models.enums import AIJobStatus, AIOperation, AIProposalStatus

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.user import User


class AIJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "ai_jobs"
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_ai_jobs_owner_idempotency"),
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
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
    operation: Mapped[AIOperation] = mapped_column(
        Enum(AIOperation, name="ai_operation", values_callable=lambda e: [i.value for i in e]),
        nullable=False,
    )
    status: Mapped[AIJobStatus] = mapped_column(
        Enum(AIJobStatus, name="ai_job_status", values_callable=lambda e: [i.value for i in e]),
        nullable=False,
        default=AIJobStatus.QUEUED,
        index=True,
    )
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    progress_events: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=list,
    )
    request_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=dict,
    )
    result_payload: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
    )
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    credits_reserved: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    prompt_template_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    owner: Mapped[User] = relationship()
    project: Mapped[Project | None] = relationship()
    proposal: Mapped[AIProposal | None] = relationship(
        back_populates="job",
        uselist=False,
        cascade="all, delete-orphan",
    )


class AIProposal(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "ai_proposals"

    job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ai_jobs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    section_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    status: Mapped[AIProposalStatus] = mapped_column(
        Enum(
            AIProposalStatus,
            name="ai_proposal_status",
            values_callable=lambda e: [i.value for i in e],
        ),
        nullable=False,
        default=AIProposalStatus.PENDING,
    )
    original_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    proposed_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    proposed_structured: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
    )
    model_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
    )
    accepted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    job: Mapped[AIJob] = relationship(back_populates="proposal")
    project: Mapped[Project] = relationship()
