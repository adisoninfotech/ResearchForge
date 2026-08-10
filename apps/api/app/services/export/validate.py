"""Pre-export validation — warnings may be acknowledged; critical issues block."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from app.models.enums import ExportValidationSeverity
from app.services.export.canonical import CanonicalManuscript


@dataclass
class ValidationIssue:
    code: str
    severity: str
    message: str
    path: str | None = None
    acknowledgeable: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_canonical(
    manuscript: CanonicalManuscript,
    *,
    unresolved_similarity: int = 0,
    require_statements: bool = True,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    fm = manuscript.front_matter

    if not fm.title.strip():
        issues.append(
            ValidationIssue(
                code="missing_title",
                severity=ExportValidationSeverity.CRITICAL.value,
                message="Manuscript title is missing.",
                path="front_matter.title",
                acknowledgeable=False,
            )
        )

    if not fm.authors:
        issues.append(
            ValidationIssue(
                code="missing_author_metadata",
                severity=ExportValidationSeverity.CRITICAL.value,
                message="At least one author is required before export.",
                path="front_matter.authors",
                acknowledgeable=False,
            )
        )

    cited_keys: set[str] = set()
    for section in manuscript.sections:
        for block in section.blocks:
            cited_keys.update(block.cite_keys)
            for xref in block.cross_ref_ids:
                if xref not in manuscript.cross_references and not xref.startswith(
                    ("fig:", "tab:")
                ):
                    # fig:/tab: may still resolve by number
                    pass
                if xref.startswith("fig:"):
                    num = xref.split(":", 1)[1]
                    if not any(str(f.number) == num for f in manuscript.figures):
                        issues.append(
                            ValidationIssue(
                                code="broken_cross_reference",
                                severity=ExportValidationSeverity.CRITICAL.value,
                                message=f"Broken figure cross-reference: {xref}",
                                path=f"sections.{section.id}",
                                acknowledgeable=False,
                            )
                        )
                if xref.startswith("tab:"):
                    num = xref.split(":", 1)[1]
                    if not any(str(t.number) == num for t in manuscript.tables):
                        issues.append(
                            ValidationIssue(
                                code="broken_cross_reference",
                                severity=ExportValidationSeverity.CRITICAL.value,
                                message=f"Broken table cross-reference: {xref}",
                                path=f"sections.{section.id}",
                                acknowledgeable=False,
                            )
                        )

    ref_keys = {r.key for r in manuscript.references}
    for key in cited_keys:
        if key not in ref_keys:
            issues.append(
                ValidationIssue(
                    code="broken_citation",
                    severity=ExportValidationSeverity.CRITICAL.value,
                    message=f"Citation key not found in references: {key}",
                    path=f"citations.{key}",
                    acknowledgeable=False,
                )
            )

    for ref in manuscript.references:
        if ref.verification_status in {"unverified", "needs_correction"}:
            issues.append(
                ValidationIssue(
                    code="unverified_reference",
                    severity=ExportValidationSeverity.WARNING.value,
                    message=f"Reference '{ref.key}' is {ref.verification_status}.",
                    path=f"references.{ref.key}",
                )
            )

    for fig in manuscript.figures:
        if fig.missing_file and not fig.is_conceptual:
            issues.append(
                ValidationIssue(
                    code="missing_figure_file",
                    severity=ExportValidationSeverity.CRITICAL.value,
                    message=f"Figure {fig.number} is missing its image file.",
                    path=f"figures.{fig.id}",
                    acknowledgeable=False,
                )
            )
        if not (fig.caption or "").strip():
            issues.append(
                ValidationIssue(
                    code="missing_caption",
                    severity=ExportValidationSeverity.WARNING.value,
                    message=f"Figure {fig.number} is missing a caption.",
                    path=f"figures.{fig.id}",
                )
            )

    for tab in manuscript.tables:
        if not (tab.caption or "").strip():
            issues.append(
                ValidationIssue(
                    code="missing_caption",
                    severity=ExportValidationSeverity.WARNING.value,
                    message=f"Table {tab.number} is missing a caption.",
                    path=f"tables.{tab.id}",
                )
            )

    # Unsupported / disclosure claims
    disclosures = manuscript.disclosures or {}
    if disclosures.get("contains_synthetic_data") and not disclosures.get(
        "synthetic_disclosed_in_text"
    ):
        issues.append(
            ValidationIssue(
                code="synthetic_data_disclosure",
                severity=ExportValidationSeverity.WARNING.value,
                message=(
                    "Project contains synthetic data; ensure the manuscript discloses this clearly."
                ),
                path="disclosures.synthetic",
            )
        )
    if disclosures.get("contains_simulated_results") and not disclosures.get(
        "simulated_disclosed_in_text"
    ):
        issues.append(
            ValidationIssue(
                code="simulated_result_disclosure",
                severity=ExportValidationSeverity.WARNING.value,
                message=(
                    "Simulated results are present; ensure the manuscript discloses this clearly."
                ),
                path="disclosures.simulated",
            )
        )

    if unresolved_similarity > 0:
        issues.append(
            ValidationIssue(
                code="unresolved_similarity_findings",
                severity=ExportValidationSeverity.WARNING.value,
                message=(
                    f"{unresolved_similarity} similarity finding(s) remain unresolved. "
                    "Human review is recommended before submission."
                ),
                path="similarity",
            )
        )

    if require_statements:
        bm = manuscript.back_matter
        for field, code, label in (
            ("funding", "missing_required_statement", "Funding"),
            ("conflict_of_interest", "missing_required_statement", "Conflict of interest"),
            ("data_availability", "missing_required_statement", "Data availability"),
        ):
            if not getattr(bm, field, "").strip():
                issues.append(
                    ValidationIssue(
                        code=code,
                        severity=ExportValidationSeverity.WARNING.value,
                        message=f"Missing recommended statement: {label}.",
                        path=f"back_matter.{field}",
                    )
                )

    # Overflow heuristics for preview warnings
    for fig in manuscript.figures:
        if len(fig.caption) > 400:
            issues.append(
                ValidationIssue(
                    code="figure_overflow_warning",
                    severity=ExportValidationSeverity.WARNING.value,
                    message=f"Figure {fig.number} caption may overflow the page layout.",
                    path=f"figures.{fig.id}",
                )
            )

    return issues


def partition_issues(
    issues: list[ValidationIssue],
    acknowledged: set[str],
) -> tuple[list[ValidationIssue], list[ValidationIssue], bool]:
    """Return (blocking, remaining_warnings, can_proceed)."""
    blocking: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []
    for issue in issues:
        if issue.severity == ExportValidationSeverity.CRITICAL.value:
            blocking.append(issue)
        elif issue.code in acknowledged or issue.message in acknowledged:
            continue
        else:
            warnings.append(issue)
    can_proceed = len(blocking) == 0
    return blocking, warnings, can_proceed
