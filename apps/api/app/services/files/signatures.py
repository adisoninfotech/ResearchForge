"""File signature (magic-byte) validation — never trust client MIME/filename."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.exceptions import ValidationAppError
from app.models.enums import FileKind


@dataclass(frozen=True)
class DetectedFile:
    kind: FileKind
    mime: str
    extension: str
    is_figure: bool = False


_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(name: str) -> str:
    base = name.replace("\\", "/").split("/")[-1]
    base = _SAFE_NAME.sub("_", base).strip("._") or "upload"
    return base[:180]


def detect_file(*, filename: str, content_type: str, data: bytes) -> DetectedFile:
    """Detect kind from signatures first; fall back carefully for text formats."""
    if len(data) == 0:
        raise ValidationAppError("Empty file rejected")

    # Browser MIME is never trusted for classification.
    _ = content_type
    lower_name = filename.lower()

    # PDF
    if data.startswith(b"%PDF-"):
        return DetectedFile(FileKind.PDF, "application/pdf", "pdf")
    # PNG
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return DetectedFile(FileKind.PNG, "image/png", "png", is_figure=True)
    # JPEG
    if data.startswith(b"\xff\xd8\xff"):
        return DetectedFile(FileKind.JPEG, "image/jpeg", "jpeg", is_figure=True)
    # ZIP-based OOXML (docx/xlsx)
    if data.startswith(b"PK\x03\x04"):
        sample = data[:16384]
        if b"word/" in sample or lower_name.endswith(".docx"):
            return DetectedFile(
                FileKind.DOCX,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "docx",
            )
        if b"xl/" in sample or lower_name.endswith(".xlsx"):
            return DetectedFile(
                FileKind.XLSX,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "xlsx",
            )
        raise ValidationAppError("Unrecognized Office Open XML archive")

    # Claimed binary extensions without matching magic bytes are rejected
    if lower_name.endswith((".pdf", ".png", ".jpg", ".jpeg", ".docx", ".xlsx")):
        raise ValidationAppError("File type not allowed or signature mismatch")

    # Textual formats — decode and sniff
    try:
        text = data[:4096].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationAppError("Unsupported or binary file type") from exc

    stripped = text.lstrip()
    if stripped.startswith("@") or (lower_name.endswith(".bib") and "@" in stripped[:200]):
        if "@" in stripped[:200]:
            return DetectedFile(FileKind.BIBTEX, "text/x-bibtex", "bib")
    if stripped.upper().startswith("TY  -") or (
        lower_name.endswith(".ris") and "TY  -" in text.upper()
    ):
        return DetectedFile(FileKind.RIS, "application/x-research-info-systems", "ris")
    if lower_name.endswith(".csv"):
        return DetectedFile(FileKind.CSV, "text/csv", "csv")
    if lower_name.endswith((".md", ".markdown")) or stripped.startswith("#") or "```" in stripped:
        return DetectedFile(FileKind.MARKDOWN, "text/markdown", "md")
    if lower_name.endswith(".txt") or all(32 <= b < 127 or b in (9, 10, 13) for b in data[:512]):
        return DetectedFile(FileKind.TXT, "text/plain", "txt")

    raise ValidationAppError("File type not allowed or signature mismatch")
