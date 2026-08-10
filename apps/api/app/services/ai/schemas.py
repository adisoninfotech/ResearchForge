"""Structured output schemas for every AI operation."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.services.ai.base import OutlineResult, OutlineSection


class EvidencePassage(BaseModel):
    id: str
    text: str
    source_label: str | None = None
    is_synthetic: bool = False


class GroundingContext(BaseModel):
    project_facts: dict[str, Any] = Field(default_factory=dict)
    evidence_passages: list[EvidencePassage] = Field(default_factory=list)
    manuscript_context: dict[str, str] = Field(default_factory=dict)
    target_format: str | None = None
    section_goal: str | None = None
    constraints: list[str] = Field(default_factory=list)
    contains_synthetic_data: bool = False


class ContentBlock(BaseModel):
    type: Literal["paragraph", "heading", "list", "figure_placeholder", "table_placeholder"] = (
        "paragraph"
    )
    text: str = ""
    level: int | None = None


class Claim(BaseModel):
    text: str
    evidence_ids: list[str] = Field(default_factory=list)
    supported: bool = True
    warning: str | None = None


class Provenance(BaseModel):
    prompt_template_id: str
    prompt_version: str
    model: str
    provider: str
    generation_parameters: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    evidence_ids: list[str] = Field(default_factory=list)
    training_eligible: bool = False


class SectionDraftResult(BaseModel):
    title: str
    content_blocks: list[ContentBlock] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    evidence_references: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    suggested_figures: list[str] = Field(default_factory=list)
    suggested_tables: list[str] = Field(default_factory=list)
    provenance: Provenance | None = None
    plain_text: str = ""


class TextTransformResult(BaseModel):
    original_text: str
    transformed_text: str
    warnings: list[str] = Field(default_factory=list)
    evidence_references: list[str] = Field(default_factory=list)
    provenance: Provenance | None = None


class SectionQuestionsResult(BaseModel):
    section_type: str
    questions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    provenance: Provenance | None = None


class MissingInformationResult(BaseModel):
    questions: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    provenance: Provenance | None = None


class AbstractResult(BaseModel):
    abstract: str
    keywords: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    provenance: Provenance | None = None


class LimitationsResult(BaseModel):
    limitations: list[str] = Field(default_factory=list)
    ethics_notes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    provenance: Provenance | None = None


class ConsistencyIssue(BaseModel):
    severity: Literal["info", "warning", "error"] = "warning"
    message: str
    section_hint: str | None = None


class ConsistencyReviewResult(BaseModel):
    issues: list[ConsistencyIssue] = Field(default_factory=list)
    summary: str = ""
    warnings: list[str] = Field(default_factory=list)
    provenance: Provenance | None = None


# Re-export for convenience
__all__ = [
    "AbstractResult",
    "Claim",
    "ConsistencyIssue",
    "ConsistencyReviewResult",
    "ContentBlock",
    "EvidencePassage",
    "GroundingContext",
    "LimitationsResult",
    "MissingInformationResult",
    "OutlineResult",
    "OutlineSection",
    "Provenance",
    "SectionDraftResult",
    "SectionQuestionsResult",
    "TextTransformResult",
]
