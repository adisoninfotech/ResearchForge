"""Crossref work discovery and reference-following.

Crossref is used rather than OpenAlex because it needs no API key and meters
nothing. The trade-off is ranking quality, which this module compensates for.

Why the local re-ranking exists
-------------------------------
Crossref offers two orderings and both are unusable on their own:

* ``query.bibliographic`` alone ranks by literal title match. For
  "explainable AI improves clinician trust in diagnosis" the top five results
  were 2025-26 papers in minor venues with zero citations between them.
* ``sort=is-referenced-by-count`` orders the whole matched set by citations and
  discards relevance entirely, returning "Initial sequencing and analysis of
  the human genome" for the same query.

Fetching one page of relevance-ranked candidates and sorting *those* by
citation count locally gives both. One request, no extra cost.

Known limitation: Crossref matches title strings and has no semantic search, so
a seminal paper whose title does not contain the query's words will not surface
(searching "attention mechanism transformer" does not return "Attention Is All
You Need"). Claim-shaped queries phrased in a field's own vocabulary work well;
concept-shaped queries are weaker.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import Settings
from app.core.exceptions import AppError
from app.core.security_hardening import assert_url_safe_for_outbound

CROSSREF_WORKS_URL = "https://api.crossref.org/works"

# Candidates pulled per search before local re-ranking. Crossref returns these
# in relevance order; we keep that as the relevance filter and re-sort within
# it. Larger values cost nothing extra but slow the response.
CANDIDATE_ROWS = 60

_SELECT_FIELDS = "title,author,issued,DOI,URL,container-title,is-referenced-by-count,type,abstract"


def _headers(settings: Settings) -> dict[str, str]:
    # Crossref asks for a contact address and gives politely-identified callers
    # better service. It is not authentication and is safe to omit.
    ua = "ResearchForge/1.0"
    if settings.crossref_mailto:
        ua = f"{ua} (mailto:{settings.crossref_mailto})"
    return {"User-Agent": ua}


def _first_str(value: Any) -> str | None:
    """Crossref returns title and container-title as lists of strings."""
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str) and item.strip():
                return item.strip()
        return None
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _year(item: dict[str, Any]) -> int | None:
    for key in ("issued", "published-print", "published-online", "created"):
        parts = (item.get(key) or {}).get("date-parts") or []
        if parts and isinstance(parts[0], list) and parts[0]:
            candidate = parts[0][0]
            if isinstance(candidate, int):
                return candidate
    return None


def _authors(item: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for author in item.get("author") or []:
        if not isinstance(author, dict):
            continue
        given = (author.get("given") or "").strip()
        family = (author.get("family") or "").strip()
        full = f"{given} {family}".strip() if (given or family) else ""
        if not full:
            full = (author.get("name") or "").strip()
        if full:
            names.append(full)
    return names


def normalize_work(item: dict[str, Any]) -> dict[str, Any]:
    """Map a Crossref work onto the shape references.import_parsed_entries expects."""
    doi = item.get("DOI")
    return {
        "title": _first_str(item.get("title")),
        "authors": _authors(item),
        "year": _year(item),
        "venue": _first_str(item.get("container-title")),
        "doi": doi,
        "url": item.get("URL") or (f"https://doi.org/{doi}" if doi else None),
        "abstract": None,  # Crossref abstracts are JATS XML; not worth rendering raw
        "cited_by_count": int(item.get("is-referenced-by-count") or 0),
        "type": item.get("type"),
    }


def rerank(
    items: list[dict[str, Any]],
    *,
    limit: int,
    min_citations: int,
) -> list[dict[str, Any]]:
    """Sort relevance-ranked candidates by citation count, dropping uncited ones.

    Applied to an already relevance-filtered set — see the module docstring for
    why sorting Crossref's full result set instead does not work.
    """
    works = [normalize_work(item) for item in items]
    works = [w for w in works if w["title"] and w["cited_by_count"] >= min_citations]
    works.sort(key=lambda w: w["cited_by_count"], reverse=True)
    return works[:limit]


async def _get_json(url: str, *, params: dict[str, Any], settings: Settings) -> dict[str, Any]:
    assert_url_safe_for_outbound(url, settings=settings)
    try:
        async with httpx.AsyncClient(timeout=settings.crossref_timeout_seconds) as client:
            response = await client.get(url, params=params, headers=_headers(settings))
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            return data
    except httpx.HTTPError as exc:
        raise AppError(
            "Paper search is unavailable right now",
            code="crossref_unavailable",
            status_code=503,
        ) from exc


async def search_works(
    query: str,
    *,
    settings: Settings,
    limit: int = 10,
    min_citations: int = 1,
) -> list[dict[str, Any]]:
    """Find papers matching a topic or claim, best-cited first."""
    query = query.strip()
    if not query:
        return []
    data = await _get_json(
        CROSSREF_WORKS_URL,
        params={
            "query.bibliographic": query,
            "rows": CANDIDATE_ROWS,
            "select": _SELECT_FIELDS,
            "filter": "type:journal-article",
        },
        settings=settings,
    )
    items = (data.get("message") or {}).get("items") or []
    return rerank(items, limit=limit, min_citations=min_citations)


def normalize_reference(entry: dict[str, Any]) -> dict[str, Any]:
    """Map one entry of a work's ``reference`` array.

    Only about a third of Crossref reference entries carry a DOI; the rest are
    author/year/title fragments or a single ``unstructured`` string. Callers
    must handle unlinkable entries rather than assuming a DOI exists.
    """
    doi = entry.get("DOI")
    title = (
        _first_str(entry.get("article-title"))
        or _first_str(entry.get("volume-title"))
        or _first_str(entry.get("series-title"))
        or _first_str(entry.get("journal-title"))
    )
    year_raw = entry.get("year")
    year: int | None = None
    if isinstance(year_raw, str) and year_raw[:4].isdigit():
        year = int(year_raw[:4])
    elif isinstance(year_raw, int):
        year = year_raw
    author = entry.get("author")
    return {
        "title": title,
        "authors": [author] if isinstance(author, str) and author.strip() else [],
        "year": year,
        "doi": doi,
        "url": f"https://doi.org/{doi}" if doi else None,
        "unstructured": _first_str(entry.get("unstructured")),
        "linkable": bool(doi),
    }


async def fetch_references(
    doi: str,
    *,
    settings: Settings,
    limit: int = 25,
    offset: int = 0,
) -> dict[str, Any]:
    """Return the bibliography of a work, paginated.

    Bibliographies run to hundreds of entries, so this pages rather than
    returning everything.
    """
    doi = doi.strip().removeprefix("https://doi.org/").removeprefix("doi:")
    if not doi:
        return {"total": 0, "references": []}
    data = await _get_json(
        f"{CROSSREF_WORKS_URL}/{doi}",
        params={},
        settings=settings,
    )
    message = data.get("message") or {}
    entries = message.get("reference") or []
    window = entries[offset : offset + limit]
    return {
        "total": len(entries),
        "title": _first_str(message.get("title")),
        "references": [normalize_reference(e) for e in window if isinstance(e, dict)],
    }
