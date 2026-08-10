"""Unit tests for upload validation."""

from __future__ import annotations

import pytest
from app.core.config import Settings
from app.services.storage import validate_upload


@pytest.mark.unit
def test_reject_oversized_upload() -> None:
    settings = Settings(
        secret_key="x" * 16,
        csrf_secret="y" * 16,
        max_upload_bytes=100,
    )
    with pytest.raises(ValueError, match="exceeds"):
        validate_upload(content_type="application/pdf", size_bytes=101, settings=settings)


@pytest.mark.unit
def test_reject_disallowed_type() -> None:
    settings = Settings(secret_key="x" * 16, csrf_secret="y" * 16)
    with pytest.raises(ValueError, match="not allowed"):
        validate_upload(content_type="application/x-msdownload", size_bytes=10, settings=settings)
