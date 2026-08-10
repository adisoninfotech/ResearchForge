"""Insert figures/tables into manuscript sections with stable cross-references."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationAppError
from app.models.dataset import Figure, ManuscriptAssetRef, Table
from app.models.enums import VersionAuthorType
from app.models.user import User
from app.services import manuscripts as manuscript_service
from app.services.authorization import get_owned_project


async def insert_asset(
    db: AsyncSession,
    *,
    project_id: UUID,
    user: User,
    section_id: UUID,
    asset_type: str,
    asset_stable_id: str,
) -> dict[str, Any]:
    project = await get_owned_project(db, project_id=project_id, user=user)
    if asset_type not in {"figure", "table"}:
        raise ValidationAppError("asset_type must be figure or table")

    caption = ""
    source = ""
    provenance = ""
    alt_text = ""
    number = 0
    title = ""
    node: dict[str, Any]

    if asset_type == "figure":
        fig = await db.scalar(
            select(Figure).where(
                Figure.project_id == project_id,
                Figure.stable_id == asset_stable_id,
            )
        )
        if fig is None:
            raise NotFoundError("Figure not found")
        caption = fig.caption
        source = fig.source_reference
        provenance = fig.provenance_label
        alt_text = fig.alt_text
        number = fig.number
        title = fig.title
        cross_ref = f"Fig. {number}"
        node = {
            "type": "figurePlaceholder",
            "attrs": {
                "caption": f"{cross_ref}: {caption}",
                "stableId": fig.stable_id,
                "number": number,
                "source": source,
                "provenance": provenance,
                "altText": alt_text,
                "title": title,
                "isConceptual": fig.is_conceptual,
            },
        }
    else:
        table = await db.scalar(
            select(Table).where(
                Table.project_id == project_id,
                Table.stable_id == asset_stable_id,
            )
        )
        if table is None:
            raise NotFoundError("Table not found")
        caption = table.caption
        source = table.source_reference
        provenance = table.provenance_label
        alt_text = table.title
        number = table.number
        title = table.title
        cross_ref = f"Table {number}"
        # encode as simpleTable text content with metadata attrs via paragraph + table
        header = " | ".join(str(h) for h in table.headers)
        body = "\n".join(" | ".join(str(c) for c in row) for row in table.rows[:20])
        node = {
            "type": "simpleTable",
            "attrs": {
                "stableId": table.stable_id,
                "number": number,
                "caption": f"{cross_ref}: {caption}",
                "source": source,
                "provenance": provenance,
                "title": title,
            },
            "content": [
                {
                    "type": "text",
                    "text": (f"{cross_ref}: {title}\n{header}\n{body}\n[{provenance}]"),
                }
            ],
        }

    manuscript = await manuscript_service.get_manuscript_for_project(db, project=project)
    section = next((s for s in manuscript.sections if s.id == section_id), None)
    if section is None:
        raise NotFoundError("Section not found")

    content = dict(section.structured_content or {"type": "doc", "content": []})
    blocks = list(content.get("content") or [])
    blocks.append(node)
    # also append a short cross-reference paragraph
    blocks.append(
        {
            "type": "paragraph",
            "content": [
                {
                    "type": "text",
                    "text": f"See {cross_ref} ({provenance}).",
                }
            ],
        }
    )
    content["content"] = blocks
    content["plain_text"] = (section.plain_text or "") + f"\nSee {cross_ref}."

    await manuscript_service.save_section(
        db,
        project=project,
        user=user,
        section_id=section.id,
        structured_content=content,
        expected_revision=section.revision_number,
        create_snapshot=False,
        author_type=VersionAuthorType.USER,
    )

    existing = await db.scalar(
        select(ManuscriptAssetRef).where(
            ManuscriptAssetRef.project_id == project_id,
            ManuscriptAssetRef.asset_type == asset_type,
            ManuscriptAssetRef.asset_stable_id == asset_stable_id,
            ManuscriptAssetRef.section_id == section_id,
        )
    )
    if existing is None:
        ref = ManuscriptAssetRef(
            project_id=project_id,
            section_id=section_id,
            asset_type=asset_type,
            asset_stable_id=asset_stable_id,
            cross_ref=cross_ref,
            caption=caption,
            source=source,
            provenance=provenance,
            alt_text=alt_text,
        )
        db.add(ref)
        await db.flush()
    else:
        ref = existing

    return {
        "section_id": str(section_id),
        "asset_type": asset_type,
        "asset_stable_id": asset_stable_id,
        "cross_ref": cross_ref,
        "caption": caption,
        "source": source,
        "provenance": provenance,
        "alt_text": alt_text,
        "ref_id": str(ref.id),
    }


async def list_asset_refs(db: AsyncSession, *, project_id: UUID) -> list[dict[str, Any]]:
    rows = await db.scalars(
        select(ManuscriptAssetRef).where(ManuscriptAssetRef.project_id == project_id)
    )
    return [
        {
            "id": str(r.id),
            "section_id": str(r.section_id),
            "asset_type": r.asset_type,
            "asset_stable_id": r.asset_stable_id,
            "cross_ref": r.cross_ref,
            "caption": r.caption,
            "source": r.source,
            "provenance": r.provenance,
            "alt_text": r.alt_text,
        }
        for r in rows.all()
    ]
