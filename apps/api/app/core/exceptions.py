"""Domain exceptions and safe API error shapes."""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base application error with a safe client-facing message."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "app_error",
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


class NotFoundError(AppError):
    def __init__(
        self,
        message: str = "Resource not found",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code="not_found", status_code=404, details=details)


class UnauthorizedError(AppError):
    def __init__(
        self,
        message: str = "Authentication required",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code="unauthorized", status_code=401, details=details)


class ForbiddenError(AppError):
    def __init__(
        self,
        message: str = "Forbidden",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code="forbidden", status_code=403, details=details)


class ConflictError(AppError):
    def __init__(
        self,
        message: str = "Conflict",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code="conflict", status_code=409, details=details)


class RateLimitError(AppError):
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code="rate_limited", status_code=429, details=details)


class ValidationAppError(AppError):
    def __init__(
        self,
        message: str = "Validation failed",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code="validation_error", status_code=422, details=details)
