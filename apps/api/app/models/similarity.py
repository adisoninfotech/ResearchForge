"""Similarity jobs, reports, findings, sources, coverage, and resolutions."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import (
    FindingResolutionAction,
    SimilarityFindingClass,
    SimilarityJobStatus,
    SimilaritySourceKind,
)

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.user import User

SAFE_OVERLAP_SUMMARY = "No significant textual overlap was identified within the sources checked."
HUMAN_REVIEW_DISCLAIMER = (
    "This report is an advisory textual-overlap and citation-risk review. "
    "It does not guarantee originality, does not claim zero plagiarism, "
    "and is not equivalent to Turnitin or iThenticate. Human review is required."
)


class SimilarityJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "similarity_jobs"

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
    status: Mapped[SimilarityJobStatus] = mapped_column(
        Enum(
            SimilarityJobStatus,
            name="similarity_job_status",
            values_callable=lambda e: [i.value for i in e],
        ),
        nullable=False,
        default=SimilarityJobStatus.QUEUED,
    )
    options: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=dict,
    )
    threshold_profile: Mapped[str] = mapped_column(String(64), nullable=False, default="default")
    algorithm_versions: Mapped[dict[str, str]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=dict,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped[Project] = relationship()
    owner: Mapped[User] = relationship()
    report: Mapped[SimilarityReport | None] = relationship(
        back_populates="job",
        uselist=False,
        cascade="all, delete-orphan",
    )


class SimilarityReport(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "similarity_reports"

    job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("similarity_jobs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False, default="low")
    section_summaries: Mapped[list[Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=list,
    )
    method_explanations: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=dict,
    )
    footer: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=dict,
    )
    finding_counts: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=dict,
    )
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False, default="")

    job: Mapped[SimilarityJob] = relationship(back_populates="report")
    findings: Mapped[list[SimilarityFinding]] = relationship(
        back_populates="report",
        cascade="all, delete-orphan",
    )
    sources: Mapped[list[SimilaritySource]] = relationship(
        back_populates="report",
        cascade="all, delete-orphan",
    )
    coverage: Mapped[ReportCoverage | None] = relationship(
        back_populates="report",
        uselist=False,
        cascade="all, delete-orphan",
    )


class SimilaritySource(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "similarity_sources"

    report_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("similarity_reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[SimilaritySourceKind] = mapped_column(
        Enum(
            SimilaritySourceKind,
            name="similarity_source_kind",
            values_callable=lambda e: [i.value for i in e],
        ),
        nullable=False,
    )
    label: Mapped[str] = mapped_column(String(500), nullable=False)
    project_file_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    manuscript_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    section_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
    )
    checked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    unavailable_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    report: Mapped[SimilarityReport] = relationship(back_populates="sources")


class ReportCoverage(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "report_coverage"

    report_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("similarity_reports.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    sources_checked: Mapped[list[Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=list,
    )
    sources_not_checked: Mapped[list[Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=list,
    )
    limitations: Mapped[list[Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=list,
    )
    open_corpus_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    licensed_provider_status: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="not_configured",
    )

    report: Mapped[SimilarityReport] = relationship(back_populates="coverage")


class SimilarityFinding(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "similarity_findings"

    report_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("similarity_reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    section_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    classification: Mapped[SimilarityFindingClass] = mapped_column(
        Enum(
            SimilarityFindingClass,
            name="similarity_finding_class",
            values_callable=lambda e: [i.value for i in e],
        ),
        nullable=False,
    )
    manuscript_text: Mapped[str] = mapped_column(Text, nullable=False)
    manuscript_start: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    manuscript_end: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("similarity_sources.id", ondelete="SET NULL"),
        nullable=True,
    )
    methods: Mapped[list[Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=list,
    )
    scores: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=dict,
    )
    citation_present: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    citation_keys: Mapped[list[Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=list,
    )
    recommended_action: Mapped[str] = mapped_column(Text, nullable=False, default="")
    explanation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    excluded_by_filter: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    report: Mapped[SimilarityReport] = relationship(back_populates="findings")
    resolution: Mapped[FindingResolution | None] = relationship(
        back_populates="finding",
        uselist=False,
        cascade="all, delete-orphan",
    )


class FindingResolution(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "finding_resolutions"

    finding_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("similarity_findings.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    action: Mapped[FindingResolutionAction] = mapped_column(
        Enum(
            FindingResolutionAction,
            name="finding_resolution_action",
            values_callable=lambda e: [i.value for i in e],
        ),
        nullable=False,
        default=FindingResolutionAction.UNRESOLVED,
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    rewrite_original: Mapped[str | None] = mapped_column(Text, nullable=True)
    rewrite_proposed: Mapped[str | None] = mapped_column(Text, nullable=True)
    rewrite_accepted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rewrite_diff: Mapped[list[Any] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
    )
    resolved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    finding: Mapped[SimilarityFinding] = relationship(back_populates="resolution")
