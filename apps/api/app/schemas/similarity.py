"""Schemas for similarity and citation-risk checker."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class SimilarityRunRequest(BaseModel):
    threshold_profile: str = "default"
    exclude_bibliography: bool = False
    exclude_quotations: bool = False
    exclude_common_phrases: bool = False
    authorized_prior_project_ids: list[UUID] = Field(default_factory=list)
    open_license_corpus: list[dict[str, Any]] = Field(default_factory=list)


class FindingResolveRequest(BaseModel):
    action: str
    note: str | None = None


class RewriteAcceptRequest(BaseModel):
    accepted_text: str | None = None
