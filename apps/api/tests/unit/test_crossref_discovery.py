"""Unit tests for Crossref discovery.

No network: the HTTP layer is stubbed and the payloads mirror real Crossref
responses, including the awkward shapes (list-typed titles, author objects,
date-parts, references without DOIs).
"""

from __future__ import annotations

from typing import Any

import pytest
from app.core.config import Settings
from app.services.files import crossref


def _settings() -> Settings:
    return Settings(secret_key="x" * 16, csrf_secret="y" * 16)


def _work(
    title: str,
    citations: int,
    *,
    doi: str | None = "10.1000/example",
    year: int = 2020,
) -> dict[str, Any]:
    return {
        "title": [title],
        "author": [{"given": "Ada", "family": "Lovelace"}],
        "issued": {"date-parts": [[year, 3, 1]]},
        "DOI": doi,
        "URL": f"https://doi.org/{doi}" if doi else None,
        "container-title": ["Journal of Testing"],
        "is-referenced-by-count": citations,
        "type": "journal-article",
    }


@pytest.mark.unit
def test_normalize_work_unwraps_crossref_list_fields() -> None:
    work = crossref.normalize_work(_work("Explainable AI", 12))
    assert work["title"] == "Explainable AI"
    assert work["venue"] == "Journal of Testing"
    assert work["authors"] == ["Ada Lovelace"]
    assert work["year"] == 2020
    assert work["cited_by_count"] == 12


@pytest.mark.unit
def test_normalize_work_survives_missing_fields() -> None:
    work = crossref.normalize_work({"DOI": "10.1/x"})
    assert work["title"] is None
    assert work["authors"] == []
    assert work["year"] is None
    assert work["cited_by_count"] == 0
    assert work["url"] == "https://doi.org/10.1/x"


@pytest.mark.unit
def test_rerank_orders_by_citations_not_input_order() -> None:
    """The whole reason this module exists.

    Crossref returns relevance order, which puts uncited recent papers first.
    Re-ranking within that set must surface the well-cited ones.
    """
    items = [
        _work("Zero-cited 2026 preprint", 0),
        _work("Barely cited", 1),
        _work("Highly cited systematic review", 223),
        _work("Moderately cited", 97),
    ]
    results = crossref.rerank(items, limit=10, min_citations=1)
    assert [r["cited_by_count"] for r in results] == [223, 97, 1]


@pytest.mark.unit
def test_rerank_drops_uncited_and_untitled() -> None:
    items = [
        _work("Cited", 5),
        _work("Uncited", 0),
        {"is-referenced-by-count": 999},  # no title at all
    ]
    results = crossref.rerank(items, limit=10, min_citations=1)
    assert [r["title"] for r in results] == ["Cited"]


@pytest.mark.unit
def test_rerank_min_citations_zero_keeps_uncited() -> None:
    results = crossref.rerank([_work("Uncited", 0)], limit=10, min_citations=0)
    assert len(results) == 1


@pytest.mark.unit
def test_rerank_respects_limit() -> None:
    items = [_work(f"Paper {i}", i + 1) for i in range(10)]
    assert len(crossref.rerank(items, limit=3, min_citations=1)) == 3


@pytest.mark.unit
def test_normalize_reference_with_doi_is_linkable() -> None:
    entry = crossref.normalize_reference(
        {"DOI": "10.1038/nature12373", "article-title": "A paper", "year": "2013"}
    )
    assert entry["linkable"] is True
    assert entry["url"] == "https://doi.org/10.1038/nature12373"
    assert entry["year"] == 2013


@pytest.mark.unit
def test_normalize_reference_without_doi_is_not_linkable() -> None:
    """Roughly two thirds of real Crossref reference entries look like this."""
    entry = crossref.normalize_reference(
        {
            "key": "bib0001",
            "series-title": "Artificial intelligence: a modern approach",
            "author": "Russell",
            "year": "2016",
        }
    )
    assert entry["linkable"] is False
    assert entry["doi"] is None
    assert entry["title"] == "Artificial intelligence: a modern approach"
    assert entry["authors"] == ["Russell"]


@pytest.mark.unit
def test_normalize_reference_unstructured_only() -> None:
    entry = crossref.normalize_reference({"unstructured": "Smith J. Some paper. 1999."})
    assert entry["title"] is None
    assert entry["unstructured"] == "Smith J. Some paper. 1999."
    assert entry["linkable"] is False


@pytest.mark.unit
async def test_search_works_reranks_stubbed_response(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "message": {
            "items": [
                _work("Uncited newcomer", 0),
                _work("Well cited", 300),
                _work("Middling", 40),
            ]
        }
    }

    async def fake_get_json(url: str, *, params: dict[str, Any], settings: Settings) -> Any:
        assert params["rows"] == crossref.CANDIDATE_ROWS
        assert params["filter"] == "type:journal-article"
        return payload

    monkeypatch.setattr(crossref, "_get_json", fake_get_json)
    results = await crossref.search_works("some claim", settings=_settings(), limit=5)
    assert [r["title"] for r in results] == ["Well cited", "Middling"]


@pytest.mark.unit
async def test_search_works_empty_query_skips_request(monkeypatch: pytest.MonkeyPatch) -> None:
    async def explode(*args: Any, **kwargs: Any) -> Any:  # pragma: no cover - must not run
        raise AssertionError("no request should be made for a blank query")

    monkeypatch.setattr(crossref, "_get_json", explode)
    assert await crossref.search_works("   ", settings=_settings()) == []


@pytest.mark.unit
async def test_fetch_references_paginates(monkeypatch: pytest.MonkeyPatch) -> None:
    entries = [{"DOI": f"10.1/{i}", "article-title": f"Ref {i}"} for i in range(40)]

    async def fake_get_json(url: str, *, params: dict[str, Any], settings: Settings) -> Any:
        assert url.endswith("10.1016/j.inffus.2019.12.012")
        return {"message": {"title": ["Parent paper"], "reference": entries}}

    monkeypatch.setattr(crossref, "_get_json", fake_get_json)
    data = await crossref.fetch_references(
        "https://doi.org/10.1016/j.inffus.2019.12.012",
        settings=_settings(),
        limit=10,
        offset=5,
    )
    assert data["total"] == 40
    assert data["title"] == "Parent paper"
    assert len(data["references"]) == 10
    assert data["references"][0]["title"] == "Ref 5"
