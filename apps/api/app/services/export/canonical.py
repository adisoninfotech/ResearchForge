"""Canonical manuscript schema — single source for all renderers."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

SCHEMA_VERSION = "1.0.0"

BlockType = Literal[
    "paragraph",
    "heading",
    "list",
    "equation",
    "table",
    "figure",
    "blockquote",
    "raw",
]


@dataclass
class Author:
    name: str
    affiliation_ids: list[str] = field(default_factory=list)
    email: str | None = None
    orcid: str | None = None
    corresponding: bool = False


@dataclass
class Affiliation:
    id: str
    name: str
    department: str | None = None
    address: str | None = None


@dataclass
class CitationRef:
    key: str
    title: str | None = None
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    doi: str | None = None
    url: str | None = None
    verification_status: str = "unverified"
    order: int = 0


@dataclass
class FigureAsset:
    id: str
    number: int
    title: str
    caption: str
    alt_text: str = ""
    filename: str | None = None
    storage_key: str | None = None
    provenance_label: str = ""
    is_conceptual: bool = False
    missing_file: bool = False


@dataclass
class TableAsset:
    id: str
    number: int
    title: str
    caption: str
    headers: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    provenance_label: str = ""


@dataclass
class ContentBlock:
    type: BlockType
    text: str = ""
    level: int | None = None
    ordered: bool | None = None
    items: list[str] = field(default_factory=list)
    latex: str | None = None
    figure_id: str | None = None
    table_id: str | None = None
    cite_keys: list[str] = field(default_factory=list)
    cross_ref_ids: list[str] = field(default_factory=list)
    attrs: dict[str, Any] = field(default_factory=dict)


@dataclass
class Section:
    id: str
    section_type: str
    title: str
    position: int
    blocks: list[ContentBlock] = field(default_factory=list)
    plain_text: str = ""
    model_generated: bool = False


@dataclass
class FrontMatter:
    title: str
    authors: list[Author] = field(default_factory=list)
    affiliations: list[Affiliation] = field(default_factory=list)
    abstract: str = ""
    keywords: list[str] = field(default_factory=list)


@dataclass
class BackMatter:
    acknowledgments: str = ""
    funding: str = ""
    conflict_of_interest: str = ""
    ethics: str = ""
    data_availability: str = ""
    supplementary_materials: str = ""


@dataclass
class CanonicalManuscript:
    schema_version: str
    project_id: str
    manuscript_version: int | None
    template_id: str
    template_version: str
    generated_at: str
    front_matter: FrontMatter
    sections: list[Section]
    back_matter: BackMatter
    references: list[CitationRef]
    figures: list[FigureAsset]
    tables: list[TableAsset]
    disclosures: dict[str, Any] = field(default_factory=dict)
    cross_references: dict[str, str] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def content_sha256(self) -> str:
        payload = json.dumps(self.to_dict(), sort_keys=True, default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


_XREF_RE = re.compile(r"\\?(?:ref|cref)\{([^}]+)\}|Fig(?:ure)?\.?\s*(\d+)|Table\.?\s*(\d+)", re.I)


def _node_text(node: dict[str, Any]) -> str:
    parts: list[str] = []
    ntype = node.get("type")
    if ntype == "text":
        return str(node.get("text") or "")
    if ntype == "citation":
        key = (node.get("attrs") or {}).get("citeKey") or "cite"
        return f"[{key}]"
    for child in node.get("content") or []:
        if isinstance(child, dict):
            parts.append(_node_text(child))
    return "".join(parts)


def _collect_cites(node: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    if node.get("type") == "citation":
        key = (node.get("attrs") or {}).get("citeKey")
        if key:
            keys.append(str(key))
    for child in node.get("content") or []:
        if isinstance(child, dict):
            keys.extend(_collect_cites(child))
    return keys


def tiptap_to_blocks(doc: dict[str, Any] | None) -> list[ContentBlock]:
    if not doc or not isinstance(doc, dict):
        return []
    blocks: list[ContentBlock] = []
    for node in doc.get("content") or []:
        if not isinstance(node, dict):
            continue
        ntype = node.get("type")
        attrs = dict(node.get("attrs") or {})
        if ntype == "paragraph":
            text = _node_text(node).strip()
            if text:
                blocks.append(
                    ContentBlock(
                        type="paragraph",
                        text=text,
                        cite_keys=_collect_cites(node),
                        cross_ref_ids=_extract_xrefs(text),
                    )
                )
        elif ntype == "heading":
            level = int(attrs.get("level") or 2)
            text = _node_text(node).strip()
            blocks.append(ContentBlock(type="heading", text=text, level=level))
        elif ntype in {"bulletList", "orderedList"}:
            items: list[str] = []
            for li in node.get("content") or []:
                if isinstance(li, dict):
                    items.append(_node_text(li).strip())
            blocks.append(
                ContentBlock(
                    type="list",
                    ordered=ntype == "orderedList",
                    items=[i for i in items if i],
                )
            )
        elif ntype == "equationPlaceholder":
            blocks.append(
                ContentBlock(
                    type="equation",
                    latex=str(attrs.get("latex") or ""),
                    text=str(attrs.get("latex") or ""),
                )
            )
        elif ntype == "figurePlaceholder":
            fid = str(attrs.get("stableId") or attrs.get("number") or "")
            blocks.append(
                ContentBlock(
                    type="figure",
                    text=str(attrs.get("caption") or attrs.get("title") or ""),
                    figure_id=fid or None,
                    attrs=attrs,
                )
            )
        elif ntype == "simpleTable":
            tid = str(attrs.get("stableId") or attrs.get("number") or "")
            blocks.append(
                ContentBlock(
                    type="table",
                    text=str(attrs.get("caption") or attrs.get("title") or ""),
                    table_id=tid or None,
                    attrs=attrs,
                )
            )
        elif ntype == "blockquote":
            blocks.append(ContentBlock(type="blockquote", text=_node_text(node).strip()))
    return blocks


def _extract_xrefs(text: str) -> list[str]:
    found: list[str] = []
    for m in _XREF_RE.finditer(text):
        if m.group(1):
            found.append(m.group(1))
        elif m.group(2):
            found.append(f"fig:{m.group(2)}")
        elif m.group(3):
            found.append(f"tab:{m.group(3)}")
    return found


def build_canonical(
    *,
    project_id: UUID | str,
    title: str,
    template_id: str,
    template_version: str,
    manuscript_version: int | None,
    authors: list[dict[str, Any]],
    affiliations: list[dict[str, Any]],
    sections: list[dict[str, Any]],
    references: list[dict[str, Any]],
    figures: list[dict[str, Any]],
    tables: list[dict[str, Any]],
    back_matter: dict[str, Any] | None = None,
    disclosures: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
) -> CanonicalManuscript:
    abstract = ""
    keywords: list[str] = []
    canon_sections: list[Section] = []
    for sec in sorted(sections, key=lambda s: int(s.get("position") or 0)):
        blocks = tiptap_to_blocks(sec.get("structured_content"))
        if not blocks and sec.get("plain_text"):
            blocks = [ContentBlock(type="paragraph", text=str(sec["plain_text"]))]
        stype = str(sec.get("section_type") or "custom")
        if stype == "abstract":
            abstract = str(sec.get("plain_text") or "") or " ".join(b.text for b in blocks)
        if stype == "keywords":
            raw = str(sec.get("plain_text") or "")
            keywords = [k.strip() for k in re.split(r"[,;]", raw) if k.strip()]
        canon_sections.append(
            Section(
                id=str(sec.get("id") or ""),
                section_type=stype,
                title=str(sec.get("title") or stype.title()),
                position=int(sec.get("position") or 0),
                blocks=blocks,
                plain_text=str(sec.get("plain_text") or ""),
                model_generated=bool(sec.get("model_generated")),
            )
        )

    fm_authors = [
        Author(
            name=str(a.get("name") or ""),
            affiliation_ids=[str(x) for x in (a.get("affiliation_ids") or [])],
            email=a.get("email"),
            orcid=a.get("orcid"),
            corresponding=bool(a.get("corresponding")),
        )
        for a in authors
        if a.get("name")
    ]
    fm_affils = [
        Affiliation(
            id=str(a.get("id") or f"aff{i + 1}"),
            name=str(a.get("name") or ""),
            department=a.get("department"),
            address=a.get("address"),
        )
        for i, a in enumerate(affiliations)
        if a.get("name")
    ]

    refs = [
        CitationRef(
            key=str(r.get("key") or r.get("cite_key") or f"ref{i + 1}"),
            title=r.get("title"),
            authors=list(r.get("authors") or []),
            year=r.get("year"),
            venue=r.get("venue"),
            doi=r.get("doi"),
            url=r.get("url"),
            verification_status=str(r.get("verification_status") or "unverified"),
            order=i + 1,
        )
        for i, r in enumerate(references)
    ]

    fig_assets = [
        FigureAsset(
            id=str(f.get("stable_id") or f.get("id") or f"fig{i + 1}"),
            number=int(f.get("number") or i + 1),
            title=str(f.get("title") or f"Figure {i + 1}"),
            caption=str(f.get("caption") or ""),
            alt_text=str(f.get("alt_text") or ""),
            filename=f.get("filename"),
            storage_key=f.get("storage_png") or f.get("storage_key"),
            provenance_label=str(f.get("provenance_label") or ""),
            is_conceptual=bool(f.get("is_conceptual")),
            missing_file=not bool(
                f.get("storage_png") or f.get("storage_key") or f.get("is_conceptual")
            ),
        )
        for i, f in enumerate(sorted(figures, key=lambda x: int(x.get("number") or 0)))
    ]
    # renumber sequentially for export consistency
    for i, fig in enumerate(fig_assets, start=1):
        fig.number = i

    tab_assets = [
        TableAsset(
            id=str(t.get("stable_id") or t.get("id") or f"tab{i + 1}"),
            number=int(t.get("number") or i + 1),
            title=str(t.get("title") or f"Table {i + 1}"),
            caption=str(t.get("caption") or ""),
            headers=list(t.get("headers") or (t.get("content_json") or {}).get("headers") or []),
            rows=list(t.get("rows") or (t.get("content_json") or {}).get("rows") or []),
            provenance_label=str(t.get("provenance_label") or ""),
        )
        for i, t in enumerate(sorted(tables, key=lambda x: int(x.get("number") or 0)))
    ]
    for i, tab in enumerate(tab_assets, start=1):
        tab.number = i

    bm = back_matter or {}
    xref: dict[str, str] = {}
    for fig in fig_assets:
        xref[f"fig:{fig.number}"] = fig.id
        xref[fig.id] = f"Figure {fig.number}"
    for tab in tab_assets:
        xref[f"tab:{tab.number}"] = tab.id
        xref[tab.id] = f"Table {tab.number}"

    return CanonicalManuscript(
        schema_version=SCHEMA_VERSION,
        project_id=str(project_id),
        manuscript_version=manuscript_version,
        template_id=template_id,
        template_version=template_version,
        generated_at=datetime.now(UTC).isoformat(),
        front_matter=FrontMatter(
            title=title.strip(),
            authors=fm_authors,
            affiliations=fm_affils,
            abstract=abstract,
            keywords=keywords,
        ),
        sections=canon_sections,
        back_matter=BackMatter(
            acknowledgments=str(bm.get("acknowledgments") or ""),
            funding=str(bm.get("funding") or ""),
            conflict_of_interest=str(bm.get("conflict_of_interest") or ""),
            ethics=str(bm.get("ethics") or ""),
            data_availability=str(bm.get("data_availability") or ""),
            supplementary_materials=str(bm.get("supplementary_materials") or ""),
        ),
        references=refs,
        figures=fig_assets,
        tables=tab_assets,
        disclosures=disclosures or {},
        cross_references=xref,
        meta=meta or {},
    )
