"""API request/response schemas for AI jobs and proposals."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class EvidencePassageIn(BaseModel):
    id: str
    text: str = ""
    chunk_id: UUID | None = None
    source_label: str | None = None
    is_synthetic: bool = False


class AIGenerateRequest(BaseModel):
    operation: str
    project_id: UUID | None = None
    section_id: UUID | None = None
    section_type: str | None = None
    section_title: str | None = None
    section_goal: str | None = None
    selected_text: str | None = None
    existing_text: str | None = None
    evidence_passages: list[EvidencePassageIn] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    length_hint: str | None = None
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=128)
    sync: bool = False


class ProposalDecisionRequest(BaseModel):
    accepted_text: str | None = None


class AIJobPublic(BaseModel):
    id: str
    project_id: str | None = None
    operation: str
    status: str
    progress: int
    progress_events: list[dict[str, Any]] = Field(default_factory=list)
    result_payload: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None
    idempotency_key: str | None = None
    prompt_template_id: str | None = None
    prompt_version: str | None = None
    model_name: str | None = None
    cancel_requested: bool = False
    proposal_id: str | None = None
    created_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
