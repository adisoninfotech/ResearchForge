"""Export jobs, artifacts, and short-lived download grants."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ExportArtifactKind, ExportJobStatus, ExportTemplateId

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.user import User

TEMPLATE_COMPATIBILITY_WARNING = (
    "These are compatible starting templates, not officially certified publisher formats. "
    "Authors must verify current journal or conference submission requirements before use."
)


class ExportJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "export_jobs"

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[ExportJobStatus] = mapped_column(
        Enum(
            ExportJobStatus,
            name="export_job_status",
            values_callable=lambda e: [i.value for i in e],
        ),
        nullable=False,
        default=ExportJobStatus.QUEUED,
    )
    template_id: Mapped[ExportTemplateId] = mapped_column(
        Enum(
            ExportTemplateId,
            name="export_template_id",
            values_callable=lambda e: [i.value for i in e],
        ),
        nullable=False,
        default=ExportTemplateId.GENERIC_ACADEMIC,
    )
    template_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0.0")
    requested_outputs: Mapped[list[Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=list,
    )
    options: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=dict,
    )
    validation_issues: Mapped[list[Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=list,
    )
    acknowledged_warnings: Mapped[list[Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=list,
    )
    manuscript_version_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    project: Mapped[Project] = relationship()
    owner: Mapped[User] = relationship()
    artifacts: Mapped[list[ExportArtifact]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
    )
    downloads: Mapped[list[ExportDownload]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
    )


class ExportArtifact(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "export_artifacts"

    job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("export_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[ExportArtifactKind] = mapped_column(
        Enum(
            ExportArtifactKind,
            name="export_artifact_kind",
            values_callable=lambda e: [i.value for i in e],
        ),
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=dict,
    )

    job: Mapped[ExportJob] = relationship(back_populates="artifacts")
    downloads: Mapped[list[ExportDownload]] = relationship(
        back_populates="artifact",
        cascade="all, delete-orphan",
    )


class ExportDownload(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Short-lived authorized download grant for an export artifact."""

    __tablename__ = "export_downloads"

    job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("export_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("export_artifacts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    downloaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    job: Mapped[ExportJob] = relationship(back_populates="downloads")
    artifact: Mapped[ExportArtifact] = relationship(back_populates="downloads")
