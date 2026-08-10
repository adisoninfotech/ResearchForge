"""Controlled analysis engine — approved operations only, no arbitrary code."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version
from typing import Any
from uuid import UUID

import numpy as np
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationAppError
from app.core.time import utcnow
from app.models.dataset import AnalysisArtifact, AnalysisRun, ReproducibilityManifest
from app.models.enums import AnalysisOperation, AnalysisRunStatus
from app.models.user import User
from app.services.datasets.profiling import read_tabular
from app.services.datasets.service import get_version
from app.services.storage import get_object_bytes


def package_versions() -> dict[str, str]:
    names = ["pandas", "numpy", "scipy", "statsmodels", "scikit-learn", "matplotlib"]
    out: dict[str, str] = {}
    for name in names:
        try:
            out[name] = pkg_version(name)
        except PackageNotFoundError:
            out[name] = "unknown"
    return out


def _code_repr(operation: AnalysisOperation, params: dict[str, Any], seed: int | None) -> str:
    return (
        f"# ResearchForge approved analysis\n"
        f"operation = {operation.value!r}\n"
        f"parameters = {params!r}\n"
        f"random_seed = {seed!r}\n"
    )


async def run_analysis(
    db: AsyncSession,
    *,
    project_id: UUID,
    user: User,
    dataset_version_id: UUID,
    operation: AnalysisOperation,
    parameters: dict[str, Any] | None = None,
    random_seed: int | None = None,
) -> AnalysisRun:
    ver = await get_version(db, project_id=project_id, version_id=dataset_version_id)
    if ver is None:
        raise NotFoundError("Dataset version not found")

    params = dict(parameters or {})
    run = AnalysisRun(
        project_id=project_id,
        dataset_version_id=ver.id,
        created_by_id=user.id,
        operation=operation,
        status=AnalysisRunStatus.RUNNING,
        parameters=params,
        package_versions=package_versions(),
        random_seed=random_seed,
        code_representation=_code_repr(operation, params, random_seed),
        warnings=[],
        started_at=utcnow(),
    )
    db.add(run)
    await db.flush()

    try:
        csv_bytes = get_object_bytes(ver.storage_key)
        df = read_tabular(csv_bytes, filename="data.csv")
        if random_seed is not None:
            np.random.seed(random_seed)
        results, warnings = _execute(operation, df, params)
        run.results = results
        run.warnings = warnings
        run.status = AnalysisRunStatus.COMPLETED
        run.completed_at = utcnow()
        db.add(
            AnalysisArtifact(
                analysis_run_id=run.id,
                project_id=project_id,
                kind="results_json",
                content_json=results,
                media_type="application/json",
            )
        )
        db.add(
            ReproducibilityManifest(
                project_id=project_id,
                dataset_id=ver.dataset_id,
                analysis_run_id=run.id,
                manifest_json={
                    "analysis_run_id": str(run.id),
                    "operation": operation.value,
                    "dataset_version_id": str(ver.id),
                    "parameters": params,
                    "package_versions": run.package_versions,
                    "random_seed": random_seed,
                    "code_representation": run.code_representation,
                    "completed_at": run.completed_at.isoformat(),
                    "scientific_limitations": SCIENTIFIC_LIMITATIONS,
                },
                provenance_label="Calculated analysis result",
            )
        )
    except ValidationAppError as exc:
        run.status = AnalysisRunStatus.FAILED
        run.error_message = exc.message
        run.completed_at = utcnow()
        run.warnings = [exc.message]
    except Exception as exc:
        run.status = AnalysisRunStatus.FAILED
        run.error_message = "Analysis failed"
        run.completed_at = utcnow()
        run.warnings = [type(exc).__name__]
    if run.status == AnalysisRunStatus.COMPLETED:
        from app.models.enums import AnalyticsEventType
        from app.services.engagement.analytics import track as track_analytics

        await track_analytics(
            db,
            event_type=AnalyticsEventType.DATASET_ANALYZED,
            user_id=user.id,
            project_id=project_id,
            properties={"operation": operation.value},
        )
    await db.flush()
    await db.refresh(run)
    return run


SCIENTIFIC_LIMITATIONS = [
    (
        "Analyses use approved statistical routines only; "
        "they are not a substitute for domain expertise."
    ),
    ("p-values and confidence intervals assume model conditions that may not hold for your data."),
    ("Synthetic or simulated inputs must not be reported as collected experimental observations."),
    (
        "Classification curves require probability/score columns; "
        "binary labels are assumed when applicable."
    ),
]


def _col(df: pd.DataFrame, name: str | None) -> str:
    if not name or name not in df.columns:
        raise ValidationAppError(f"Column required and must exist: {name}")
    return name


def _execute(
    operation: AnalysisOperation,
    df: pd.DataFrame,
    params: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    if operation == AnalysisOperation.DESCRIPTIVE:
        desc = df.describe(include="all").replace({np.nan: None}).to_dict()
        return {"descriptive": desc, "row_count": len(df)}, warnings
    if operation == AnalysisOperation.MISSING_VALUES:
        missing = df.isna().sum().to_dict()
        return {
            "missing_counts": {str(k): int(v) for k, v in missing.items()},
            "total_rows": len(df),
        }, warnings
    if operation == AnalysisOperation.CORRELATION:
        numeric = df.select_dtypes(include=[np.number])
        if numeric.shape[1] < 2:
            raise ValidationAppError("Need at least two numeric columns for correlation")
        corr = numeric.corr().replace({np.nan: None})
        return {"correlation": corr.to_dict()}, warnings
    if operation == AnalysisOperation.GROUP_COMPARISON:
        group = _col(df, params.get("group_column"))
        value = _col(df, params.get("value_column"))
        grouped = df.groupby(group)[value].agg(["count", "mean", "std"]).reset_index()
        return {"groups": grouped.replace({np.nan: None}).to_dict(orient="records")}, warnings
    if operation == AnalysisOperation.CONFIDENCE_INTERVALS:
        from scipy import stats

        col = _col(df, params.get("column"))
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        if len(series) < 2:
            raise ValidationAppError("Need at least two values for confidence interval")
        mean = float(series.mean())
        sem = float(stats.sem(series))
        ci = stats.t.interval(0.95, len(series) - 1, loc=mean, scale=sem)
        return {
            "column": col,
            "mean": mean,
            "ci95": [float(ci[0]), float(ci[1])],
            "n": len(series),
        }, warnings
    if operation == AnalysisOperation.T_TEST:
        from scipy import stats

        a = _col(df, params.get("column_a"))
        b = _col(df, params.get("column_b"))
        x = pd.to_numeric(df[a], errors="coerce").dropna()
        y = pd.to_numeric(df[b], errors="coerce").dropna()
        if params.get("paired"):
            n = min(len(x), len(y))
            res = stats.ttest_rel(x.iloc[:n], y.iloc[:n])
            kind = "paired"
        else:
            res = stats.ttest_ind(x, y, equal_var=False)
            kind = "independent"
        return {
            "test": "t_test",
            "kind": kind,
            "statistic": float(res.statistic),
            "pvalue": float(res.pvalue),
        }, warnings
    if operation == AnalysisOperation.MANN_WHITNEY:
        from scipy import stats

        a = _col(df, params.get("column_a"))
        b = _col(df, params.get("column_b"))
        x = pd.to_numeric(df[a], errors="coerce").dropna()
        y = pd.to_numeric(df[b], errors="coerce").dropna()
        res = stats.mannwhitneyu(x, y, alternative="two-sided")
        return {
            "test": "mann_whitney",
            "statistic": float(res.statistic),
            "pvalue": float(res.pvalue),
        }, warnings
    if operation == AnalysisOperation.ANOVA:
        from scipy import stats

        group = _col(df, params.get("group_column"))
        value = _col(df, params.get("value_column"))
        samples = [pd.to_numeric(g[value], errors="coerce").dropna() for _, g in df.groupby(group)]
        samples = [s for s in samples if len(s) > 0]
        if len(samples) < 2:
            raise ValidationAppError("ANOVA requires at least two groups")
        res = stats.f_oneway(*samples)
        return {
            "test": "anova",
            "statistic": float(res.statistic),
            "pvalue": float(res.pvalue),
            "groups": len(samples),
        }, warnings
    if operation == AnalysisOperation.CHI_SQUARE:
        from scipy.stats import chi2_contingency

        a = _col(df, params.get("column_a"))
        b = _col(df, params.get("column_b"))
        table = pd.crosstab(df[a], df[b])
        chi2, p, dof, _expected = chi2_contingency(table)
        return {
            "test": "chi_square",
            "chi2": float(chi2),
            "pvalue": float(p),
            "dof": int(dof),
            "table": table.to_dict(),
        }, warnings
    if operation == AnalysisOperation.SIMPLE_REGRESSION:
        import statsmodels.api as sm

        x_col = _col(df, params.get("x_column"))
        y_col = _col(df, params.get("y_column"))
        x = pd.to_numeric(df[x_col], errors="coerce")
        y = pd.to_numeric(df[y_col], errors="coerce")
        mask = x.notna() & y.notna()
        x = x[mask]
        y = y[mask]
        if len(x) < 3:
            raise ValidationAppError("Need at least 3 rows for regression")
        design = sm.add_constant(x)
        model = sm.OLS(y, design).fit()
        return {
            "test": "simple_regression",
            "params": {str(k): float(v) for k, v in model.params.items()},
            "rsquared": float(model.rsquared),
            "pvalue": float(model.f_pvalue) if model.f_pvalue is not None else None,
        }, warnings
    if operation in {
        AnalysisOperation.CLASSIFICATION_METRICS,
        AnalysisOperation.CONFUSION_MATRIX,
        AnalysisOperation.ROC_CURVE,
        AnalysisOperation.PRECISION_RECALL,
    }:
        return _classification(operation, df, params, warnings)
    raise ValidationAppError(f"Unsupported operation: {operation.value}")


def _classification(
    operation: AnalysisOperation,
    df: pd.DataFrame,
    params: dict[str, Any],
    warnings: list[str],
) -> tuple[dict[str, Any], list[str]]:
    from sklearn.metrics import (
        accuracy_score,
        average_precision_score,
        confusion_matrix,
        f1_score,
        precision_recall_curve,
        precision_score,
        recall_score,
        roc_auc_score,
        roc_curve,
    )

    y_true_col = _col(df, params.get("y_true_column") or params.get("label_column"))
    y_pred_col = params.get("y_pred_column") or params.get("prediction_column")
    score_col = params.get("score_column") or params.get("probability_column")
    y_true = df[y_true_col]
    if operation == AnalysisOperation.CLASSIFICATION_METRICS:
        if not y_pred_col:
            raise ValidationAppError("y_pred_column is required")
        y_pred = df[_col(df, y_pred_col)]
        return {
            "accuracy": float(accuracy_score(y_true, y_pred)),
            "precision": float(
                precision_score(y_true, y_pred, average="weighted", zero_division=0)
            ),
            "recall": float(recall_score(y_true, y_pred, average="weighted", zero_division=0)),
            "f1": float(f1_score(y_true, y_pred, average="weighted", zero_division=0)),
        }, warnings
    if operation == AnalysisOperation.CONFUSION_MATRIX:
        if not y_pred_col:
            raise ValidationAppError("y_pred_column is required")
        y_pred = df[_col(df, y_pred_col)]
        labels = sorted(
            set(y_true.dropna().unique()) | set(y_pred.dropna().unique()),
            key=str,
        )
        cm = confusion_matrix(y_true, y_pred, labels=labels)
        return {
            "labels": [str(x) for x in labels],
            "matrix": cm.tolist(),
        }, warnings
    if not score_col:
        raise ValidationAppError("score_column / probability_column is required")
    scores = pd.to_numeric(df[_col(df, score_col)], errors="coerce")
    # binarize labels if needed
    classes = list(pd.Series(y_true).dropna().unique())
    if len(classes) != 2:
        raise ValidationAppError("ROC/PR currently require binary labels")
    pos = classes[1]
    y_bin = (y_true == pos).astype(int)
    mask = scores.notna()
    y_bin = y_bin[mask]
    scores = scores[mask]
    if operation == AnalysisOperation.ROC_CURVE:
        fpr, tpr, thresholds = roc_curve(y_bin, scores)
        return {
            "fpr": fpr.tolist(),
            "tpr": tpr.tolist(),
            "thresholds": thresholds.tolist(),
            "auc": float(roc_auc_score(y_bin, scores)),
            "positive_label": str(pos),
        }, warnings
    precision, recall, thresholds = precision_recall_curve(y_bin, scores)
    return {
        "precision": precision.tolist(),
        "recall": recall.tolist(),
        "thresholds": thresholds.tolist(),
        "average_precision": float(average_precision_score(y_bin, scores)),
        "positive_label": str(pos),
    }, warnings


def run_to_dict(run: AnalysisRun) -> dict[str, Any]:
    return {
        "id": str(run.id),
        "project_id": str(run.project_id),
        "dataset_version_id": str(run.dataset_version_id),
        "operation": run.operation.value,
        "status": run.status.value,
        "parameters": run.parameters,
        "package_versions": run.package_versions,
        "random_seed": run.random_seed,
        "code_representation": run.code_representation,
        "results": run.results,
        "warnings": run.warnings,
        "error_message": run.error_message,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "scientific_limitations": SCIENTIFIC_LIMITATIONS,
    }
