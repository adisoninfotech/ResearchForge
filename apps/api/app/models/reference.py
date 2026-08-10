"""Bibliographic references and identifiers."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
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
from app.models.enums import ReferenceVerificationStatus

if TYPE_CHECKING:
    from app.models.project import Project


class Reference(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "references"
    __table_args__ = (
        UniqueConstraint("project_id", "fingerprint", name="uq_reference_fingerprint"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    venue: Mapped[str | None] = mapped_column(String(500), nullable=True)
    url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    doi: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    verification_status: Mapped[ReferenceVerificationStatus] = mapped_column(
        Enum(
            ReferenceVerificationStatus,
            name="reference_verification_status",
            values_callable=lambda e: [i.value for i in e],
        ),
        nullable=False,
        default=ReferenceVerificationStatus.UNVERIFIED,
    )
    source_file_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("project_files.id", ondelete="SET NULL"),
        nullable=True,
    )
    raw_bibtex: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
    )
    needs_user_correction: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    project: Mapped[Project] = relationship()
    authors: Mapped[list[ReferenceAuthor]] = relationship(
        back_populates="reference",
        cascade="all, delete-orphan",
        order_by="ReferenceAuthor.position",
    )
    identifiers: Mapped[list[ReferenceIdentifier]] = relationship(
        back_populates="reference",
        cascade="all, delete-orphan",
    )


class ReferenceAuthor(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "reference_authors"

    reference_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("references.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    full_name: Mapped[str] = mapped_column(String(500), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    reference: Mapped[Reference] = relationship(back_populates="authors")


class ReferenceIdentifier(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "reference_identifiers"
    __table_args__ = (
        UniqueConstraint("reference_id", "id_type", "value", name="uq_reference_identifier"),
    )

    reference_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("references.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    id_type: Mapped[str] = mapped_column(String(40), nullable=False)  # doi, isbn, arxiv, ...
    value: Mapped[str] = mapped_column(String(255), nullable=False)

    reference: Mapped[Reference] = relationship(back_populates="identifiers")
