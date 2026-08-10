"""Redact secrets and PII-like values from structured logs and telemetry."""

from __future__ import annotations

import re
from collections.abc import MutableMapping
from typing import Any

SENSITIVE_KEY_RE = re.compile(
    r"(password|secret|token|authorization|api[_-]?key|cookie|refresh|csrf|"
    r"credential|private[_-]?key|session)",
    re.IGNORECASE,
)
EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
BEARER_RE = re.compile(r"Bearer\s+\S+", re.IGNORECASE)

# Keys that may carry manuscript content — never log values
CONTENT_KEYS = frozenset(
    {
        "content",
        "plain_text",
        "manuscript",
        "body",
        "prompt",
        "evidence",
        "evidence_passages",
        "chunk_text",
        "text",
        "raw_content",
        "user_template",
    }
)


def redact_string(value: str) -> str:
    value = BEARER_RE.sub("Bearer [REDACTED]", value)
    value = EMAIL_RE.sub("[REDACTED_EMAIL]", value)
    return value


def redact_value(key: str, value: Any) -> Any:
    if key.lower() in CONTENT_KEYS:
        return "[REDACTED_CONTENT]"
    if SENSITIVE_KEY_RE.search(key):
        return "[REDACTED]"
    if isinstance(value, str):
        return redact_string(value)
    if isinstance(value, dict):
        return {k: redact_value(str(k), v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_value(key, item) for item in value[:20]]
    return value


def redact_event_dict(
    _logger: Any, _method_name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """Structlog processor — strip secrets and manuscript content from log events."""
    for key in list(event_dict.keys()):
        event_dict[key] = redact_value(str(key), event_dict[key])
    return event_dict
