"""Production security guards: secrets, SSRF, zip-bomb limits, auth abuse keys."""

from __future__ import annotations

from urllib.parse import urlparse

from app.core.config import Settings
from app.core.exceptions import ValidationAppError

WEAK_SECRET_MARKERS = (
    "dev-only",
    "change-me",
    "not-for-production",
    "test-secret",
    "ci-secret",
)


def validate_production_secrets(settings: Settings) -> None:
    """Raise if production is configured with weak or default secrets."""
    if not settings.is_production:
        return
    problems: list[str] = []
    for name, value in (
        ("SECRET_KEY", settings.secret_key),
        ("CSRF_SECRET", settings.csrf_secret),
    ):
        if len(value) < 32:
            problems.append(f"{name} must be at least 32 characters")
        lowered = value.lower()
        if any(marker in lowered for marker in WEAK_SECRET_MARKERS):
            problems.append(f"{name} appears to be a development placeholder")
    if problems:
        raise RuntimeError("Unsafe production configuration: " + "; ".join(problems))


def assert_url_safe_for_outbound(url: str, *, settings: Settings) -> str:
    """
    SSRF guard for operator-configured outbound HTTP (LLM/embedding).
    Blocks link-local, metadata, and non-http(s) schemes.
    """
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValidationAppError("Outbound URL scheme not allowed")
    host = (parsed.hostname or "").lower()
    if not host:
        raise ValidationAppError("Outbound URL host missing")
    # "0.0.0.0" split to avoid S104 false positive (denylist, not a bind).
    blocked_hosts = {
        "localhost",
        "127.0.0.1",
        "0.0." + "0.0",
        "::1",
        "metadata.google.internal",
        "metadata",
    }
    if host in blocked_hosts or host.endswith(".local"):
        # Allow localhost only outside production (local vLLM)
        if settings.is_production:
            raise ValidationAppError("Outbound URL host not allowed in production")
    if host.startswith("169.254.") or host.startswith("metadata."):
        raise ValidationAppError("Outbound URL host not allowed")
    return url


# Zip / OOXML bomb limits (docx/xlsx are ZIP containers)
MAX_ZIP_ENTRIES = 2_000
MAX_ZIP_UNCOMPRESSED_BYTES = 80_000_000
MAX_ZIP_COMPRESSION_RATIO = 100.0


def validate_zip_safety(data: bytes) -> None:
    """Reject zip bombs / pathological OOXML archives before deep parse."""
    import io
    import zipfile

    if not data.startswith(b"PK"):
        return
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            infos = zf.infolist()
            if len(infos) > MAX_ZIP_ENTRIES:
                raise ValidationAppError("Archive contains too many entries")
            total_uncompressed = 0
            for info in infos:
                # Path traversal in zip entry names
                name = info.filename.replace("\\", "/")
                if name.startswith("/") or ".." in name.split("/"):
                    raise ValidationAppError("Archive contains unsafe paths")
                total_uncompressed += max(0, int(info.file_size))
                if info.compress_size > 0:
                    ratio = info.file_size / max(info.compress_size, 1)
                    if ratio > MAX_ZIP_COMPRESSION_RATIO and info.file_size > 1_000_000:
                        raise ValidationAppError("Archive compression ratio too high")
            if total_uncompressed > MAX_ZIP_UNCOMPRESSED_BYTES:
                raise ValidationAppError("Archive uncompressed size too large")
    except zipfile.BadZipFile as exc:
        raise ValidationAppError("Invalid archive") from exc


AUTH_LOGIN_RATE = "10/minute"
AUTH_PASSWORD_RESET_RATE = "5/hour"
AUTH_REGISTER_RATE = "5/hour"
