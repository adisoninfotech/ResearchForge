"""Guided ethical engagement APIs."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, DbSession, enforce_rate_limit, require_csrf
from app.core.exceptions import ValidationAppError
from app.schemas.engagement import (
    DailyGoalRequest,
    GoalStepRequest,
    GuidedAnswerRequest,
    NotificationPreferencesUpdate,
    RetentionActionRequest,
)
from app.services.authorization import get_owned_project
from app.services.engagement import goals as goals_service
from app.services.engagement import milestones as milestones_service
from app.services.engagement import notifications as notif_service
from app.services.engagement import retention_actions
from app.services.engagement import service as engagement_service
from app.services.engagement.progress import compute_progress, latest_progress_explanation
from app.services.engagement.questions import guided_questions_catalog
from app.services.facts import fact_to_public, upsert_fact
from app.services.projects import project_to_public

router = APIRouter(tags=["engagement"])


@router.get("/projects/{project_id}/engagement/home")
async def engagement_home(
    project_id: UUID,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    project = await get_owned_project(session, project_id=project_id, user=user)
    return await engagement_service.project_home(session, project=project, user=user)


@router.get("/projects/{project_id}/engagement/progress")
async def engagement_progress(
    project_id: UUID,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    project = await get_owned_project(session, project_id=project_id, user=user)
    snap = await compute_progress(session, project=project)
    explanation = await latest_progress_explanation(session, project_id=project.id)
    return {"progress": snap.to_dict(), "completion_change": explanation}


@router.get("/projects/{project_id}/engagement/questions")
async def list_guided_questions(
    project_id: UUID,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    await get_owned_project(session, project_id=project_id, user=user)
    return {"questions": guided_questions_catalog()}


@router.post(
    "/projects/{project_id}/engagement/questions/answer",
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def answer_guided_question(
    project_id: UUID,
    payload: GuidedAnswerRequest,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    project = await get_owned_project(session, project_id=project_id, user=user)
    fact = await upsert_fact(
        session,
        project=project,
        category=payload.category,
        key=payload.key,
        value=payload.value,
        verification_status=payload.verification_status,
    )
    from app.services.engagement.progress import refresh_project_completion

    snap = await refresh_project_completion(session, project=project)
    await milestones_service.refresh_milestones(session, project=project)
    return {
        "fact": fact_to_public(fact).model_dump(mode="json"),
        "completion_percent": snap.percent,
        "next_recommended_action": snap.next_action,
    }


@router.get("/projects/{project_id}/engagement/milestones")
async def list_project_milestones(
    project_id: UUID,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    project = await get_owned_project(session, project_id=project_id, user=user)
    await milestones_service.refresh_milestones(session, project=project)
    return {"milestones": await milestones_service.list_milestones(session, project_id=project.id)}


@router.post(
    "/projects/{project_id}/engagement/goals",
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def set_goal(
    project_id: UUID,
    payload: DailyGoalRequest,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    project = await get_owned_project(session, project_id=project_id, user=user)
    goal = await goals_service.set_daily_goal(
        session,
        project=project,
        user=user,
        goal_type=payload.goal_type,
        goal_date=payload.goal_date,
    )
    return {"goal": goals_service.goal_to_dict(goal)}


@router.post(
    "/projects/{project_id}/engagement/goals/steps",
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def complete_step(
    project_id: UUID,
    payload: GoalStepRequest,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    await get_owned_project(session, project_id=project_id, user=user)
    goal = await goals_service.complete_goal_step(
        session,
        project_id=project_id,
        user_id=user.id,
        step_id=payload.step_id,
    )
    return {"goal": goals_service.goal_to_dict(goal)}


@router.get("/projects/{project_id}/engagement/retention")
async def get_retention(
    project_id: UUID,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    project = await get_owned_project(session, project_id=project_id, user=user)
    return await retention_actions.retention_status(session, project=project, user=user)


@router.post(
    "/projects/{project_id}/engagement/retention/actions",
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def retention_action(
    project_id: UUID,
    payload: RetentionActionRequest,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    project = await get_owned_project(session, project_id=project_id, user=user)
    action = payload.action.strip().lower()
    if action == "keep":
        project = await retention_actions.keep_project(session, project=project, user=user)
        await session.refresh(project)
        return {"ok": True, "project": project_to_public(project).model_dump(mode="json")}
    if action == "archive":
        project = await retention_actions.archive_project(session, project=project)
        await session.refresh(project)
        return {"ok": True, "project": project_to_public(project).model_dump(mode="json")}
    if action == "delete_now":
        if payload.confirmation != "DELETE":
            raise ValidationAppError('Confirmation must be the string "DELETE"')
        result = await retention_actions.delete_now(session, project=project, user=user)
        return {"ok": True, "deleted": result}
    if action == "export":
        return {
            "ok": True,
            "redirect": f"/projects/{project_id}#export",
            "message": "Use the Export panel to generate a package before deletion.",
        }
    raise ValidationAppError("Unsupported retention action")


@router.get("/account/notifications/preferences")
async def get_notification_preferences(
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    return await notif_service.get_preferences(session, user=user)


@router.put(
    "/account/notifications/preferences",
    dependencies=[Depends(enforce_rate_limit), Depends(require_csrf)],
)
async def put_notification_preferences(
    payload: NotificationPreferencesUpdate,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    return await notif_service.update_preferences(
        session, user=user, preferences=payload.preferences
    )


@router.get("/account/notifications")
async def list_account_notifications(
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    return {"notifications": await notif_service.list_notifications(session, user_id=user.id)}
