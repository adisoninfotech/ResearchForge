"""Configurable embedding provider with deterministic fake for tests."""

from __future__ import annotations

import hashlib
import math
from typing import Protocol

import httpx

from app.core.config import Settings, get_settings
from app.core.security_hardening import assert_url_safe_for_outbound


class EmbeddingProvider(Protocol):
    name: str

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class FakeEmbeddingProvider:
    name = "fake"

    def __init__(self, dimensions: int = 64) -> None:
        self.dimensions = dimensions

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [_hash_embed(text, self.dimensions) for text in texts]


class OpenAICompatibleEmbeddingProvider:
    name = "openai_compatible"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def embed(self, texts: list[str]) -> list[list[float]]:
        base = (self.settings.embedding_base_url or self.settings.llm_base_url).rstrip("/")
        assert_url_safe_for_outbound(base, settings=self.settings)
        url = f"{base}/embeddings"
        payload = {"model": self.settings.embedding_model, "input": texts}
        headers = {
            "Authorization": f"Bearer {self.settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        items = sorted(data.get("data") or [], key=lambda x: x.get("index", 0))
        return [list(map(float, item.get("embedding") or [])) for item in items]


def get_embedding_provider(settings: Settings | None = None) -> EmbeddingProvider:
    settings = settings or get_settings()
    use_fake = (
        settings.app_env == "test"
        or settings.ai_provider == "fake"
        or not settings.embedding_base_url
    )
    if use_fake:
        return FakeEmbeddingProvider(settings.embedding_dimensions)
    return OpenAICompatibleEmbeddingProvider(settings)


def _hash_embed(text: str, dimensions: int) -> list[float]:
    vec = [0.0] * dimensions
    tokens = text.lower().split()
    if not tokens:
        return vec
    for token in tokens:
        digest = hashlib.sha256(token.encode()).digest()
        for i in range(dimensions):
            vec[i] += ((digest[i % len(digest)] / 255.0) * 2.0) - 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    n = min(len(a), len(b))
    dot = sum(a[i] * b[i] for i in range(n))
    na = math.sqrt(sum(a[i] * a[i] for i in range(n))) or 1.0
    nb = math.sqrt(sum(b[i] * b[i] for i in range(n))) or 1.0
    return dot / (na * nb)
