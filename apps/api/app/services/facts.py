"""Research completeness facts for projects."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationAppError
from app.core.time import utcnow
from app.models.enums import FactCategory, FactSourceType, FactVerificationStatus
from app.models.project import Project
from app.models.project_fact import ProjectFact
from app.schemas.projects import FactPublic

COMPLETENESS_KEYS: list[tuple[FactCategory, str, str]] = [
    (FactCategory.PROBLEM, "research_problem", "Research problem"),
    (FactCategory.CONTRIBUTION, "novel_contribution", "Novel contribution"),
    (FactCategory.DATASET, "dataset_used", "Dataset used"),
    (FactCategory.DATASET, "dataset_source", "Dataset source"),
    (FactCategory.DATASET, "dataset_size", "Dataset size"),
    (FactCategory.DATASET, "dataset_provenance", "Real / synthetic / simulated"),
    (FactCategory.EXPERIMENT, "experiment_configuration", "Experiment configuration"),
    (FactCategory.EXPERIMENT, "baseline_models", "Baseline models"),
    (FactCategory.EVALUATION, "evaluation_metrics", "Evaluation metrics"),
    (FactCategory.EVALUATION, "statistical_validation", "Statistical validation"),
    (FactCategory.EVALUATION, "limitations", "Limitations"),
    (FactCategory.ETHICS, "ethics_statement", "Ethics statement"),
    (FactCategory.ETHICS, "conflict_of_interest", "Conflict of interest"),
    (FactCategory.ETHICS, "funding", "Funding statement"),
    (FactCategory.ETHICS, "data_availability", "Data availability statement"),
]


def fact_map(facts: list[ProjectFact]) -> dict[str, Any]:
    return {f"{f.category.value}:{f.key}": f.value for f in facts}


async def list_facts(db: AsyncSession, *, project_id: UUID) -> list[ProjectFact]:
    rows = await db.scalars(
        select(ProjectFact)
        .where(ProjectFact.project_id == project_id)
        .order_by(ProjectFact.category, ProjectFact.key)
    )
    return list(rows.all())


async def upsert_fact(
    db: AsyncSession,
    *,
    project: Project,
    category: str,
    key: str,
    value: Any,
    verification_status: str | None = None,
) -> ProjectFact:
    try:
        cat = FactCategory(category)
    except ValueError as exc:
        raise ValidationAppError(f"Invalid fact category: {category}") from exc

    existing = await db.scalar(
        select(ProjectFact).where(
            ProjectFact.project_id == project.id,
            ProjectFact.category == cat,
            ProjectFact.key == key,
        )
    )
    now = utcnow()
    status = FactVerificationStatus.UNVERIFIED
    if verification_status is not None:
        try:
            status = FactVerificationStatus(verification_status)
        except ValueError as exc:
            raise ValidationAppError("Invalid verification_status") from exc

    if existing is None:
        fact = ProjectFact(
            project_id=project.id,
            category=cat,
            key=key,
            value=value,
            source_type=FactSourceType.USER,
            verification_status=status,
            created_at=now,
            updated_at=now,
        )
        db.add(fact)
    else:
        fact = existing
        fact.value = value
        fact.verification_status = status
        fact.updated_at = now
        fact.source_type = FactSourceType.USER

    project.last_activity_at = now
    await db.flush()
    await db.refresh(fact)
    return fact


def fact_to_public(fact: ProjectFact) -> FactPublic:
    return FactPublic(
        id=str(fact.id),
        category=fact.category.value,
        key=fact.key,
        value=fact.value,
        source_type=fact.source_type.value,
        verification_status=fact.verification_status.value,
        updated_at=fact.updated_at,
    )


def completeness_template() -> list[dict[str, str]]:
    return [
        {"category": cat.value, "key": key, "label": label} for cat, key, label in COMPLETENESS_KEYS
    ]
