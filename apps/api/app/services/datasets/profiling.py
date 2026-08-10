"""Schema inference, profiling, and PII-risk heuristics for tabular data."""

from __future__ import annotations

import io
import re
from typing import Any

import numpy as np
import pandas as pd

from app.models.enums import DatasetColumnType

PREVIEW_ROW_LIMIT = 50
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}")
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")


def read_tabular(data: bytes, *, filename: str) -> pd.DataFrame:
    lower = filename.lower()
    if lower.endswith(".xlsx"):
        return pd.read_excel(io.BytesIO(data))
    return pd.read_csv(io.BytesIO(data))


def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")


def infer_column_type(series: pd.Series) -> DatasetColumnType:
    non_null = series.dropna()
    if non_null.empty:
        return DatasetColumnType.STRING
    if pd.api.types.is_bool_dtype(series) or set(non_null.astype(str).str.lower().unique()) <= {
        "true",
        "false",
        "0",
        "1",
    }:
        if non_null.nunique() <= 2:
            return DatasetColumnType.BOOLEAN
    if pd.api.types.is_integer_dtype(series):
        return DatasetColumnType.INTEGER
    if pd.api.types.is_float_dtype(series):
        return DatasetColumnType.FLOAT
    if pd.api.types.is_datetime64_any_dtype(series):
        return DatasetColumnType.DATETIME
    # numeric-looking strings
    coerced = pd.to_numeric(non_null, errors="coerce")
    if coerced.notna().mean() > 0.9:
        if (coerced.dropna() % 1 == 0).all():
            return DatasetColumnType.INTEGER
        return DatasetColumnType.FLOAT
    if non_null.nunique() <= max(10, int(len(non_null) * 0.2)):
        return DatasetColumnType.CATEGORY
    return DatasetColumnType.STRING


def _column_stats(series: pd.Series, col_type: DatasetColumnType) -> dict[str, Any]:
    non_null = series.dropna()
    stats: dict[str, Any] = {
        "count": int(non_null.shape[0]),
        "missing": int(series.isna().sum()),
        "unique": int(non_null.nunique()),
    }
    if col_type in {DatasetColumnType.INTEGER, DatasetColumnType.FLOAT}:
        numeric = pd.to_numeric(non_null, errors="coerce").dropna()
        if not numeric.empty:
            stats.update(
                {
                    "mean": float(numeric.mean()),
                    "std": float(numeric.std(ddof=1)) if len(numeric) > 1 else 0.0,
                    "min": float(numeric.min()),
                    "max": float(numeric.max()),
                    "p25": float(numeric.quantile(0.25)),
                    "p50": float(numeric.quantile(0.50)),
                    "p75": float(numeric.quantile(0.75)),
                }
            )
    if col_type == DatasetColumnType.CATEGORY:
        top = non_null.astype(str).value_counts().head(5)
        stats["top_values"] = {str(k): int(v) for k, v in top.items()}
    return stats


def pii_warnings(df: pd.DataFrame) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    for col in df.columns:
        name = str(col).lower()
        sample = " ".join(df[col].astype(str).head(200).tolist())
        if any(token in name for token in ("email", "ssn", "phone", "address", "name")):
            warnings.append(
                {
                    "column": str(col),
                    "risk": "column_name",
                    "message": f"Column '{col}' name suggests possible PII",
                }
            )
        if EMAIL_RE.search(sample):
            warnings.append(
                {
                    "column": str(col),
                    "risk": "email_pattern",
                    "message": f"Email-like values detected in '{col}'",
                }
            )
        if PHONE_RE.search(sample):
            warnings.append(
                {
                    "column": str(col),
                    "risk": "phone_pattern",
                    "message": f"Phone-like values detected in '{col}'",
                }
            )
        if SSN_RE.search(sample):
            warnings.append(
                {
                    "column": str(col),
                    "risk": "ssn_pattern",
                    "message": f"SSN-like values detected in '{col}'",
                }
            )
    # dedupe by column+risk
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, str]] = []
    for item in warnings:
        key = (item["column"], item["risk"])
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def profile_dataframe(
    df: pd.DataFrame,
    *,
    type_overrides: dict[str, DatasetColumnType] | None = None,
) -> dict[str, Any]:
    overrides = type_overrides or {}
    columns: list[dict[str, Any]] = []
    missing_summary: dict[str, Any] = {}
    descriptive: dict[str, Any] = {}
    for idx, col in enumerate(df.columns):
        name = str(col)
        inferred = infer_column_type(df[col])
        override = overrides.get(name)
        effective = override or inferred
        stats = _column_stats(df[col], effective)
        missing_summary[name] = {
            "missing": stats["missing"],
            "ratio": float(stats["missing"] / max(1, len(df))),
        }
        descriptive[name] = stats
        columns.append(
            {
                "name": name,
                "position": idx,
                "inferred_type": inferred.value,
                "override_type": override.value if override else None,
                "nullable_ratio": float(stats["missing"] / max(1, len(df))),
                "unique_count": stats["unique"],
                "stats_json": stats,
            }
        )

    preview = df.head(PREVIEW_ROW_LIMIT).replace({np.nan: None}).to_dict(orient="records")
    # stringify keys
    preview_rows = [{str(k): v for k, v in row.items()} for row in preview]
    duplicate_count = int(df.duplicated().sum())
    schema = {
        "columns": [
            {
                "name": c["name"],
                "type": c["override_type"] or c["inferred_type"],
            }
            for c in columns
        ]
    }
    return {
        "row_count": len(df),
        "column_count": len(df.columns),
        "columns": columns,
        "schema": schema,
        "missing_summary": missing_summary,
        "duplicate_row_count": duplicate_count,
        "descriptive_stats": descriptive,
        "pii_warnings": pii_warnings(df),
        "preview_rows": preview_rows,
    }
