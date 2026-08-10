"""Table Studio — structured tables with multi-format export."""

from __future__ import annotations

import csv
import io
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationAppError
from app.models.dataset import AnalysisRun, Dataset, ReproducibilityManifest, Table
from app.models.enums import AnalysisRunStatus, TableKind
from app.services.datasets.service import get_version, new_stable_id


def table_to_dict(table: Table) -> dict[str, Any]:
    return {
        "id": str(table.id),
        "stable_id": table.stable_id,
        "number": table.number,
        "kind": table.kind.value,
        "title": table.title,
        "caption": table.caption,
        "dataset_version_id": str(table.dataset_version_id) if table.dataset_version_id else None,
        "analysis_run_id": str(table.analysis_run_id) if table.analysis_run_id else None,
        "source_reference": table.source_reference,
        "provenance_label": table.provenance_label,
        "headers": table.headers,
        "rows": table.rows,
        "parameters": table.parameters,
    }


async def _next_number(db: AsyncSession, project_id: UUID) -> int:
    current = await db.scalar(
        select(func.coalesce(func.max(Table.number), 0)).where(Table.project_id == project_id)
    )
    return int(current or 0) + 1


async def create_table(
    db: AsyncSession,
    *,
    project_id: UUID,
    kind: TableKind,
    title: str,
    dataset_version_id: UUID | None = None,
    analysis_run_id: UUID | None = None,
    caption: str = "",
    headers: list[str] | None = None,
    rows: list[list[Any]] | None = None,
    parameters: dict[str, Any] | None = None,
) -> Table:
    params = dict(parameters or {})
    provenance = "Calculated result"
    source_ref = ""
    out_headers = list(headers or [])
    out_rows: list[list[Any]] = [list(r) for r in (rows or [])]

    if analysis_run_id is not None:
        run = await db.get(AnalysisRun, analysis_run_id)
        if run is None or run.project_id != project_id:
            raise NotFoundError("Analysis run not found")
        if run.status != AnalysisRunStatus.COMPLETED or not run.results:
            raise ValidationAppError("Analysis run has no completed results")
        dataset_version_id = dataset_version_id or run.dataset_version_id
        source_ref = f"analysis_run:{run.id}"
        if not out_headers:
            out_headers, out_rows = _from_analysis(kind, run.results)

    if dataset_version_id is not None and not out_headers:
        ver = await get_version(db, project_id=project_id, version_id=dataset_version_id)
        if ver is None:
            raise NotFoundError("Dataset version not found")
        source_ref = source_ref or f"dataset_version:{ver.id}"
        ds = await db.get(Dataset, ver.dataset_id)
        if ds and ds.synthetic:
            provenance = ds.provenance_label
        if kind == TableKind.DATASET_SUMMARY:
            out_headers = ["metric", "value"]
            out_rows = [
                ["rows", ver.row_count],
                ["columns", ver.column_count],
                ["checksum", ver.content_sha256],
            ]
            if ds:
                out_rows.extend(
                    [
                        ["provenance_type", ds.provenance_type.value],
                        ["synthetic", ds.synthetic],
                        ["provenance_label", ds.provenance_label],
                    ]
                )
        elif kind == TableKind.DESCRIPTIVE_STATS and ver.profile:
            out_headers = ["column", "mean", "std", "min", "max", "missing"]
            for col, stats in (ver.profile.descriptive_stats or {}).items():
                out_rows.append(
                    [
                        col,
                        stats.get("mean"),
                        stats.get("std"),
                        stats.get("min"),
                        stats.get("max"),
                        stats.get("missing"),
                    ]
                )

    if kind == TableKind.STATISTICAL_TEST and analysis_run_id and not out_rows:
        raise ValidationAppError("Statistical test table requires analysis results")

    if not out_headers:
        raise ValidationAppError("Table requires headers/rows or a source dataset/analysis")

    number = await _next_number(db, project_id)
    table = Table(
        project_id=project_id,
        stable_id=new_stable_id("tbl"),
        number=number,
        kind=kind,
        title=title,
        caption=caption or title,
        dataset_version_id=dataset_version_id,
        analysis_run_id=analysis_run_id,
        source_reference=source_ref,
        provenance_label=provenance,
        headers=out_headers,
        rows=out_rows,
        parameters=params,
    )
    db.add(table)
    await db.flush()
    db.add(
        ReproducibilityManifest(
            project_id=project_id,
            analysis_run_id=analysis_run_id,
            table_id=table.id,
            manifest_json={
                "table_id": str(table.id),
                "kind": kind.value,
                "headers": out_headers,
                "row_count": len(out_rows),
                "source_reference": source_ref,
            },
            provenance_label=provenance,
        )
    )
    await db.flush()
    await db.refresh(table)
    return table


def _from_analysis(kind: TableKind, results: dict[str, Any]) -> tuple[list[str], list[list[Any]]]:
    if kind == TableKind.STATISTICAL_TEST:
        headers = ["metric", "value"]
        rows = [[str(k), v] for k, v in results.items() if not isinstance(v, (dict, list))]
        return headers, rows
    if kind == TableKind.PERFORMANCE_COMPARISON:
        headers = list(results.keys())
        rows = [[results[h] for h in headers]]
        return headers, rows
    if kind in {TableKind.HYPERPARAMETERS, TableKind.ABLATION}:
        headers = ["name", "value"]
        rows = [[str(k), str(v)] for k, v in results.items()]
        return headers, rows
    headers = ["key", "value"]
    rows = [[str(k), str(v)] for k, v in results.items()]
    return headers, rows


def export_table(table: Table, fmt: str) -> tuple[str, str]:
    """Return (content, media_type)."""
    if fmt == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(table.headers)
        writer.writerows(table.rows)
        return buf.getvalue(), "text/csv"
    if fmt == "html":
        th = "".join(f"<th>{h}</th>" for h in table.headers)
        body = "".join(
            "<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in table.rows
        )
        html = (
            f"<table><caption>{table.caption}</caption>"
            f"<thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>"
            f"<p><em>{table.provenance_label}</em></p>"
        )
        return html, "text/html"
    if fmt == "latex":
        cols = "l" * max(1, len(table.headers))
        lines = [
            f"% {table.provenance_label}",
            f"\\begin{{tabular}}{{{cols}}}",
            " & ".join(str(h) for h in table.headers) + " \\\\",
            "\\hline",
        ]
        for row in table.rows:
            lines.append(" & ".join(str(c) for c in row) + " \\\\")
        lines.append("\\end{tabular}")
        return "\n".join(lines) + "\n", "application/x-latex"
    if fmt == "docx":
        # Minimal Office Open XML fragment (wordprocessing paragraph/table-like text)
        rows_txt = "\n".join("\t".join(str(c) for c in row) for row in [table.headers, *table.rows])
        fragment = f"{table.title}\n{table.caption}\n{rows_txt}\n[{table.provenance_label}]\n"
        media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document.fragment"
        return fragment, media
    raise ValidationAppError("Unsupported export format")
