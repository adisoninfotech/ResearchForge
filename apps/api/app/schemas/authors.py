"""Manuscript author schemas (max 6 per project)."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

MAX_PROJECT_AUTHORS = 6


class ManuscriptAuthor(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    affiliation: str | None = Field(default=None, max_length=500)
    email: str | None = Field(default=None, max_length=320)
    corresponding: bool = False

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Author name is required")
        return cleaned

    @field_validator("affiliation", "email")
    @classmethod
    def strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


def normalize_authors(
    authors: list[ManuscriptAuthor] | list[dict[str, object]] | None,
) -> list[dict[str, object]]:
    if not authors:
        return []
    parsed = [
        a if isinstance(a, ManuscriptAuthor) else ManuscriptAuthor.model_validate(a)
        for a in authors
    ]
    if len(parsed) > MAX_PROJECT_AUTHORS:
        raise ValueError(f"At most {MAX_PROJECT_AUTHORS} authors are allowed")
    corresponding = sum(1 for a in parsed if a.corresponding)
    if corresponding == 0 and parsed:
        parsed[0].corresponding = True
    if corresponding > 1:
        # Keep the first corresponding author only
        seen = False
        for author in parsed:
            if author.corresponding:
                if seen:
                    author.corresponding = False
                else:
                    seen = True
    return [a.model_dump() for a in parsed]
