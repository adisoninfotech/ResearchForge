"""Resolve configured LLM / AI providers without binding business logic."""

from __future__ import annotations

from app.core.config import Settings, get_settings
from app.services.ai.base import AIProvider, LLMProvider, OutlineResult
from app.services.ai.client import LLMClient
from app.services.ai.fake import FakeAIProvider
from app.services.ai.openai_compatible import OpenAICompatibleProvider

_fake_singleton: FakeAIProvider | None = None


def get_fake_provider() -> FakeAIProvider:
    global _fake_singleton
    if _fake_singleton is None:
        _fake_singleton = FakeAIProvider()
    return _fake_singleton


def reset_fake_provider() -> FakeAIProvider:
    global _fake_singleton
    _fake_singleton = FakeAIProvider()
    return _fake_singleton


def get_llm_provider(settings: Settings | None = None) -> LLMProvider:
    settings = settings or get_settings()
    provider = settings.ai_provider
    if settings.app_env == "test" or provider == "fake":
        return get_fake_provider()
    if provider in {"openai_compatible", "vllm"}:
        return OpenAICompatibleProvider(settings)
    return get_fake_provider()


def get_llm_client(settings: Settings | None = None) -> LLMClient:
    settings = settings or get_settings()
    return LLMClient(get_llm_provider(settings), settings)


def get_ai_provider(settings: Settings | None = None) -> AIProvider:
    """Legacy outline-facing provider for guest preview compatibility."""
    settings = settings or get_settings()
    if settings.app_env == "test" or settings.ai_provider == "fake":
        return get_fake_provider()
    return _LegacyOutlineAdapter(settings)


class _LegacyOutlineAdapter:
    name = "openai_compatible"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def generate_outline(
        self,
        *,
        title: str,
        research_area: str,
        research_problem: str,
        proposed_contribution: str,
        target_format: str,
        max_sections: int,
    ) -> OutlineResult:
        from app.models.enums import AIOperation
        from app.services.ai.orchestrator import run_structured_operation

        client = get_llm_client(self.settings)
        result = await run_structured_operation(
            client=client,
            operation=AIOperation.OUTLINE,
            variables={
                "title": title,
                "research_field": research_area,
                "research_problem": research_problem,
                "proposed_contribution": proposed_contribution,
                "target_format": target_format,
                "max_sections": max_sections,
                "contains_synthetic_data": False,
                "constraints": [],
            },
            training_eligible=False,
            settings=self.settings,
        )
        data = result.payload
        return OutlineResult.model_validate(
            {
                **data,
                "provider": result.provenance.provider,
                "model": result.provenance.model,
                "is_preview": True,
            }
        )
