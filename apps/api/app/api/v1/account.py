"""Account settings and session management."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response

from app.api.cookies import clear_auth_cookies
from app.api.deps import (
    AppSettings,
    CurrentSession,
    CurrentUser,
    DbSession,
    client_ip,
    require_csrf,
)
from app.core.exceptions import NotFoundError, ValidationAppError
from app.core.security import hash_ip
from app.models.enums import AuditAction
from app.schemas.auth import (
    DeleteAccountRequest,
    MessageResponse,
    SessionPublic,
    UpdateAccountRequest,
    UserPublic,
)
from app.services import auth as auth_service
from app.services import sessions as session_service
from app.services.audit import record_audit

router = APIRouter(prefix="/account", tags=["account"])


@router.get("/me", response_model=UserPublic)
async def get_account(user: CurrentUser) -> UserPublic:
    return auth_service.user_to_public(user)


@router.patch(
    "/me",
    response_model=UserPublic,
    dependencies=[Depends(require_csrf)],
)
async def update_account(
    payload: UpdateAccountRequest,
    session: DbSession,
    user: CurrentUser,
) -> UserPublic:
    updated = await auth_service.update_account(session, user=user, payload=payload)
    return auth_service.user_to_public(updated)


@router.get("/sessions", response_model=list[SessionPublic])
async def list_sessions(
    session: DbSession,
    user: CurrentUser,
    current: CurrentSession,
) -> list[SessionPublic]:
    rows = await session_service.list_sessions(session, user_id=user.id)
    return [
        SessionPublic(
            id=row.id,
            device_name=row.device_name,
            user_agent=row.user_agent,
            remember_me=row.remember_me,
            created_at=row.created_at,
            last_seen_at=row.last_seen_at,
            expires_at=row.expires_at,
            revoked_at=row.revoked_at,
            is_current=row.id == current.id,
        )
        for row in rows
        if row.revoked_at is None
    ]


@router.post(
    "/sessions/{session_id}/revoke",
    response_model=MessageResponse,
    dependencies=[Depends(require_csrf)],
)
async def revoke_session(
    session_id: UUID,
    request: Request,
    session: DbSession,
    settings: AppSettings,
    user: CurrentUser,
) -> MessageResponse:
    ok = await session_service.revoke_session(session, session_id=session_id, user_id=user.id)
    if not ok:
        raise NotFoundError("Session not found")
    await record_audit(
        session,
        action=AuditAction.REVOKE_SESSION,
        user_id=user.id,
        ip_hash=hash_ip(client_ip(request), settings),
        user_agent=request.headers.get("User-Agent"),
        metadata={"session_id": str(session_id)},
    )
    return MessageResponse(message="Session revoked")


@router.post(
    "/sessions/revoke-others",
    response_model=MessageResponse,
    dependencies=[Depends(require_csrf)],
)
async def revoke_other_sessions(
    request: Request,
    session: DbSession,
    settings: AppSettings,
    user: CurrentUser,
    current: CurrentSession,
) -> MessageResponse:
    count = await session_service.revoke_all_sessions(
        session,
        user_id=user.id,
        except_session_id=current.id,
    )
    await record_audit(
        session,
        action=AuditAction.REVOKE_OTHER_SESSIONS,
        user_id=user.id,
        ip_hash=hash_ip(client_ip(request), settings),
        user_agent=request.headers.get("User-Agent"),
        metadata={"revoked_count": count},
    )
    return MessageResponse(message=f"Revoked {count} other session(s)")


@router.get("/export")
async def export_account_data(
    request: Request,
    session: DbSession,
    settings: AppSettings,
    user: CurrentUser,
) -> dict[str, Any]:
    """Portable JSON export of the authenticated user's account and projects."""
    from app.services.account_export import build_user_export

    return await build_user_export(
        session,
        user=user,
        ip_hash=hash_ip(client_ip(request), settings),
        user_agent=request.headers.get("User-Agent"),
    )


@router.post(
    "/delete",
    response_model=MessageResponse,
    dependencies=[Depends(require_csrf)],
)
async def delete_account(
    payload: DeleteAccountRequest,
    request: Request,
    response: Response,
    session: DbSession,
    settings: AppSettings,
    user: CurrentUser,
) -> MessageResponse:
    if payload.confirmation != "DELETE":
        raise ValidationAppError('Confirmation must be the string "DELETE"')
    await auth_service.delete_account(
        session,
        user=user,
        password=payload.password,
        settings=settings,
        ip=client_ip(request),
        user_agent=request.headers.get("User-Agent"),
    )
    clear_auth_cookies(response, settings)
    return MessageResponse(message="Account deleted")
