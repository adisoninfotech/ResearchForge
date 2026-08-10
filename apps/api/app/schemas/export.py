"""Export API request/response schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.schemas.authors import MAX_PROJECT_AUTHORS, ManuscriptAuthor, normalize_authors


class ExportRunRequest(BaseModel):
    template_id: str = "generic_academic"
    outputs: list[str] | None = None
    acknowledged_warnings: list[str] = Field(default_factory=list)
    authors: list[ManuscriptAuthor] | None = Field(default=None, max_length=MAX_PROJECT_AUTHORS)
    affiliations: list[dict[str, Any]] | None = None
    back_matter: dict[str, Any] | None = None
    idempotency_key: str | None = None
    process_sync: bool | None = None

    @field_validator("authors")
    @classmethod
    def validate_authors(
        cls, value: list[ManuscriptAuthor] | None
    ) -> list[ManuscriptAuthor] | None:
        if value is None:
            return value
        normalize_authors(value)
        return value


class ExportPreviewRequest(BaseModel):
    template_id: str = "generic_academic"
    page: int = 1
    authors: list[ManuscriptAuthor] | None = Field(default=None, max_length=MAX_PROJECT_AUTHORS)
    affiliations: list[dict[str, Any]] | None = None
    back_matter: dict[str, Any] | None = None

    @field_validator("authors")
    @classmethod
    def validate_authors(
        cls, value: list[ManuscriptAuthor] | None
    ) -> list[ManuscriptAuthor] | None:
        if value is None:
            return value
        normalize_authors(value)
        return value
