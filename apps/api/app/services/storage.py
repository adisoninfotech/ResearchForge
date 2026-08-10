"""S3-compatible object storage (MinIO locally) with in-memory test backend."""

from __future__ import annotations

import uuid
from functools import lru_cache
from typing import Any, Protocol, cast

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import Settings, get_settings

_MEMORY_STORE: dict[str, bytes] = {}
_MEMORY_META: dict[str, str] = {}


class S3ClientProtocol(Protocol):
    def head_bucket(self, *, Bucket: str) -> dict[str, Any]: ...
    def create_bucket(self, *, Bucket: str) -> dict[str, Any]: ...
    def put_object(
        self,
        *,
        Bucket: str,
        Key: str,
        Body: bytes,
        ContentType: str,
    ) -> dict[str, Any]: ...
    def get_object(self, *, Bucket: str, Key: str) -> dict[str, Any]: ...
    def generate_presigned_url(
        self,
        ClientMethod: str,
        Params: dict[str, Any],
        ExpiresIn: int,
    ) -> str: ...
    def list_objects_v2(self, *, Bucket: str, Prefix: str) -> dict[str, Any]: ...
    def delete_objects(self, *, Bucket: str, Delete: dict[str, Any]) -> dict[str, Any]: ...
    def delete_object(self, *, Bucket: str, Key: str) -> dict[str, Any]: ...


def _use_memory(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    return settings.app_env == "test" or settings.s3_endpoint_url.startswith("memory://")


@lru_cache
def get_s3_client() -> S3ClientProtocol:
    settings = get_settings()
    client = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        use_ssl=settings.s3_use_ssl,
    )
    return cast(S3ClientProtocol, client)


def ensure_bucket(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    if _use_memory(settings):
        return
    client = get_s3_client()
    try:
        client.head_bucket(Bucket=settings.s3_bucket)
    except ClientError:
        client.create_bucket(Bucket=settings.s3_bucket)


def check_object_storage() -> bool:
    settings = get_settings()
    if _use_memory(settings):
        return True
    try:
        client = get_s3_client()
        client.head_bucket(Bucket=settings.s3_bucket)
        return True
    except (ClientError, BotoCoreError, Exception):
        return False


def validate_upload(
    *,
    content_type: str,
    size_bytes: int,
    settings: Settings | None = None,
) -> None:
    settings = settings or get_settings()
    if size_bytes > settings.max_upload_bytes:
        raise ValueError(
            f"File exceeds maximum size of {settings.max_upload_bytes} bytes",
        )
    if content_type not in settings.allowed_upload_content_types:
        raise ValueError(f"Content type not allowed: {content_type}")


def put_object(*, key: str, body: bytes, content_type: str) -> dict[str, Any]:
    settings = get_settings()
    validate_upload(content_type=content_type, size_bytes=len(body), settings=settings)
    return put_object_trusted(key=key, body=body, content_type=content_type)


def put_object_trusted(*, key: str, body: bytes, content_type: str) -> dict[str, Any]:
    settings = get_settings()
    if _use_memory(settings):
        _MEMORY_STORE[key] = body
        _MEMORY_META[key] = content_type
        return {"etag": f'"{uuid.uuid4().hex}"', "key": key, "bucket": "memory"}
    client = get_s3_client()
    response = client.put_object(
        Bucket=settings.s3_bucket,
        Key=key,
        Body=body,
        ContentType=content_type,
    )
    return {"etag": response.get("ETag"), "key": key, "bucket": settings.s3_bucket}


def generate_object_key(*, project_id: str, extension: str) -> str:
    ext = extension.lstrip(".").lower() or "bin"
    return f"projects/{project_id}/uploads/{uuid.uuid4().hex}.{ext}"


def get_object_bytes(key: str) -> bytes:
    settings = get_settings()
    if _use_memory(settings):
        if key not in _MEMORY_STORE:
            raise FileNotFoundError(key)
        return _MEMORY_STORE[key]
    client = get_s3_client()
    response = client.get_object(Bucket=settings.s3_bucket, Key=key)
    body = response["Body"].read()
    return cast(bytes, body)


def presigned_get_url(key: str, *, expires_in: int | None = None) -> str:
    settings = get_settings()
    expire = expires_in or settings.upload_signed_url_expire_seconds
    if _use_memory(settings):
        return f"memory://{key}?expires_in={expire}"
    client = get_s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": key},
        ExpiresIn=expire,
    )


def delete_object(key: str) -> bool:
    settings = get_settings()
    if _use_memory(settings):
        _MEMORY_STORE.pop(key, None)
        _MEMORY_META.pop(key, None)
        return True
    try:
        client = get_s3_client()
        client.delete_object(Bucket=settings.s3_bucket, Key=key)
        return True
    except (ClientError, BotoCoreError, Exception):
        return False


def delete_prefix(prefix: str) -> bool:
    """Delete all objects under a key prefix. Returns False if storage is unavailable."""
    settings = get_settings()
    if _use_memory(settings):
        keys = [k for k in list(_MEMORY_STORE) if k.startswith(prefix)]
        for key in keys:
            _MEMORY_STORE.pop(key, None)
            _MEMORY_META.pop(key, None)
        return True
    try:
        client = get_s3_client()
        continuation: str | None = None
        while True:
            kwargs: dict[str, Any] = {"Bucket": settings.s3_bucket, "Prefix": prefix}
            if continuation:
                kwargs["ContinuationToken"] = continuation
            listed = client.list_objects_v2(**kwargs)
            contents = listed.get("Contents") or []
            if contents:
                client.delete_objects(
                    Bucket=settings.s3_bucket,
                    Delete={
                        "Objects": [{"Key": item["Key"]} for item in contents if item.get("Key")]
                    },
                )
            if not listed.get("IsTruncated"):
                break
            continuation = listed.get("NextContinuationToken")
            if not continuation:
                break
        return True
    except (ClientError, BotoCoreError, Exception):
        return False


def clear_memory_store() -> None:
    _MEMORY_STORE.clear()
    _MEMORY_META.clear()
