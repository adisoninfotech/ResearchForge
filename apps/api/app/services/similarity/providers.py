"""Extensible licensed-provider adapter — no fake publisher coverage claims."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.core.config import Settings, get_settings


@dataclass
class LicensedProviderResult:
    status: str
    sources_checked: list[dict[str, Any]]
    sources_not_checked: list[dict[str, Any]]
    matches: list[dict[str, Any]]
    message: str


class LicensedSimilarityProvider(Protocol):
    name: str

    async def check(
        self,
        *,
        manuscript_text: str,
        metadata: dict[str, Any] | None = None,
    ) -> LicensedProviderResult: ...


class NullLicensedProvider:
    """Default: licensed commercial databases are not configured/used."""

    name = "null"

    async def check(
        self,
        *,
        manuscript_text: str,
        metadata: dict[str, Any] | None = None,
    ) -> LicensedProviderResult:
        _ = manuscript_text, metadata
        return LicensedProviderResult(
            status="not_configured",
            sources_checked=[],
            sources_not_checked=[
                {
                    "label": "Subscription publisher full-text databases",
                    "reason": (
                        "ResearchForge does not scrape or copy subscription-only "
                        "publisher databases. A licensed provider adapter may be "
                        "configured separately; none is active."
                    ),
                }
            ],
            matches=[],
            message="No licensed provider configured; publisher databases were not checked.",
        )


def get_licensed_provider(settings: Settings | None = None) -> LicensedSimilarityProvider:
    settings = settings or get_settings()
    # Future: branch on settings.similarity_licensed_provider
    _ = getattr(settings, "similarity_licensed_provider", "null")
    return NullLicensedProvider()
