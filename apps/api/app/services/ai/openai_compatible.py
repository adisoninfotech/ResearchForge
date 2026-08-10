"""OpenAI-compatible / vLLM chat completions adapter."""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.core.config import Settings
from app.core.exceptions import AppError
from app.core.security_hardening import assert_url_safe_for_outbound
from app.services.ai.base import LLMCompletionRequest, LLMCompletionResult


class OpenAICompatibleProvider:
    """Low-level LLM adapter — no business orchestration."""

    name = "openai_compatible"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def complete(
        self,
        request: LLMCompletionRequest,
        *,
        cancel_event: Any | None = None,
    ) -> LLMCompletionResult:
        if cancel_event is not None and cancel_event.is_set():
            raise AppError("AI generation cancelled", code="ai_cancelled", status_code=499)

        model = request.model or self.settings.llm_model
        payload: dict[str, Any] = {
            "model": model,
            "messages": [m.model_dump() for m in request.messages],
            "max_tokens": request.max_tokens or self.settings.llm_max_output_tokens,
            "temperature": request.temperature,
        }
        if request.response_format:
            payload["response_format"] = request.response_format

        headers = {
            "Authorization": f"Bearer {self.settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        assert_url_safe_for_outbound(self.settings.llm_base_url, settings=self.settings)
        url = f"{self.settings.llm_base_url.rstrip('/')}/chat/completions"
        try:
            async with httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds) as client:
                response = await client.post(url, headers=headers, json=payload)
                if cancel_event is not None and cancel_event.is_set():
                    raise AppError(
                        "AI generation cancelled",
                        code="ai_cancelled",
                        status_code=499,
                    )
                response.raise_for_status()
                data: dict[str, Any] = response.json()
        except AppError:
            raise
        except httpx.HTTPError as exc:
            raise AppError(
                "AI provider unavailable",
                code="ai_unavailable",
                status_code=503,
                details={"provider": self.name},
            ) from exc

        choice = (data.get("choices") or [{}])[0]
        content = choice.get("message", {}).get("content", "") or ""
        usage_raw = data.get("usage") or {}
        usage = {
            "prompt_tokens": int(usage_raw.get("prompt_tokens") or 0),
            "completion_tokens": int(usage_raw.get("completion_tokens") or 0),
            "total_tokens": int(usage_raw.get("total_tokens") or 0),
        }
        return LLMCompletionResult(
            content=content,
            model=str(data.get("model") or model),
            provider=self.name,
            finish_reason=choice.get("finish_reason"),
            usage=usage,
        )

    async def health_check(self) -> bool:
        url = f"{self.settings.llm_base_url.rstrip('/')}/models"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {self.settings.llm_api_key}"},
                )
                return response.status_code < 500
        except httpx.HTTPError:
            return False


def extract_json(content: str) -> dict[str, Any]:
    content = content.strip()
    if content.startswith("```"):
        lines = content.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines).strip()
    try:
        value = json.loads(content)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start >= 0 and end > start:
            try:
                value = json.loads(content[start : end + 1])
                if isinstance(value, dict):
                    return value
            except json.JSONDecodeError:
                return {}
    return {}
