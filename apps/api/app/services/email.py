"""Transactional email abstraction — console/fake providers (no secrets required)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class OutboundEmail:
    to: str
    subject: str
    body: str


class EmailProvider(Protocol):
    async def send(self, message: OutboundEmail) -> None: ...


@dataclass
class FakeEmailProvider:
    """In-memory capture for automated tests."""

    messages: list[OutboundEmail] = field(default_factory=list)

    async def send(self, message: OutboundEmail) -> None:
        self.messages.append(message)


class ConsoleEmailProvider:
    async def send(self, message: OutboundEmail) -> None:
        logger.info(
            "email_sent",
            to=message.to,
            subject=message.subject,
            body_preview=message.body[:240],
        )


_fake_singleton = FakeEmailProvider()


def get_email_provider(settings: Settings | None = None) -> EmailProvider:
    settings = settings or get_settings()
    if settings.app_env == "test" or settings.email_provider == "fake":
        return _fake_singleton
    return ConsoleEmailProvider()


def reset_fake_email_provider() -> FakeEmailProvider:
    _fake_singleton.messages.clear()
    return _fake_singleton


async def send_verification_email(
    *,
    to: str,
    token: str,
    settings: Settings | None = None,
) -> None:
    settings = settings or get_settings()
    link = f"{settings.public_app_url.rstrip('/')}/verify-email?token={token}"
    await get_email_provider(settings).send(
        OutboundEmail(
            to=to,
            subject="Verify your ResearchForge email",
            body=f"Verify your email by opening: {link}",
        )
    )


async def send_password_reset_email(
    *,
    to: str,
    token: str,
    settings: Settings | None = None,
) -> None:
    settings = settings or get_settings()
    link = f"{settings.public_app_url.rstrip('/')}/reset-password?token={token}"
    await get_email_provider(settings).send(
        OutboundEmail(
            to=to,
            subject="Reset your ResearchForge password",
            body=f"Reset your password by opening: {link}",
        )
    )


async def send_pending_deletion_email(
    *,
    to: str,
    project_title: str,
    purge_after_iso: str,
    settings: Settings | None = None,
) -> None:
    """Abstraction for pre-purge retention notifications."""
    settings = settings or get_settings()
    trash_url = f"{settings.public_app_url.rstrip('/')}/dashboard?status=trash"
    await get_email_provider(settings).send(
        OutboundEmail(
            to=to,
            subject=f"ResearchForge: “{project_title}” will be permanently deleted",
            body=(
                f"Your project “{project_title}” is scheduled for permanent deletion "
                f"after {purge_after_iso}. Restore it from Trash before then: {trash_url}"
            ),
        )
    )
