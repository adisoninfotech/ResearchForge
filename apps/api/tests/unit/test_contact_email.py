"""Unit tests for contact-form delivery and the Resend provider selection."""

from __future__ import annotations

import pytest
from app.core.config import Settings
from app.services import email as email_service


def _settings(**kwargs: object) -> Settings:
    base: dict[str, object] = {"secret_key": "x" * 16, "csrf_secret": "y" * 16}
    base.update(kwargs)
    return Settings(**base)  # type: ignore[arg-type]


@pytest.mark.unit
def test_console_provider_when_selected() -> None:
    # email_provider is passed explicitly: the test suite exports
    # EMAIL_PROVIDER=fake, which Settings would otherwise pick up from the
    # environment and return the fake singleton instead.
    provider = email_service.get_email_provider(
        _settings(app_env="production", email_provider="console")
    )
    assert isinstance(provider, email_service.ConsoleEmailProvider)


@pytest.mark.unit
def test_resend_selected_when_configured() -> None:
    provider = email_service.get_email_provider(
        _settings(app_env="production", email_provider="resend", resend_api_key="re_test_key")
    )
    assert isinstance(provider, email_service.ResendEmailProvider)


@pytest.mark.unit
def test_resend_without_key_degrades_to_console() -> None:
    """A deploy missing the key must still serve rather than 500 on signup."""
    provider = email_service.get_email_provider(
        _settings(app_env="production", email_provider="resend", resend_api_key="")
    )
    assert isinstance(provider, email_service.ConsoleEmailProvider)


@pytest.mark.unit
async def test_contact_message_targets_inbox_and_replies_to_sender() -> None:
    settings = _settings(app_env="test", contact_recipient="info@example.com")
    fake = email_service.reset_fake_email_provider()

    await email_service.send_contact_message(
        name="Jane Okafor",
        email="jane@university.ac.uk",
        message="Do you support institutional licences?",
        settings=settings,
    )

    assert len(fake.messages) == 1
    sent = fake.messages[0]
    assert sent.to == "info@example.com"
    # Reply-To is the enquirer, so hitting reply reaches them rather than the
    # noreply sending address.
    assert sent.reply_to == "jane@university.ac.uk"
    assert "Jane Okafor" in sent.subject
    assert "Do you support institutional licences?" in sent.body
    assert "jane@university.ac.uk" in sent.body
