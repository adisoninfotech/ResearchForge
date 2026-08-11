"""Schemas for Crossref-backed paper discovery."""

from __future__ import annotations

from pydantic import BaseModel, Field


class WorkSearchRequest(BaseModel):
    query: str = Field(min_length=3, max_length=1000)
    limit: int = Field(default=10, ge=1, le=25)
    # Crossref's relevance ranking surfaces a lot of uncited recent work; the
    # default of 1 drops papers nothing has cited yet. Set 0 to include them.
    min_citations: int = Field(default=1, ge=0, le=1000)


class WorkPublic(BaseModel):
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    doi: str | None = None
    url: str | None = None
    cited_by_count: int = 0
    type: str | None = None


class WorkSearchResponse(BaseModel):
    query: str
    source: str = "crossref"
    results: list[WorkPublic] = Field(default_factory=list)


class ReferencePublic(BaseModel):
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    doi: str | None = None
    url: str | None = None
    # Present when Crossref holds only a raw citation string for this entry.
    unstructured: str | None = None
    # False for roughly two thirds of entries — no DOI, so nothing to link to.
    linkable: bool = False


class WorkReferencesResponse(BaseModel):
    doi: str
    title: str | None = None
    total: int = 0
    references: list[ReferencePublic] = Field(default_factory=list)
