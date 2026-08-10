"""Manuscript author normalization."""

from __future__ import annotations

import pytest
from app.schemas.authors import MAX_PROJECT_AUTHORS, ManuscriptAuthor, normalize_authors
from pydantic import ValidationError


def test_normalize_authors_caps_corresponding() -> None:
    result = normalize_authors(
        [
            {"name": "A", "corresponding": True},
            {"name": "B", "corresponding": True},
        ]
    )
    assert result[0]["corresponding"] is True
    assert result[1]["corresponding"] is False


def test_normalize_authors_defaults_first_corresponding() -> None:
    result = normalize_authors([{"name": "Solo"}])
    assert result[0]["corresponding"] is True


def test_normalize_authors_rejects_over_max() -> None:
    authors = [{"name": f"Author {i}"} for i in range(MAX_PROJECT_AUTHORS + 1)]
    with pytest.raises(ValueError, match="At most"):
        normalize_authors(authors)


def test_manuscript_author_requires_name() -> None:
    with pytest.raises(ValidationError):
        ManuscriptAuthor.model_validate({"name": "   "})
