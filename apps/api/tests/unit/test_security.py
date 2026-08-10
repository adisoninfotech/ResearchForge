"""Unit tests for security helpers."""

from __future__ import annotations

import pytest
from app.core.config import Settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_csrf_token,
    hash_password,
    hash_token,
    sign_csrf_token,
    verify_csrf_token,
    verify_password,
)


@pytest.mark.unit
def test_password_hash_roundtrip_argon2id() -> None:
    hashed = hash_password("Str0ngPass!")
    assert hashed.startswith("$argon2id$")
    assert verify_password("Str0ngPass!", hashed)
    assert not verify_password("wrong", hashed)


@pytest.mark.unit
def test_access_token_roundtrip() -> None:
    settings = Settings(
        secret_key="jwt-test-secret-key-32chars-min!!",
        csrf_secret="csrf-test-secret-key-32chars-min!",
    )
    token = create_access_token(
        user_id="11111111-1111-1111-1111-111111111111",
        session_id="22222222-2222-2222-2222-222222222222",
        settings=settings,
    )
    payload = decode_access_token(token, settings)
    assert payload["sub"] == "11111111-1111-1111-1111-111111111111"
    assert payload["sid"] == "22222222-2222-2222-2222-222222222222"
    assert payload["type"] == "access"


@pytest.mark.unit
def test_csrf_sign_verify() -> None:
    settings = Settings(
        secret_key="jwt-test-secret-key-32chars-min!!",
        csrf_secret="csrf-test-secret-key-32chars-min!",
    )
    raw = generate_csrf_token()
    signed = sign_csrf_token(raw, settings)
    assert verify_csrf_token(signed, settings)
    assert not verify_csrf_token("tampered.token", settings)


@pytest.mark.unit
def test_token_hash_is_digest() -> None:
    digest = hash_token("plaintext-token")
    assert digest != "plaintext-token"
    assert len(digest) == 64
