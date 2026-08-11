"""Public contact form.

Unauthenticated by design — it is the route for people who do not have an
account. That makes it the most abusable surface in the API, so it carries a
rate limit, a honeypot, and hard caps on attachment size and type.
"""

from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, Depends, File, UploadFile

from app.api.deps import AppSettings, enforce_rate_limit
from app.core.exceptions import AppError, ValidationAppError
from app.core.logging import get_logger
from app.schemas.contact import AttachmentResponse, ContactRequest, ContactResponse
from app.services.email import send_contact_message
from app.services.storage import presigned_get_url, put_object_trusted

logger = get_logger(__name__)

router = APIRouter(prefix="/contact", tags=["contact"])

# Deliberately narrower than the app-wide upload allowlist. This endpoint takes
# files from anonymous strangers, so only the two document types a CV or
# supporting document would realistically use are accepted.
ATTACHMENT_TYPES = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/msword": ".doc",
}
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024  # 10 MB
ATTACHMENT_PREFIX = "contact/"
# Seven days: long enough to read the enquiry after a weekend.
ATTACHMENT_URL_TTL_SECONDS = 7 * 24 * 3600

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_filename(raw: str | None) -> str:
    """Strip anything that could traverse paths or confuse a mail client."""
    name = (raw or "attachment").rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    name = _SAFE_NAME.sub("_", name).strip("._") or "attachment"
    return name[:120]


@router.post(
    "/attachment",
    response_model=AttachmentResponse,
    dependencies=[Depends(enforce_rate_limit)],
)
async def upload_attachment(
    settings: AppSettings, file: UploadFile = File(...)
) -> AttachmentResponse:
    """Accept a single PDF or Word document and stash it in object storage.

    Returns a storage key rather than a URL — the key is echoed back on submit,
    and only then turned into a time-limited link inside the email. That stops
    the endpoint being used as an open file host with public URLs.
    """
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type not in ATTACHMENT_TYPES:
        raise ValidationAppError("Only PDF and Word documents can be attached")

    body = await file.read()
    if not body:
        raise ValidationAppError("That file is empty")
    if len(body) > MAX_ATTACHMENT_BYTES:
        raise ValidationAppError("Attachments must be 10 MB or smaller")

    filename = _safe_filename(file.filename)
    key = f"{ATTACHMENT_PREFIX}{uuid.uuid4().hex}/{filename}"

    # put_object_trusted skips the app-wide content-type allowlist, which is
    # tuned for project evidence. The stricter check above has already run.
    put_object_trusted(key=key, body=body, content_type=content_type)
    logger.info("contact_attachment_stored", size_bytes=len(body), content_type=content_type)

    return AttachmentResponse(key=key, filename=filename, size_bytes=len(body))


@router.post(
    "",
    response_model=ContactResponse,
    dependencies=[Depends(enforce_rate_limit)],
)
async def submit_contact(payload: ContactRequest, settings: AppSettings) -> ContactResponse:
    # Honeypot: a field hidden from humans by CSS. Anything that fills it is a
    # bot, so return the normal success response rather than an error — telling
    # a scraper it was detected just teaches it to avoid the trap.
    if payload.website:
        logger.info("contact_honeypot_triggered")
        return ContactResponse(status="sent")

    message = payload.message
    key = payload.attachment_key
    if key:
        # Never trust a client-supplied storage key: without this, a caller
        # could name any object in the bucket and have us mail them a signed
        # URL for it.
        if not key.startswith(ATTACHMENT_PREFIX) or ".." in key:
            raise ValidationAppError("Invalid attachment reference")
        link = presigned_get_url(key, expires_in=ATTACHMENT_URL_TTL_SECONDS)
        name = _safe_filename(payload.attachment_name)
        message = f"{message}\n\n---\nAttachment: {name}\n{link}\n(link valid for 7 days)"

    try:
        await send_contact_message(
            name=payload.name,
            email=payload.email,
            message=message,
            settings=settings,
        )
    except Exception as exc:
        logger.error("contact_send_failed", error=str(exc))
        raise AppError(
            "We could not send your message. Please email us directly.",
            code="contact_send_failed",
            status_code=503,
        ) from exc

    return ContactResponse(status="sent")
