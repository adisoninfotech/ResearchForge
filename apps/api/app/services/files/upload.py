"""Authenticated secure upload orchestration."""

from __future__ import annotations

import hashlib
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import ConflictError, ValidationAppError
from app.core.security_hardening import validate_zip_safety
from app.core.time import utcnow
from app.models.enums import FileProcessingStatus
from app.models.project import Project
from app.models.project_file import FileProcessingJob, ProjectFile
from app.models.user import User
from app.observability.metrics import UPLOAD_JOBS, metrics
from app.services.files.malware import get_malware_scanner
from app.services.files.signatures import detect_file, sanitize_filename
from app.services.storage import generate_object_key, put_object_trusted


def file_to_dict(file: ProjectFile) -> dict[str, Any]:
    return {
        "id": str(file.id),
        "project_id": str(file.project_id),
        "original_filename": file.original_filename,
        "safe_filename": file.safe_filename,
        "kind": file.kind.value,
        "detected_mime": file.detected_mime,
        "size_bytes": file.size_bytes,
        "status": file.status.value,
        "error_message": file.error_message,
        "exclude_from_ai": file.exclude_from_ai,
        "is_figure": file.is_figure,
        "created_at": file.created_at.isoformat() if file.created_at else None,
    }


async def authorize_and_store_upload(
    db: AsyncSession,
    *,
    project: Project,
    user: User,
    filename: str,
    claimed_content_type: str,
    data: bytes,
    settings: Settings | None = None,
) -> ProjectFile:
    settings = settings or get_settings()
    if len(data) > settings.max_upload_bytes:
        raise ValidationAppError(f"File exceeds maximum size of {settings.max_upload_bytes} bytes")

    safe_name = sanitize_filename(filename)
    # Never trust claimed_content_type or browser filename for kind detection
    detected = detect_file(
        filename=safe_name,
        content_type=claimed_content_type or "",
        data=data,
    )
    if detected.mime not in settings.allowed_upload_content_types:
        raise ValidationAppError("Detected file type is not allowed")
    # OOXML containers are ZIP archives — reject zip bombs / path traversal
    if data.startswith(b"PK"):
        validate_zip_safety(data)

    digest = hashlib.sha256(data).hexdigest()
    existing = await db.scalar(
        select(ProjectFile).where(
            ProjectFile.project_id == project.id,
            ProjectFile.content_sha256 == digest,
        )
    )
    if existing is not None:
        raise ConflictError(
            "Duplicate upload",
            details={"file_id": str(existing.id), "content_sha256": digest},
        )

    scanner = get_malware_scanner(settings)
    scan = await scanner.scan(data=data, filename=safe_name)
    key = generate_object_key(project_id=str(project.id), extension=detected.extension)
    put_object_trusted(key=key, body=data, content_type=detected.mime)

    status = FileProcessingStatus.PENDING
    error = None
    if not scan.clean:
        status = FileProcessingStatus.QUARANTINED
        error = "File failed security scan"

    file = ProjectFile(
        project_id=project.id,
        uploaded_by_id=user.id,
        original_filename=safe_name,
        safe_filename=f"{digest[:12]}.{detected.extension}",
        kind=detected.kind,
        detected_mime=detected.mime,
        size_bytes=len(data),
        content_sha256=digest,
        storage_key=key,
        status=status,
        error_message=error,
        exclude_from_ai=False,
        is_figure=detected.is_figure,
        scan_result={"clean": scan.clean, "engine": scan.engine, "detail": scan.detail},
    )
    db.add(file)
    await db.flush()

    job = FileProcessingJob(
        project_file_id=file.id,
        status=status,
        stage="queued" if scan.clean else "quarantined",
        attempts=0,
    )
    db.add(job)
    await db.flush()
    await db.refresh(file)
    project.last_activity_at = utcnow()
    metrics.incr(
        UPLOAD_JOBS,
        labels={
            "status": "quarantined" if status == FileProcessingStatus.QUARANTINED else "queued",
            "kind": detected.kind.value,
        },
    )
    return file


async def get_project_file(
    db: AsyncSession,
    *,
    project_id: UUID,
    file_id: UUID,
) -> ProjectFile | None:
    row = await db.scalar(
        select(ProjectFile).where(
            ProjectFile.id == file_id,
            ProjectFile.project_id == project_id,
        )
    )
    return row if isinstance(row, ProjectFile) else None
