"""FastAPI dependencies."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated, Any
from uuid import UUID

from fastapi import Cookie, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token, verify_csrf_token
from app.db.session import get_db_session
from app.models.auth_session import AuthSession
from app.models.user import User
from app.services import auth as auth_service
from app.services import sessions as session_service
from app.services.rate_limit import RateLimiter

DbSession = Annotated[AsyncSession, Depends(get_db_session)]
AppSettings = Annotated[Settings, Depends(get_settings)]


async def get_rate_limiter(settings: AppSettings) -> RateLimiter:
    return RateLimiter(settings)


async def enforce_rate_limit(
    request: Request,
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> None:
    client = request.client.host if request.client else "unknown"
    await limiter.check(f"{client}:{request.url.path}")


def rate_limit_dependency(rule_spec: str) -> Any:
    """Create a FastAPI dependency that applies a custom rate-limit rule."""
    from collections.abc import Callable, Coroutine

    from app.services.rate_limit import parse_rate_limit

    rule = parse_rate_limit(rule_spec)

    async def _dep(
        request: Request,
        limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    ) -> None:
        client = request.client.host if request.client else "unknown"
        await limiter.check(f"{client}:{request.url.path}:{rule_spec}", rule=rule)

    _: Callable[..., Coroutine[Any, Any, None]] = _dep
    return _dep


def _extract_access_token(
    settings: Settings,
    access_cookie: str | None,
    authorization: str | None,
) -> str | None:
    if access_cookie:
        return access_cookie
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    return None


async def get_current_user_optional(
    request: Request,
    session: DbSession,
    settings: AppSettings,
    access_cookie: Annotated[str | None, Cookie()] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> User | None:
    # Resolve cookie by configured name (FastAPI Cookie() alias via dynamic lookup)
    cookie_token = request.cookies.get(settings.cookie_access_name) or access_cookie
    token = _extract_access_token(settings, cookie_token, authorization)
    if not token:
        return None
    try:
        payload = decode_access_token(token, settings)
        user_id = UUID(str(payload["sub"]))
        session_id = UUID(str(payload["sid"]))
    except Exception:
        return None

    try:
        user = await auth_service.get_user_by_id(session, user_id)
    except UnauthorizedError:
        return None

    auth_session = await session_service.get_active_session(
        session,
        session_id=session_id,
        user_id=user.id,
    )
    if auth_session is None:
        return None

    await session_service.touch_last_seen(session, session=auth_session, settings=settings)
    request.state.auth_session = auth_session
    request.state.user = user
    return user


async def get_current_user(
    user: Annotated[User | None, Depends(get_current_user_optional)],
) -> User:
    if user is None:
        raise UnauthorizedError("Authentication required")
    return user


async def get_current_session(
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
) -> AuthSession:
    auth_session = getattr(request.state, "auth_session", None)
    if not isinstance(auth_session, AuthSession):
        raise UnauthorizedError("Authentication required")
    return auth_session


async def require_csrf(
    request: Request,
    settings: AppSettings,
    x_csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> None:
    """
    CSRF double-submit for cookie-authenticated mutating requests.

    Browser JS must echo the CSRF cookie into X-CSRF-Token. Relying on the
    cookie alone would not mitigate cross-site form posts.
    """
    import hmac

    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    cookie_token = request.cookies.get(settings.cookie_csrf_name)
    if not x_csrf_token or not cookie_token:
        raise ForbiddenError("CSRF validation failed")
    if not verify_csrf_token(x_csrf_token, settings):
        raise ForbiddenError("CSRF validation failed")
    if not hmac.compare_digest(x_csrf_token, cookie_token):
        raise ForbiddenError("CSRF validation failed")


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_current_user_optional)]
CurrentSession = Annotated[AuthSession, Depends(get_current_session)]


async def db_session_dependency() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db_session():
        yield session


def client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None
