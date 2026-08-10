"""Authentication, sessions, guest conversion, and authorization tests."""

from __future__ import annotations

import pytest
from app.services.email import reset_fake_email_provider
from httpx import AsyncClient


def _csrf(client: AsyncClient) -> str:
    token = client.cookies.get("rf_csrf")
    assert token
    return token


async def _register(
    client: AsyncClient,
    email: str = "alice@example.com",
    password: str = "Password123!",
    **extra: object,
) -> dict:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "display_name": "Alice",
            **extra,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_registration_and_training_opt_in_default(client: AsyncClient) -> None:
    body = await _register(client)
    assert body["user"]["email"] == "alice@example.com"
    assert body["user"]["training_opt_in"] is False
    assert body["user"]["email_verified"] is False
    assert client.cookies.get("rf_access")
    assert client.cookies.get("rf_refresh")
    assert client.cookies.get("rf_csrf")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_duplicate_email(client: AsyncClient) -> None:
    await _register(client)
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "Alice@Example.com", "password": "Password123!"},
    )
    assert response.status_code == 409


@pytest.mark.integration
@pytest.mark.asyncio
async def test_login_and_invalid_credentials(client: AsyncClient) -> None:
    await _register(client)
    client.cookies.clear()
    bad = await client.post(
        "/api/v1/auth/login",
        json={"email": "alice@example.com", "password": "wrong-password"},
    )
    assert bad.status_code == 401

    ok = await client.post(
        "/api/v1/auth/login",
        json={"email": "alice@example.com", "password": "Password123!", "remember_me": True},
    )
    assert ok.status_code == 200
    assert ok.json()["user"]["email"] == "alice@example.com"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_email_verification(client: AsyncClient) -> None:
    fake = reset_fake_email_provider()
    await _register(client, email="verify@example.com")
    assert fake.messages
    body = fake.messages[0].body
    token = body.rsplit("token=", 1)[-1].strip()
    response = await client.post("/api/v1/auth/verify-email", json={"token": token})
    assert response.status_code == 200
    me = await client.get("/api/v1/auth/me")
    assert me.json()["email_verified"] is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_password_reset_revokes_sessions(client: AsyncClient) -> None:
    fake = reset_fake_email_provider()
    await _register(client, email="reset@example.com")
    access_before = client.cookies.get("rf_access")

    forgot = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "reset@example.com"},
    )
    assert forgot.status_code == 200
    assert "If an account exists" in forgot.json()["message"]
    reset_msgs = [m for m in fake.messages if "Reset" in m.subject]
    assert reset_msgs
    token = reset_msgs[-1].body.rsplit("token=", 1)[-1].strip()

    reset = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "NewPassword123!"},
    )
    assert reset.status_code == 200

    # Old session should no longer work
    client.cookies.set("rf_access", access_before)
    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 401

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "reset@example.com", "password": "NewPassword123!"},
    )
    assert login.status_code == 200


@pytest.mark.integration
@pytest.mark.asyncio
async def test_token_rotation_and_reuse_detection(client: AsyncClient) -> None:
    await _register(client, email="rotate@example.com")
    old_refresh = client.cookies.get("rf_refresh")
    assert old_refresh

    first = await client.post("/api/v1/auth/refresh")
    assert first.status_code == 200
    new_refresh = client.cookies.get("rf_refresh")
    assert new_refresh
    assert new_refresh != old_refresh

    # Reuse old refresh token → revoke all
    client.cookies.set("rf_refresh", old_refresh, path="/api/v1/auth")
    reused = await client.post("/api/v1/auth/refresh")
    assert reused.status_code == 401
    assert "reuse" in reused.json()["error"]["message"].lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_session_revocation(client: AsyncClient) -> None:
    await _register(client, email="sess@example.com")
    sessions = await client.get("/api/v1/account/sessions")
    assert sessions.status_code == 200
    assert len(sessions.json()) == 1
    current_id = sessions.json()[0]["id"]

    # Second login creates another session for the same user
    other = AsyncClient(transport=client._transport, base_url="http://test", cookies={})  # type: ignore[attr-defined]
    async with other:
        login = await other.post(
            "/api/v1/auth/login",
            json={"email": "sess@example.com", "password": "Password123!"},
        )
        assert login.status_code == 200

    listed = await client.get("/api/v1/account/sessions")
    assert len(listed.json()) == 2

    revoke_others = await client.post(
        "/api/v1/account/sessions/revoke-others",
        headers={"X-CSRF-Token": _csrf(client)},
    )
    assert revoke_others.status_code == 200

    remaining = await client.get("/api/v1/account/sessions")
    ids = {row["id"] for row in remaining.json()}
    assert ids == {current_id}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_authorization_isolation(client: AsyncClient) -> None:
    await _register(client, email="owner@example.com")
    created = await client.post(
        "/api/v1/projects/from-guest",
        headers={"X-CSRF-Token": _csrf(client)},
        json={
            "title": "Owner Project",
            "research_area": "NLP",
            "guest_conversion_key": "conv-owner-1",
        },
    )
    assert created.status_code == 200
    project_id = created.json()["project"]["id"]

    outsider = AsyncClient(transport=client._transport, base_url="http://test", cookies={})  # type: ignore[attr-defined]
    async with outsider:
        reg = await outsider.post(
            "/api/v1/auth/register",
            json={"email": "intruder@example.com", "password": "Password123!"},
        )
        assert reg.status_code == 200
        leak = await outsider.get(f"/api/v1/projects/{project_id}")
        assert leak.status_code == 404


@pytest.mark.integration
@pytest.mark.asyncio
async def test_guest_conversion_idempotency(client: AsyncClient) -> None:
    await _register(client, email="guestconv@example.com")
    payload = {
        "title": "Guest Paper",
        "research_area": "Biology",
        "target_format": "Nature",
        "research_problem": "Problem",
        "proposed_contribution": "Contribution",
        "outline": [{"title": "Intro", "summary": "s"}],
        "draft_content": {"sectionContent": "<p>Hi</p>"},
        "guest_conversion_key": "idempotent-key-1",
    }
    first = await client.post(
        "/api/v1/projects/from-guest",
        headers={"X-CSRF-Token": _csrf(client)},
        json=payload,
    )
    second = await client.post(
        "/api/v1/projects/from-guest",
        headers={"X-CSRF-Token": _csrf(client)},
        json=payload,
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["created"] is True
    assert second.json()["created"] is False
    assert first.json()["project"]["id"] == second.json()["project"]["id"]

    projects = await client.get("/api/v1/projects")
    assert len(projects.json()) == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_account_deletion(client: AsyncClient) -> None:
    await _register(client, email="delete-me@example.com")
    deleted = await client.post(
        "/api/v1/account/delete",
        headers={"X-CSRF-Token": _csrf(client)},
        json={"password": "Password123!", "confirmation": "DELETE"},
    )
    assert deleted.status_code == 200
    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 401
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "delete-me@example.com", "password": "Password123!"},
    )
    assert login.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_logout_revokes_current_session(client: AsyncClient) -> None:
    await _register(client, email="logout@example.com")
    response = await client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": _csrf(client)},
    )
    assert response.status_code == 200
    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_csrf_required_for_mutating_account_routes(client: AsyncClient) -> None:
    await _register(client, email="csrf@example.com")
    response = await client.patch(
        "/api/v1/account/me",
        json={"display_name": "No CSRF"},
    )
    assert response.status_code == 403


@pytest.mark.integration
@pytest.mark.asyncio
async def test_forgot_password_does_not_leak_existence(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "nobody@example.com"},
    )
    assert response.status_code == 200
    assert "If an account exists" in response.json()["message"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_google_oauth_disabled_without_credentials(client: AsyncClient) -> None:
    status = await client.get("/api/v1/auth/oauth/status")
    assert status.status_code == 200
    assert status.json()["google_enabled"] is False
    start = await client.get("/api/v1/auth/oauth/google/start")
    assert start.status_code == 503
