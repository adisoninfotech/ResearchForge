"""Evidence links, citation mentions, and claim provenance."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ClaimSupportStatus, EvidenceRelation

if TYPE_CHECKING:
    from app.models.project import Project


class EvidenceLink(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "evidence_links"

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("document_chunks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    section_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    relation: Mapped[EvidenceRelation] = mapped_column(
        Enum(
            EvidenceRelation,
            name="evidence_relation",
            values_callable=lambda e: [i.value for i in e],
        ),
        nullable=False,
        default=EvidenceRelation.SUPPORTS,
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    pinned: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    exclude_from_ai: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    project: Mapped[Project] = relationship()


class CitationMention(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "citation_mentions"

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reference_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("references.id", ondelete="SET NULL"),
        nullable=True,
    )
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("document_chunks.id", ondelete="SET NULL"),
        nullable=True,
    )
    section_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    cite_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    context_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)


class ClaimProvenance(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "claim_provenance"

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    section_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_chunk_ids: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=list,
    )
    support_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    support_status: Mapped[ClaimSupportStatus] = mapped_column(
        Enum(
            ClaimSupportStatus,
            name="claim_support_status",
            values_callable=lambda e: [i.value for i in e],
        ),
        nullable=False,
        default=ClaimSupportStatus.UNSUPPORTED,
    )
    user_verification_status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="unverified",
    )
    citation_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    model_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
    )
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    project: Mapped[Project] = relationship()
