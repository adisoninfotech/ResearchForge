"""Project lifecycle: create, list, update, guest conversion."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationAppError
from app.core.time import utcnow
from app.models.enums import AuditAction, ProjectStatus, RetentionPolicy
from app.models.project import Project
from app.models.user import User
from app.schemas.authors import ManuscriptAuthor, normalize_authors
from app.schemas.guest import GuestTransferRequest
from app.schemas.projects import ProjectCreateRequest, ProjectPublic, ProjectUpdateRequest
from app.services import manuscripts as manuscript_service
from app.services.audit import record_audit
from app.services.slugs import slugify


def _authors_public(raw: object) -> list[ManuscriptAuthor]:
    if not isinstance(raw, list):
        return []
    out: list[ManuscriptAuthor] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            out.append(ManuscriptAuthor.model_validate(item))
        except (TypeError, ValueError):
            continue
    return out


def project_to_public(project: Project) -> ProjectPublic:
    return ProjectPublic(
        id=str(project.id),
        title=project.title,
        slug=project.slug,
        research_field=project.research_field or project.research_area,
        paper_type=project.paper_type,
        target_publisher=project.target_publisher,
        target_template=project.target_template or project.target_format,
        target_word_count=project.target_word_count,
        intended_submission_date=project.intended_submission_date,
        research_problem=project.research_problem,
        proposed_contribution=project.proposed_contribution,
        authors=_authors_public(project.authors),
        status=project.status.value,
        retention_policy=project.retention_policy.value,
        last_activity_at=project.last_activity_at,
        trash_at=project.trash_at,
        purge_after=project.purge_after,
        legal_hold=project.legal_hold,
        ai_enabled=project.ai_enabled,
        is_private=project.is_private,
        transferred_from_guest=project.transferred_from_guest,
        contains_synthetic_data=project.contains_synthetic_data,
        guest_conversion_key=project.guest_conversion_key,
        completion_percent=project.completion_percent,
        updated_at=project.updated_at,
        created_at=project.created_at,
    )


def _parse_status(
    value: str | None,
    *,
    default: ProjectStatus = ProjectStatus.DRAFT,
) -> ProjectStatus:
    if value is None:
        return default
    try:
        return ProjectStatus(value)
    except ValueError as exc:
        raise ValidationAppError(f"Invalid status: {value}") from exc


def _parse_retention(value: str | None) -> RetentionPolicy:
    if value is None:
        return RetentionPolicy.PLAN_DEFAULT
    try:
        return RetentionPolicy(value)
    except ValueError as exc:
        raise ValidationAppError(f"Invalid retention_policy: {value}") from exc


async def create_project(
    db: AsyncSession,
    *,
    user: User,
    payload: ProjectCreateRequest,
) -> Project:
    now = utcnow()
    status = _parse_status(payload.status, default=ProjectStatus.DRAFT)
    if payload.authors:
        authors = normalize_authors(payload.authors)
    else:
        default_name = (user.display_name or user.email.split("@", 1)[0] or "Author").strip()
        authors = normalize_authors(
            [{"name": default_name, "email": user.email, "corresponding": True}]
        )
    project = Project(
        owner_id=user.id,
        title=payload.title.strip(),
        slug=slugify(payload.title),
        research_field=payload.research_field,
        research_area=payload.research_field,
        paper_type=payload.paper_type,
        target_publisher=payload.target_publisher,
        target_template=payload.target_template,
        target_format=payload.target_template,
        target_word_count=payload.target_word_count,
        intended_submission_date=payload.intended_submission_date,
        research_problem=payload.research_problem,
        proposed_contribution=payload.proposed_contribution,
        authors=authors,
        status=status,
        retention_policy=_parse_retention(payload.retention_policy),
        last_activity_at=now,
        is_private=True,
    )
    db.add(project)
    await db.flush()
    await manuscript_service.ensure_manuscript(db, project=project)
    await record_audit(
        db,
        action=AuditAction.PROJECT_CREATED,
        user_id=user.id,
        metadata={"project_id": str(project.id)},
    )
    from app.models.enums import AnalyticsEventType
    from app.services.engagement.analytics import track as track_analytics

    await track_analytics(
        db,
        event_type=AnalyticsEventType.PROJECT_CREATED,
        user_id=user.id,
        project_id=project.id,
        properties={"status": project.status.value},
    )
    await db.refresh(project)
    return project


async def update_project(
    db: AsyncSession,
    *,
    project: Project,
    user: User,
    payload: ProjectUpdateRequest,
) -> Project:
    data = payload.model_dump(exclude_unset=True)
    if "title" in data and data["title"] is not None:
        project.title = data["title"].strip()
    if "research_field" in data:
        project.research_field = data["research_field"]
        project.research_area = data["research_field"]
    if "paper_type" in data:
        project.paper_type = data["paper_type"]
    if "target_publisher" in data:
        project.target_publisher = data["target_publisher"]
    if "target_template" in data:
        project.target_template = data["target_template"]
        project.target_format = data["target_template"]
    if "target_word_count" in data:
        project.target_word_count = data["target_word_count"]
    if "intended_submission_date" in data:
        project.intended_submission_date = data["intended_submission_date"]
    if "research_problem" in data:
        project.research_problem = data["research_problem"]
    if "proposed_contribution" in data:
        project.proposed_contribution = data["proposed_contribution"]
    if "retention_policy" in data and data["retention_policy"] is not None:
        project.retention_policy = _parse_retention(data["retention_policy"])
    if "status" in data and data["status"] is not None:
        new_status = _parse_status(data["status"])
        if new_status == ProjectStatus.TRASH:
            raise ValidationAppError("Use the trash endpoint to move projects to trash")
        if project.status.value == ProjectStatus.TRASH.value:
            raise ValidationAppError("Use restore to leave trash")
        project.status = new_status
    if "legal_hold" in data and data["legal_hold"] is not None:
        project.legal_hold = bool(data["legal_hold"])
    if "ai_enabled" in data and data["ai_enabled"] is not None:
        project.ai_enabled = bool(data["ai_enabled"])
    if "authors" in data and data["authors"] is not None:
        try:
            project.authors = list(normalize_authors(data["authors"]))
        except ValueError as exc:
            raise ValidationAppError(str(exc)) from exc

    project.last_activity_at = utcnow()
    await record_audit(
        db,
        action=AuditAction.PROJECT_UPDATED,
        user_id=user.id,
        metadata={"project_id": str(project.id), "fields": sorted(data.keys())},
    )
    await db.flush()
    await db.refresh(project)
    return project


async def convert_guest_draft(
    db: AsyncSession,
    *,
    user: User,
    payload: GuestTransferRequest,
) -> tuple[Project, bool]:
    """
    Transfer a browser-local guest draft into a private project.

    Idempotent on (owner_id, guest_conversion_key). Returns (project, created).
    """
    existing = await db.scalar(
        select(Project).where(
            Project.owner_id == user.id,
            Project.guest_conversion_key == payload.guest_conversion_key,
        )
    )
    if existing is not None:
        return existing, False

    now = utcnow()
    default_name = (user.display_name or user.email.split("@", 1)[0] or "Author").strip()
    authors = normalize_authors(
        [{"name": default_name, "email": user.email, "corresponding": True}]
    )
    project = Project(
        owner_id=user.id,
        title=payload.title,
        slug=slugify(payload.title),
        research_field=payload.research_area,
        research_area=payload.research_area,
        target_template=payload.target_format,
        target_format=payload.target_format,
        research_problem=payload.research_problem,
        proposed_contribution=payload.proposed_contribution,
        outline=payload.outline,
        draft_content=payload.draft_content,
        authors=authors,
        status=ProjectStatus.ACTIVE,
        retention_policy=RetentionPolicy.PLAN_DEFAULT,
        last_activity_at=now,
        is_private=True,
        contains_synthetic_data=payload.contains_synthetic_data,
        transferred_from_guest=True,
        guest_conversion_key=payload.guest_conversion_key,
    )
    db.add(project)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raced = await db.scalar(
            select(Project).where(
                Project.owner_id == user.id,
                Project.guest_conversion_key == payload.guest_conversion_key,
            )
        )
        if raced is not None:
            return raced, False
        raise
    manuscript = await manuscript_service.ensure_manuscript(db, project=project)

    # Seed introduction from guest draft content when present
    if payload.draft_content and isinstance(payload.draft_content, dict):
        text = str(payload.draft_content.get("sectionContent") or "")
        if text.strip():
            intro = next(
                (s for s in manuscript.sections if s.section_type.value == "introduction"),
                None,
            )
            if intro is not None:
                structured = {
                    "type": "doc",
                    "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
                    "plain_text": text,
                }
                await manuscript_service.save_section(
                    db,
                    project=project,
                    user=user,
                    section_id=intro.id,
                    structured_content=structured,
                    expected_revision=intro.revision_number,
                    create_snapshot=True,
                    snapshot_summary="Imported guest draft content",
                )

    await record_audit(
        db,
        action=AuditAction.GUEST_DRAFT_CONVERTED,
        user_id=user.id,
        metadata={
            "project_id": str(project.id),
            "guest_conversion_key": payload.guest_conversion_key,
        },
    )
    from app.models.enums import AnalyticsEventType
    from app.services.engagement.analytics import track as track_analytics

    await track_analytics(
        db,
        event_type=AnalyticsEventType.DRAFT_CONVERTED_FROM_GUEST,
        user_id=user.id,
        project_id=project.id,
        properties={},
    )
    await db.refresh(project)
    return project, True


async def list_user_projects(
    db: AsyncSession,
    *,
    user: User,
    status: str | None = None,
    q: str | None = None,
    sort: str = "last_edited",
) -> list[Project]:
    stmt = select(Project).where(Project.owner_id == user.id)
    if status:
        stmt = stmt.where(Project.status == _parse_status(status))
    else:
        # Default dashboard list excludes trash unless explicitly requested
        stmt = stmt.where(Project.status != ProjectStatus.TRASH)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Project.title.ilike(pattern),
                Project.research_field.ilike(pattern),
                Project.target_publisher.ilike(pattern),
            )
        )

    if sort == "title":
        stmt = stmt.order_by(Project.title.asc())
    elif sort == "submission_date":
        stmt = stmt.order_by(Project.intended_submission_date.asc().nulls_last())
    elif sort == "completion":
        stmt = stmt.order_by(Project.completion_percent.desc())
    else:
        stmt = stmt.order_by(
            Project.last_activity_at.desc().nulls_last(),
            Project.updated_at.desc(),
        )

    result = await db.scalars(stmt)
    return list(result.all())


async def get_project_by_id(db: AsyncSession, *, project_id: UUID) -> Project | None:
    return await db.get(Project, project_id)
