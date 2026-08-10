"""Worker pipeline: scan → extract → chunk → embed."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.time import utcnow
from app.models.enums import FileKind, FileProcessingStatus
from app.models.project_file import (
    ChunkEmbedding,
    DocumentChunk,
    DocumentPage,
    ExtractedDocument,
    FileProcessingJob,
    ProjectFile,
)
from app.services.files import references as reference_service
from app.services.files.chunking import chunk_text
from app.services.files.embeddings import get_embedding_provider
from app.services.files.extract import extract_content
from app.services.storage import get_object_bytes

logger = get_logger(__name__)


async def process_file_job(
    db: AsyncSession,
    *,
    file_id: UUID,
    settings: Settings | None = None,
) -> ProjectFile:
    settings = settings or get_settings()
    file = await db.scalar(
        select(ProjectFile)
        .where(ProjectFile.id == file_id)
        .options(selectinload(ProjectFile.processing_jobs))
    )
    if file is None:
        raise ValueError("file_not_found")
    if file.status == FileProcessingStatus.QUARANTINED:
        return file

    job = await db.scalar(
        select(FileProcessingJob)
        .where(FileProcessingJob.project_file_id == file.id)
        .order_by(FileProcessingJob.created_at.desc())
    )
    if job is None:
        job = FileProcessingJob(project_file_id=file.id, status=FileProcessingStatus.PENDING)
        db.add(job)
        await db.flush()

    job.attempts += 1
    job.started_at = utcnow()
    job.status = FileProcessingStatus.EXTRACTING
    job.stage = "extracting"
    file.status = FileProcessingStatus.EXTRACTING
    await db.flush()

    try:
        data = get_object_bytes(file.storage_key)
        if file.kind in {FileKind.PNG, FileKind.JPEG}:
            file.status = FileProcessingStatus.READY
            job.status = FileProcessingStatus.READY
            job.stage = "ready"
            job.completed_at = utcnow()
            await db.flush()
            return file

        extracted = extract_content(kind=file.kind, data=data, filename=file.safe_filename)
        doc = await db.scalar(
            select(ExtractedDocument).where(ExtractedDocument.project_file_id == file.id)
        )
        if doc is None:
            doc = ExtractedDocument(
                project_file_id=file.id,
                project_id=file.project_id,
            )
            db.add(doc)
            await db.flush()
        doc.title = extracted.title
        doc.plain_text = extracted.plain_text
        doc.page_count = len(extracted.pages)
        doc.metadata_json = extracted.metadata
        await db.flush()

        # replace pages
        existing_pages = await db.scalars(
            select(DocumentPage).where(DocumentPage.document_id == doc.id)
        )
        for page in existing_pages.all():
            await db.delete(page)
        await db.flush()
        for extracted_page in extracted.pages:
            db.add(
                DocumentPage(
                    document_id=doc.id,
                    page_number=extracted_page.page_number,
                    text=extracted_page.text,
                )
            )
        await db.flush()

        if file.kind in {FileKind.BIBTEX, FileKind.RIS} and extracted.bib_entries:
            await reference_service.import_parsed_entries(
                db,
                project_id=file.project_id,
                entries=extracted.bib_entries,
                source_file_id=file.id,
                source_format=file.kind.value,
            )

        job.stage = "chunking"
        file.status = FileProcessingStatus.CHUNKING
        await db.flush()

        # replace chunks/embeddings
        old_chunks = await db.scalars(
            select(DocumentChunk).where(DocumentChunk.document_id == doc.id)
        )
        for chunk in old_chunks.all():
            await db.delete(chunk)
        await db.flush()

        pages = [(p.page_number, p.text) for p in extracted.pages] or None
        drafts = chunk_text(
            extracted.plain_text,
            pages=pages,
            project_file_id=str(file.id),
            settings=settings,
        )
        chunk_rows: list[DocumentChunk] = []
        for draft in drafts:
            row = DocumentChunk(
                document_id=doc.id,
                project_id=file.project_id,
                project_file_id=file.id,
                chunk_index=draft.chunk_index,
                text=draft.text,
                heading=draft.heading,
                page_number=draft.page_number,
                char_start=draft.char_start,
                char_end=draft.char_end,
                token_count=draft.token_count,
                evidence_key=draft.evidence_key,
            )
            db.add(row)
            chunk_rows.append(row)
        await db.flush()

        job.stage = "embedding"
        file.status = FileProcessingStatus.EMBEDDING
        await db.flush()

        provider = get_embedding_provider(settings)
        vectors = await provider.embed([c.text for c in chunk_rows]) if chunk_rows else []
        for chunk, vector in zip(chunk_rows, vectors, strict=False):
            db.add(
                ChunkEmbedding(
                    chunk_id=chunk.id,
                    project_id=file.project_id,
                    model_name=getattr(provider, "name", "unknown"),
                    dimensions=len(vector),
                    embedding=vector,
                    created_at=utcnow(),
                )
            )

        file.status = FileProcessingStatus.READY
        file.error_message = None
        job.status = FileProcessingStatus.READY
        job.stage = "ready"
        job.completed_at = utcnow()
        job.error_message = None
        await db.flush()
        await db.refresh(file)
        return file
    except Exception as exc:
        logger.warning("file_processing_failed", error_type=type(exc).__name__)
        file.status = FileProcessingStatus.FAILED
        # Never expose internal paths
        file.error_message = "Extraction or indexing failed. Check the file and retry."
        job.status = FileProcessingStatus.FAILED
        job.stage = "failed"
        job.error_message = "processing_failed"
        job.completed_at = utcnow()
        await db.flush()
        return file
