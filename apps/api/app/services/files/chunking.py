"""Heading/paragraph-aware chunking with provenance offsets."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from app.core.config import Settings, get_settings


@dataclass
class ChunkDraft:
    chunk_index: int
    text: str
    heading: str | None
    page_number: int | None
    char_start: int | None
    char_end: int | None
    evidence_key: str
    token_count: int


_HEADING = re.compile(r"^(#{1,6}\s+.+|[A-Z][A-Za-z0-9 ,/&\-]{0,80})$")


def chunk_text(
    text: str,
    *,
    pages: list[tuple[int, str]] | None = None,
    project_file_id: str,
    settings: Settings | None = None,
) -> list[ChunkDraft]:
    settings = settings or get_settings()
    max_chars = settings.chunk_max_chars
    overlap = settings.chunk_overlap_chars

    if pages:
        drafts: list[ChunkDraft] = []
        idx = 0
        for page_number, page_text in pages:
            for piece, start, end, heading in _split_unit(page_text, max_chars, overlap):
                key = _evidence_key(project_file_id, idx, start, end)
                drafts.append(
                    ChunkDraft(
                        chunk_index=idx,
                        text=piece,
                        heading=heading,
                        page_number=page_number,
                        char_start=start,
                        char_end=end,
                        evidence_key=key,
                        token_count=max(1, len(piece.split())),
                    )
                )
                idx += 1
        return drafts

    drafts = []
    for idx, (piece, start, end, heading) in enumerate(_split_unit(text, max_chars, overlap)):
        drafts.append(
            ChunkDraft(
                chunk_index=idx,
                text=piece,
                heading=heading,
                page_number=1 if text else None,
                char_start=start,
                char_end=end,
                evidence_key=_evidence_key(project_file_id, idx, start, end),
                token_count=max(1, len(piece.split())),
            )
        )
    return drafts


def _split_unit(
    text: str,
    max_chars: int,
    overlap: int,
) -> list[tuple[str, int, int, str | None]]:
    if not text.strip():
        return []
    paragraphs = re.split(r"\n\s*\n", text)
    units: list[tuple[str, str | None]] = []
    current_heading: str | None = None
    for para in paragraphs:
        cleaned = para.strip()
        if not cleaned:
            continue
        first = cleaned.splitlines()[0].strip()
        if _HEADING.match(first) and len(cleaned.splitlines()) == 1:
            current_heading = first.lstrip("#").strip()
            continue
        units.append((cleaned, current_heading))

    out: list[tuple[str, int, int, str | None]] = []
    cursor = 0
    buf = ""
    buf_start = 0
    heading: str | None = None
    for unit, unit_heading in units:
        pos = text.find(unit, cursor)
        if pos < 0:
            pos = cursor
        if not buf:
            buf_start = pos
            heading = unit_heading
        candidate = f"{buf}\n\n{unit}".strip() if buf else unit
        if len(candidate) > max_chars and buf:
            end = buf_start + len(buf)
            out.append((buf, buf_start, end, heading))
            # overlap
            overlap_text = buf[-overlap:] if overlap and len(buf) > overlap else ""
            buf = f"{overlap_text}\n\n{unit}".strip() if overlap_text else unit
            buf_start = max(buf_start, end - len(overlap_text)) if overlap_text else pos
            heading = unit_heading
        else:
            buf = candidate
        cursor = pos + len(unit)
    if buf:
        out.append((buf, buf_start, buf_start + len(buf), heading))
    return out


def _evidence_key(file_id: str, index: int, start: int | None, end: int | None) -> str:
    raw = f"{file_id}:{index}:{start}:{end}"
    return "ev_" + hashlib.sha256(raw.encode()).hexdigest()[:16]
