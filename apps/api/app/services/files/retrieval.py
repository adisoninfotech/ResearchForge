"""Hybrid lexical + semantic retrieval with project isolation and provenance."""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.project_file import ChunkEmbedding, DocumentChunk, ProjectFile
from app.services.files.embeddings import cosine_similarity, get_embedding_provider


class Reranker(Protocol):
    async def rerank(self, query: str, passages: list[dict[str, Any]]) -> list[dict[str, Any]]: ...


class IdentityReranker:
    """Reranking abstraction default — preserves incoming order/scores."""

    name = "identity"

    async def rerank(self, query: str, passages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return passages


def get_reranker() -> IdentityReranker:
    return IdentityReranker()


def chunk_to_passage(chunk: DocumentChunk, *, score: float, source: str) -> dict[str, Any]:
    return {
        "chunk_id": str(chunk.id),
        "evidence_key": chunk.evidence_key,
        "text": chunk.text,
        "source_file_id": str(chunk.project_file_id),
        "page": chunk.page_number,
        "section": chunk.heading,
        "char_start": chunk.char_start,
        "char_end": chunk.char_end,
        "reference_id": str(chunk.reference_id) if chunk.reference_id else None,
        "score": score,
        "match_source": source,
    }


async def hybrid_search(
    db: AsyncSession,
    *,
    project_id: UUID,
    query: str,
    limit: int = 10,
    exclude_ai_excluded: bool = True,
    file_ids: list[UUID] | None = None,
) -> list[dict[str, Any]]:
    stmt = (
        select(DocumentChunk)
        .where(DocumentChunk.project_id == project_id)
        .options(selectinload(DocumentChunk.embedding))
    )
    if file_ids:
        stmt = stmt.where(DocumentChunk.project_file_id.in_(file_ids))
    chunks = list((await db.scalars(stmt)).all())

    if exclude_ai_excluded and chunks:
        file_rows = await db.scalars(
            select(ProjectFile).where(
                ProjectFile.project_id == project_id,
                ProjectFile.exclude_from_ai.is_(True),
            )
        )
        excluded = {f.id for f in file_rows.all()}
        chunks = [c for c in chunks if c.project_file_id not in excluded]

    q = query.strip().lower()
    lexical: list[tuple[DocumentChunk, float]] = []
    if q:
        for chunk in chunks:
            text = chunk.text.lower()
            if q in text:
                score = text.count(q) / max(1, len(text.split()))
                lexical.append((chunk, float(score)))
        lexical.sort(key=lambda x: x[1], reverse=True)

    provider = get_embedding_provider()
    query_vec = (await provider.embed([query]))[0] if query.strip() else []
    semantic: list[tuple[DocumentChunk, float]] = []
    if query_vec:
        emb_rows = await db.scalars(
            select(ChunkEmbedding).where(ChunkEmbedding.project_id == project_id)
        )
        by_chunk = {e.chunk_id: e for e in emb_rows.all()}
        for chunk in chunks:
            emb = chunk.embedding or by_chunk.get(chunk.id)
            if emb is None:
                continue
            score = cosine_similarity(query_vec, list(emb.embedding))
            semantic.append((chunk, score))
        semantic.sort(key=lambda x: x[1], reverse=True)

    ranks: dict[UUID, float] = {}
    passages_by_id: dict[UUID, DocumentChunk] = {}
    for rank, (chunk, _) in enumerate(lexical[:50]):
        ranks[chunk.id] = ranks.get(chunk.id, 0.0) + 1.0 / (60 + rank)
        passages_by_id[chunk.id] = chunk
    for rank, (chunk, _) in enumerate(semantic[:50]):
        ranks[chunk.id] = ranks.get(chunk.id, 0.0) + 1.0 / (60 + rank)
        passages_by_id[chunk.id] = chunk

    fused = sorted(ranks.items(), key=lambda x: x[1], reverse=True)[: limit * 2]
    # Defense-in-depth: never return chunks from another project
    for cid, _ in fused:
        chunk = passages_by_id[cid]
        if chunk.project_id != project_id:
            raise RuntimeError("Cross-project retrieval leakage blocked")
    results = [
        chunk_to_passage(passages_by_id[cid], score=score, source="hybrid") for cid, score in fused
    ]
    reranker = get_reranker()
    reranked = await reranker.rerank(query, results)
    return reranked[:limit]
