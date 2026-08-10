"""Deterministic fake LLM provider for tests and offline development."""

from __future__ import annotations

import json
from typing import Any

from app.services.ai.base import (
    LLMCompletionRequest,
    LLMCompletionResult,
    OutlineResult,
    OutlineSection,
)


class FakeAIProvider:
    """Implements LLMProvider + legacy outline helper."""

    name = "fake"

    def __init__(self) -> None:
        self.force_invalid_json = False
        self.force_timeout = False
        self.calls = 0

    async def complete(
        self,
        request: LLMCompletionRequest,
        *,
        cancel_event: Any | None = None,
    ) -> LLMCompletionResult:
        self.calls += 1
        if cancel_event is not None and cancel_event.is_set():
            from app.core.exceptions import AppError

            raise AppError("AI generation cancelled", code="ai_cancelled", status_code=499)
        if self.force_timeout:
            import asyncio

            await asyncio.sleep(3600)
        if self.force_invalid_json:
            return LLMCompletionResult(
                content="not-json{{{",
                model="fake-deterministic",
                provider=self.name,
            )

        user = " ".join(m.content for m in request.messages if m.role == "user")
        system = " ".join(m.content for m in request.messages if m.role == "system")
        payload = self._payload_for(system=system, user=user)
        return LLMCompletionResult(
            content=json.dumps(payload),
            model="fake-deterministic",
            provider=self.name,
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        )

    async def health_check(self) -> bool:
        return True

    def _payload_for(self, *, system: str, user: str) -> dict[str, Any]:
        lowered = (system + "\n" + user).lower()
        if "paper outline" in lowered or ('"sections"' in lowered and "max sections" in lowered):
            return {
                "title": "Fake Outline",
                "sections": [
                    {"title": "Introduction", "summary": "Motivate the problem."},
                    {"title": "Method", "summary": "Describe the approach."},
                    {"title": "Results", "summary": "Report findings with evidence."},
                ],
            }
        if "clarifying questions" in lowered or (
            "section_type" in lowered and "questions" in lowered
        ):
            return {
                "section_type": "methodology",
                "questions": [
                    "What dataset was used?",
                    "What baselines were compared?",
                    "Was any data synthetic?",
                ],
                "warnings": [],
            }
        if "draft one manuscript section" in lowered or "content_blocks" in lowered:
            evidence_ids = []
            if "ev-" in user:
                # Keep only IDs that appear in the user payload
                for token in user.split():
                    if token.startswith("ev-") or '"id": "ev-' in user:
                        pass
                if '"id":' in user:
                    evidence_ids = ["ev-1"] if "ev-1" in user else []
            claim_warning = None
            supported = bool(evidence_ids)
            if not supported:
                claim_warning = "Unsupported claim: no evidence IDs supplied"
            return {
                "title": "Drafted Section",
                "content_blocks": [
                    {
                        "type": "paragraph",
                        "text": (
                            "This draft uses only supplied project facts and evidence. "
                            "No invented citations are included."
                        ),
                    }
                ],
                "claims": [
                    {
                        "text": "The method addresses the stated research problem.",
                        "evidence_ids": evidence_ids,
                        "supported": supported,
                        "warning": claim_warning,
                    }
                ],
                "evidence_references": evidence_ids,
                "missing_information": (["Provide evaluation metrics"] if not evidence_ids else []),
                "warnings": (
                    [claim_warning]
                    if claim_warning
                    else ["Generated content requires human review"]
                ),
                "suggested_figures": ["Figure: method overview"],
                "suggested_tables": ["Table: dataset summary"],
            }
        if "rewrite selected text for clarity" in lowered:
            return {
                "original_text": "original",
                "transformed_text": "Clearer rewritten text based on the selection.",
                "warnings": [],
                "evidence_references": [],
            }
        if "shorten selected text" in lowered:
            return {
                "original_text": "original",
                "transformed_text": "Shortened text.",
                "warnings": [],
            }
        if "expand selected text using only supplied evidence" in lowered:
            refs = ["ev-1"] if "ev-1" in user else []
            return {
                "original_text": "original",
                "transformed_text": (
                    "Expanded text grounded in supplied evidence."
                    if refs
                    else "Cannot expand without evidence."
                ),
                "evidence_references": refs,
                "warnings": [] if refs else ["No evidence provided; expansion refused"],
            }
        if "missing information needed" in lowered:
            return {
                "questions": [
                    "What is the dataset size?",
                    "Which baselines were used?",
                    "Was statistical validation performed?",
                ],
                "categories": ["dataset", "experiment", "evaluation"],
                "warnings": [],
            }
        if "generate an abstract" in lowered:
            return {
                "abstract": (
                    "We study an evidence-grounded writing workflow. "
                    "Findings are limited to the completed sections provided."
                ),
                "keywords": ["research writing", "evidence"],
                "warnings": [],
            }
        if "generate limitations" in lowered:
            return {
                "limitations": [
                    "Results depend on the completeness of project facts.",
                    "Synthetic data, if used, is not collected experimental evidence.",
                ],
                "ethics_notes": ["Disclose synthetic data usage."],
                "warnings": [],
            }
        if "consistency issues" in lowered:
            return {
                "issues": [
                    {
                        "severity": "warning",
                        "message": (
                            "Contribution statement is thinner than the introduction claims."
                        ),
                        "section_hint": "introduction",
                    }
                ],
                "summary": "Minor consistency gaps detected.",
                "warnings": [],
            }
        return {"warnings": ["Unrecognized fake operation"], "summary": "ok"}

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
        base_sections = [
            OutlineSection(
                title="Introduction",
                summary=f"Motivate the problem in {research_area}.",
            ),
            OutlineSection(
                title="Related Work",
                summary="Summarize prior evidence-grounded approaches.",
            ),
            OutlineSection(
                title="Method",
                summary=proposed_contribution[:240] or "Describe the proposed method.",
            ),
            OutlineSection(
                title="Experiments",
                summary="Report evaluation protocol. Label any synthetic datasets clearly.",
            ),
            OutlineSection(
                title="Results",
                summary="Present findings with figures and tables.",
            ),
            OutlineSection(
                title="Discussion & Conclusion",
                summary=f"Discuss implications for: {research_problem[:160]}",
            ),
        ]
        sections = base_sections[: max(1, max_sections)]
        return OutlineResult(
            title=title or "Untitled manuscript",
            sections=sections,
            provider=self.name,
            model="fake-deterministic",
            is_preview=True,
            disclaimer=(
                f"Guest preview outline for {target_format}. "
                "Sign in to generate full sections and save your project."
            ),
        )
