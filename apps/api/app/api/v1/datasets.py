"""Dataset Studio API: datasets, analysis, figures, tables, manuscript inserts."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy import select

from app.api.deps import AppSettings, CurrentUser, DbSession, enforce_rate_limit, require_csrf
from app.core.exceptions import NotFoundError, ValidationAppError
from app.models.dataset import AnalysisRun, Figure, Table
from app.models.enums import (
    AnalysisOperation,
    DatasetProvenanceType,
    FigureKind,
    TableKind,
)
from app.schemas.datasets import (
    AnalysisRequest,
    ColumnOverrideRequest,
    ConceptualFigureRequest,
    FigureCreateRequest,
    LabelUpdateRequest,
    ManuscriptInsertRequest,
    SyntheticDatasetRequest,
    TableCreateRequest,
)
from app.services.authorization import get_owned_project
from app.services.datasets import analysis as analysis_service
from app.services.datasets import figures as figure_service
from app.services.datasets import manuscript_assets as asset_service
from app.services.datasets import service as dataset_service
from app.services.datasets import tables as table_service
from app.services.datasets.analysis import SCIENTIFIC_LIMITATIONS

router = APIRouter(prefix="/projects/{project_id}", tags=["datasets"])


@router.get("/datasets/limitations")
async def scientific_limitations(
    project_id: UUID,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    await get_owned_project(session, project_id=project_id, user=user)
    return {"limitations": SCIENTIFIC_LIMITATIONS}


@router.get("/datasets")
async def list_datasets(
    project_id: UUID,
    session: DbSession,
    user: CurrentUser,
) -> list[dict[str, Any]]:
    await get_owned_project(session, project_id=project_id, user=user)
    rows = await dataset_service.list_datasets(session, project_id=project_id)
    return [dataset_service.dataset_to_dict(d) for d in rows]


@router.post(
    "/datasets/upload",
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def upload_dataset(
    project_id: UUID,
    session: DbSession,
    user: CurrentUser,
    settings: AppSettings,
    file: UploadFile = File(...),
    name: str | None = Form(default=None),
    source_description: str | None = Form(default=None),
    license: str | None = Form(default=None),
    provenance_type: str = Form(default="uploaded_real"),
) -> dict[str, Any]:
    project = await get_owned_project(session, project_id=project_id, user=user)
    data = await file.read()
    try:
        prov = DatasetProvenanceType(provenance_type)
    except ValueError as exc:
        raise ValidationAppError("Invalid provenance_type") from exc
    if prov == DatasetProvenanceType.SYNTHETIC:
        raise ValidationAppError("Use the synthetic generation endpoint for synthetic datasets")
    ds = await dataset_service.upload_dataset(
        session,
        project=project,
        user=user,
        filename=file.filename or "data.csv",
        data=data,
        name=name,
        source_description=source_description,
        license=license,
        provenance_type=prov,
        settings=settings,
    )
    return dataset_service.dataset_to_dict(ds)


@router.post(
    "/datasets/synthetic",
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def create_synthetic(
    project_id: UUID,
    payload: SyntheticDatasetRequest,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    project = await get_owned_project(session, project_id=project_id, user=user)
    spec = payload.model_dump()
    name = spec.pop("name")
    source_description = spec.pop("source_description", None)
    ds = await dataset_service.create_synthetic_dataset(
        session,
        project=project,
        user=user,
        name=name,
        spec=spec,
        source_description=source_description,
    )
    return dataset_service.dataset_to_dict(ds)


@router.get("/datasets/{dataset_id}")
async def get_dataset(
    project_id: UUID,
    dataset_id: UUID,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    await get_owned_project(session, project_id=project_id, user=user)
    ds = await dataset_service.get_dataset(session, project_id=project_id, dataset_id=dataset_id)
    if ds is None:
        raise NotFoundError("Dataset not found")
    return dataset_service.dataset_to_dict(ds)


@router.patch(
    "/datasets/{dataset_id}/column-types",
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def override_types(
    project_id: UUID,
    dataset_id: UUID,
    payload: ColumnOverrideRequest,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    await get_owned_project(session, project_id=project_id, user=user)
    ds = await dataset_service.update_column_types(
        session,
        project_id=project_id,
        dataset_id=dataset_id,
        overrides=payload.overrides,
    )
    return dataset_service.dataset_to_dict(ds)


@router.patch(
    "/datasets/{dataset_id}/label",
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def update_label(
    project_id: UUID,
    dataset_id: UUID,
    payload: LabelUpdateRequest,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    await get_owned_project(session, project_id=project_id, user=user)
    ds = await dataset_service.try_remove_synthetic_label(
        session,
        project_id=project_id,
        dataset_id=dataset_id,
        new_label=payload.provenance_label,
    )
    return dataset_service.dataset_to_dict(ds)


@router.delete(
    "/datasets/{dataset_id}",
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def delete_dataset(
    project_id: UUID,
    dataset_id: UUID,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, str]:
    await get_owned_project(session, project_id=project_id, user=user)
    await dataset_service.delete_dataset(session, project_id=project_id, dataset_id=dataset_id)
    return {"status": "deleted"}


@router.post(
    "/analyses",
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def run_analysis(
    project_id: UUID,
    payload: AnalysisRequest,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    await get_owned_project(session, project_id=project_id, user=user)
    try:
        op = AnalysisOperation(payload.operation)
    except ValueError as exc:
        raise ValidationAppError("Invalid analysis operation") from exc
    run = await analysis_service.run_analysis(
        session,
        project_id=project_id,
        user=user,
        dataset_version_id=payload.dataset_version_id,
        operation=op,
        parameters=payload.parameters,
        random_seed=payload.random_seed,
    )
    return analysis_service.run_to_dict(run)


@router.get("/analyses")
async def list_analyses(
    project_id: UUID,
    session: DbSession,
    user: CurrentUser,
) -> list[dict[str, Any]]:
    await get_owned_project(session, project_id=project_id, user=user)
    rows = await session.scalars(
        select(AnalysisRun)
        .where(AnalysisRun.project_id == project_id)
        .order_by(AnalysisRun.created_at.desc())
    )
    return [analysis_service.run_to_dict(r) for r in rows.all()]


@router.get("/analyses/{run_id}")
async def get_analysis(
    project_id: UUID,
    run_id: UUID,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    await get_owned_project(session, project_id=project_id, user=user)
    run = await session.get(AnalysisRun, run_id)
    if run is None or run.project_id != project_id:
        raise NotFoundError("Analysis run not found")
    return analysis_service.run_to_dict(run)


@router.post(
    "/figures",
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def create_figure(
    project_id: UUID,
    payload: FigureCreateRequest,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    await get_owned_project(session, project_id=project_id, user=user)
    try:
        kind = FigureKind(payload.kind)
    except ValueError as exc:
        raise ValidationAppError("Invalid figure kind") from exc
    fig = await figure_service.create_result_figure(
        session,
        project_id=project_id,
        kind=kind,
        title=payload.title,
        dataset_version_id=payload.dataset_version_id,
        analysis_run_id=payload.analysis_run_id,
        caption=payload.caption,
        alt_text=payload.alt_text,
        x_label=payload.x_label,
        y_label=payload.y_label,
        journal_preset=payload.journal_preset,
        parameters=payload.parameters,
    )
    return figure_service.figure_to_dict(fig)


@router.post(
    "/figures/conceptual",
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def create_conceptual(
    project_id: UUID,
    payload: ConceptualFigureRequest,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    await get_owned_project(session, project_id=project_id, user=user)
    fig = await figure_service.create_conceptual_diagram(
        session,
        project_id=project_id,
        title=payload.title,
        mermaid=payload.mermaid,
        caption=payload.caption,
        alt_text=payload.alt_text,
    )
    return figure_service.figure_to_dict(fig)


@router.get("/figures")
async def list_figures(
    project_id: UUID,
    session: DbSession,
    user: CurrentUser,
) -> list[dict[str, Any]]:
    await get_owned_project(session, project_id=project_id, user=user)
    rows = await session.scalars(
        select(Figure).where(Figure.project_id == project_id).order_by(Figure.number)
    )
    return [figure_service.figure_to_dict(f) for f in rows.all()]


@router.post(
    "/tables",
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def create_table(
    project_id: UUID,
    payload: TableCreateRequest,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    await get_owned_project(session, project_id=project_id, user=user)
    try:
        kind = TableKind(payload.kind)
    except ValueError as exc:
        raise ValidationAppError("Invalid table kind") from exc
    table = await table_service.create_table(
        session,
        project_id=project_id,
        kind=kind,
        title=payload.title,
        dataset_version_id=payload.dataset_version_id,
        analysis_run_id=payload.analysis_run_id,
        caption=payload.caption,
        headers=payload.headers,
        rows=payload.rows,
        parameters=payload.parameters,
    )
    return table_service.table_to_dict(table)


@router.get("/tables")
async def list_tables(
    project_id: UUID,
    session: DbSession,
    user: CurrentUser,
) -> list[dict[str, Any]]:
    await get_owned_project(session, project_id=project_id, user=user)
    rows = await session.scalars(
        select(Table).where(Table.project_id == project_id).order_by(Table.number)
    )
    return [table_service.table_to_dict(t) for t in rows.all()]


@router.get("/tables/{table_id}/export")
async def export_table(
    project_id: UUID,
    table_id: UUID,
    session: DbSession,
    user: CurrentUser,
    format: str = Query(default="csv"),
) -> Response:
    await get_owned_project(session, project_id=project_id, user=user)
    table = await session.get(Table, table_id)
    if table is None or table.project_id != project_id:
        raise NotFoundError("Table not found")
    content, media = table_service.export_table(table, format)
    if format in {"csv", "html", "latex", "docx"}:
        return PlainTextResponse(content, media_type=media)
    return Response(content=content, media_type=media)


@router.post(
    "/manuscript-assets/insert",
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def insert_manuscript_asset(
    project_id: UUID,
    payload: ManuscriptInsertRequest,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    return await asset_service.insert_asset(
        session,
        project_id=project_id,
        user=user,
        section_id=payload.section_id,
        asset_type=payload.asset_type,
        asset_stable_id=payload.asset_stable_id,
    )


@router.get("/manuscript-assets")
async def list_manuscript_assets(
    project_id: UUID,
    session: DbSession,
    user: CurrentUser,
) -> list[dict[str, Any]]:
    await get_owned_project(session, project_id=project_id, user=user)
    return await asset_service.list_asset_refs(session, project_id=project_id)
