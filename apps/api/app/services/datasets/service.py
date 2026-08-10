"""Dataset CRUD: upload, synthetic create, versioning, deletion."""

from __future__ import annotations

import hashlib
import uuid
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings, get_settings
from app.core.exceptions import NotFoundError, ValidationAppError
from app.core.time import utcnow
from app.models.dataset import (
    SYNTHETIC_DATASET_LABEL,
    Dataset,
    DatasetColumn,
    DatasetProfile,
    DatasetVersion,
    ReproducibilityManifest,
)
from app.models.enums import DatasetColumnType, DatasetProvenanceType
from app.models.project import Project
from app.models.user import User
from app.services.datasets.profiling import dataframe_to_csv_bytes, profile_dataframe, read_tabular
from app.services.datasets.synthetic import generate_synthetic_dataframe
from app.services.storage import delete_object, put_object_trusted


def _provenance_label(provenance: DatasetProvenanceType, *, synthetic: bool) -> str:
    if synthetic or provenance == DatasetProvenanceType.SYNTHETIC:
        return SYNTHETIC_DATASET_LABEL
    labels = {
        DatasetProvenanceType.UPLOADED_REAL: "Uploaded real data",
        DatasetProvenanceType.PUBLICLY_SOURCED: "Publicly sourced data",
        DatasetProvenanceType.SIMULATED_EXPERIMENT: "Simulated experiment output",
        DatasetProvenanceType.CALCULATED_RESULT: "Calculated result",
        DatasetProvenanceType.USER_ENTERED: "User-entered value",
    }
    return labels.get(provenance, provenance.value)


def dataset_to_dict(ds: Dataset, version: DatasetVersion | None = None) -> dict[str, Any]:
    ver = version
    versions = list(ds.__dict__.get("versions") or [])
    if ver is None and versions:
        ver = max(versions, key=lambda v: v.version_number)
    payload: dict[str, Any] = {
        "id": str(ds.id),
        "project_id": str(ds.project_id),
        "name": ds.name,
        "provenance_type": ds.provenance_type.value,
        "synthetic": ds.synthetic,
        "source_description": ds.source_description,
        "license": ds.license,
        "provenance_label": ds.provenance_label,
        "label_locked": ds.label_locked,
        "creation_parameters": ds.creation_parameters,
        "random_seed": ds.random_seed,
        "created_by_id": str(ds.created_by_id) if ds.created_by_id else None,
        "created_at": ds.created_at.isoformat() if ds.created_at else None,
        "current_version_id": str(ds.current_version_id) if ds.current_version_id else None,
    }
    if ver is not None:
        payload["version"] = version_to_dict(ver)
    return payload


def version_to_dict(ver: DatasetVersion) -> dict[str, Any]:
    # Use __dict__ to avoid implicit lazy-loads in async contexts
    profile = ver.__dict__.get("profile")
    columns = list(ver.__dict__.get("columns") or [])
    return {
        "id": str(ver.id),
        "version_number": ver.version_number,
        "content_sha256": ver.content_sha256,
        "row_count": ver.row_count,
        "column_count": ver.column_count,
        "schema": ver.schema_json,
        "is_immutable_original": ver.is_immutable_original,
        "columns": [
            {
                "name": c.name,
                "position": c.position,
                "inferred_type": c.inferred_type.value,
                "override_type": c.override_type.value if c.override_type else None,
                "nullable_ratio": c.nullable_ratio,
                "unique_count": c.unique_count,
                "stats": c.stats_json,
            }
            for c in columns
        ],
        "profile": (
            {
                "missing_summary": profile.missing_summary,
                "duplicate_row_count": profile.duplicate_row_count,
                "descriptive_stats": profile.descriptive_stats,
                "pii_warnings": profile.pii_warnings,
                "preview_rows": profile.preview_rows,
            }
            if profile is not None
            else None
        ),
    }


async def _persist_version(
    db: AsyncSession,
    *,
    dataset: Dataset,
    project_id: UUID,
    csv_bytes: bytes,
    original_bytes: bytes | None,
    original_ext: str,
    profile: dict[str, Any],
    notes: str | None = None,
) -> DatasetVersion:
    digest = hashlib.sha256(csv_bytes).hexdigest()
    existing = await db.scalars(
        select(DatasetVersion).where(DatasetVersion.dataset_id == dataset.id)
    )
    version_number = len(list(existing.all())) + 1

    key = f"projects/{project_id}/datasets/{dataset.id}/v{version_number}.csv"
    put_object_trusted(key=key, body=csv_bytes, content_type="text/csv")
    original_key = None
    if original_bytes is not None:
        original_key = (
            f"projects/{project_id}/datasets/{dataset.id}/original_v{version_number}.{original_ext}"
        )
        put_object_trusted(
            key=original_key,
            body=original_bytes,
            content_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                if original_ext == "xlsx"
                else "text/csv"
            ),
        )

    ver = DatasetVersion(
        dataset_id=dataset.id,
        project_id=project_id,
        version_number=version_number,
        storage_key=key,
        original_storage_key=original_key,
        content_sha256=digest,
        row_count=profile["row_count"],
        column_count=profile["column_count"],
        schema_json=profile["schema"],
        is_immutable_original=True,
        notes=notes,
    )
    db.add(ver)
    await db.flush()

    for col in profile["columns"]:
        override = DatasetColumnType(col["override_type"]) if col.get("override_type") else None
        db.add(
            DatasetColumn(
                version_id=ver.id,
                name=col["name"],
                position=col["position"],
                inferred_type=DatasetColumnType(col["inferred_type"]),
                override_type=override,
                nullable_ratio=col["nullable_ratio"],
                unique_count=col["unique_count"],
                stats_json=col["stats_json"],
            )
        )
    db.add(
        DatasetProfile(
            version_id=ver.id,
            project_id=project_id,
            missing_summary=profile["missing_summary"],
            duplicate_row_count=profile["duplicate_row_count"],
            descriptive_stats=profile["descriptive_stats"],
            pii_warnings=profile["pii_warnings"],
            preview_rows=profile["preview_rows"],
        )
    )
    dataset.current_version_id = ver.id
    await db.flush()

    manifest = ReproducibilityManifest(
        project_id=project_id,
        dataset_id=dataset.id,
        manifest_json={
            "dataset_id": str(dataset.id),
            "version_id": str(ver.id),
            "version_number": ver.version_number,
            "content_sha256": digest,
            "row_count": ver.row_count,
            "column_count": ver.column_count,
            "schema": ver.schema_json,
            "provenance_type": dataset.provenance_type.value,
            "synthetic": dataset.synthetic,
            "random_seed": dataset.random_seed,
            "creation_parameters": dataset.creation_parameters,
            "created_at": utcnow().isoformat(),
        },
        provenance_label=dataset.provenance_label,
    )
    db.add(manifest)
    await db.flush()
    await db.refresh(ver, attribute_names=["columns", "profile"])
    return ver


async def upload_dataset(
    db: AsyncSession,
    *,
    project: Project,
    user: User,
    filename: str,
    data: bytes,
    name: str | None = None,
    source_description: str | None = None,
    license: str | None = None,
    provenance_type: DatasetProvenanceType = DatasetProvenanceType.UPLOADED_REAL,
    type_overrides: dict[str, str] | None = None,
    settings: Settings | None = None,
) -> Dataset:
    settings = settings or get_settings()
    max_bytes = min(settings.max_upload_bytes, settings.max_dataset_bytes)
    if len(data) > max_bytes:
        raise ValidationAppError(f"Dataset exceeds maximum size of {max_bytes} bytes")
    lower = filename.lower()
    if not (lower.endswith(".csv") or lower.endswith(".xlsx")):
        raise ValidationAppError("Only CSV and XLSX datasets are supported")

    try:
        df = read_tabular(data, filename=filename)
    except Exception as exc:
        raise ValidationAppError("Unable to parse dataset file") from exc
    if df.empty:
        raise ValidationAppError("Dataset has no rows")

    overrides = {k: DatasetColumnType(v) for k, v in (type_overrides or {}).items() if v}
    profile = profile_dataframe(df, type_overrides=overrides)
    csv_bytes = dataframe_to_csv_bytes(df)

    synthetic = provenance_type == DatasetProvenanceType.SYNTHETIC
    label = _provenance_label(provenance_type, synthetic=synthetic)
    ds = Dataset(
        project_id=project.id,
        created_by_id=user.id,
        name=name or filename.rsplit(".", 1)[0][:255],
        provenance_type=provenance_type,
        synthetic=synthetic,
        source_description=source_description,
        license=license,
        provenance_label=label,
        label_locked=provenance_type
        in {
            DatasetProvenanceType.SYNTHETIC,
            DatasetProvenanceType.SIMULATED_EXPERIMENT,
        },
        creation_parameters={"upload_filename": filename},
        random_seed=None,
    )
    db.add(ds)
    await db.flush()
    ext = "xlsx" if lower.endswith(".xlsx") else "csv"
    await _persist_version(
        db,
        dataset=ds,
        project_id=project.id,
        csv_bytes=csv_bytes,
        original_bytes=data,
        original_ext=ext,
        profile=profile,
        notes="Immutable original upload",
    )
    if provenance_type in {
        DatasetProvenanceType.SYNTHETIC,
        DatasetProvenanceType.SIMULATED_EXPERIMENT,
    }:
        project.contains_synthetic_data = True
    loaded = await get_dataset(db, project_id=project.id, dataset_id=ds.id)
    assert loaded is not None
    return loaded


async def create_synthetic_dataset(
    db: AsyncSession,
    *,
    project: Project,
    user: User,
    name: str,
    spec: dict[str, Any],
    source_description: str | None = None,
) -> Dataset:
    df, metadata = generate_synthetic_dataframe(spec)
    profile = profile_dataframe(df)
    csv_bytes = dataframe_to_csv_bytes(df)

    ds = Dataset(
        project_id=project.id,
        created_by_id=user.id,
        name=name,
        provenance_type=DatasetProvenanceType.SYNTHETIC,
        synthetic=True,
        source_description=source_description or "Generated by ResearchForge Dataset Studio",
        license="synthetic-not-collected-data",
        provenance_label=SYNTHETIC_DATASET_LABEL,
        label_locked=True,
        creation_parameters={**spec, **metadata},
        random_seed=int(spec["random_seed"]),
    )
    db.add(ds)
    await db.flush()
    await _persist_version(
        db,
        dataset=ds,
        project_id=project.id,
        csv_bytes=csv_bytes,
        original_bytes=csv_bytes,
        original_ext="csv",
        profile=profile,
        notes="Synthetic generation",
    )
    project.contains_synthetic_data = True
    loaded = await get_dataset(db, project_id=project.id, dataset_id=ds.id)
    assert loaded is not None
    return loaded


async def list_datasets(db: AsyncSession, *, project_id: UUID) -> list[Dataset]:
    rows = await db.scalars(
        select(Dataset)
        .where(Dataset.project_id == project_id)
        .options(selectinload(Dataset.versions).selectinload(DatasetVersion.columns))
        .options(selectinload(Dataset.versions).selectinload(DatasetVersion.profile))
        .order_by(Dataset.created_at.desc())
    )
    return list(rows.all())


async def get_dataset(
    db: AsyncSession,
    *,
    project_id: UUID,
    dataset_id: UUID,
) -> Dataset | None:
    row = await db.scalar(
        select(Dataset)
        .where(Dataset.id == dataset_id, Dataset.project_id == project_id)
        .options(selectinload(Dataset.versions).selectinload(DatasetVersion.columns))
        .options(selectinload(Dataset.versions).selectinload(DatasetVersion.profile))
    )
    return row if isinstance(row, Dataset) else None


async def get_version(
    db: AsyncSession,
    *,
    project_id: UUID,
    version_id: UUID,
) -> DatasetVersion | None:
    row = await db.scalar(
        select(DatasetVersion)
        .where(DatasetVersion.id == version_id, DatasetVersion.project_id == project_id)
        .options(selectinload(DatasetVersion.columns), selectinload(DatasetVersion.profile))
    )
    return row if isinstance(row, DatasetVersion) else None


async def update_column_types(
    db: AsyncSession,
    *,
    project_id: UUID,
    dataset_id: UUID,
    overrides: dict[str, str],
) -> Dataset:
    ds = await get_dataset(db, project_id=project_id, dataset_id=dataset_id)
    if ds is None or not ds.current_version_id:
        raise NotFoundError("Dataset not found")
    ver = await get_version(db, project_id=project_id, version_id=ds.current_version_id)
    if ver is None:
        raise NotFoundError("Dataset version not found")
    from app.services.storage import get_object_bytes

    csv_bytes = get_object_bytes(ver.storage_key)
    df = read_tabular(csv_bytes, filename="data.csv")
    typed = {k: DatasetColumnType(v) for k, v in overrides.items()}
    profile = profile_dataframe(df, type_overrides=typed)
    # new version with overrides (original remains immutable)
    await _persist_version(
        db,
        dataset=ds,
        project_id=project_id,
        csv_bytes=csv_bytes,
        original_bytes=None,
        original_ext="csv",
        profile=profile,
        notes="Type overrides",
    )
    loaded = await get_dataset(db, project_id=project_id, dataset_id=dataset_id)
    assert loaded is not None
    return loaded


async def delete_dataset(db: AsyncSession, *, project_id: UUID, dataset_id: UUID) -> None:
    ds = await get_dataset(db, project_id=project_id, dataset_id=dataset_id)
    if ds is None:
        raise NotFoundError("Dataset not found")
    for ver in ds.versions:
        delete_object(ver.storage_key)
        if ver.original_storage_key:
            delete_object(ver.original_storage_key)
    await db.delete(ds)
    await db.flush()


async def try_remove_synthetic_label(
    db: AsyncSession,
    *,
    project_id: UUID,
    dataset_id: UUID,
    new_label: str,
) -> Dataset:
    """Synthetic labels are locked and cannot be removed."""
    ds = await get_dataset(db, project_id=project_id, dataset_id=dataset_id)
    if ds is None:
        raise NotFoundError("Dataset not found")
    if (
        ds.label_locked
        or ds.synthetic
        or ds.provenance_type
        in {
            DatasetProvenanceType.SYNTHETIC,
            DatasetProvenanceType.SIMULATED_EXPERIMENT,
        }
    ):
        raise ValidationAppError(
            "Synthetic or simulated provenance label cannot be removed or replaced",
            details={"provenance_label": ds.provenance_label},
        )
    ds.provenance_label = new_label
    await db.flush()
    return ds


def new_stable_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"
