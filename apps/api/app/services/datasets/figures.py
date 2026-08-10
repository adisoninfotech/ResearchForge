"""Figure Studio — publication figures tied to datasets/analysis results."""

from __future__ import annotations

import io
from typing import Any
from uuid import UUID

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationAppError
from app.models.dataset import (
    CONCEPTUAL_DIAGRAM_LABEL,
    AnalysisRun,
    Dataset,
    Figure,
    ReproducibilityManifest,
)
from app.models.enums import AnalysisRunStatus, FigureKind
from app.services.datasets.analysis import package_versions
from app.services.datasets.profiling import read_tabular
from app.services.datasets.service import get_version, new_stable_id
from app.services.storage import get_object_bytes, put_object_trusted

JOURNAL_PRESETS = {
    "default": (6.5, 4.0),
    "single_column": (3.5, 2.8),
    "double_column": (7.0, 4.5),
    "nature": (89 / 25.4, 89 / 25.4),
}


def figure_to_dict(fig: Figure) -> dict[str, Any]:
    return {
        "id": str(fig.id),
        "stable_id": fig.stable_id,
        "number": fig.number,
        "kind": fig.kind.value,
        "title": fig.title,
        "caption": fig.caption,
        "alt_text": fig.alt_text,
        "x_label": fig.x_label,
        "y_label": fig.y_label,
        "journal_preset": fig.journal_preset,
        "dataset_version_id": str(fig.dataset_version_id) if fig.dataset_version_id else None,
        "analysis_run_id": str(fig.analysis_run_id) if fig.analysis_run_id else None,
        "source_reference": fig.source_reference,
        "provenance_label": fig.provenance_label,
        "is_conceptual": fig.is_conceptual,
        "storage_png": fig.storage_png,
        "storage_svg": fig.storage_svg,
        "storage_pdf": fig.storage_pdf,
        "parameters": fig.parameters,
        "reproducibility": fig.reproducibility,
    }


async def _next_number(db: AsyncSession, project_id: UUID) -> int:
    current = await db.scalar(
        select(func.coalesce(func.max(Figure.number), 0)).where(Figure.project_id == project_id)
    )
    return int(current or 0) + 1


def _save_matplotlib(fig: Any, *, project_id: UUID, stable_id: str) -> dict[str, str]:
    png_key = f"projects/{project_id}/figures/{stable_id}.png"
    svg_key = f"projects/{project_id}/figures/{stable_id}.svg"
    pdf_key = f"projects/{project_id}/figures/{stable_id}.pdf"
    for key, fmt, mime in (
        (png_key, "png", "image/png"),
        (svg_key, "svg", "image/svg+xml"),
        (pdf_key, "pdf", "application/pdf"),
    ):
        buf = io.BytesIO()
        fig.savefig(buf, format=fmt, dpi=300 if fmt == "png" else None, bbox_inches="tight")
        put_object_trusted(key=key, body=buf.getvalue(), content_type=mime)
    return {"png": png_key, "svg": svg_key, "pdf": pdf_key}


async def create_result_figure(
    db: AsyncSession,
    *,
    project_id: UUID,
    kind: FigureKind,
    title: str,
    dataset_version_id: UUID | None = None,
    analysis_run_id: UUID | None = None,
    caption: str = "",
    alt_text: str = "",
    x_label: str | None = None,
    y_label: str | None = None,
    journal_preset: str = "default",
    parameters: dict[str, Any] | None = None,
) -> Figure:
    if kind == FigureKind.CONCEPTUAL:
        raise ValidationAppError("Use the conceptual diagram endpoint for conceptual figures")
    if dataset_version_id is None and analysis_run_id is None:
        raise ValidationAppError("Figures require an associated dataset version or analysis result")

    params = dict(parameters or {})
    df: pd.DataFrame | None = None
    run: AnalysisRun | None = None
    provenance = "Calculated result"
    source_ref = ""

    if analysis_run_id is not None:
        run = await db.get(AnalysisRun, analysis_run_id)
        if run is None or run.project_id != project_id:
            raise NotFoundError("Analysis run not found")
        if run.status != AnalysisRunStatus.COMPLETED or not run.results:
            raise ValidationAppError("Analysis run has no completed results")
        dataset_version_id = dataset_version_id or run.dataset_version_id
        source_ref = f"analysis_run:{run.id}"
        provenance = "Calculated analysis result"

    if dataset_version_id is not None:
        ver = await get_version(db, project_id=project_id, version_id=dataset_version_id)
        if ver is None:
            raise NotFoundError("Dataset version not found")
        df = read_tabular(get_object_bytes(ver.storage_key), filename="data.csv")
        source_ref = source_ref or f"dataset_version:{ver.id}"
        ds = await db.get(Dataset, ver.dataset_id)
        if ds and ds.synthetic:
            provenance = ds.provenance_label

    mpl_fig = _render(
        kind,
        df,
        run.results if run else None,
        params,
        title,
        x_label,
        y_label,
        journal_preset,
    )
    try:
        stable_id = new_stable_id("fig")
        paths = _save_matplotlib(mpl_fig, project_id=project_id, stable_id=stable_id)
    finally:
        plt.close(mpl_fig)

    number = await _next_number(db, project_id)
    figure = Figure(
        project_id=project_id,
        stable_id=stable_id,
        number=number,
        kind=kind,
        title=title,
        caption=caption or title,
        alt_text=alt_text or title,
        x_label=x_label,
        y_label=y_label,
        journal_preset=journal_preset,
        dataset_version_id=dataset_version_id,
        analysis_run_id=analysis_run_id,
        source_reference=source_ref,
        provenance_label=provenance,
        is_conceptual=False,
        storage_png=paths["png"],
        storage_svg=paths["svg"],
        storage_pdf=paths["pdf"],
        parameters=params,
        reproducibility={
            "package_versions": package_versions(),
            "kind": kind.value,
            "parameters": params,
            "source_reference": source_ref,
        },
    )
    db.add(figure)
    await db.flush()
    db.add(
        ReproducibilityManifest(
            project_id=project_id,
            analysis_run_id=analysis_run_id,
            figure_id=figure.id,
            manifest_json=figure.reproducibility,
            provenance_label=provenance,
        )
    )
    await db.flush()
    await db.refresh(figure)
    return figure


async def create_conceptual_diagram(
    db: AsyncSession,
    *,
    project_id: UUID,
    title: str,
    mermaid: str,
    caption: str = "",
    alt_text: str = "",
) -> Figure:
    """Store Mermaid/Graphviz source as conceptual illustration (not a result figure)."""
    if not mermaid.strip():
        raise ValidationAppError("mermaid source is required")
    stable_id = new_stable_id("concept")
    number = await _next_number(db, project_id)
    # Store source text as SVG-ish payload (source of truth is Mermaid text)
    key = f"projects/{project_id}/figures/{stable_id}.mmd"
    put_object_trusted(key=key, body=mermaid.encode("utf-8"), content_type="text/plain")
    figure = Figure(
        project_id=project_id,
        stable_id=stable_id,
        number=number,
        kind=FigureKind.CONCEPTUAL,
        title=title,
        caption=caption or title,
        alt_text=alt_text or title,
        journal_preset="default",
        source_reference="conceptual",
        provenance_label=CONCEPTUAL_DIAGRAM_LABEL,
        is_conceptual=True,
        storage_svg=key,
        parameters={"mermaid": mermaid},
        reproducibility={"type": "conceptual", "label": CONCEPTUAL_DIAGRAM_LABEL},
    )
    db.add(figure)
    await db.flush()
    await db.refresh(figure)
    return figure


def _render(
    kind: FigureKind,
    df: pd.DataFrame | None,
    results: dict[str, Any] | None,
    params: dict[str, Any],
    title: str,
    x_label: str | None,
    y_label: str | None,
    journal_preset: str,
) -> Any:
    size = JOURNAL_PRESETS.get(journal_preset, JOURNAL_PRESETS["default"])
    fig, ax = plt.subplots(figsize=size)
    ax.set_title(title)

    if kind == FigureKind.CORRELATION_HEATMAP:
        if df is None:
            raise ValidationAppError("Heatmap requires dataset")
        numeric = df.select_dtypes(include=[np.number])
        corr = numeric.corr()
        im = ax.imshow(corr.values, cmap="viridis")
        ax.set_xticks(range(len(corr.columns)))
        ax.set_yticks(range(len(corr.columns)))
        ax.set_xticklabels(list(corr.columns), rotation=45, ha="right")
        ax.set_yticklabels(list(corr.columns))
        fig.colorbar(im, ax=ax)
    elif kind == FigureKind.CONFUSION_MATRIX:
        if not results or "matrix" not in results:
            raise ValidationAppError("Confusion matrix figure requires analysis results")
        matrix = np.array(results["matrix"])
        im = ax.imshow(matrix, cmap="Blues")
        labels = results.get("labels") or []
        ax.set_xticks(range(len(labels)))
        ax.set_yticks(range(len(labels)))
        ax.set_xticklabels(labels)
        ax.set_yticklabels(labels)
        ax.set_xlabel(x_label or "Predicted")
        ax.set_ylabel(y_label or "Actual")
        fig.colorbar(im, ax=ax)
    elif kind == FigureKind.ROC_CURVE:
        if not results or "fpr" not in results:
            raise ValidationAppError("ROC figure requires analysis results")
        ax.plot(results["fpr"], results["tpr"], label=f"AUC={results.get('auc', 0):.3f}")
        ax.plot([0, 1], [0, 1], linestyle="--", color="gray")
        ax.set_xlabel(x_label or "False positive rate")
        ax.set_ylabel(y_label or "True positive rate")
        ax.legend()
    elif kind == FigureKind.PRECISION_RECALL:
        if not results or "precision" not in results:
            raise ValidationAppError("PR figure requires analysis results")
        ax.plot(results["recall"], results["precision"])
        ax.set_xlabel(x_label or "Recall")
        ax.set_ylabel(y_label or "Precision")
    else:
        if df is None:
            raise ValidationAppError("Chart requires dataset")
        x_col = params.get("x_column")
        y_col = params.get("y_column")
        if kind == FigureKind.HISTOGRAM:
            col = params.get("column") or y_col or x_col
            if not col:
                raise ValidationAppError("column is required for histogram")
            series = pd.to_numeric(df[col], errors="coerce").dropna()
            ax.hist(series, bins=int(params.get("bins", 20)))
            ax.set_xlabel(x_label or str(col))
            ax.set_ylabel(y_label or "Count")
        elif kind == FigureKind.BOX:
            col = params.get("column") or y_col
            if not col:
                raise ValidationAppError("column is required for box plot")
            ax.boxplot(pd.to_numeric(df[col], errors="coerce").dropna())
            ax.set_ylabel(y_label or str(col))
        elif kind == FigureKind.BAR:
            if not x_col or not y_col:
                raise ValidationAppError("x_column and y_column required")
            ax.bar(df[x_col].astype(str), pd.to_numeric(df[y_col], errors="coerce"))
            ax.set_xlabel(x_label or x_col)
            ax.set_ylabel(y_label or y_col)
        elif kind == FigureKind.LINE:
            if not x_col or not y_col:
                raise ValidationAppError("x_column and y_column required")
            ax.plot(df[x_col], pd.to_numeric(df[y_col], errors="coerce"))
            ax.set_xlabel(x_label or x_col)
            ax.set_ylabel(y_label or y_col)
        elif kind == FigureKind.SCATTER:
            if not x_col or not y_col:
                raise ValidationAppError("x_column and y_column required")
            ax.scatter(
                pd.to_numeric(df[x_col], errors="coerce"),
                pd.to_numeric(df[y_col], errors="coerce"),
            )
            ax.set_xlabel(x_label or x_col)
            ax.set_ylabel(y_label or y_col)
        else:
            raise ValidationAppError(f"Unsupported figure kind: {kind.value}")

    ax.set_xlabel(ax.get_xlabel() or x_label or "")
    ax.set_ylabel(ax.get_ylabel() or y_label or "")
    fig.tight_layout()
    return fig
