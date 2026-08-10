"""Slug helpers for projects."""

from __future__ import annotations

import re
import uuid


def slugify(title: str, *, suffix: str | None = None) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    base = (base or "project")[:80]
    ending = suffix or uuid.uuid4().hex[:8]
    return f"{base}-{ending}"
