"""Provider-independent LLM client with retry, timeout, circuit breaker, cancel."""

from __future__ import annotations

import asyncio
from typing import Any

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.services.ai.base import LLMCompletionRequest, LLMCompletionResult, LLMProvider
from app.services.ai.circuit_breaker import CircuitBreaker

logger = get_logger(__name__)


class LLMClient:
    def __init__(
        self,
        provider: LLMProvider,
        settings: Settings | None = None,
        circuit: CircuitBreaker | None = None,
    ) -> None:
        self.provider = provider
        self.settings = settings or get_settings()
        self.circuit = circuit or CircuitBreaker(
            failure_threshold=self.settings.llm_circuit_failure_threshold,
            reset_seconds=float(self.settings.llm_circuit_reset_seconds),
        )
        self._semaphore = asyncio.Semaphore(self.settings.llm_max_concurrency)

    async def complete(
        self,
        request: LLMCompletionRequest,
        *,
        cancel_event: asyncio.Event | None = None,
    ) -> LLMCompletionResult:
        if not self.circuit.allow():
            raise AppError(
                "AI provider circuit open",
                code="ai_circuit_open",
                status_code=503,
                details={"provider": self.provider.name},
            )

        last_error: Exception | None = None
        attempts = self.settings.llm_max_retries + 1
        async with self._semaphore:
            for attempt in range(attempts):
                if cancel_event is not None and cancel_event.is_set():
                    raise AppError(
                        "AI generation cancelled",
                        code="ai_cancelled",
                        status_code=499,
                    )
                try:
                    result = await asyncio.wait_for(
                        self.provider.complete(request, cancel_event=cancel_event),
                        timeout=self.settings.llm_timeout_seconds,
                    )
                    self.circuit.record_success()
                    logger.info(
                        "llm_complete",
                        provider=self.provider.name,
                        model=result.model,
                        attempt=attempt + 1,
                        usage=result.usage,
                        # Never log prompt content by default
                        logged_prompt=bool(self.settings.ai_log_prompt_text),
                    )
                    return result
                except TimeoutError as exc:
                    last_error = exc
                    self.circuit.record_failure()
                    logger.warning(
                        "llm_timeout",
                        provider=self.provider.name,
                        attempt=attempt + 1,
                    )
                except AppError as exc:
                    if exc.code == "ai_cancelled":
                        raise
                    last_error = exc
                    self.circuit.record_failure()
                    if exc.status_code < 500:
                        raise
                except Exception as exc:
                    last_error = exc
                    self.circuit.record_failure()
                    logger.warning(
                        "llm_error",
                        provider=self.provider.name,
                        attempt=attempt + 1,
                        error_type=type(exc).__name__,
                    )
                if attempt + 1 < attempts:
                    await asyncio.sleep(0.25 * (2**attempt))

        raise AppError(
            "AI provider unavailable",
            code="ai_unavailable",
            status_code=503,
            details={
                "provider": self.provider.name,
                "error": type(last_error).__name__ if last_error else "unknown",
            },
        )

    async def health_check(self) -> dict[str, Any]:
        ok = False
        try:
            ok = await self.provider.health_check()
        except Exception:
            ok = False
        return {
            "provider": self.provider.name,
            "healthy": ok,
            "circuit_open": not self.circuit.allow(),
            "model": self.settings.llm_model,
        }
