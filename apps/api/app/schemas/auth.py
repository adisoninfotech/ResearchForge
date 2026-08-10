"""Auth request/response schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=255)
    training_opt_in: bool | None = Field(
        default=None,
        description="Explicit opt-in for using content in model training. Default false.",
    )
    device_name: str | None = Field(default=None, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    remember_me: bool = False
    device_name: str | None = Field(default=None, max_length=255)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=20, max_length=512)
    new_password: str = Field(min_length=8, max_length=128)


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=20, max_length=512)


class UpdateAccountRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=255)
    training_opt_in: bool | None = None


class DeleteAccountRequest(BaseModel):
    password: str = Field(min_length=1, max_length=128)
    confirmation: str = Field(description='Must equal "DELETE"')


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    display_name: str | None
    email_verified: bool
    training_opt_in: bool
    subscription_plan: str
    status: str


class AuthResponse(BaseModel):
    user: UserPublic
    message: str = "Authenticated"
    csrf_token: str | None = None


class MessageResponse(BaseModel):
    message: str


class SessionPublic(BaseModel):
    id: UUID
    device_name: str | None
    user_agent: str | None
    remember_me: bool
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
    is_current: bool = False


class OAuthStatusResponse(BaseModel):
    google_enabled: bool
    google_authorization_url: str | None = None
