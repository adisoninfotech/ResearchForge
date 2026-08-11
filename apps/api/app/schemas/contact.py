"""Schemas for the public contact form."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class ContactRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    message: str = Field(min_length=10, max_length=5000)
    # Honeypot. Hidden from humans via CSS, so a real submission always leaves
    # it empty. Named "website" because that is what naive bots look for.
    website: str | None = Field(default=None, max_length=200)
    # Storage key returned by POST /contact/attachment. Never a client-supplied
    # path: it is validated against the contact/ prefix before use.
    attachment_key: str | None = Field(default=None, max_length=300)
    attachment_name: str | None = Field(default=None, max_length=255)


class ContactResponse(BaseModel):
    status: str = "sent"


class AttachmentResponse(BaseModel):
    key: str
    filename: str
    size_bytes: int
