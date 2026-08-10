"""Secure uploads, processing, retrieval, references, and evidence APIs."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import PlainTextResponse
from sqlalchemy import select

from app.api.deps import AppSettings, CurrentUser, DbSession, enforce_rate_limit, require_csrf
from app.core.exceptions import NotFoundError, ValidationAppError
from app.models.enums import ClaimSupportStatus, FileProcessingStatus
from app.models.evidence import ClaimProvenance
from app.models.project_file import ProjectFile
from app.schemas.files import (
    ClaimUpdateRequest,
    EvidenceLinkCreate,
    EvidenceLinkUpdate,
    FileAuthorizeResponse,
    FilePatchRequest,
    ReferenceCreateRequest,
    ReferenceImportRequest,
    ReferenceUpdateRequest,
    SearchRequest,
)
from app.services.authorization import get_owned_project
from app.services.files import evidence as evidence_service
from app.services.files import references as reference_service
from app.services.files import retrieval as retrieval_service
from app.services.files import upload as upload_service
from app.services.files.processing import process_file_job
from app.services.storage import presigned_get_url

router = APIRouter(prefix="/projects/{project_id}", tags=["files"])


@router.post(
    "/files/authorize",
    response_model=FileAuthorizeResponse,
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def authorize_upload(
    project_id: UUID,
    session: DbSession,
    user: CurrentUser,
    settings: AppSettings,
) -> FileAuthorizeResponse:
    """Steps 1-2: authenticated upload authorization + project ownership check."""
    await get_owned_project(session, project_id=project_id, user=user)
    return FileAuthorizeResponse(
        authorized=True,
        max_bytes=settings.max_upload_bytes,
        allowed_content_types=list(settings.allowed_upload_content_types),
        upload_path=f"/api/v1/projects/{project_id}/files/upload",
    )


@router.post(
    "/files/upload",
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def upload_file(
    project_id: UUID,
    session: DbSession,
    user: CurrentUser,
    settings: AppSettings,
    file: UploadFile = File(...),
    process_sync: bool = Form(default=False),
) -> dict[str, Any]:
    project = await get_owned_project(session, project_id=project_id, user=user)
    data = await file.read()
    # Intentionally ignore client content_type for authorization decisions
    stored = await upload_service.authorize_and_store_upload(
        session,
        project=project,
        user=user,
        filename=file.filename or "upload.bin",
        claimed_content_type=file.content_type or "",
        data=data,
        settings=settings,
    )
    if stored.status != FileProcessingStatus.QUARANTINED:
        if process_sync or settings.app_env == "test":
            stored = await process_file_job(session, file_id=stored.id, settings=settings)
        else:
            from app.workers.tasks import process_project_file

            process_project_file.delay(str(stored.id))
    return upload_service.file_to_dict(stored)


@router.get("/files")
async def list_files(
    project_id: UUID,
    session: DbSession,
    user: CurrentUser,
) -> list[dict[str, Any]]:
    await get_owned_project(session, project_id=project_id, user=user)
    rows = await session.scalars(
        select(ProjectFile)
        .where(ProjectFile.project_id == project_id)
        .order_by(ProjectFile.created_at.desc())
    )
    return [upload_service.file_to_dict(f) for f in rows.all()]


@router.get("/files/{file_id}")
async def get_file(
    project_id: UUID,
    file_id: UUID,
    session: DbSession,
    user: CurrentUser,
    settings: AppSettings,
) -> dict[str, Any]:
    await get_owned_project(session, project_id=project_id, user=user)
    row = await upload_service.get_project_file(session, project_id=project_id, file_id=file_id)
    if row is None:
        raise NotFoundError("File not found")
    payload = upload_service.file_to_dict(row)
    payload["download_url"] = presigned_get_url(
        row.storage_key,
        expires_in=settings.upload_signed_url_expire_seconds,
    )
    payload["signed_url_expires_in"] = settings.upload_signed_url_expire_seconds
    return payload


@router.patch(
    "/files/{file_id}",
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def patch_file(
    project_id: UUID,
    file_id: UUID,
    payload: FilePatchRequest,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    await get_owned_project(session, project_id=project_id, user=user)
    row = await upload_service.get_project_file(session, project_id=project_id, file_id=file_id)
    if row is None:
        raise NotFoundError("File not found")
    if payload.exclude_from_ai is not None:
        row.exclude_from_ai = payload.exclude_from_ai
    await session.flush()
    return upload_service.file_to_dict(row)


@router.post(
    "/files/{file_id}/retry",
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def retry_processing(
    project_id: UUID,
    file_id: UUID,
    session: DbSession,
    user: CurrentUser,
    settings: AppSettings,
) -> dict[str, Any]:
    await get_owned_project(session, project_id=project_id, user=user)
    row = await upload_service.get_project_file(session, project_id=project_id, file_id=file_id)
    if row is None:
        raise NotFoundError("File not found")
    if row.status == FileProcessingStatus.QUARANTINED:
        raise ValidationAppError("Quarantined files cannot be retried")
    row = await process_file_job(session, file_id=row.id, settings=settings)
    return upload_service.file_to_dict(row)


@router.post(
    "/search",
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def search_evidence(
    project_id: UUID,
    payload: SearchRequest,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    await get_owned_project(session, project_id=project_id, user=user)
    results = await retrieval_service.hybrid_search(
        session,
        project_id=project_id,
        query=payload.query,
        limit=payload.limit,
        file_ids=payload.file_ids,
    )
    return {"results": results}


@router.get("/references")
async def list_references(
    project_id: UUID,
    session: DbSession,
    user: CurrentUser,
    q: str | None = Query(default=None),
) -> list[dict[str, Any]]:
    await get_owned_project(session, project_id=project_id, user=user)
    refs = await reference_service.list_references(session, project_id=project_id, q=q)
    return [reference_service.reference_to_dict(r) for r in refs]


@router.post(
    "/references",
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def create_reference(
    project_id: UUID,
    payload: ReferenceCreateRequest,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    await get_owned_project(session, project_id=project_id, user=user)
    ref = await reference_service.create_manual_reference(
        session,
        project_id=project_id,
        payload=payload.model_dump(),
    )
    return reference_service.reference_to_dict(ref)


@router.post(
    "/references/import",
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def import_references(
    project_id: UUID,
    payload: ReferenceImportRequest,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    await get_owned_project(session, project_id=project_id, user=user)
    refs = await reference_service.import_text(
        session,
        project_id=project_id,
        text=payload.text,
        format=payload.format,
    )
    return {"references": [reference_service.reference_to_dict(r) for r in refs]}


@router.patch(
    "/references/{reference_id}",
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def update_reference(
    project_id: UUID,
    reference_id: UUID,
    payload: ReferenceUpdateRequest,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    await get_owned_project(session, project_id=project_id, user=user)
    ref = await reference_service.update_reference(
        session,
        project_id=project_id,
        reference_id=reference_id,
        payload=payload.model_dump(exclude_unset=True),
    )
    return reference_service.reference_to_dict(ref)


@router.get("/references/export/bibtex")
async def export_bibtex(
    project_id: UUID,
    session: DbSession,
    user: CurrentUser,
) -> PlainTextResponse:
    await get_owned_project(session, project_id=project_id, user=user)
    refs = await reference_service.list_references(session, project_id=project_id)
    return PlainTextResponse(
        reference_service.export_bibtex(refs),
        media_type="application/x-bibtex",
    )


@router.get("/references/export/ris")
async def export_ris(
    project_id: UUID,
    session: DbSession,
    user: CurrentUser,
) -> PlainTextResponse:
    await get_owned_project(session, project_id=project_id, user=user)
    refs = await reference_service.list_references(session, project_id=project_id)
    return PlainTextResponse(
        reference_service.export_ris(refs),
        media_type="application/x-research-info-systems",
    )


@router.post(
    "/evidence",
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def pin_evidence(
    project_id: UUID,
    payload: EvidenceLinkCreate,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    await get_owned_project(session, project_id=project_id, user=user)
    link = await evidence_service.pin_evidence(
        session,
        project_id=project_id,
        chunk_id=payload.chunk_id,
        section_id=payload.section_id,
        relation=payload.relation,
        note=payload.note,
    )
    return {
        "id": str(link.id),
        "chunk_id": str(link.chunk_id),
        "relation": link.relation.value,
        "note": link.note,
    }


@router.get("/evidence")
async def list_evidence(
    project_id: UUID,
    session: DbSession,
    user: CurrentUser,
    section_id: UUID | None = Query(default=None),
) -> list[dict[str, Any]]:
    await get_owned_project(session, project_id=project_id, user=user)
    return await evidence_service.list_evidence_links(
        session, project_id=project_id, section_id=section_id
    )


@router.patch(
    "/evidence/{link_id}",
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def update_evidence(
    project_id: UUID,
    link_id: UUID,
    payload: EvidenceLinkUpdate,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    await get_owned_project(session, project_id=project_id, user=user)
    link = await evidence_service.update_evidence_link(
        session,
        project_id=project_id,
        link_id=link_id,
        payload=payload.model_dump(exclude_unset=True),
    )
    return {
        "id": str(link.id),
        "relation": link.relation.value,
        "note": link.note,
        "exclude_from_ai": link.exclude_from_ai,
        "pinned": link.pinned,
    }


@router.delete(
    "/evidence/{link_id}",
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def delete_evidence(
    project_id: UUID,
    link_id: UUID,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, str]:
    await get_owned_project(session, project_id=project_id, user=user)
    await evidence_service.remove_evidence_link(session, project_id=project_id, link_id=link_id)
    return {"status": "removed"}


@router.get("/claims")
async def list_claims(
    project_id: UUID,
    session: DbSession,
    user: CurrentUser,
    section_id: UUID | None = Query(default=None),
) -> list[dict[str, Any]]:
    await get_owned_project(session, project_id=project_id, user=user)
    return await evidence_service.list_claims(session, project_id=project_id, section_id=section_id)


@router.patch(
    "/claims/{claim_id}",
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def update_claim(
    project_id: UUID,
    claim_id: UUID,
    payload: ClaimUpdateRequest,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    await get_owned_project(session, project_id=project_id, user=user)
    claim = await session.get(ClaimProvenance, claim_id)
    if claim is None or claim.project_id != project_id:
        raise NotFoundError("Claim not found")
    if payload.user_verification_status is not None:
        claim.user_verification_status = payload.user_verification_status
    if payload.support_status is not None:
        claim.support_status = ClaimSupportStatus(payload.support_status)
    await session.flush()
    return {
        "id": str(claim.id),
        "support_status": claim.support_status.value,
        "user_verification_status": claim.user_verification_status,
    }


@router.get("/citations")
async def list_citations(
    project_id: UUID,
    session: DbSession,
    user: CurrentUser,
    reference_id: UUID | None = Query(default=None),
) -> list[dict[str, Any]]:
    await get_owned_project(session, project_id=project_id, user=user)
    return await evidence_service.list_citation_mentions(
        session, project_id=project_id, reference_id=reference_id
    )
