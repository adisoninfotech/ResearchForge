"""Project home aggregate for guided ethical engagement."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.user import User
from app.services.engagement import goals as goals_service
from app.services.engagement import milestones as milestones_service
from app.services.engagement import retention_actions
from app.services.engagement.progress import (
    latest_progress_explanation,
    refresh_project_completion,
)
from app.services.engagement.questions import guided_questions_catalog
from app.services.facts import completeness_template, fact_map, list_facts


async def project_home(
    db: AsyncSession,
    *,
    project: Project,
    user: User,
) -> dict[str, Any]:
    await milestones_service.refresh_milestones(db, project=project)
    progress = await refresh_project_completion(db, project=project)
    explanation = await latest_progress_explanation(db, project_id=project.id)
    goal = await goals_service.get_daily_goal(db, project_id=project.id, user_id=user.id)
    facts = await list_facts(db, project_id=project.id)
    fmap = fact_map(facts)
    unanswered = [
        q
        for q in guided_questions_catalog()
        if not fmap.get(q["fact_path"])
        or (isinstance(fmap.get(q["fact_path"]), str) and not str(fmap.get(q["fact_path"])).strip())
    ]
    retention = await retention_actions.retention_status(db, project=project, user=user)

    return {
        "project_id": str(project.id),
        "completion_percent": progress.percent,
        "progress": progress.to_dict(),
        "completion_change": explanation,
        "sections_completed": progress.sections_completed,
        "sections_total": progress.sections_total,
        "missing_evidence": progress.missing_evidence,
        "unsupported_claims": progress.unsupported_claims,
        "unverified_references": progress.unverified_references,
        "dataset_status": progress.dataset_status,
        "figures_needed": progress.figures_needed,
        "tables_needed": progress.tables_needed,
        "similarity_findings": progress.similarity_findings_open,
        "target_submission_date": (
            project.intended_submission_date.isoformat()
            if project.intended_submission_date
            else None
        ),
        "last_saved_at": (
            (project.last_activity_at or project.updated_at).isoformat()
            if (project.last_activity_at or project.updated_at)
            else None
        ),
        "next_recommended_action": progress.next_action,
        "next_recommended_action_code": progress.next_action_code,
        "milestones": await milestones_service.list_milestones(db, project_id=project.id),
        "daily_goal": goals_service.goal_to_dict(goal) if goal else None,
        "available_daily_goals": goals_service.available_goals(),
        "guided_questions": guided_questions_catalog(),
        "unanswered_questions": unanswered[:8],
        "facts_template": completeness_template(),
        "retention": retention,
        "engagement_principles": {
            "no_manipulative_patterns": True,
            "no_unreliable_time_promises": True,
            "writing_reminders_opt_in_only": True,
            "ai_must_not_invent_facts": True,
        },
    }
