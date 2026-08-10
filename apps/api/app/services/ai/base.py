"""Provider-independent AI protocols and shared outline types."""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field


class OutlineSection(BaseModel):
    title: str
    summary: str = ""


class OutlineResult(BaseModel):
    title: str
    sections: list[OutlineSection] = Field(default_factory=list)
    provider: str
    model: str
    is_preview: bool = True
    disclaimer: str = "Guest preview only. Sign in to generate full sections and save your project."


class ChatMessage(BaseModel):
    role: str
    content: str


class LLMCompletionRequest(BaseModel):
    messages: list[ChatMessage]
    max_tokens: int | None = None
    temperature: float = 0.2
    response_format: dict[str, Any] | None = None
    model: str | None = None


class LLMCompletionResult(BaseModel):
    content: str
    model: str
    provider: str
    finish_reason: str | None = None
    usage: dict[str, int] = Field(default_factory=dict)


class LLMProvider(Protocol):
    """Low-level chat/completions adapter — no business logic."""

    name: str

    async def complete(
        self,
        request: LLMCompletionRequest,
        *,
        cancel_event: Any | None = None,
    ) -> LLMCompletionResult: ...

    async def health_check(self) -> bool: ...


class AIProvider(Protocol):
    """Legacy outline-facing protocol retained for guest preview compatibility."""

    name: str

    async def generate_outline(
        self,
        *,
        title: str,
        research_area: str,
        research_problem: str,
        proposed_contribution: str,
        target_format: str,
        max_sections: int,
    ) -> OutlineResult: ...
