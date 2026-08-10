"""Auth session lifecycle: create, rotate, revoke, reuse detection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import UnauthorizedError
from app.core.security import (
    create_access_token,
    generate_csrf_token,
    generate_opaque_token,
    hash_ip,
    hash_token,
    sign_csrf_token,
)
from app.core.time import ensure_utc, utcnow
from app.models.auth_session import AuthSession
from app.models.enums import AuditAction
from app.models.user import User
from app.services.audit import record_audit


@dataclass(frozen=True)
class IssuedSession:
    session: AuthSession
    access_token: str
    refresh_token: str
    csrf_token: str


def _expiry(*, remember_me: bool, settings: Settings) -> datetime:
    days = (
        settings.remember_me_refresh_token_expire_days
        if remember_me
        else settings.refresh_token_expire_days
    )
    return utcnow() + timedelta(days=days)


async def create_session(
    db: AsyncSession,
    *,
    user: User,
    remember_me: bool = False,
    device_name: str | None = None,
    user_agent: str | None = None,
    ip: str | None = None,
    settings: Settings | None = None,
) -> IssuedSession:
    settings = settings or get_settings()
    now = utcnow()
    refresh_token = generate_opaque_token()
    session = AuthSession(
        user_id=user.id,
        refresh_token_hash=hash_token(refresh_token),
        previous_refresh_token_hash=None,
        device_name=device_name,
        user_agent=user_agent,
        approximate_ip_hash=hash_ip(ip, settings),
        remember_me=remember_me,
        created_at=now,
        last_seen_at=now,
        expires_at=_expiry(remember_me=remember_me, settings=settings),
        revoked_at=None,
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)

    access = create_access_token(user_id=user.id, session_id=session.id, settings=settings)
    csrf = sign_csrf_token(generate_csrf_token(), settings)
    return IssuedSession(
        session=session,
        access_token=access,
        refresh_token=refresh_token,
        csrf_token=csrf,
    )


async def rotate_refresh_token(
    db: AsyncSession,
    *,
    refresh_token: str,
    user_agent: str | None = None,
    ip: str | None = None,
    settings: Settings | None = None,
) -> IssuedSession:
    settings = settings or get_settings()
    token_hash = hash_token(refresh_token)
    now = utcnow()

    session = await db.scalar(
        select(AuthSession).where(AuthSession.refresh_token_hash == token_hash)
    )

    if session is None:
        # Possible reuse of an already-rotated token
        previous = await db.scalar(
            select(AuthSession).where(AuthSession.previous_refresh_token_hash == token_hash)
        )
        if previous is not None:
            previous.reuse_detected_at = now
            await revoke_all_sessions(db, user_id=previous.user_id)
            await record_audit(
                db,
                action=AuditAction.REFRESH_REUSE,
                user_id=previous.user_id,
                ip_hash=hash_ip(ip, settings),
                user_agent=user_agent,
                metadata={"session_id": str(previous.id)},
            )
            raise UnauthorizedError("Refresh token reuse detected; all sessions revoked")
        raise UnauthorizedError("Invalid refresh token")

    if session.revoked_at is not None or ensure_utc(session.expires_at) <= now:
        raise UnauthorizedError("Session expired or revoked")

    user = await db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("User not found or inactive")

    new_refresh = generate_opaque_token()
    session.previous_refresh_token_hash = session.refresh_token_hash
    session.refresh_token_hash = hash_token(new_refresh)
    session.last_seen_at = now
    session.expires_at = _expiry(remember_me=session.remember_me, settings=settings)
    if user_agent:
        session.user_agent = user_agent
    if ip:
        session.approximate_ip_hash = hash_ip(ip, settings)
    await db.flush()

    access = create_access_token(user_id=user.id, session_id=session.id, settings=settings)
    csrf = sign_csrf_token(generate_csrf_token(), settings)
    await record_audit(
        db,
        action=AuditAction.REFRESH,
        user_id=user.id,
        ip_hash=hash_ip(ip, settings),
        user_agent=user_agent,
        metadata={"session_id": str(session.id)},
    )
    return IssuedSession(
        session=session,
        access_token=access,
        refresh_token=new_refresh,
        csrf_token=csrf,
    )


async def revoke_session(db: AsyncSession, *, session_id: UUID, user_id: UUID) -> bool:
    session = await db.get(AuthSession, session_id)
    if session is None or session.user_id != user_id:
        return False
    if session.revoked_at is None:
        session.revoked_at = utcnow()
        await db.flush()
    return True


async def revoke_all_sessions(
    db: AsyncSession,
    *,
    user_id: UUID,
    except_session_id: UUID | None = None,
) -> int:
    now = utcnow()
    stmt = (
        update(AuthSession)
        .where(
            AuthSession.user_id == user_id,
            AuthSession.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    if except_session_id is not None:
        stmt = stmt.where(AuthSession.id != except_session_id)
    result = await db.execute(stmt)
    return int(getattr(result, "rowcount", 0) or 0)


async def touch_last_seen(
    db: AsyncSession,
    *,
    session: AuthSession,
    settings: Settings | None = None,
) -> None:
    """Update last_seen_at at most once per configured interval."""
    settings = settings or get_settings()
    now = utcnow()
    elapsed = (now - ensure_utc(session.last_seen_at)).total_seconds()
    if elapsed < settings.session_last_seen_min_interval_seconds:
        return
    session.last_seen_at = now
    await db.flush()


async def get_active_session(
    db: AsyncSession,
    *,
    session_id: UUID,
    user_id: UUID,
) -> AuthSession | None:
    session = await db.get(AuthSession, session_id)
    if session is None:
        return None
    if session.user_id != user_id:
        return None
    if session.revoked_at is not None:
        return None
    if ensure_utc(session.expires_at) <= utcnow():
        return None
    return session


async def list_sessions(db: AsyncSession, *, user_id: UUID) -> list[AuthSession]:
    result = await db.scalars(
        select(AuthSession)
        .where(AuthSession.user_id == user_id)
        .order_by(AuthSession.created_at.desc())
    )
    return list(result.all())
