"""Daily goals — short task sequences without unreliable time estimates."""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationAppError
from app.core.time import utcnow
from app.models.engagement import DailyGoal
from app.models.enums import DailyGoalType
from app.models.project import Project
from app.models.user import User

GOAL_SEQUENCES: dict[str, list[dict[str, str]]] = {
    DailyGoalType.COMPLETE_SECTION.value: [
        {"id": "pick_section", "label": "Choose one incomplete section to advance"},
        {"id": "capture_facts", "label": "Capture any missing facts for that section"},
        {"id": "draft_paragraphs", "label": "Write or revise grounded paragraphs"},
        {"id": "attach_evidence", "label": "Attach supporting evidence where claims need it"},
        {"id": "mark_review", "label": "Re-read for unsupported statements before leaving"},
    ],
    DailyGoalType.VERIFY_REFERENCES.value: [
        {"id": "list_refs", "label": "Open the references list"},
        {"id": "check_metadata", "label": "Verify titles, years, and identifiers"},
        {"id": "fix_unverified", "label": "Correct or mark each unverified reference"},
        {"id": "scan_citations", "label": "Confirm in-text citations still match keys"},
    ],
    DailyGoalType.ANALYZE_DATASET.value: [
        {
            "id": "confirm_provenance",
            "label": "Confirm dataset provenance (real/synthetic/simulated)",
        },
        {"id": "choose_analysis", "label": "Select an approved analysis operation"},
        {"id": "run_analysis", "label": "Run the analysis and review outputs"},
        {"id": "record_metrics", "label": "Save evaluation metrics as project facts"},
    ],
    DailyGoalType.RESOLVE_SIMILARITY.value: [
        {"id": "open_report", "label": "Open the latest similarity report"},
        {"id": "review_findings", "label": "Review each open finding with source context"},
        {"id": "cite_or_rewrite", "label": "Add citations or meaning-preserving rewrites"},
        {"id": "mark_resolved", "label": "Resolve false positives or technical language honestly"},
    ],
    DailyGoalType.CREATE_FIGURES.value: [
        {"id": "identify_need", "label": "Identify which result needs a figure or table"},
        {"id": "create_asset", "label": "Create the figure/table with provenance labels"},
        {"id": "caption", "label": "Write an accurate caption and alt text"},
        {"id": "insert", "label": "Insert into the manuscript with a stable ID"},
    ],
    DailyGoalType.PREPARE_EXPORT.value: [
        {"id": "fix_validation", "label": "Address critical export validation issues"},
        {"id": "statements", "label": "Complete required journal statements"},
        {"id": "preview_template", "label": "Preview a compatible starting template"},
        {"id": "run_export", "label": "Generate the submission package when ready"},
    ],
}

GOAL_DISCLAIMER = (
    "This sequence is guidance only. ResearchForge does not estimate how long tasks will take."
)


async def set_daily_goal(
    db: AsyncSession,
    *,
    project: Project,
    user: User,
    goal_type: str,
    goal_date: date | None = None,
) -> DailyGoal:
    try:
        gtype = DailyGoalType(goal_type)
    except ValueError as exc:
        raise ValidationAppError(f"Invalid daily goal: {goal_type}") from exc
    day = goal_date or utcnow().date()
    existing = await db.scalar(
        select(DailyGoal).where(
            DailyGoal.project_id == project.id,
            DailyGoal.user_id == user.id,
            DailyGoal.goal_date == day,
        )
    )
    sequence = list(GOAL_SEQUENCES[gtype.value])
    if existing is None:
        goal = DailyGoal(
            project_id=project.id,
            user_id=user.id,
            goal_type=gtype,
            goal_date=day,
            task_sequence=sequence,
            completed_step_ids=[],
            note=GOAL_DISCLAIMER,
        )
        db.add(goal)
    else:
        goal = existing
        goal.goal_type = gtype
        goal.task_sequence = sequence
        goal.completed_step_ids = []
        goal.note = GOAL_DISCLAIMER
    project.last_activity_at = utcnow()
    await db.flush()
    await db.refresh(goal)
    return goal


async def get_daily_goal(
    db: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    goal_date: date | None = None,
) -> DailyGoal | None:
    day = goal_date or utcnow().date()
    goal = await db.scalar(
        select(DailyGoal).where(
            DailyGoal.project_id == project_id,
            DailyGoal.user_id == user_id,
            DailyGoal.goal_date == day,
        )
    )
    return goal


async def complete_goal_step(
    db: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    step_id: str,
) -> DailyGoal:
    goal = await get_daily_goal(db, project_id=project_id, user_id=user_id)
    if goal is None:
        raise ValidationAppError("No daily goal set for today")
    done = list(goal.completed_step_ids or [])
    if step_id not in done:
        done.append(step_id)
    goal.completed_step_ids = done
    await db.flush()
    return goal


def goal_to_dict(goal: DailyGoal) -> dict[str, Any]:
    return {
        "id": str(goal.id),
        "goal_type": goal.goal_type.value,
        "goal_date": goal.goal_date.isoformat(),
        "task_sequence": goal.task_sequence,
        "completed_step_ids": goal.completed_step_ids,
        "note": goal.note or GOAL_DISCLAIMER,
        "disclaimer": GOAL_DISCLAIMER,
    }


def available_goals() -> list[dict[str, str]]:
    return [
        {
            "type": g.value,
            "label": g.value.replace("_", " ").capitalize(),
            "disclaimer": GOAL_DISCLAIMER,
        }
        for g in DailyGoalType
    ]
