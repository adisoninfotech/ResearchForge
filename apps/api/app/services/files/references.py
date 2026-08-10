"""Reference management: import, dedupe, export — never invent metadata."""

from __future__ import annotations

import hashlib
import re
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError, ValidationAppError
from app.models.enums import ReferenceVerificationStatus
from app.models.reference import Reference, ReferenceAuthor, ReferenceIdentifier
from app.services.files.extract import parse_bibtex, parse_ris


def _fingerprint(
    *,
    title: str | None,
    doi: str | None,
    year: int | None,
    authors: list[str],
) -> str:
    doi_norm = (doi or "").strip().lower()
    if doi_norm:
        return hashlib.sha256(f"doi:{doi_norm}".encode()).hexdigest()
    author_key = "|".join(a.lower().strip() for a in authors[:3])
    title_key = re.sub(r"\s+", " ", (title or "").lower()).strip()
    raw = f"{title_key}|{year or ''}|{author_key}"
    return hashlib.sha256(raw.encode()).hexdigest()


def reference_to_dict(ref: Reference) -> dict[str, Any]:
    return {
        "id": str(ref.id),
        "project_id": str(ref.project_id),
        "title": ref.title,
        "year": ref.year,
        "venue": ref.venue,
        "url": ref.url,
        "doi": ref.doi,
        "abstract": ref.abstract,
        "verification_status": ref.verification_status.value,
        "needs_user_correction": ref.needs_user_correction,
        "authors": [a.full_name for a in sorted(ref.authors, key=lambda x: x.position)],
        "identifiers": [{"type": i.id_type, "value": i.value} for i in ref.identifiers],
        "source_file_id": str(ref.source_file_id) if ref.source_file_id else None,
    }


async def import_parsed_entries(
    db: AsyncSession,
    *,
    project_id: UUID,
    entries: list[dict[str, Any]],
    source_file_id: UUID | None = None,
    source_format: str = "manual",
) -> list[Reference]:
    created: list[Reference] = []
    for entry in entries:
        authors = list(entry.get("authors") or [])
        title = entry.get("title")
        doi = entry.get("doi")
        year = entry.get("year")
        if isinstance(year, str) and year.isdigit():
            year = int(year)
        if not isinstance(year, int):
            year = None
        fp = _fingerprint(title=title, doi=doi, year=year, authors=authors)
        existing = await db.scalar(
            select(Reference).where(
                Reference.project_id == project_id,
                Reference.fingerprint == fp,
            )
        )
        if existing is not None:
            existing.verification_status = ReferenceVerificationStatus.DUPLICATE
            continue

        needs_correction = not title or not authors
        ref = Reference(
            project_id=project_id,
            title=title,
            year=year,
            venue=entry.get("venue") or entry.get("journal"),
            url=entry.get("url"),
            abstract=entry.get("abstract"),
            doi=doi,
            fingerprint=fp,
            verification_status=(
                ReferenceVerificationStatus.NEEDS_CORRECTION
                if needs_correction
                else ReferenceVerificationStatus.UNVERIFIED
            ),
            source_file_id=source_file_id,
            raw_bibtex=None,
            metadata_json={"source_format": source_format, "cite_key": entry.get("cite_key")},
            needs_user_correction=needs_correction,
        )
        db.add(ref)
        await db.flush()
        for idx, name in enumerate(authors):
            db.add(ReferenceAuthor(reference_id=ref.id, full_name=name, position=idx))
        if doi:
            db.add(ReferenceIdentifier(reference_id=ref.id, id_type="doi", value=doi))
        created.append(ref)
    await db.flush()
    return created


async def create_manual_reference(
    db: AsyncSession,
    *,
    project_id: UUID,
    payload: dict[str, Any],
) -> Reference:
    authors = list(payload.get("authors") or [])
    title = payload.get("title")
    doi = payload.get("doi")
    year = payload.get("year")
    fp = _fingerprint(title=title, doi=doi, year=year, authors=authors)
    existing = await db.scalar(
        select(Reference).where(Reference.project_id == project_id, Reference.fingerprint == fp)
    )
    if existing is not None:
        existing.verification_status = ReferenceVerificationStatus.DUPLICATE
        await db.flush()
        return existing
    needs_correction = not title
    ref = Reference(
        project_id=project_id,
        title=title,
        year=year,
        venue=payload.get("venue"),
        url=payload.get("url"),
        abstract=payload.get("abstract"),
        doi=doi,
        fingerprint=fp,
        verification_status=(
            ReferenceVerificationStatus.NEEDS_CORRECTION
            if needs_correction
            else ReferenceVerificationStatus.UNVERIFIED
        ),
        needs_user_correction=needs_correction,
        metadata_json={"source_format": "manual"},
    )
    db.add(ref)
    await db.flush()
    for idx, name in enumerate(authors):
        db.add(ReferenceAuthor(reference_id=ref.id, full_name=str(name), position=idx))
    if doi:
        db.add(ReferenceIdentifier(reference_id=ref.id, id_type="doi", value=str(doi)))
    await db.refresh(ref, attribute_names=["authors", "identifiers"])
    return ref


async def import_text(
    db: AsyncSession,
    *,
    project_id: UUID,
    text: str,
    format: str,
) -> list[Reference]:
    if format == "bibtex":
        entries = parse_bibtex(text)
    elif format == "ris":
        entries = parse_ris(text)
    else:
        raise ValidationAppError("Unsupported reference import format")
    refs = await import_parsed_entries(
        db, project_id=project_id, entries=entries, source_format=format
    )
    # load authors
    result = []
    for ref in refs:
        loaded = await db.scalar(
            select(Reference)
            .where(Reference.id == ref.id)
            .options(selectinload(Reference.authors), selectinload(Reference.identifiers))
        )
        if loaded:
            result.append(loaded)
    return result


async def update_reference(
    db: AsyncSession,
    *,
    project_id: UUID,
    reference_id: UUID,
    payload: dict[str, Any],
) -> Reference:
    ref = await db.scalar(
        select(Reference)
        .where(Reference.id == reference_id, Reference.project_id == project_id)
        .options(selectinload(Reference.authors), selectinload(Reference.identifiers))
    )
    if ref is None:
        raise NotFoundError("Reference not found")
    for field in ("title", "venue", "url", "abstract", "doi"):
        if field in payload:
            setattr(ref, field, payload[field])
    if "year" in payload:
        ref.year = payload["year"]
    if "authors" in payload and payload["authors"] is not None:
        for author in list(ref.authors):
            await db.delete(author)
        await db.flush()
        for idx, name in enumerate(payload["authors"]):
            db.add(ReferenceAuthor(reference_id=ref.id, full_name=str(name), position=idx))
    if payload.get("verification_status"):
        ref.verification_status = ReferenceVerificationStatus(payload["verification_status"])
    ref.needs_user_correction = not bool(ref.title)
    authors = [a.full_name for a in ref.authors]
    ref.fingerprint = _fingerprint(title=ref.title, doi=ref.doi, year=ref.year, authors=authors)
    await db.flush()
    await db.refresh(ref, attribute_names=["authors", "identifiers"])
    return ref


async def list_references(
    db: AsyncSession,
    *,
    project_id: UUID,
    q: str | None = None,
) -> list[Reference]:
    stmt = (
        select(Reference)
        .where(Reference.project_id == project_id)
        .options(selectinload(Reference.authors), selectinload(Reference.identifiers))
        .order_by(Reference.created_at.desc())
    )
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Reference.title.ilike(pattern),
                Reference.doi.ilike(pattern),
                Reference.venue.ilike(pattern),
            )
        )
    rows = await db.scalars(stmt)
    return list(rows.all())


def export_bibtex(refs: list[Reference]) -> str:
    blocks: list[str] = []
    for idx, ref in enumerate(refs, start=1):
        key = (ref.metadata_json or {}).get("cite_key") or f"ref{idx}"
        authors = " and ".join(a.full_name for a in sorted(ref.authors, key=lambda x: x.position))
        lines = [f"@article{{{key},"]
        if ref.title:
            lines.append(f"  title = {{{ref.title}}},")
        if authors:
            lines.append(f"  author = {{{authors}}},")
        if ref.year:
            lines.append(f"  year = {{{ref.year}}},")
        if ref.venue:
            lines.append(f"  journal = {{{ref.venue}}},")
        if ref.doi:
            lines.append(f"  doi = {{{ref.doi}}},")
        if ref.url:
            lines.append(f"  url = {{{ref.url}}},")
        lines.append("}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def export_ris(refs: list[Reference]) -> str:
    blocks: list[str] = []
    for ref in refs:
        lines = ["TY  - JOUR"]
        if ref.title:
            lines.append(f"TI  - {ref.title}")
        for author in sorted(ref.authors, key=lambda x: x.position):
            lines.append(f"AU  - {author.full_name}")
        if ref.year:
            lines.append(f"PY  - {ref.year}")
        if ref.venue:
            lines.append(f"JO  - {ref.venue}")
        if ref.doi:
            lines.append(f"DO  - {ref.doi}")
        if ref.url:
            lines.append(f"UR  - {ref.url}")
        lines.append("ER  - ")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + ("\n" if blocks else "")
