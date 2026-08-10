"""PDF renderer from canonical manuscript / HTML.

Primary path uses reportlab (pure Python). Optional weasyprint can be used when
system packages are installed; absence must not break exports.
"""

from __future__ import annotations

import io
import textwrap
from typing import Any

from app.services.export.canonical import CanonicalManuscript
from app.services.export.templates import get_template

PDF_ENGINE_VERSION = "reportlab-minimal/1.0"


def pdf_available() -> bool:
    try:
        import reportlab  # noqa: F401

        return True
    except ImportError:
        return False


def render_pdf(manuscript: CanonicalManuscript) -> tuple[bytes, dict[str, Any]]:
    """Render PDF; raises RuntimeError if no PDF engine is available."""
    if pdf_available():
        return _render_reportlab(manuscript), {
            "engine": "reportlab",
            "version": PDF_ENGINE_VERSION,
            "available": True,
        }
    # Optional weasyprint path
    try:
        import weasyprint  # type: ignore[import-not-found]

        from app.services.export.html_render import render_html

        html = render_html(manuscript)["html"]
        data = weasyprint.HTML(string=html).write_pdf()
        return bytes(data), {
            "engine": "weasyprint",
            "version": "optional",
            "available": True,
        }
    except Exception as exc:
        raise RuntimeError(
            "PDF generation dependencies are not available. "
            "Install reportlab (preferred) or weasyprint with system libraries."
        ) from exc


def render_text_pdf(title: str, body: str) -> bytes:
    """Simple multi-page PDF from plain text (similarity reports, etc.)."""
    if not pdf_available():
        # Minimal valid PDF fallback
        return _minimal_pdf(title, body[:500])
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    _width, height = letter
    y = height - 54
    c.setFont("Helvetica-Bold", 12)
    c.drawString(54, y, title[:90])
    y -= 24
    c.setFont("Helvetica", 9)
    for line in body.splitlines():
        for wrapped in textwrap.wrap(line, width=95) or [""]:
            if y < 54:
                c.showPage()
                c.setFont("Helvetica", 9)
                y = height - 54
            c.drawString(54, y, wrapped)
            y -= 12
    c.save()
    return buf.getvalue()


def _render_reportlab(manuscript: CanonicalManuscript) -> bytes:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.pdfgen import canvas

    tpl = get_template(manuscript.template_id)
    buf = io.BytesIO()
    page = letter
    c = canvas.Canvas(buf, pagesize=page)
    width, height = page
    margin = 0.75 * inch
    y = height - margin
    col_gap = 0.3 * inch
    two_col = tpl.column_layout == "two"
    col_width = (width - 2 * margin - (col_gap if two_col else 0)) / (2 if two_col else 1)

    def new_page() -> None:
        nonlocal y
        c.showPage()
        y = height - margin

    def draw_wrapped(
        text: str,
        *,
        font: str = "Times-Roman",
        size: int = 11,
        indent: float = 0,
    ) -> None:
        nonlocal y
        c.setFont(font, size)
        usable = col_width - indent
        chars = max(40, int(usable / (size * 0.5)))
        for line in textwrap.wrap(text, width=chars) or [""]:
            if y < margin + 24:
                new_page()
                c.setFont(font, size)
            c.drawString(margin + indent, y, line)
            y -= size + 3

    fm = manuscript.front_matter
    c.setFont("Times-Bold", 16)
    for line in textwrap.wrap(fm.title or "Untitled", width=60) or [""]:
        c.drawCentredString(width / 2, y, line)
        y -= 20
    y -= 6
    if fm.authors:
        draw_wrapped(", ".join(a.name for a in fm.authors), font="Times-Italic", size=11)
    y -= 8
    if fm.abstract:
        draw_wrapped("Abstract", font="Times-Bold", size=12)
        draw_wrapped(fm.abstract, size=10)
        y -= 8
    if fm.keywords:
        draw_wrapped("Keywords: " + ", ".join(fm.keywords), size=10)
        y -= 10

    for section in manuscript.sections:
        if section.section_type in {"abstract", "keywords"}:
            continue
        if y < margin + 48:
            new_page()
        draw_wrapped(section.title, font="Times-Bold", size=12)
        for block in section.blocks:
            if block.type == "list":
                for i, item in enumerate(block.items, start=1):
                    prefix = f"{i}. " if block.ordered else "• "
                    draw_wrapped(prefix + item, size=10, indent=12)
            elif block.type == "equation":
                draw_wrapped(f"[Equation] {block.latex or block.text}", font="Courier", size=9)
            elif block.type == "figure":
                fig = next((f for f in manuscript.figures if f.id == block.figure_id), None)
                if fig:
                    draw_wrapped(f"[Figure {fig.number}]", size=10)
                    draw_wrapped(
                        f"Figure {fig.number}: {fig.caption or fig.title}",
                        font="Times-Italic",
                        size=9,
                    )
            elif block.type == "table":
                tab = next((t for t in manuscript.tables if t.id == block.table_id), None)
                if tab:
                    draw_wrapped(f"Table {tab.number}: {tab.caption or tab.title}", size=10)
                    if tab.headers:
                        draw_wrapped(" | ".join(tab.headers), font="Courier", size=8)
                    for row in tab.rows[:40]:
                        draw_wrapped(" | ".join(str(x) for x in row), font="Courier", size=8)
            else:
                draw_wrapped(block.text, size=11)

    bm = manuscript.back_matter
    for heading, value in (
        ("Acknowledgments", bm.acknowledgments),
        ("Funding", bm.funding),
        ("Conflict of Interest", bm.conflict_of_interest),
        ("Ethics", bm.ethics),
        ("Data Availability", bm.data_availability),
        ("Supplementary Materials", bm.supplementary_materials),
    ):
        if value.strip():
            draw_wrapped(heading, font="Times-Bold", size=12)
            draw_wrapped(value, size=10)

    if manuscript.references:
        draw_wrapped("References", font="Times-Bold", size=12)
        for ref in manuscript.references:
            authors = ", ".join(ref.authors)
            year = f" ({ref.year})" if ref.year else ""
            draw_wrapped(f"[{ref.order}] {authors}. {ref.title or ''}{year}.", size=9)

    y -= 16
    draw_wrapped(tpl.warning, font="Helvetica-Oblique", size=8)

    c.save()
    return buf.getvalue()


def _minimal_pdf(title: str, body: str) -> bytes:
    """Tiny PDF so ZIP packages remain valid when reportlab is absent."""
    content = f"BT /F1 12 Tf 50 750 Td ({_pdf_escape(title[:80])}) Tj ET"
    stream = content.encode("latin-1", errors="replace")
    objects = [
        b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n",
        b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n",
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>endobj\n",
        f"4 0 obj<< /Length {len(stream)} >>stream\n".encode() + stream + b"\nendstream\nendobj\n",
        b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(out))
        out.extend(obj)
    xref_pos = len(out)
    out.extend(f"xref\n0 {len(offsets)}\n".encode())
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode())
    out.extend(
        f"trailer<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode()
    )
    return bytes(out)


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
