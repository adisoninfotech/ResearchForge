"""Manuscript, sections, and version history models."""

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
from app.models.enums import SectionStatus, SectionType, VersionAuthorType

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.user import User


class Manuscript(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "manuscripts"

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("manuscript_versions.id", use_alter=True, name="fk_manuscripts_current_version"),
        nullable=True,
    )
    schema_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    project: Mapped[Project] = relationship(back_populates="manuscript")
    sections: Mapped[list[ManuscriptSection]] = relationship(
        back_populates="manuscript",
        cascade="all, delete-orphan",
        order_by="ManuscriptSection.position",
    )
    versions: Mapped[list[ManuscriptVersion]] = relationship(
        back_populates="manuscript",
        cascade="all, delete-orphan",
        foreign_keys="ManuscriptVersion.manuscript_id",
        order_by="ManuscriptVersion.version_number",
    )


class ManuscriptSection(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "manuscript_sections"
    __table_args__ = (
        UniqueConstraint("manuscript_id", "position", name="uq_section_manuscript_position"),
    )

    manuscript_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("manuscripts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    section_type: Mapped[SectionType] = mapped_column(
        Enum(SectionType, name="section_type", values_callable=lambda e: [i.value for i in e]),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    structured_content: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=dict,
    )
    plain_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[SectionStatus] = mapped_column(
        Enum(SectionStatus, name="section_status", values_callable=lambda e: [i.value for i in e]),
        nullable=False,
        default=SectionStatus.EMPTY,
    )
    revision_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    manuscript: Mapped[Manuscript] = relationship(back_populates="sections")


class ManuscriptVersion(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "manuscript_versions"
    __table_args__ = (
        UniqueConstraint("manuscript_id", "version_number", name="uq_manuscript_version_number"),
    )

    manuscript_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("manuscripts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
    )
    change_summary: Mapped[str] = mapped_column(String(500), nullable=False)
    created_by_type: Mapped[VersionAuthorType] = mapped_column(
        Enum(
            VersionAuthorType,
            name="version_author_type",
            values_callable=lambda e: [i.value for i in e],
        ),
        nullable=False,
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    model_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
    )
    is_named: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    manuscript: Mapped[Manuscript] = relationship(
        back_populates="versions",
        foreign_keys=[manuscript_id],
    )
    created_by_user: Mapped[User | None] = relationship()
