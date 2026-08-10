"""Schemas for Dataset Studio."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class SyntheticColumnSpec(BaseModel):
    name: str
    type: str = "float"
    min: float | int | None = None
    max: float | int | None = None
    mean: float | None = None
    std: float | None = None
    categories: list[str] | None = None
    missingness: float = 0.0
    distribution: str | None = "uniform"
    true_probability: float | None = None
    prefix: str | None = None


class SyntheticDatasetRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    rows: int = Field(ge=1, le=50_000)
    columns: list[SyntheticColumnSpec] = Field(min_length=1)
    random_seed: int
    correlations: list[dict[str, Any]] = Field(default_factory=list)
    class_balance: dict[str, Any] | None = None
    source_description: str | None = None


class ColumnOverrideRequest(BaseModel):
    overrides: dict[str, str]


class AnalysisRequest(BaseModel):
    dataset_version_id: UUID
    operation: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    random_seed: int | None = None


class FigureCreateRequest(BaseModel):
    kind: str
    title: str
    dataset_version_id: UUID | None = None
    analysis_run_id: UUID | None = None
    caption: str = ""
    alt_text: str = ""
    x_label: str | None = None
    y_label: str | None = None
    journal_preset: str = "default"
    parameters: dict[str, Any] = Field(default_factory=dict)


class ConceptualFigureRequest(BaseModel):
    title: str
    mermaid: str
    caption: str = ""
    alt_text: str = ""


class TableCreateRequest(BaseModel):
    kind: str
    title: str
    dataset_version_id: UUID | None = None
    analysis_run_id: UUID | None = None
    caption: str = ""
    headers: list[str] | None = None
    rows: list[list[Any]] | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class ManuscriptInsertRequest(BaseModel):
    section_id: UUID
    asset_type: str
    asset_stable_id: str


class LabelUpdateRequest(BaseModel):
    provenance_label: str
