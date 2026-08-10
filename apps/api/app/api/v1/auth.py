"""Authentication endpoints with rotating refresh sessions."""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, Request, Response

from app.api.cookies import clear_auth_cookies, set_auth_cookies
from app.api.deps import (
    AppSettings,
    CurrentSession,
    CurrentUser,
    DbSession,
    client_ip,
    enforce_rate_limit,
    rate_limit_dependency,
    require_csrf,
)
from app.core.exceptions import AppError
from app.core.security import hash_ip
from app.core.security_hardening import (
    AUTH_LOGIN_RATE,
    AUTH_PASSWORD_RESET_RATE,
    AUTH_REGISTER_RATE,
)
from app.models.enums import AuditAction
from app.schemas.auth import (
    AuthResponse,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    OAuthStatusResponse,
    RegisterRequest,
    ResetPasswordRequest,
    UserPublic,
    VerifyEmailRequest,
)
from app.services import auth as auth_service
from app.services import sessions as session_service
from app.services.audit import record_audit
from app.services.oauth import get_google_oauth_provider

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=AuthResponse,
    dependencies=[Depends(rate_limit_dependency(AUTH_REGISTER_RATE))],
)
async def register(
    payload: RegisterRequest,
    response: Response,
    request: Request,
    session: DbSession,
    settings: AppSettings,
) -> AuthResponse:
    user, issued, _verification = await auth_service.register_user(
        session,
        payload,
        settings=settings,
        ip=client_ip(request),
        user_agent=request.headers.get("User-Agent"),
    )
    set_auth_cookies(response, issued, settings)
    return AuthResponse(
        user=auth_service.user_to_public(user),
        message="Registration successful. Please verify your email.",
        csrf_token=issued.csrf_token,
    )


@router.post(
    "/login",
    response_model=AuthResponse,
    dependencies=[Depends(rate_limit_dependency(AUTH_LOGIN_RATE))],
)
async def login(
    payload: LoginRequest,
    response: Response,
    request: Request,
    session: DbSession,
    settings: AppSettings,
) -> AuthResponse:
    user, issued = await auth_service.authenticate_user(
        session,
        payload,
        settings=settings,
        ip=client_ip(request),
        user_agent=request.headers.get("User-Agent"),
    )
    set_auth_cookies(response, issued, settings)
    return AuthResponse(
        user=auth_service.user_to_public(user),
        message="Login successful",
        csrf_token=issued.csrf_token,
    )


@router.post(
    "/logout",
    response_model=MessageResponse,
    dependencies=[Depends(require_csrf)],
)
async def logout(
    response: Response,
    request: Request,
    session: DbSession,
    settings: AppSettings,
    user: CurrentUser,
    auth_session: CurrentSession,
) -> MessageResponse:
    await session_service.revoke_session(session, session_id=auth_session.id, user_id=user.id)
    await record_audit(
        session,
        action=AuditAction.LOGOUT,
        user_id=user.id,
        ip_hash=hash_ip(client_ip(request), settings),
        user_agent=request.headers.get("User-Agent"),
        metadata={"session_id": str(auth_session.id)},
    )
    clear_auth_cookies(response, settings)
    return MessageResponse(message="Logged out")


@router.post(
    "/refresh",
    response_model=AuthResponse,
    dependencies=[Depends(enforce_rate_limit)],
)
async def refresh(
    response: Response,
    request: Request,
    session: DbSession,
    settings: AppSettings,
) -> AuthResponse:
    refresh_token = request.cookies.get(settings.cookie_refresh_name)
    if not refresh_token:
        from app.core.exceptions import UnauthorizedError

        raise UnauthorizedError("Refresh token missing")

    issued = await session_service.rotate_refresh_token(
        session,
        refresh_token=refresh_token,
        user_agent=request.headers.get("User-Agent"),
        ip=client_ip(request),
        settings=settings,
    )
    user = await auth_service.get_user_by_id(session, issued.session.user_id)
    set_auth_cookies(response, issued, settings)
    return AuthResponse(
        user=auth_service.user_to_public(user),
        message="Session refreshed",
        csrf_token=issued.csrf_token,
    )


@router.get("/me", response_model=UserPublic)
async def me(user: CurrentUser) -> UserPublic:
    return auth_service.user_to_public(user)


@router.post(
    "/verify-email",
    response_model=MessageResponse,
    dependencies=[Depends(enforce_rate_limit)],
)
async def verify_email(payload: VerifyEmailRequest, session: DbSession) -> MessageResponse:
    await auth_service.verify_email(session, token=payload.token)
    return MessageResponse(message="Email verified")


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    dependencies=[Depends(rate_limit_dependency(AUTH_PASSWORD_RESET_RATE))],
)
async def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    session: DbSession,
    settings: AppSettings,
) -> MessageResponse:
    result = await auth_service.request_password_reset(
        session,
        email=payload.email,
        settings=settings,
        ip=client_ip(request),
        user_agent=request.headers.get("User-Agent"),
    )
    return MessageResponse(message=result["message"])


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    dependencies=[Depends(rate_limit_dependency(AUTH_PASSWORD_RESET_RATE))],
)
async def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    response: Response,
    session: DbSession,
    settings: AppSettings,
) -> MessageResponse:
    await auth_service.reset_password(
        session,
        token=payload.token,
        new_password=payload.new_password,
        settings=settings,
        ip=client_ip(request),
        user_agent=request.headers.get("User-Agent"),
    )
    clear_auth_cookies(response, settings)
    return MessageResponse(message="Password reset successful. Please sign in again.")


@router.get("/oauth/status", response_model=OAuthStatusResponse)
async def oauth_status(settings: AppSettings) -> OAuthStatusResponse:
    provider = get_google_oauth_provider(settings)
    if not provider.is_enabled():
        return OAuthStatusResponse(google_enabled=False, google_authorization_url=None)
    state = str(uuid4())
    return OAuthStatusResponse(
        google_enabled=True,
        google_authorization_url=provider.authorization_url(state=state),
    )


@router.get("/oauth/google/start")
async def oauth_google_start(settings: AppSettings) -> dict[str, str]:
    provider = get_google_oauth_provider(settings)
    if not provider.is_enabled():
        raise AppError(
            "Google OAuth is disabled. Set GOOGLE_OAUTH_ENABLED=true and provide credentials.",
            code="oauth_disabled",
            status_code=503,
        )
    state = str(uuid4())
    return {"authorization_url": provider.authorization_url(state=state), "state": state}
