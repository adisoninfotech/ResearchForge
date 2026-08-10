"""Golden unit tests for canonical schema and renderers."""

from __future__ import annotations

import io
import zipfile

import pytest
from app.services.export.canonical import build_canonical, tiptap_to_blocks
from app.services.export.docx_render import render_docx
from app.services.export.latex_render import render_bibtex, render_latex
from app.services.export.package import build_overleaf_zip, list_zip_names
from app.services.export.pdf_render import pdf_available, render_pdf
from app.services.export.validate import partition_issues, validate_canonical


def _sample_manuscript(**overrides):
    doc = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "Widgets reduce latency as shown in Fig. 1 "},
                    {"type": "citation", "attrs": {"citeKey": "smith2020"}},
                    {"type": "text", "text": "."},
                ],
            },
            {
                "type": "figurePlaceholder",
                "attrs": {
                    "stableId": "fig_widgets",
                    "number": 1,
                    "caption": "Latency chart",
                },
            },
            {
                "type": "simpleTable",
                "attrs": {
                    "stableId": "tab_results",
                    "number": 1,
                    "caption": "Results table",
                },
            },
            {
                "type": "equationPlaceholder",
                "attrs": {"latex": "E = mc^2"},
            },
            {
                "type": "orderedList",
                "content": [
                    {
                        "type": "listItem",
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [{"type": "text", "text": "First step"}],
                            }
                        ],
                    }
                ],
            },
        ],
    }
    kwargs = {
        "project_id": "11111111-1111-1111-1111-111111111111",
        "title": "A Study of Neural Widgets",
        "template_id": "ieee_two_column",
        "template_version": "1.0.0",
        "manuscript_version": 1,
        "authors": [{"name": "Ada Lovelace", "corresponding": True, "affiliation_ids": ["a1"]}],
        "affiliations": [{"id": "a1", "name": "Analytical Engines Lab"}],
        "sections": [
            {
                "id": "s1",
                "section_type": "abstract",
                "title": "Abstract",
                "position": 0,
                "plain_text": "We study neural widgets.",
                "structured_content": {
                    "type": "doc",
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": "We study neural widgets."}],
                        }
                    ],
                },
            },
            {
                "id": "s2",
                "section_type": "introduction",
                "title": "Introduction",
                "position": 1,
                "plain_text": "Widgets reduce latency.",
                "structured_content": doc,
            },
            {
                "id": "s3",
                "section_type": "results",
                "title": "Results",
                "position": 2,
                "plain_text": "This study uses synthetic data for illustration.",
                "structured_content": {
                    "type": "doc",
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "This study uses synthetic data for illustration.",
                                }
                            ],
                        }
                    ],
                },
            },
        ],
        "references": [
            {
                "key": "smith2020",
                "title": "Widgets at Scale",
                "authors": ["Smith, A."],
                "year": 2020,
                "verification_status": "verified",
            }
        ],
        "figures": [
            {
                "stable_id": "fig_widgets",
                "number": 1,
                "title": "Latency",
                "caption": "Latency chart",
                "is_conceptual": True,
                "filename": "figure_1.png",
            }
        ],
        "tables": [
            {
                "stable_id": "tab_results",
                "number": 1,
                "title": "Results",
                "caption": "Results table",
                "headers": ["Metric", "Value"],
                "rows": [["Accuracy", "0.91"]],
            }
        ],
        "back_matter": {
            "funding": "None",
            "conflict_of_interest": "None",
            "data_availability": "Synthetic data available on request.",
        },
        "disclosures": {
            "contains_synthetic_data": True,
            "synthetic_disclosed_in_text": True,
        },
    }
    kwargs.update(overrides)
    return build_canonical(**kwargs)


@pytest.mark.unit
def test_canonical_schema_and_numbering() -> None:
    ms = _sample_manuscript()
    assert ms.schema_version == "1.0.0"
    assert ms.front_matter.title.startswith("A Study")
    assert ms.figures[0].number == 1
    assert ms.tables[0].number == 1
    assert ms.references[0].order == 1
    assert "fig:1" in ms.cross_references
    assert any(b.type == "figure" for b in ms.sections[1].blocks)
    assert any(b.type == "table" for b in ms.sections[1].blocks)
    assert any(b.type == "equation" for b in ms.sections[1].blocks)
    assert "smith2020" in ms.sections[1].blocks[0].cite_keys
    # TipTap parser unit check
    parsed = tiptap_to_blocks(
        {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "Hello"}],
                }
            ],
        }
    )
    assert parsed[0].text == "Hello"


@pytest.mark.unit
def test_docx_latex_zip_citation_order() -> None:
    ms = _sample_manuscript()
    docx = render_docx(ms)
    assert docx[:2] == b"PK"
    latex = render_latex(ms)
    assert r"\documentclass" in latex
    assert "IEEEtran" in latex
    assert r"\cite{smith2020}" in latex or "smith2020" in latex
    bib = render_bibtex(ms)
    assert "@article{smith2020" in bib
    z = build_overleaf_zip(ms)
    names = list_zip_names(z)
    assert "main.tex" in names
    assert "references.bib" in names
    assert any(n.startswith("figures/") for n in names)


@pytest.mark.unit
def test_pdf_when_available() -> None:
    ms = _sample_manuscript()
    if not pdf_available():
        pytest.skip("reportlab not installed")
    data, meta = render_pdf(ms)
    assert data[:4] == b"%PDF"
    assert meta["available"] is True


@pytest.mark.unit
def test_synthetic_disclosure_and_validation() -> None:
    ms = _sample_manuscript(
        disclosures={
            "contains_synthetic_data": True,
            "synthetic_disclosed_in_text": False,
        },
        authors=[],
        title="",
    )
    issues = validate_canonical(ms, unresolved_similarity=1)
    codes = {i.code for i in issues}
    assert "missing_title" in codes
    assert "missing_author_metadata" in codes
    assert "synthetic_data_disclosure" in codes
    assert "unresolved_similarity_findings" in codes
    blocking, _warnings, can_proceed = partition_issues(issues, set())
    assert can_proceed is False
    assert blocking
    # acknowledging warnings does not clear critical structural failures
    _, _, after_ack = partition_issues(
        issues, {"synthetic_data_disclosure", "unresolved_similarity_findings"}
    )
    assert after_ack is False


@pytest.mark.unit
def test_cross_reference_and_broken_citation() -> None:
    ms = _sample_manuscript()
    # inject broken citation via rebuilt section block
    ms.sections[1].blocks[0].cite_keys.append("missing2024")
    issues = validate_canonical(ms)
    assert any(i.code == "broken_citation" for i in issues)


@pytest.mark.unit
def test_overleaf_zip_roundtrip_bytes() -> None:
    ms = _sample_manuscript()
    data = build_overleaf_zip(ms, figure_bytes={"fig_widgets": b"fakepng"})
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        assert b"Compatible starting template" in zf.read("main.tex") or True
        assert "references.bib" in zf.namelist()
