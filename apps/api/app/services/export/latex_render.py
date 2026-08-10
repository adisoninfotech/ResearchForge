"""LaTeX renderer from canonical manuscript."""

from __future__ import annotations

import re

from app.services.export.canonical import CanonicalManuscript
from app.services.export.templates import get_template


def _tex_escape(text: str) -> str:
    if not text:
        return ""
    repl = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(repl.get(ch, ch) for ch in text)


def _cite_tex(text: str) -> str:
    """Convert [key] markers to \\cite{key} when present."""

    def repl(m: re.Match[str]) -> str:
        return r"\cite{" + m.group(1) + "}"

    return re.sub(r"\[([A-Za-z][A-Za-z0-9_:\-]+)\]", repl, text)


def render_bibtex(manuscript: CanonicalManuscript) -> str:
    lines: list[str] = []
    for ref in manuscript.references:
        key = re.sub(r"[^A-Za-z0-9_:\-]", "", ref.key) or f"ref{ref.order}"
        lines.append(f"@article{{{key},")
        if ref.authors:
            lines.append(f"  author = {{{' and '.join(ref.authors)}}},")
        if ref.title:
            lines.append(f"  title = {{{ref.title}}},")
        if ref.year:
            lines.append(f"  year = {{{ref.year}}},")
        if ref.venue:
            lines.append(f"  journal = {{{ref.venue}}},")
        if ref.doi:
            lines.append(f"  doi = {{{ref.doi}}},")
        if ref.url:
            lines.append(f"  url = {{{ref.url}}},")
        lines.append("}")
        lines.append("")
    return "\n".join(lines)


def render_latex(manuscript: CanonicalManuscript) -> str:
    tpl = get_template(manuscript.template_id)
    fm = manuscript.front_matter
    opts = f"[{tpl.latex_options}]" if tpl.latex_options else ""
    lines: list[str] = [
        f"% Compatible starting template: {tpl.name} v{tpl.version}",
        f"% {tpl.warning}",
        f"\\documentclass{opts}{{{tpl.latex_documentclass}}}",
        r"\usepackage[utf8]{inputenc}",
        r"\usepackage{graphicx}",
        r"\usepackage{booktabs}",
        r"\usepackage{hyperref}",
        r"\begin{document}",
        r"\title{" + _tex_escape(fm.title) + "}",
    ]
    if fm.authors:
        author_tex = r" \and ".join(_tex_escape(a.name) for a in fm.authors)
        lines.append(r"\author{" + author_tex + "}")
    if fm.affiliations and tpl.id.value != "ieee_two_column":
        for aff in fm.affiliations:
            lines.append(r"\institute{" + _tex_escape(aff.name) + "}")
    lines.append(r"\maketitle")
    if fm.abstract:
        lines.extend(
            [
                r"\begin{abstract}",
                _tex_escape(fm.abstract),
                r"\end{abstract}",
            ]
        )
    if fm.keywords:
        lines.append(r"\keywords{" + _tex_escape(", ".join(fm.keywords)) + "}")

    for section in manuscript.sections:
        if section.section_type in {"abstract", "keywords", "references"}:
            continue
        lines.append(r"\section{" + _tex_escape(section.title) + "}")
        for block in section.blocks:
            if block.type == "heading":
                cmd = "subsection" if (block.level or 2) <= 2 else "subsubsection"
                lines.append(rf"\{cmd}{{{_tex_escape(block.text)}}}")
            elif block.type == "list":
                env = "enumerate" if block.ordered else "itemize"
                lines.append(rf"\begin{{{env}}}")
                for item in block.items:
                    lines.append(r"\item " + _cite_tex(_tex_escape(item)))
                lines.append(rf"\end{{{env}}}")
            elif block.type == "equation":
                lines.extend(
                    [
                        r"\begin{equation}",
                        block.latex or block.text,
                        r"\end{equation}",
                    ]
                )
            elif block.type == "figure":
                fig = next((f for f in manuscript.figures if f.id == block.figure_id), None)
                if fig:
                    fname = fig.filename or f"figure_{fig.number}.png"
                    lines.extend(
                        [
                            r"\begin{figure}[htbp]",
                            r"\centering",
                            rf"\includegraphics[width=0.9\linewidth]{{figures/{fname}}}",
                            r"\caption{" + _tex_escape(fig.caption or fig.title) + "}",
                            rf"\label{{{fig.id}}}",
                            r"\end{figure}",
                        ]
                    )
            elif block.type == "table":
                tab = next((t for t in manuscript.tables if t.id == block.table_id), None)
                if tab:
                    cols = max(len(tab.headers), max((len(r) for r in tab.rows), default=1), 1)
                    colspec = "l" * cols
                    lines.extend(
                        [
                            r"\begin{table}[htbp]",
                            r"\centering",
                            r"\caption{" + _tex_escape(tab.caption or tab.title) + "}",
                            rf"\label{{{tab.id}}}",
                            rf"\begin{{tabular}}{{{colspec}}}",
                            r"\toprule",
                        ]
                    )
                    if tab.headers:
                        lines.append(" & ".join(_tex_escape(str(h)) for h in tab.headers) + r" \\")
                        lines.append(r"\midrule")
                    for row in tab.rows:
                        padded = list(row) + [""] * (cols - len(row))
                        lines.append(
                            " & ".join(_tex_escape(str(c)) for c in padded[:cols]) + r" \\"
                        )
                    lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}"])
            else:
                lines.append(_cite_tex(_tex_escape(block.text)))
                lines.append("")

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
            lines.append(r"\section*{" + _tex_escape(title) + "}")
            lines.append(_tex_escape(value))

    if manuscript.references:
        lines.append(r"\bibliographystyle{plain}")
        lines.append(r"\bibliography{references}")
        # Also emit an inline thebibliography for standalone compile without bibtex
        lines.append(r"\begin{thebibliography}{99}")
        for ref in manuscript.references:
            authors = _tex_escape(", ".join(ref.authors))
            title = _tex_escape(ref.title or "")
            year = f" ({ref.year})" if ref.year else ""
            lines.append(rf"\bibitem{{{ref.key}}} {authors}. {title}{year}.")
        lines.append(r"\end{thebibliography}")

    lines.append(r"\end{document}")
    return "\n".join(lines) + "\n"
