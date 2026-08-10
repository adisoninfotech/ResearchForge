"""Lightweight tracing hooks (OpenTelemetry-ready no-op by default)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from uuid import uuid4

from app.core.logging import get_logger

logger = get_logger(__name__)


@contextmanager
def span(name: str, **attributes: Any) -> Iterator[str]:
    """
    Emit a span around a unit of work.
    Attribute values must never include manuscript content.
    """
    span_id = uuid4().hex[:16]
    safe_attrs = {
        k: v
        for k, v in attributes.items()
        if k
        not in {
            "content",
            "text",
            "prompt",
            "manuscript",
            "evidence",
            "body",
            "raw_content",
        }
    }
    logger.debug("trace_span_start", span=name, span_id=span_id, **safe_attrs)
    try:
        yield span_id
    except Exception as exc:
        logger.debug(
            "trace_span_error",
            span=name,
            span_id=span_id,
            error_type=type(exc).__name__,
        )
        raise
    else:
        logger.debug("trace_span_end", span=name, span_id=span_id)
