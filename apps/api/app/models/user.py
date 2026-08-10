"""User ORM model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import SubscriptionPlan, UserStatus

if TYPE_CHECKING:
    from app.models.auth_session import AuthSession
    from app.models.oauth_account import OAuthAccount
    from app.models.project import Project


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    # Stored normalized (lowercase) for case-insensitive uniqueness.
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="user_status", values_callable=lambda e: [i.value for i in e]),
        nullable=False,
        default=UserStatus.ACTIVE,
        server_default=UserStatus.ACTIVE.value,
    )
    subscription_plan: Mapped[SubscriptionPlan] = mapped_column(
        Enum(
            SubscriptionPlan,
            name="subscription_plan",
            values_callable=lambda e: [i.value for i in e],
        ),
        nullable=False,
        default=SubscriptionPlan.FREE,
        server_default=SubscriptionPlan.FREE.value,
    )
    training_opt_in: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    privacy_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    projects: Mapped[list[Project]] = relationship(back_populates="owner", lazy="selectin")
    sessions: Mapped[list[AuthSession]] = relationship(back_populates="user", lazy="selectin")
    oauth_accounts: Mapped[list[OAuthAccount]] = relationship(
        back_populates="user",
        lazy="selectin",
    )

    @property
    def is_active(self) -> bool:
        return self.status == UserStatus.ACTIVE and self.deleted_at is None
