"""project files, references, chunks, evidence, claim provenance

Revision ID: 20260802_0004
Revises: 20260802_0003
Create Date: 2026-08-02 20:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260802_0004"
down_revision: Union[str, None] = "20260802_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

file_kind = postgresql.ENUM(
    "pdf",
    "docx",
    "txt",
    "markdown",
    "bibtex",
    "ris",
    "csv",
    "xlsx",
    "png",
    "jpeg",
    "other",
    name="file_kind",
    create_type=False,
)
file_processing_status = postgresql.ENUM(
    "pending",
    "scanning",
    "extracting",
    "chunking",
    "embedding",
    "ready",
    "failed",
    "quarantined",
    name="file_processing_status",
    create_type=False,
)
file_job_status = postgresql.ENUM(
    "pending",
    "scanning",
    "extracting",
    "chunking",
    "embedding",
    "ready",
    "failed",
    "quarantined",
    name="file_job_status",
    create_type=False,
)
reference_verification_status = postgresql.ENUM(
    "unverified",
    "verified",
    "needs_correction",
    "duplicate",
    name="reference_verification_status",
    create_type=False,
)
evidence_relation = postgresql.ENUM(
    "supports",
    "contradicts",
    "background",
    "method",
    name="evidence_relation",
    create_type=False,
)
claim_support_status = postgresql.ENUM(
    "supported",
    "partially_supported",
    "unsupported",
    "conflicting_evidence",
    "citation_missing",
    "user_provided_fact",
    "calculated_result",
    name="claim_support_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    for enum in (
        file_kind,
        file_processing_status,
        file_job_status,
        reference_verification_status,
        evidence_relation,
        claim_support_status,
    ):
        enum.create(bind, checkfirst=True)

    json_type = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")

    op.create_table(
        "project_files",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "uploaded_by_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("original_filename", sa.String(length=512), nullable=False),
        sa.Column("safe_filename", sa.String(length=255), nullable=False),
        sa.Column("kind", file_kind, nullable=False),
        sa.Column("detected_mime", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=1024), nullable=False),
        sa.Column("status", file_processing_status, nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("exclude_from_ai", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_figure", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("scan_result", json_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "content_sha256", name="uq_project_file_sha"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index("ix_project_files_project_id", "project_files", ["project_id"])
    op.create_index("ix_project_files_content_sha256", "project_files", ["content_sha256"])
    op.create_index("ix_project_files_status", "project_files", ["status"])

    op.create_table(
        "file_processing_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "project_file_id",
            sa.Uuid(),
            sa.ForeignKey("project_files.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", file_job_status, nullable=False),
        sa.Column("stage", sa.String(length=64), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("celery_task_id", sa.String(length=255), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_file_processing_jobs_project_file_id",
        "file_processing_jobs",
        ["project_file_id"],
    )

    op.create_table(
        "extracted_documents",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "project_file_id",
            sa.Uuid(),
            sa.ForeignKey("project_files.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("plain_text", sa.Text(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_file_id"),
    )
    op.create_index("ix_extracted_documents_project_id", "extracted_documents", ["project_id"])

    op.create_table(
        "document_pages",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "document_id",
            sa.Uuid(),
            sa.ForeignKey("extracted_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.UniqueConstraint("document_id", "page_number", name="uq_document_page"),
    )
    op.create_index("ix_document_pages_document_id", "document_pages", ["document_id"])

    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "document_id",
            sa.Uuid(),
            sa.ForeignKey("extracted_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_file_id",
            sa.Uuid(),
            sa.ForeignKey("project_files.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("heading", sa.String(length=500), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("char_start", sa.Integer(), nullable=True),
        sa.Column("char_end", sa.Integer(), nullable=True),
        sa.Column("reference_id", sa.Uuid(), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("evidence_key", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("evidence_key"),
    )
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])
    op.create_index("ix_document_chunks_project_id", "document_chunks", ["project_id"])
    op.create_index("ix_document_chunks_project_file_id", "document_chunks", ["project_file_id"])

    op.create_table(
        "chunk_embeddings",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "chunk_id",
            sa.Uuid(),
            sa.ForeignKey("document_chunks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("model_name", sa.String(length=255), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("embedding", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("chunk_id"),
    )
    op.create_index("ix_chunk_embeddings_project_id", "chunk_embeddings", ["project_id"])

    op.create_table(
        "references",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=1000), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("venue", sa.String(length=500), nullable=True),
        sa.Column("url", sa.String(length=2000), nullable=True),
        sa.Column("abstract", sa.Text(), nullable=True),
        sa.Column("doi", sa.String(length=255), nullable=True),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("verification_status", reference_verification_status, nullable=False),
        sa.Column(
            "source_file_id",
            sa.Uuid(),
            sa.ForeignKey("project_files.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("raw_bibtex", sa.Text(), nullable=True),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column(
            "needs_user_correction",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "fingerprint", name="uq_reference_fingerprint"),
    )
    op.create_index("ix_references_project_id", "references", ["project_id"])
    op.create_index("ix_references_doi", "references", ["doi"])

    op.create_table(
        "reference_authors",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "reference_id",
            sa.Uuid(),
            sa.ForeignKey("references.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("full_name", sa.String(length=500), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_reference_authors_reference_id", "reference_authors", ["reference_id"])

    op.create_table(
        "reference_identifiers",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "reference_id",
            sa.Uuid(),
            sa.ForeignKey("references.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("id_type", sa.String(length=40), nullable=False),
        sa.Column("value", sa.String(length=255), nullable=False),
        sa.UniqueConstraint(
            "reference_id",
            "id_type",
            "value",
            name="uq_reference_identifier",
        ),
    )
    op.create_index(
        "ix_reference_identifiers_reference_id",
        "reference_identifiers",
        ["reference_id"],
    )

    op.create_table(
        "evidence_links",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "chunk_id",
            sa.Uuid(),
            sa.ForeignKey("document_chunks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("section_id", sa.Uuid(), nullable=True),
        sa.Column("relation", evidence_relation, nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("pinned", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "exclude_from_ai",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_evidence_links_project_id", "evidence_links", ["project_id"])
    op.create_index("ix_evidence_links_chunk_id", "evidence_links", ["chunk_id"])

    op.create_table(
        "citation_mentions",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "reference_id",
            sa.Uuid(),
            sa.ForeignKey("references.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "chunk_id",
            sa.Uuid(),
            sa.ForeignKey("document_chunks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("section_id", sa.Uuid(), nullable=True),
        sa.Column("cite_key", sa.String(length=100), nullable=True),
        sa.Column("context_snippet", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_citation_mentions_project_id", "citation_mentions", ["project_id"])

    op.create_table(
        "claim_provenance",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("section_id", sa.Uuid(), nullable=True),
        sa.Column("claim_text", sa.Text(), nullable=False),
        sa.Column("evidence_chunk_ids", json_type, nullable=False),
        sa.Column("support_score", sa.Float(), nullable=True),
        sa.Column("support_status", claim_support_status, nullable=False),
        sa.Column(
            "user_verification_status",
            sa.String(length=40),
            nullable=False,
            server_default="unverified",
        ),
        sa.Column(
            "citation_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("model_metadata", json_type, nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_claim_provenance_project_id", "claim_provenance", ["project_id"])


def downgrade() -> None:
    op.drop_table("claim_provenance")
    op.drop_table("citation_mentions")
    op.drop_table("evidence_links")
    op.drop_table("reference_identifiers")
    op.drop_table("reference_authors")
    op.drop_table("references")
    op.drop_table("chunk_embeddings")
    op.drop_table("document_chunks")
    op.drop_table("document_pages")
    op.drop_table("extracted_documents")
    op.drop_table("file_processing_jobs")
    op.drop_table("project_files")
    bind = op.get_bind()
    for enum in (
        claim_support_status,
        evidence_relation,
        reference_verification_status,
        file_job_status,
        file_processing_status,
        file_kind,
    ):
        enum.drop(bind, checkfirst=True)
