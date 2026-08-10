"""Schemas for uploads, references, evidence, and retrieval."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class FileAuthorizeResponse(BaseModel):
    authorized: bool = True
    max_bytes: int
    allowed_content_types: list[str]
    upload_path: str


class FilePatchRequest(BaseModel):
    exclude_from_ai: bool | None = None


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=10, ge=1, le=50)
    file_ids: list[UUID] | None = None


class ReferenceCreateRequest(BaseModel):
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    url: str | None = None
    doi: str | None = None
    abstract: str | None = None


class ReferenceUpdateRequest(BaseModel):
    title: str | None = None
    authors: list[str] | None = None
    year: int | None = None
    venue: str | None = None
    url: str | None = None
    doi: str | None = None
    abstract: str | None = None
    verification_status: str | None = None


class ReferenceImportRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2_000_000)
    format: str = Field(pattern="^(bibtex|ris)$")


class EvidenceLinkCreate(BaseModel):
    chunk_id: UUID
    section_id: UUID | None = None
    relation: str = "supports"
    note: str | None = None


class EvidenceLinkUpdate(BaseModel):
    relation: str | None = None
    note: str | None = None
    exclude_from_ai: bool | None = None
    pinned: bool | None = None


class ClaimUpdateRequest(BaseModel):
    user_verification_status: str | None = None
    support_status: str | None = None
