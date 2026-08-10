"""Error reporting abstraction — swap for Sentry/etc. in production."""

from __future__ import annotations

from typing import Any, Protocol

from app.core.logging import get_logger
from app.core.redaction import redact_value

logger = get_logger(__name__)


class ErrorReporter(Protocol):
    def capture_exception(
        self, exc: BaseException, *, context: dict[str, Any] | None = None
    ) -> None: ...

    def capture_message(self, message: str, *, level: str = "error") -> None: ...


class LoggingErrorReporter:
    """Default reporter: structured logs only (no manuscript content)."""

    def capture_exception(
        self, exc: BaseException, *, context: dict[str, Any] | None = None
    ) -> None:
        safe = {k: redact_value(str(k), v) for k, v in (context or {}).items()}
        logger.error(
            "captured_exception",
            error_type=type(exc).__name__,
            error_message=str(exc)[:200],
            **safe,
        )

    def capture_message(self, message: str, *, level: str = "error") -> None:
        log = getattr(logger, level, logger.error)
        log("captured_message", message=message[:500])


_reporter: ErrorReporter = LoggingErrorReporter()


def get_error_reporter() -> ErrorReporter:
    return _reporter


def set_error_reporter(reporter: ErrorReporter) -> None:
    global _reporter
    _reporter = reporter
