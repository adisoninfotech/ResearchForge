"""Deterministic synthetic dataset generation (Python, not LLM rows)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from app.core.exceptions import ValidationAppError
from app.models.dataset import SYNTHETIC_DATASET_LABEL
from app.models.enums import DatasetColumnType

MAX_SYNTHETIC_ROWS = 50_000
MAX_COLUMNS = 64


def _validate_spec(spec: dict[str, Any]) -> tuple[int, int, list[dict[str, Any]]]:
    rows = int(spec.get("rows") or 0)
    if rows < 1 or rows > MAX_SYNTHETIC_ROWS:
        raise ValidationAppError(f"rows must be between 1 and {MAX_SYNTHETIC_ROWS}")
    columns = list(spec.get("columns") or [])
    if not columns or len(columns) > MAX_COLUMNS:
        raise ValidationAppError(f"columns must be between 1 and {MAX_COLUMNS}")
    names = [str(c.get("name") or "").strip() for c in columns]
    if any(not n for n in names):
        raise ValidationAppError("Every column requires a name")
    if len(set(names)) != len(names):
        raise ValidationAppError("Column names must be unique")
    seed = spec.get("random_seed")
    if seed is None:
        raise ValidationAppError("random_seed is required for synthetic generation")
    return rows, int(seed), columns


def generate_synthetic_dataframe(spec: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Generate and validate a synthetic dataframe from a schema spec."""
    rows, seed, columns = _validate_spec(spec)
    rng = np.random.default_rng(seed)
    data: dict[str, Any] = {}
    meta_columns: list[dict[str, Any]] = []

    # optional class balance on a designated target
    target = spec.get("class_balance")
    target_col = None
    if target and isinstance(target, dict):
        target_col = str(target.get("column") or "")
        proportions = target.get("proportions") or {}

    for col in columns:
        name = str(col["name"]).strip()
        dtype = str(col.get("type") or "float").lower()
        missingness = float(col.get("missingness") or 0.0)
        missingness = min(max(missingness, 0.0), 0.9)
        values: np.ndarray | list[Any]
        if dtype in {"integer", "int"}:
            low_i = int(col["min"] if col.get("min") is not None else 0)
            high_i = int(col["max"] if col.get("max") is not None else 100)
            if high_i < low_i:
                raise ValidationAppError(f"Invalid range for column {name}")
            dist = str(col.get("distribution") or "uniform")
            if dist == "normal":
                mean = float(col["mean"] if col.get("mean") is not None else (low_i + high_i) / 2)
                default_std = max(1.0, (high_i - low_i) / 6)
                std = float(col["std"] if col.get("std") is not None else default_std)
                values = (
                    np.clip(rng.normal(mean, std, size=rows), low_i, high_i).round().astype(int)
                )
            else:
                values = rng.integers(low_i, high_i + 1, size=rows)
            col_type = DatasetColumnType.INTEGER
        elif dtype in {"float", "number"}:
            low_f = float(col["min"] if col.get("min") is not None else 0.0)
            high_f = float(col["max"] if col.get("max") is not None else 1.0)
            if high_f < low_f:
                raise ValidationAppError(f"Invalid range for column {name}")
            dist = str(col.get("distribution") or "uniform")
            if dist == "normal":
                mean = float(col["mean"] if col.get("mean") is not None else (low_f + high_f) / 2)
                default_std = max(1e-6, (high_f - low_f) / 6)
                std = float(col["std"] if col.get("std") is not None else default_std)
                values = np.clip(rng.normal(mean, std, size=rows), low_f, high_f)
            else:
                values = rng.uniform(low_f, high_f, size=rows)
            col_type = DatasetColumnType.FLOAT
        elif dtype in {"boolean", "bool"}:
            p = float(col["true_probability"] if col.get("true_probability") is not None else 0.5)
            values = rng.random(rows) < p
            col_type = DatasetColumnType.BOOLEAN
        elif dtype in {"category", "categorical"}:
            categories = list(col.get("categories") or [])
            if not categories:
                raise ValidationAppError(f"Column {name} requires categories")
            if target_col == name and proportions:
                probs = [float(proportions.get(str(c), 0.0)) for c in categories]
                total = sum(probs) or 1.0
                probs = [p / total for p in probs]
                values = rng.choice(categories, size=rows, p=probs)
            else:
                values = rng.choice(categories, size=rows)
            col_type = DatasetColumnType.CATEGORY
        elif dtype in {"string", "text"}:
            prefix = str(col.get("prefix") or name)
            values = np.array([f"{prefix}_{i}" for i in range(rows)], dtype=object)
            col_type = DatasetColumnType.STRING
        else:
            raise ValidationAppError(f"Unsupported column type: {dtype}")

        series = pd.Series(values)
        if missingness > 0:
            mask = rng.random(rows) < missingness
            series = series.mask(mask)
        data[name] = series
        meta_columns.append(
            {
                "name": name,
                "type": col_type.value,
                "missingness": missingness,
                "distribution": col.get("distribution"),
            }
        )

    df = pd.DataFrame(data)

    # simple pairwise correlation adjustment for numeric pairs
    correlations = list(spec.get("correlations") or [])
    for item in correlations:
        a = item.get("a")
        b = item.get("b")
        r = float(item.get("r", 0.0))
        if a not in df.columns or b not in df.columns:
            continue
        if not pd.api.types.is_numeric_dtype(df[a]) or not pd.api.types.is_numeric_dtype(df[b]):
            continue
        r = max(-0.95, min(0.95, r))
        x = df[a].astype(float).to_numpy()
        noise = rng.normal(0, 1, size=rows)
        y = r * (x - np.nanmean(x)) / (np.nanstd(x) + 1e-9) + np.sqrt(max(0.0, 1 - r * r)) * noise
        # rescale to original b range if available
        b_series = df[b].astype(float)
        lo, hi = float(np.nanmin(b_series)), float(np.nanmax(b_series))
        y = (y - y.min()) / (y.max() - y.min() + 1e-9)
        df[b] = lo + y * (hi - lo)

    # validate shape
    if df.shape[0] != rows or df.shape[1] != len(columns):
        raise ValidationAppError("Synthetic generation failed validation")

    metadata = {
        "generator": "researchforge.synthetic.v1",
        "random_seed": seed,
        "rows": rows,
        "columns": meta_columns,
        "correlations": correlations,
        "class_balance": target,
        "provenance_label": SYNTHETIC_DATASET_LABEL,
        "synthetic": True,
    }
    return df, metadata
