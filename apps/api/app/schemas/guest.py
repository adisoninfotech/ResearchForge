"""Guest preview schemas — no server-side persistence of guest drafts."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.projects import ProjectPublic
from app.services.ai.base import OutlineResult


class GuestOutlineRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    research_area: str = Field(min_length=1, max_length=255)
    target_format: str = Field(min_length=1, max_length=100)
    research_problem: str = Field(min_length=1, max_length=5000)
    proposed_contribution: str = Field(min_length=1, max_length=5000)


class GuestOutlineResponse(BaseModel):
    outline: OutlineResult
    storage_hint: str = (
        "This draft is stored only in this browser. "
        "Sign in to save and continue from another device."
    )
    gated_actions: list[str] = Field(
        default_factory=lambda: [
            "save",
            "upload",
            "full_export",
            "full_similarity_check",
            "generate_full_section",
        ]
    )


class GuestTransferRequest(BaseModel):
    """Transfer temporary guest draft into a saved project after login."""

    title: str = Field(min_length=1, max_length=500)
    research_area: str | None = Field(default=None, max_length=255)
    target_format: str | None = Field(default=None, max_length=100)
    research_problem: str | None = None
    proposed_contribution: str | None = None
    outline: list[dict[str, str]] | None = None
    draft_content: dict[str, object] | None = None
    contains_synthetic_data: bool = False
    guest_conversion_key: str = Field(
        min_length=8,
        max_length=64,
        description="Client-generated key required for idempotent conversion.",
    )


class GuestTransferResponse(BaseModel):
    project: ProjectPublic
    created: bool
    message: str
