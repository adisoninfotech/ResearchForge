"""Project, manuscript, version, and fact schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.schemas.authors import MAX_PROJECT_AUTHORS, ManuscriptAuthor, normalize_authors


class ProjectCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    research_field: str | None = Field(default=None, max_length=255)
    paper_type: str | None = Field(default=None, max_length=100)
    target_publisher: str | None = Field(default=None, max_length=255)
    target_template: str | None = Field(default=None, max_length=100)
    target_word_count: int | None = Field(default=None, ge=0)
    intended_submission_date: date | None = None
    research_problem: str | None = None
    proposed_contribution: str | None = None
    retention_policy: str | None = None
    status: str | None = None
    authors: list[ManuscriptAuthor] | None = Field(
        default=None,
        max_length=MAX_PROJECT_AUTHORS,
    )

    @field_validator("authors")
    @classmethod
    def validate_create_authors(
        cls, value: list[ManuscriptAuthor] | None
    ) -> list[ManuscriptAuthor] | None:
        if value is None:
            return value
        normalize_authors(value)
        return value


class ProjectUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    research_field: str | None = None
    paper_type: str | None = None
    target_publisher: str | None = None
    target_template: str | None = None
    target_word_count: int | None = Field(default=None, ge=0)
    intended_submission_date: date | None = None
    research_problem: str | None = None
    proposed_contribution: str | None = None
    retention_policy: str | None = None
    status: str | None = None
    legal_hold: bool | None = None
    ai_enabled: bool | None = None
    authors: list[ManuscriptAuthor] | None = Field(
        default=None,
        max_length=MAX_PROJECT_AUTHORS,
    )

    @field_validator("authors")
    @classmethod
    def validate_update_authors(
        cls, value: list[ManuscriptAuthor] | None
    ) -> list[ManuscriptAuthor] | None:
        if value is None:
            return value
        normalize_authors(value)
        return value


class ProjectPublic(BaseModel):
    id: str
    title: str
    slug: str
    research_field: str | None = None
    paper_type: str | None = None
    target_publisher: str | None = None
    target_template: str | None = None
    target_word_count: int | None = None
    intended_submission_date: date | None = None
    research_problem: str | None = None
    proposed_contribution: str | None = None
    authors: list[ManuscriptAuthor] = Field(default_factory=list)
    status: str
    retention_policy: str
    last_activity_at: datetime | None = None
    trash_at: datetime | None = None
    purge_after: datetime | None = None
    legal_hold: bool = False
    ai_enabled: bool = True
    is_private: bool = True
    transferred_from_guest: bool = False
    contains_synthetic_data: bool = False
    guest_conversion_key: str | None = None
    completion_percent: int = 0
    updated_at: datetime | None = None
    created_at: datetime | None = None


class SectionSaveRequest(BaseModel):
    structured_content: dict[str, Any]
    expected_revision: int = Field(ge=1)
    title: str | None = Field(default=None, max_length=255)
    create_snapshot: bool = False
    snapshot_summary: str | None = Field(default=None, max_length=500)
    reason: str | None = Field(
        default=None,
        description="autosave | section_change | before_ai | after_ai | shortcut",
    )


class SectionReorderRequest(BaseModel):
    ordered_section_ids: list[UUID]


class CustomSectionRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class NamedVersionRequest(BaseModel):
    change_summary: str = Field(min_length=1, max_length=500)


class PermanentDeleteRequest(BaseModel):
    confirmation: str


class FactUpsertRequest(BaseModel):
    category: str
    key: str = Field(min_length=1, max_length=100)
    value: Any = None
    verification_status: str | None = None


class FactPublic(BaseModel):
    id: str
    category: str
    key: str
    value: Any = None
    source_type: str
    verification_status: str
    updated_at: datetime
