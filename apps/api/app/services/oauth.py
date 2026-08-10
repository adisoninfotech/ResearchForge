"""Optional OAuth provider interface. Google is documented but disabled without credentials."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError


@dataclass(frozen=True)
class OAuthIdentity:
    provider: str
    subject: str
    email: str | None
    display_name: str | None


class OAuthProvider(Protocol):
    name: str

    def is_enabled(self) -> bool: ...

    def authorization_url(self, *, state: str) -> str: ...

    async def exchange_code(self, *, code: str) -> OAuthIdentity: ...


class GoogleOAuthProvider:
    name = "google"

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def is_enabled(self) -> bool:
        return self.settings.google_oauth_is_configured

    def authorization_url(self, *, state: str) -> str:
        if not self.is_enabled():
            raise AppError(
                "Google OAuth is not configured",
                code="oauth_disabled",
                status_code=503,
            )
        from urllib.parse import urlencode

        params = urlencode(
            {
                "client_id": self.settings.google_oauth_client_id,
                "redirect_uri": self.settings.google_oauth_redirect_uri,
                "response_type": "code",
                "scope": "openid email profile",
                "state": state,
                "access_type": "online",
                "prompt": "select_account",
            }
        )
        return f"https://accounts.google.com/o/oauth2/v2/auth?{params}"

    async def exchange_code(self, *, code: str) -> OAuthIdentity:
        if not self.is_enabled():
            raise AppError(
                "Google OAuth is not configured",
                code="oauth_disabled",
                status_code=503,
            )
        raise AppError(
            "Google OAuth token exchange is not enabled in this environment",
            code="oauth_disabled",
            status_code=503,
            details={"hint": "Configure GOOGLE_OAUTH_* and set GOOGLE_OAUTH_ENABLED=true"},
        )


def get_google_oauth_provider(settings: Settings | None = None) -> GoogleOAuthProvider:
    return GoogleOAuthProvider(settings)
