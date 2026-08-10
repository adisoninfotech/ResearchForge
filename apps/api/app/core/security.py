"""Argon2id password hashing, JWT access tokens, and opaque token hashing."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import Settings

_password_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=2,
    hash_len=32,
    salt_len=16,
)


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(plain: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    try:
        return _password_hasher.verify(hashed, plain)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def needs_rehash(hashed: str) -> bool:
    try:
        return _password_hasher.check_needs_rehash(hashed)
    except Exception:
        return False


def generate_opaque_token(nbytes: int = 48) -> str:
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> str:
    """One-way hash for refresh/verification/reset tokens (never store plaintext)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_ip(ip: str | None, settings: Settings) -> str | None:
    if not ip:
        return None
    digest = hmac.new(
        settings.secret_key.encode("utf-8"),
        ip.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return digest


def create_access_token(
    *,
    user_id: str | UUID,
    session_id: str | UUID,
    settings: Settings,
    extra: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(UTC)
    expire = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "sid": str(session_id),
        "type": "access",
        "iat": now,
        "exp": expire,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_access_token(token: str, settings: Settings) -> dict[str, Any]:
    payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Invalid token type")
    return payload


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def sign_csrf_token(token: str, settings: Settings) -> str:
    digest = hmac.new(
        settings.csrf_secret.encode("utf-8"),
        token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{token}.{digest}"


def verify_csrf_token(signed: str, settings: Settings) -> bool:
    if "." not in signed:
        return False
    token, signature = signed.rsplit(".", 1)
    expected = hmac.new(
        settings.csrf_secret.encode("utf-8"),
        token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(signature, expected)
