"""HTML preview renderer from canonical manuscript."""

from __future__ import annotations

import html
from typing import Any

from app.services.export.canonical import CanonicalManuscript, ContentBlock, Section
from app.services.export.templates import ExportTemplate, get_template


def _esc(text: str) -> str:
    return html.escape(text or "", quote=True)


def _render_block(block: ContentBlock, manuscript: CanonicalManuscript) -> str:
    if block.type == "heading":
        level = min(max(block.level or 2, 2), 4)
        return f"<h{level}>{_esc(block.text)}</h{level}>"
    if block.type == "list":
        tag = "ol" if block.ordered else "ul"
        items = "".join(f"<li>{_esc(i)}</li>" for i in block.items)
        return f"<{tag}>{items}</{tag}>"
    if block.type == "equation":
        return f'<pre class="rf-equation">{_esc(block.latex or block.text)}</pre>'
    if block.type == "figure":
        fig = next(
            (f for f in manuscript.figures if f.id == block.figure_id),
            None,
        )
        if fig is None and block.figure_id:
            try:
                num = int(block.figure_id)
                fig = next((f for f in manuscript.figures if f.number == num), None)
            except ValueError:
                fig = None
        if fig:
            return (
                f'<figure id="{_esc(fig.id)}">'
                f'<div class="rf-figure-box">[Figure {fig.number}]</div>'
                f"<figcaption>Figure {fig.number}: {_esc(fig.caption or fig.title)}"
                f"{' [' + _esc(fig.provenance_label) + ']' if fig.provenance_label else ''}"
                f"</figcaption></figure>"
            )
        return f"<figure><figcaption>{_esc(block.text)}</figcaption></figure>"
    if block.type == "table":
        tab = next((t for t in manuscript.tables if t.id == block.table_id), None)
        if tab is None:
            return f'<div class="rf-table">{_esc(block.text)}</div>'
        head = ""
        if tab.headers:
            head = (
                "<thead><tr>"
                + "".join(f"<th>{_esc(h)}</th>" for h in tab.headers)
                + "</tr></thead>"
            )
        body_rows = "".join(
            "<tr>" + "".join(f"<td>{_esc(str(c))}</td>" for c in row) + "</tr>" for row in tab.rows
        )
        return (
            f'<table id="{_esc(tab.id)}">{head}<tbody>{body_rows}</tbody></table>'
            f"<p class='rf-caption'>Table {tab.number}: {_esc(tab.caption or tab.title)}</p>"
        )
    if block.type == "blockquote":
        return f"<blockquote>{_esc(block.text)}</blockquote>"
    return f"<p>{_esc(block.text)}</p>"


def _render_section(section: Section, manuscript: CanonicalManuscript) -> str:
    if section.section_type in {"abstract", "keywords"}:
        return ""
    body = "".join(_render_block(b, manuscript) for b in section.blocks)
    return f'<section id="sec-{_esc(section.id)}"><h2>{_esc(section.title)}</h2>{body}</section>'


def render_html(
    manuscript: CanonicalManuscript,
    *,
    template_id: str | None = None,
    page: int | None = None,
    page_size_chars: int = 3500,
) -> dict[str, Any]:
    tpl = get_template(template_id or manuscript.template_id)
    fm = manuscript.front_matter
    authors = ", ".join(a.name for a in fm.authors) or "Author metadata required"
    affils = "".join(f"<li>{_esc(a.name)}</li>" for a in fm.affiliations)
    keywords = ", ".join(fm.keywords)

    body_parts = [
        f'<header class="rf-front"><h1>{_esc(fm.title)}</h1>',
        f'<p class="rf-authors">{_esc(authors)}</p>',
        f'<ul class="rf-affils">{affils}</ul>' if affils else "",
        f'<section class="rf-abstract"><h2>Abstract</h2><p>{_esc(fm.abstract)}</p></section>'
        if fm.abstract
        else "",
        f'<p class="rf-keywords"><strong>Keywords:</strong> {_esc(keywords)}</p>'
        if keywords
        else "",
        "</header>",
    ]
    for section in manuscript.sections:
        body_parts.append(_render_section(section, manuscript))

    bm = manuscript.back_matter
    for title, value in (
        ("Acknowledgments", bm.acknowledgments),
        ("Funding", bm.funding),
        ("Conflict of Interest", bm.conflict_of_interest),
        ("Ethics", bm.ethics),
        ("Data Availability", bm.data_availability),
        ("Supplementary Materials", bm.supplementary_materials),
    ):
        if value.strip():
            body_parts.append(f"<section><h2>{_esc(title)}</h2><p>{_esc(value)}</p></section>")

    if manuscript.references:
        refs_html = "".join(
            f'<li id="cite-{_esc(r.key)}">[{r.order}] '
            f"{_esc(', '.join(r.authors))}. {_esc(r.title or '')}"
            f"{' (' + str(r.year) + ')' if r.year else ''}.</li>"
            for r in manuscript.references
        )
        body_parts.append(f"<section><h2>References</h2><ol>{refs_html}</ol></section>")

    body_parts.append(f'<aside class="rf-template-warning"><p>{_esc(tpl.warning)}</p></aside>')

    full_body = "\n".join(p for p in body_parts if p)
    pages = _paginate(full_body, page_size_chars)
    selected = pages[(page or 1) - 1] if page and 1 <= page <= len(pages) else full_body

    css = _template_css(tpl)
    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>{_esc(fm.title)}</title>
<style>{css}</style>
</head>
<body class="{tpl.css_class} cols-{tpl.column_layout}">
{selected}
</body>
</html>
"""
    return {
        "html": html_doc,
        "page": page or 1,
        "page_count": max(1, len(pages)),
        "template_id": tpl.id.value,
        "template_warning": tpl.warning,
        "column_layout": tpl.column_layout,
    }


def _paginate(html_body: str, size: int) -> list[str]:
    if len(html_body) <= size:
        return [html_body]
    pages: list[str] = []
    start = 0
    while start < len(html_body):
        pages.append(html_body[start : start + size])
        start += size
    return pages


def _template_css(tpl: ExportTemplate) -> str:
    cols = (
        "column-count: 2; column-gap: 1.2rem;" if tpl.column_layout == "two" else "column-count: 1;"
    )
    return f"""
body {{ font-family: "Libre Baskerville", "Georgia", serif; margin: 1.5rem; line-height: 1.45;
  max-width: {tpl.page_width_in}in; }}
body.cols-two .rf-front, body.cols-two section {{ {cols} }}
h1 {{ font-size: 1.6rem; margin-bottom: 0.4rem; }}
h2 {{ font-size: 1.15rem; margin-top: 1.2rem; }}
.rf-authors {{ font-style: italic; }}
.rf-figure-box {{ border: 1px dashed #888; padding: 2rem; text-align: center; }}
.rf-template-warning {{ margin-top: 2rem; font-size: 0.85rem; color: #444;
  border-top: 1px solid #ccc; padding-top: 0.75rem; }}
table {{ border-collapse: collapse; width: 100%; margin: 0.75rem 0; }}
th, td {{ border: 1px solid #999; padding: 0.25rem 0.4rem; font-size: 0.9rem; }}
"""
