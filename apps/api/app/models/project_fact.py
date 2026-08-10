"""Structured research completeness facts for a project."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.db.base import Base, UUIDPrimaryKeyMixin
from app.models.enums import FactCategory, FactSourceType, FactVerificationStatus

if TYPE_CHECKING:
    from app.models.project import Project


class ProjectFact(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "project_facts"
    __table_args__ = (
        UniqueConstraint("project_id", "category", "key", name="uq_project_fact_key"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category: Mapped[FactCategory] = mapped_column(
        Enum(FactCategory, name="fact_category", values_callable=lambda e: [i.value for i in e]),
        nullable=False,
    )
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[dict[str, Any] | list[Any] | str | int | float | bool | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
    )
    source_type: Mapped[FactSourceType] = mapped_column(
        Enum(
            FactSourceType,
            name="fact_source_type",
            values_callable=lambda e: [i.value for i in e],
        ),
        nullable=False,
        default=FactSourceType.USER,
    )
    verification_status: Mapped[FactVerificationStatus] = mapped_column(
        Enum(
            FactVerificationStatus,
            name="fact_verification_status",
            values_callable=lambda e: [i.value for i in e],
        ),
        nullable=False,
        default=FactVerificationStatus.UNVERIFIED,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    project: Mapped[Project] = relationship(back_populates="facts")
