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
    # Set for the contact form so replying goes to the enquirer, not to the
    # verified sending address nobody reads.
    reply_to: str | None = None


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


class ResendEmailProvider:
    """Transactional sending via Resend's HTTP API.

    Chosen over SMTP because it needs no long-lived connection or port access,
    which suits short-lived Fly machines.

    The ``from`` address must sit on a domain verified in Resend (DKIM/SPF
    records); unverified senders are rejected outright.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def send(self, message: OutboundEmail) -> None:
        import httpx

        payload: dict[str, object] = {
            "from": self.settings.email_from,
            "to": [message.to],
            "subject": message.subject,
            "text": message.body,
        }
        if message.reply_to:
            payload["reply_to"] = message.reply_to

        try:
            async with httpx.AsyncClient(timeout=self.settings.email_timeout_seconds) as client:
                response = await client.post(
                    "https://api.resend.com/emails",
                    headers={"Authorization": f"Bearer {self.settings.resend_api_key}"},
                    json=payload,
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            # Deliberately not re-raised as a user-facing failure by callers of
            # registration: a bounced verification email must not roll back an
            # otherwise valid signup. The contact endpoint does surface it.
            logger.error("email_send_failed", to=message.to, error=str(exc))
            raise


_fake_singleton = FakeEmailProvider()


def get_email_provider(settings: Settings | None = None) -> EmailProvider:
    settings = settings or get_settings()
    if settings.app_env == "test" or settings.email_provider == "fake":
        return _fake_singleton
    if settings.email_provider == "resend":
        if not settings.resend_api_key:
            # Degrade rather than fail: a deploy missing the key still serves,
            # and the message lands in the logs where it can be recovered.
            logger.warning("resend_api_key_missing_falling_back_to_console")
            return ConsoleEmailProvider()
        return ResendEmailProvider(settings)
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


async def send_contact_message(
    *,
    name: str,
    email: str,
    message: str,
    settings: Settings | None = None,
) -> None:
    """Deliver a public contact-form enquiry to the team inbox.

    reply_to is the enquirer so a reply goes straight back to them. The from
    address stays on the verified domain — putting the visitor's address there
    would fail SPF and land the mail in spam.
    """
    settings = settings or get_settings()
    await get_email_provider(settings).send(
        OutboundEmail(
            to=settings.contact_recipient,
            subject=f"ResearchForge enquiry from {name}",
            body=f"Name: {name}\nEmail: {email}\n\n{message}",
            reply_to=email,
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
