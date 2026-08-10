"""Privacy-conscious product analytics — never store manuscript content."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utcnow
from app.models.engagement import AnalyticsEvent
from app.models.enums import AnalyticsEventType

# Property keys that must never appear in analytics payloads
FORBIDDEN_PROPERTY_KEYS = {
    "title",
    "manuscript",
    "manuscript_text",
    "text",
    "content",
    "plain_text",
    "filename",
    "file_name",
    "original_filename",
    "citation",
    "citations",
    "cite_key",
    "dataset_values",
    "rows",
    "values",
    "abstract",
    "section_text",
}


def sanitize_properties(properties: dict[str, Any] | None) -> dict[str, Any]:
    if not properties:
        return {}
    clean: dict[str, Any] = {}
    for key, val in properties.items():
        lk = key.lower()
        if lk in FORBIDDEN_PROPERTY_KEYS or any(
            bad in lk for bad in ("title", "filename", "text", "content", "citation")
        ):
            continue
        if isinstance(val, (str, bytes)):
            # Opaque IDs / enums only — reject free text longer than short codes
            if len(str(val)) > 64:
                continue
            clean[key] = str(val)
        elif isinstance(val, (int, float, bool)) or val is None:
            clean[key] = val
        elif isinstance(val, list) and all(isinstance(x, (int, float, bool)) for x in val):
            clean[key] = val
    return clean


async def track(
    db: AsyncSession,
    *,
    event_type: AnalyticsEventType | str,
    user_id: UUID | None = None,
    project_id: UUID | None = None,
    properties: dict[str, Any] | None = None,
) -> AnalyticsEvent:
    if isinstance(event_type, str):
        event_type = AnalyticsEventType(event_type)
    event = AnalyticsEvent(
        user_id=user_id,
        project_id=project_id,
        event_type=event_type,
        properties=sanitize_properties(properties),
        created_at=utcnow(),
    )
    db.add(event)
    await db.flush()
    return event
