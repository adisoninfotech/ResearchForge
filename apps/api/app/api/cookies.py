"""HTTP-only cookie helpers for access/refresh/CSRF."""

from __future__ import annotations

from typing import Literal

from fastapi import Response

from app.core.config import Settings
from app.services.sessions import IssuedSession


def set_auth_cookies(response: Response, issued: IssuedSession, settings: Settings) -> None:
    samesite: Literal["lax", "strict", "none"] = settings.cookie_samesite
    secure = settings.effective_cookie_secure
    refresh_max_age = (
        (
            settings.remember_me_refresh_token_expire_days
            if issued.session.remember_me
            else settings.refresh_token_expire_days
        )
        * 24
        * 60
        * 60
    )

    response.set_cookie(
        key=settings.cookie_access_name,
        value=issued.access_token,
        max_age=settings.access_token_expire_minutes * 60,
        httponly=True,
        secure=secure,
        samesite=samesite,
        domain=settings.cookie_domain,
        path="/",
    )
    response.set_cookie(
        key=settings.cookie_refresh_name,
        value=issued.refresh_token,
        max_age=refresh_max_age,
        httponly=True,
        secure=secure,
        samesite=samesite,
        domain=settings.cookie_domain,
        path="/api/v1/auth",
    )
    response.set_cookie(
        key=settings.cookie_csrf_name,
        value=issued.csrf_token,
        max_age=refresh_max_age,
        httponly=False,
        secure=secure,
        samesite=samesite,
        domain=settings.cookie_domain,
        path="/",
    )


def clear_auth_cookies(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=settings.cookie_access_name,
        domain=settings.cookie_domain,
        path="/",
    )
    response.delete_cookie(
        key=settings.cookie_refresh_name,
        domain=settings.cookie_domain,
        path="/api/v1/auth",
    )
    response.delete_cookie(
        key=settings.cookie_csrf_name,
        domain=settings.cookie_domain,
        path="/",
    )
