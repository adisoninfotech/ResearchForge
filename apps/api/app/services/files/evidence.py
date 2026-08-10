"""Evidence workspace and claim provenance."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationAppError
from app.core.time import utcnow
from app.models.enums import ClaimSupportStatus, EvidenceRelation
from app.models.evidence import CitationMention, ClaimProvenance, EvidenceLink
from app.models.project_file import DocumentChunk


def _relation(value: str) -> EvidenceRelation:
    try:
        return EvidenceRelation(value)
    except ValueError as exc:
        raise ValidationAppError(f"Invalid evidence relation: {value}") from exc


async def pin_evidence(
    db: AsyncSession,
    *,
    project_id: UUID,
    chunk_id: UUID,
    section_id: UUID | None,
    relation: str,
    note: str | None = None,
) -> EvidenceLink:
    chunk = await db.scalar(
        select(DocumentChunk).where(
            DocumentChunk.id == chunk_id,
            DocumentChunk.project_id == project_id,
        )
    )
    if chunk is None:
        raise NotFoundError("Evidence chunk not found")
    link = EvidenceLink(
        project_id=project_id,
        chunk_id=chunk_id,
        section_id=section_id,
        relation=_relation(relation),
        note=note,
        pinned=True,
        exclude_from_ai=False,
    )
    db.add(link)
    await db.flush()
    await db.refresh(link)
    return link


async def list_evidence_links(
    db: AsyncSession,
    *,
    project_id: UUID,
    section_id: UUID | None = None,
) -> list[dict[str, Any]]:
    stmt = select(EvidenceLink).where(EvidenceLink.project_id == project_id)
    if section_id:
        stmt = stmt.where(EvidenceLink.section_id == section_id)
    links = list((await db.scalars(stmt)).all())
    out: list[dict[str, Any]] = []
    for link in links:
        chunk = await db.get(DocumentChunk, link.chunk_id)
        out.append(
            {
                "id": str(link.id),
                "chunk_id": str(link.chunk_id),
                "section_id": str(link.section_id) if link.section_id else None,
                "relation": link.relation.value,
                "note": link.note,
                "pinned": link.pinned,
                "exclude_from_ai": link.exclude_from_ai,
                "passage": {
                    "text": chunk.text if chunk else "",
                    "evidence_key": chunk.evidence_key if chunk else None,
                    "page": chunk.page_number if chunk else None,
                    "source_file_id": str(chunk.project_file_id) if chunk else None,
                },
            }
        )
    return out


async def update_evidence_link(
    db: AsyncSession,
    *,
    project_id: UUID,
    link_id: UUID,
    payload: dict[str, Any],
) -> EvidenceLink:
    link = await db.scalar(
        select(EvidenceLink).where(
            EvidenceLink.id == link_id,
            EvidenceLink.project_id == project_id,
        )
    )
    if link is None:
        raise NotFoundError("Evidence link not found")
    if "note" in payload:
        link.note = payload["note"]
    if payload.get("relation"):
        link.relation = _relation(str(payload["relation"]))
    if payload.get("exclude_from_ai") is not None:
        link.exclude_from_ai = bool(payload["exclude_from_ai"])
    if payload.get("pinned") is not None:
        link.pinned = bool(payload["pinned"])
    await db.flush()
    return link


async def remove_evidence_link(
    db: AsyncSession,
    *,
    project_id: UUID,
    link_id: UUID,
) -> None:
    link = await db.scalar(
        select(EvidenceLink).where(
            EvidenceLink.id == link_id,
            EvidenceLink.project_id == project_id,
        )
    )
    if link is None:
        raise NotFoundError("Evidence link not found")
    await db.delete(link)
    await db.flush()


def infer_support_status(
    *,
    evidence_ids: list[str],
    warning: str | None = None,
) -> ClaimSupportStatus:
    if warning and "conflict" in warning.lower():
        return ClaimSupportStatus.CONFLICTING_EVIDENCE
    if not evidence_ids:
        return ClaimSupportStatus.UNSUPPORTED
    if warning and "partial" in warning.lower():
        return ClaimSupportStatus.PARTIALLY_SUPPORTED
    if warning and "citation" in warning.lower():
        return ClaimSupportStatus.CITATION_MISSING
    return ClaimSupportStatus.SUPPORTED


async def store_claims_from_ai(
    db: AsyncSession,
    *,
    project_id: UUID,
    section_id: UUID | None,
    claims: list[dict[str, Any]],
    model_metadata: dict[str, Any] | None,
) -> list[ClaimProvenance]:
    rows: list[ClaimProvenance] = []
    for claim in claims:
        evidence_ids = [str(x) for x in (claim.get("evidence_ids") or [])]
        status = infer_support_status(
            evidence_ids=evidence_ids,
            warning=claim.get("warning"),
        )
        if claim.get("supported") is False and evidence_ids:
            status = ClaimSupportStatus.PARTIALLY_SUPPORTED
        if claim.get("supported") is False and not evidence_ids:
            status = ClaimSupportStatus.UNSUPPORTED
        row = ClaimProvenance(
            project_id=project_id,
            section_id=section_id,
            claim_text=str(claim.get("text") or ""),
            evidence_chunk_ids=evidence_ids,
            support_score=1.0 if status == ClaimSupportStatus.SUPPORTED else 0.0,
            support_status=status,
            user_verification_status="unverified",
            citation_required=True,
            model_metadata=model_metadata,
            generated_at=utcnow(),
        )
        db.add(row)
        rows.append(row)
    await db.flush()
    return rows


async def list_claims(
    db: AsyncSession,
    *,
    project_id: UUID,
    section_id: UUID | None = None,
) -> list[dict[str, Any]]:
    stmt = select(ClaimProvenance).where(ClaimProvenance.project_id == project_id)
    if section_id:
        stmt = stmt.where(ClaimProvenance.section_id == section_id)
    rows = await db.scalars(stmt.order_by(ClaimProvenance.generated_at.desc()))
    return [
        {
            "id": str(r.id),
            "claim_text": r.claim_text,
            "evidence_chunk_ids": r.evidence_chunk_ids,
            "support_score": r.support_score,
            "support_status": r.support_status.value,
            "user_verification_status": r.user_verification_status,
            "citation_required": r.citation_required,
            "section_id": str(r.section_id) if r.section_id else None,
            "generated_at": r.generated_at.isoformat(),
            "model_metadata": r.model_metadata,
        }
        for r in rows.all()
    ]


async def list_citation_mentions(
    db: AsyncSession,
    *,
    project_id: UUID,
    reference_id: UUID | None = None,
) -> list[dict[str, Any]]:
    stmt = select(CitationMention).where(CitationMention.project_id == project_id)
    if reference_id:
        stmt = stmt.where(CitationMention.reference_id == reference_id)
    rows = await db.scalars(stmt)
    return [
        {
            "id": str(r.id),
            "reference_id": str(r.reference_id) if r.reference_id else None,
            "chunk_id": str(r.chunk_id) if r.chunk_id else None,
            "section_id": str(r.section_id) if r.section_id else None,
            "cite_key": r.cite_key,
            "context_snippet": r.context_snippet,
        }
        for r in rows.all()
    ]
