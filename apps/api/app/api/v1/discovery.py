"""Paper discovery via Crossref.

Unauthenticated on purpose: /citations is a public page, and every response is
public bibliographic metadata that Crossref already serves to anyone. Nothing
here touches a project or a user. Rate limiting is applied because each call
makes an outbound request on the server's behalf.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import AppSettings, enforce_rate_limit
from app.schemas.discovery import (
    WorkReferencesResponse,
    WorkSearchRequest,
    WorkSearchResponse,
)
from app.services.files import crossref

router = APIRouter(prefix="/discovery", tags=["discovery"])


@router.post(
    "/search",
    response_model=WorkSearchResponse,
    dependencies=[Depends(enforce_rate_limit)],
)
async def search_papers(
    payload: WorkSearchRequest,
    settings: AppSettings,
) -> WorkSearchResponse:
    """Find papers matching a topic or a claim pasted from a draft."""
    results = await crossref.search_works(
        payload.query,
        settings=settings,
        limit=payload.limit,
        min_citations=payload.min_citations,
    )
    return WorkSearchResponse(query=payload.query, results=results)  # type: ignore[arg-type]


@router.get(
    "/references",
    response_model=WorkReferencesResponse,
    dependencies=[Depends(enforce_rate_limit)],
)
async def list_work_references(
    settings: AppSettings,
    doi: str = Query(min_length=3, max_length=200),
    limit: int = Query(default=25, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
) -> WorkReferencesResponse:
    """Return a paper's bibliography — often a better source of citable work
    than keyword search, since it is what the authors themselves relied on."""
    data = await crossref.fetch_references(doi, settings=settings, limit=limit, offset=offset)
    return WorkReferencesResponse(
        doi=doi,
        title=data.get("title"),
        total=data.get("total", 0),
        references=data.get("references", []),
    )
