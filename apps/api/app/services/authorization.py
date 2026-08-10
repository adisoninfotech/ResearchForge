"""Server-side authorization policies. Never trust client role claims."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.project import Project
from app.models.user import User


async def get_owned_project(
    db: AsyncSession,
    *,
    project_id: UUID,
    user: User,
) -> Project:
    """Return project only if owned by user; otherwise 404 to avoid existence leaks."""
    project = await db.get(Project, project_id)
    if project is None or project.owner_id != user.id:
        raise NotFoundError("Project not found")
    return project


def assert_same_user(*, actor: User, target_user_id: UUID) -> None:
    if actor.id != target_user_id:
        raise NotFoundError("Resource not found")
