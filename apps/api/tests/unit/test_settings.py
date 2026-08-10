"""Unit tests for settings and rate-limit parsing."""

from __future__ import annotations

import pytest
from app.core.config import Settings
from app.services.rate_limit import parse_rate_limit


@pytest.mark.unit
def test_cors_origins_csv_parsing() -> None:
    settings = Settings(
        cors_origins="http://localhost:3000,http://127.0.0.1:3000",
        secret_key="unit-test-secret",
        csrf_secret="unit-test-csrf",
    )
    assert settings.cors_origins == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


@pytest.mark.unit
def test_parse_rate_limit() -> None:
    rule = parse_rate_limit("100/minute")
    assert rule.limit == 100
    assert rule.window_seconds == 60


@pytest.mark.unit
def test_training_opt_in_default_false() -> None:
    settings = Settings(secret_key="unit-test-secret", csrf_secret="unit-test-csrf")
    assert settings.training_opt_in_default is False
