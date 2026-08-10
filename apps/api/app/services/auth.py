"""Authentication and account lifecycle services."""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import ConflictError, UnauthorizedError, ValidationAppError
from app.core.security import (
    generate_opaque_token,
    hash_ip,
    hash_password,
    hash_token,
    needs_rehash,
    verify_password,
)
from app.core.time import ensure_utc, utcnow
from app.models.email_verification import EmailVerificationToken
from app.models.enums import AuditAction, SubscriptionPlan, UserStatus
from app.models.password_reset import PasswordResetToken
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    UpdateAccountRequest,
    UserPublic,
)
from app.services import sessions as session_service
from app.services.audit import record_audit
from app.services.email import send_password_reset_email, send_verification_email
from app.services.sessions import IssuedSession


def normalize_email(email: str) -> str:
    return email.strip().lower()


def user_to_public(user: User) -> UserPublic:
    return UserPublic(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        email_verified=user.email_verified_at is not None,
        training_opt_in=user.training_opt_in,
        subscription_plan=user.subscription_plan.value,
        status=user.status.value,
    )


async def register_user(
    db: AsyncSession,
    payload: RegisterRequest,
    *,
    settings: Settings | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> tuple[User, IssuedSession, str]:
    settings = settings or get_settings()
    email = normalize_email(payload.email)
    existing = await db.scalar(select(User).where(User.email == email))
    if existing and existing.deleted_at is None:
        raise ConflictError("An account with this email already exists")

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        training_opt_in=bool(payload.training_opt_in)
        if payload.training_opt_in is not None
        else settings.training_opt_in_default,
        status=UserStatus.ACTIVE,
        subscription_plan=SubscriptionPlan.FREE,
        email_verified_at=None,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    verification_token = await _issue_email_verification(db, user=user, settings=settings)
    await send_verification_email(to=user.email, token=verification_token, settings=settings)

    issued = await session_service.create_session(
        db,
        user=user,
        remember_me=False,
        device_name=payload.device_name,
        user_agent=user_agent,
        ip=ip,
        settings=settings,
    )
    user.last_login_at = utcnow()
    await record_audit(
        db,
        action=AuditAction.REGISTER,
        user_id=user.id,
        ip_hash=hash_ip(ip, settings),
        user_agent=user_agent,
    )
    from app.models.enums import AnalyticsEventType
    from app.services.engagement.analytics import track as track_analytics

    await track_analytics(
        db,
        event_type=AnalyticsEventType.ACCOUNT_CREATED,
        user_id=user.id,
        properties={"plan": user.subscription_plan.value},
    )
    return user, issued, verification_token


async def authenticate_user(
    db: AsyncSession,
    payload: LoginRequest,
    *,
    settings: Settings | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> tuple[User, IssuedSession]:
    settings = settings or get_settings()
    email = normalize_email(payload.email)
    user = await db.scalar(select(User).where(User.email == email, User.deleted_at.is_(None)))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise UnauthorizedError("Invalid email or password")
    if not user.is_active:
        raise UnauthorizedError("Account is inactive")

    if user.password_hash and needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)

    issued = await session_service.create_session(
        db,
        user=user,
        remember_me=payload.remember_me,
        device_name=payload.device_name,
        user_agent=user_agent,
        ip=ip,
        settings=settings,
    )
    user.last_login_at = utcnow()
    await record_audit(
        db,
        action=AuditAction.LOGIN,
        user_id=user.id,
        ip_hash=hash_ip(ip, settings),
        user_agent=user_agent,
        metadata={"remember_me": payload.remember_me},
    )
    return user, issued


async def _issue_email_verification(
    db: AsyncSession,
    *,
    user: User,
    settings: Settings,
) -> str:
    raw = generate_opaque_token()
    token = EmailVerificationToken(
        user_id=user.id,
        token_hash=hash_token(raw),
        expires_at=utcnow() + timedelta(hours=settings.email_verification_expire_hours),
        created_at=utcnow(),
    )
    db.add(token)
    await db.flush()
    return raw


async def verify_email(
    db: AsyncSession,
    *,
    token: str,
    settings: Settings | None = None,
) -> User:
    settings = settings or get_settings()
    row = await db.scalar(
        select(EmailVerificationToken).where(EmailVerificationToken.token_hash == hash_token(token))
    )
    if row is None or row.used_at is not None or ensure_utc(row.expires_at) <= utcnow():
        raise ValidationAppError("Invalid or expired verification token")

    user = await db.get(User, row.user_id)
    if user is None or user.deleted_at is not None:
        raise ValidationAppError("Invalid or expired verification token")

    row.used_at = utcnow()
    user.email_verified_at = utcnow()
    await record_audit(db, action=AuditAction.VERIFY_EMAIL, user_id=user.id)
    await db.flush()
    return user


async def request_password_reset(
    db: AsyncSession,
    *,
    email: str,
    settings: Settings | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> dict[str, str]:
    """Always return the same message — do not reveal account existence."""
    settings = settings or get_settings()
    message = "If an account exists for that email, password reset instructions will be sent."
    normalized = normalize_email(email)
    if "@" not in normalized or "." not in normalized.split("@")[-1]:
        raise ValidationAppError("Invalid email address")

    user = await db.scalar(select(User).where(User.email == normalized, User.deleted_at.is_(None)))
    if user and user.password_hash:
        raw = generate_opaque_token()
        row = PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(raw),
            expires_at=utcnow() + timedelta(hours=settings.password_reset_expire_hours),
            created_at=utcnow(),
        )
        db.add(row)
        await db.flush()
        await send_password_reset_email(to=user.email, token=raw, settings=settings)
        await record_audit(
            db,
            action=AuditAction.REQUEST_PASSWORD_RESET,
            user_id=user.id,
            ip_hash=hash_ip(ip, settings),
            user_agent=user_agent,
        )
    return {"message": message}


async def reset_password(
    db: AsyncSession,
    *,
    token: str,
    new_password: str,
    settings: Settings | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> User:
    settings = settings or get_settings()
    row = await db.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(token))
    )
    if row is None or row.used_at is not None or ensure_utc(row.expires_at) <= utcnow():
        raise ValidationAppError("Invalid or expired reset token")

    user = await db.get(User, row.user_id)
    if user is None or user.deleted_at is not None:
        raise ValidationAppError("Invalid or expired reset token")

    row.used_at = utcnow()
    user.password_hash = hash_password(new_password)
    await session_service.revoke_all_sessions(db, user_id=user.id)
    await record_audit(
        db,
        action=AuditAction.RESET_PASSWORD,
        user_id=user.id,
        ip_hash=hash_ip(ip, settings),
        user_agent=user_agent,
    )
    await db.flush()
    return user


async def update_account(
    db: AsyncSession,
    *,
    user: User,
    payload: UpdateAccountRequest,
) -> User:
    if payload.display_name is not None:
        user.display_name = payload.display_name
    if payload.training_opt_in is not None:
        user.training_opt_in = payload.training_opt_in
    await record_audit(
        db,
        action=AuditAction.UPDATE_ACCOUNT,
        user_id=user.id,
        metadata={
            "training_opt_in": user.training_opt_in,
            "display_name_updated": payload.display_name is not None,
        },
    )
    await db.flush()
    await db.refresh(user)
    return user


async def delete_account(
    db: AsyncSession,
    *,
    user: User,
    password: str,
    settings: Settings | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> None:
    settings = settings or get_settings()
    if not verify_password(password, user.password_hash):
        raise UnauthorizedError("Invalid password")

    now = utcnow()
    user.deleted_at = now
    user.status = UserStatus.DELETED
    user.email = f"deleted+{user.id}@invalid.local"
    user.password_hash = None
    user.display_name = None
    await session_service.revoke_all_sessions(db, user_id=user.id)
    await record_audit(
        db,
        action=AuditAction.DELETE_ACCOUNT,
        user_id=user.id,
        ip_hash=hash_ip(ip, settings),
        user_agent=user_agent,
    )
    await db.flush()


async def get_user_by_id(db: AsyncSession, user_id: UUID) -> User:
    user = await db.get(User, user_id)
    if user is None or user.deleted_at is not None or not user.is_active:
        raise UnauthorizedError("User not found or inactive")
    return user
