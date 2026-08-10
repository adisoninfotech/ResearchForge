"""Structured AI operation runner with validation and bounded repair."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.models.enums import AIOperation
from app.observability.metrics import AI_LATENCY, AI_REQUESTS, Timer, metrics
from app.observability.tracing import span
from app.services.ai.base import ChatMessage, LLMCompletionRequest
from app.services.ai.client import LLMClient
from app.services.ai.openai_compatible import extract_json
from app.services.ai.prompts import PromptTemplate, load_prompt
from app.services.ai.schemas import (
    AbstractResult,
    ConsistencyReviewResult,
    LimitationsResult,
    MissingInformationResult,
    OutlineResult,
    OutlineSection,
    Provenance,
    SectionDraftResult,
    SectionQuestionsResult,
    TextTransformResult,
)
from app.services.prompt_injection import allowed_evidence_ids, filter_citation_ids

logger = get_logger(__name__)
T = TypeVar("T", bound=BaseModel)

OPERATION_PROMPT: dict[AIOperation, str] = {
    AIOperation.OUTLINE: "outline",
    AIOperation.SECTION_QUESTIONS: "section_questions",
    AIOperation.DRAFT_SECTION: "draft_section",
    AIOperation.REWRITE_CLARITY: "rewrite_clarity",
    AIOperation.SHORTEN: "shorten",
    AIOperation.EXPAND_WITH_EVIDENCE: "expand_with_evidence",
    AIOperation.MISSING_INFORMATION: "missing_information",
    AIOperation.GENERATE_ABSTRACT: "generate_abstract",
    AIOperation.GENERATE_LIMITATIONS: "generate_limitations",
    AIOperation.CONSISTENCY_REVIEW: "consistency_review",
}

OPERATION_MODEL: dict[AIOperation, type[BaseModel]] = {
    AIOperation.OUTLINE: OutlineResult,
    AIOperation.SECTION_QUESTIONS: SectionQuestionsResult,
    AIOperation.DRAFT_SECTION: SectionDraftResult,
    AIOperation.REWRITE_CLARITY: TextTransformResult,
    AIOperation.SHORTEN: TextTransformResult,
    AIOperation.EXPAND_WITH_EVIDENCE: TextTransformResult,
    AIOperation.MISSING_INFORMATION: MissingInformationResult,
    AIOperation.GENERATE_ABSTRACT: AbstractResult,
    AIOperation.GENERATE_LIMITATIONS: LimitationsResult,
    AIOperation.CONSISTENCY_REVIEW: ConsistencyReviewResult,
}


@dataclass
class StructuredRunResult:
    operation: AIOperation
    payload: dict[str, Any]
    model_instance: BaseModel
    provenance: Provenance
    raw_content: str
    repaired: bool = False


def _provenance(
    template: PromptTemplate,
    *,
    model: str,
    provider: str,
    params: dict[str, Any],
    evidence_ids: list[str],
    training_eligible: bool,
) -> Provenance:
    return Provenance(
        prompt_template_id=template.id,
        prompt_version=template.version,
        model=model,
        provider=provider,
        generation_parameters=params,
        created_at=datetime.now(UTC).isoformat(),
        evidence_ids=evidence_ids,
        training_eligible=training_eligible,
    )


def _scrub_citations(payload: dict[str, Any], allowed: set[str]) -> dict[str, Any]:
    """Drop model-claimed evidence IDs that were not supplied server-side."""

    def scrub(value: Any) -> Any:
        if isinstance(value, dict):
            out = {k: scrub(v) for k, v in value.items()}
            if "evidence_ids" in out and isinstance(out["evidence_ids"], list):
                out["evidence_ids"] = filter_citation_ids(
                    [str(x) for x in out["evidence_ids"]], allowed
                )
            if "evidence_references" in out and isinstance(out["evidence_references"], list):
                out["evidence_references"] = filter_citation_ids(
                    [str(x) for x in out["evidence_references"]], allowed
                )
            return out
        if isinstance(value, list):
            return [scrub(item) for item in value]
        return value

    result = scrub(payload)
    assert isinstance(result, dict)
    return result


def _validate_operation(operation: AIOperation, data: dict[str, Any]) -> BaseModel:
    model_cls = OPERATION_MODEL[operation]
    if operation == AIOperation.OUTLINE:
        # OutlineResult requires provider/model; inject placeholders then overwrite
        data = {
            **data,
            "provider": data.get("provider") or "pending",
            "model": data.get("model") or "pending",
            "sections": data.get("sections") or [],
        }
        # Validate via a lighter intermediate then wrap
        sections = [
            OutlineSection(title=str(s.get("title", "")), summary=str(s.get("summary", "")))
            for s in data.get("sections", [])
            if isinstance(s, dict)
        ]
        return OutlineResult(
            title=str(data.get("title") or "Untitled"),
            sections=sections,
            provider=str(data["provider"]),
            model=str(data["model"]),
            is_preview=bool(data.get("is_preview", False)),
        )
    return model_cls.model_validate(data)


async def run_structured_operation(
    *,
    client: LLMClient,
    operation: AIOperation,
    variables: dict[str, Any],
    training_eligible: bool = False,
    cancel_event: asyncio.Event | None = None,
    settings: Settings | None = None,
) -> StructuredRunResult:
    settings = settings or get_settings()
    template = load_prompt(OPERATION_PROMPT[operation])
    evidence = variables.get("evidence_passages") or []
    evidence_ids: list[str] = []
    if isinstance(evidence, list):
        evidence_ids = sorted(allowed_evidence_ids(evidence))

    params: dict[str, Any] = {
        "temperature": 0.2,
        "max_tokens": int(settings.llm_max_output_tokens),
    }
    messages = [
        ChatMessage(role="system", content=template.render_system()),
        ChatMessage(role="user", content=template.render_user(variables)),
    ]
    request = LLMCompletionRequest(
        messages=messages,
        max_tokens=int(params["max_tokens"]),
        temperature=float(params["temperature"]),
    )

    labels = {"operation": operation.value}
    with span("ai.structured_operation", operation=operation.value), Timer(AI_LATENCY, labels):
        try:
            completion = await client.complete(request, cancel_event=cancel_event)
            metrics.incr(AI_REQUESTS, labels={**labels, "status": "ok"})
        except Exception:
            metrics.incr(AI_REQUESTS, labels={**labels, "status": "error"})
            raise
        parsed = extract_json(completion.content)
        repaired = False
        try:
            model_instance = _validate_operation(operation, parsed)
        except ValidationError as exc:
            if settings.ai_repair_attempts < 1:
                logger.warning(
                    "ai_invalid_structured_output",
                    operation=operation.value,
                    error_count=exc.error_count(),
                )
                raise AppError(
                    "AI returned invalid structured output",
                    code="ai_invalid_output",
                    status_code=502,
                    details={"operation": operation.value, "errors": exc.errors()},
                ) from exc

            repair_messages = [
                *messages,
                ChatMessage(role="assistant", content=completion.content),
                ChatMessage(
                    role="user",
                    content=(
                        "Your previous response was invalid JSON for the schema. "
                        "Return corrected JSON only. Validation errors: "
                        f"{exc.errors()}"
                    ),
                ),
            ]
            completion = await client.complete(
                LLMCompletionRequest(
                    messages=repair_messages,
                    max_tokens=int(params["max_tokens"]),
                    temperature=0.0,
                ),
                cancel_event=cancel_event,
            )
            parsed = extract_json(completion.content)
            repaired = True
            try:
                model_instance = _validate_operation(operation, parsed)
            except ValidationError as exc2:
                logger.warning(
                    "ai_invalid_structured_output_after_repair",
                    operation=operation.value,
                    error_count=exc2.error_count(),
                )
                raise AppError(
                    "AI returned invalid structured output after repair",
                    code="ai_invalid_output",
                    status_code=502,
                    details={"operation": operation.value, "errors": exc2.errors()},
                ) from exc2

    allowed = set(evidence_ids)
    provenance = _provenance(
        template,
        model=completion.model,
        provider=completion.provider,
        params=params,
        evidence_ids=evidence_ids,
        training_eligible=training_eligible,
    )

    # Attach provenance where supported
    payload = _scrub_citations(model_instance.model_dump(), allowed)
    if operation == AIOperation.OUTLINE and isinstance(model_instance, OutlineResult):
        model_instance = OutlineResult(
            title=model_instance.title,
            sections=model_instance.sections,
            provider=completion.provider,
            model=completion.model,
            is_preview=model_instance.is_preview,
            disclaimer=model_instance.disclaimer,
        )
        payload = model_instance.model_dump()
    elif hasattr(model_instance, "provenance"):
        payload["provenance"] = provenance.model_dump()
        model_instance = OPERATION_MODEL[operation].model_validate(payload)
    else:
        try:
            model_instance = OPERATION_MODEL[operation].model_validate(payload)
        except ValidationError:
            pass

    if operation == AIOperation.DRAFT_SECTION and isinstance(model_instance, SectionDraftResult):
        plain = " ".join(b.text for b in model_instance.content_blocks if b.text).strip()
        model_instance = model_instance.model_copy(update={"plain_text": plain})
        payload = _scrub_citations(model_instance.model_dump(), allowed)

    return StructuredRunResult(
        operation=operation,
        payload=payload,
        model_instance=model_instance,
        provenance=provenance,
        raw_content=completion.content if settings.ai_log_prompt_text else "",
        repaired=repaired,
    )
