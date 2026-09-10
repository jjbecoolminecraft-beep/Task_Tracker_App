"""Project use-cases. Authorization first, then repository, then audit — all in
the request's transaction.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.domain.enums import Action, ProjectStatus, Role, WorkflowCategory
from app.models.project import Project, ProjectMember
from app.models.role_grant import RoleGrant
from app.models.user import User
from app.models.workflow_state import WorkflowState
from app.repositories.projects import ProjectRepository
from app.repositories.tasks import TaskRepository
from app.repositories.users import UserRepository
from app.schemas.project import (
    ProjectCreate,
    ProjectMemberIn,
    ProjectMemberOut,
    ProjectOut,
    ProjectUpdate,
    WorkflowStateOut,
)
from app.services import audit
from app.services.authorization import AuthZ

_DEFAULT_STATES: tuple[tuple[str, WorkflowCategory, bool], ...] = (
    ("To Do", WorkflowCategory.BACKLOG, True),
    ("In Progress", WorkflowCategory.IN_PROGRESS, False),
    ("In Review", WorkflowCategory.IN_PROGRESS, False),
    ("Done", WorkflowCategory.DONE, False),
)


class ProjectService:
    def __init__(self, session: AsyncSession, authz: AuthZ) -> None:
        self._s = session
        self._authz = authz
        self._repo = ProjectRepository(session)
        self._users = UserRepository(session)
        self._tasks = TaskRepository(session)

    async def _to_out(self, project: Project, *, role: Role | None, open_count: int | None) -> ProjectOut:
        out = ProjectOut.model_validate(project)
        out.my_role = role
        out.open_task_count = open_count
        return out

    async def list_visible(self, *, include_archived: bool = False) -> list[ProjectOut]:
        ids = await self._authz.accessible_project_ids()
        projects = await self._repo.list_by_ids(ids, include_archived=include_archived)
        counts = await self._tasks.count_open_by_state([p.id for p in projects])
        # count_open_by_state is keyed by state_id; roll up per project cheaply.
        open_by_project: dict[uuid.UUID, int] = {}
        for project in projects:
            states = await self._repo.list_workflow_states(project.id)
            non_done = {s.id for s in states if s.category != WorkflowCategory.DONE.value}
            open_by_project[project.id] = sum(n for sid, n in counts.items() if sid in non_done)

        result: list[ProjectOut] = []
        for project in projects:
            role = await self._authz.effective_project_role(project)
            result.append(await self._to_out(project, role=role, open_count=open_by_project.get(project.id, 0)))
        return result

    async def get(self, project_id: uuid.UUID) -> ProjectOut:
        project = await self._require_project(project_id)
        access = await self._authz.require(Action.PROJECT_READ, project)
        role = access.role if access else None
        return await self._to_out(project, role=role, open_count=None)

    async def create(self, payload: ProjectCreate, actor: User) -> ProjectOut:
        await self._authz.require(Action.PROJECT_CREATE, payload.portfolio_id)

        if await self._repo.get_by_key(payload.key):
            raise ConflictError(f"Project key '{payload.key}' is already in use.", code="key_taken")

        project = Project(
            key=payload.key,
            name=payload.name,
            description=payload.description,
            portfolio_id=payload.portfolio_id,
            visibility=payload.visibility.value,
            status=ProjectStatus.ACTIVE.value,
            created_by=actor.id,
        )
        self._repo.add(project)
        await self._s.flush()

        states_spec = (
            [(s.name, s.category, i == 0) for i, s in enumerate(payload.workflow_states)]
            if payload.workflow_states
            else [(n, c, d) for n, c, d in _DEFAULT_STATES]
        )
        for position, (name, category, is_default) in enumerate(states_spec):
            self._repo.add_workflow_state(
                WorkflowState(
                    project_id=project.id,
                    name=name,
                    category=category.value if isinstance(category, WorkflowCategory) else category,
                    position=position,
                    is_default=is_default,
                )
            )

        # The creator becomes Project Admin so they can immediately manage it.
        self._repo.add_member(
            ProjectMember(project_id=project.id, user_id=actor.id, role=Role.PROJECT_ADMIN.value)
        )
        await self._s.flush()

        await audit.record(
            self._s,
            action="project.created",
            resource_type="project",
            resource_id=project.id,
            project_id=project.id,
            actor=actor,
            after={"key": project.key, "visibility": project.visibility},
        )
        return await self._to_out(project, role=Role.PROJECT_ADMIN, open_count=0)

    async def update(
        self, project_id: uuid.UUID, payload: ProjectUpdate, actor: User
    ) -> ProjectOut:
        project = await self._require_project(project_id)
        await self._authz.require(Action.PROJECT_UPDATE, project)

        before = {
            "name": project.name,
            "description": project.description,
            "visibility": project.visibility,
        }
        if payload.name is not None:
            project.name = payload.name
        if payload.description is not None:
            project.description = payload.description
        if payload.visibility is not None:
            project.visibility = payload.visibility.value
        after = {
            "name": project.name,
            "description": project.description,
            "visibility": project.visibility,
        }
        b, a = audit.diff(before, after)
        await audit.record(
            self._s,
            action="project.updated",
            resource_type="project",
            resource_id=project.id,
            project_id=project.id,
            actor=actor,
            before=b,
            after=a,
        )
        role = await self._authz.effective_project_role(project)
        return await self._to_out(project, role=role, open_count=None)

    async def archive(self, project_id: uuid.UUID, actor: User) -> ProjectOut:
        project = await self._require_project(project_id)
        await self._authz.require(Action.PROJECT_ARCHIVE, project)
        if project.status == ProjectStatus.ARCHIVED.value:
            raise ConflictError("Project is already archived.")
        project.status = ProjectStatus.ARCHIVED.value
        project.archived_at = datetime.now(UTC)
        await audit.record(
            self._s,
            action="project.archived",
            resource_type="project",
            resource_id=project.id,
            project_id=project.id,
            actor=actor,
        )
        role = await self._authz.effective_project_role(project)
        return await self._to_out(project, role=role, open_count=None)

    # ---- workflow states ----
    async def list_workflow_states(self, project_id: uuid.UUID) -> list[WorkflowStateOut]:
        project = await self._require_project(project_id)
        await self._authz.require(Action.PROJECT_READ, project)
        states = await self._repo.list_workflow_states(project_id)
        return [WorkflowStateOut.model_validate(s) for s in states]

    # ---- members ----
    async def list_members(self, project_id: uuid.UUID) -> list[ProjectMemberOut]:
        project = await self._require_project(project_id)
        await self._authz.require(Action.PROJECT_READ, project)
        members = await self._repo.list_members(project_id)
        users = await self._users.get_many([m.user_id for m in members if m.user_id])
        out: list[ProjectMemberOut] = []
        for m in members:
            row = ProjectMemberOut.model_validate(m)
            if m.user_id and (u := users.get(m.user_id)):
                row.display_name = u.display_name
            out.append(row)
        return out

    async def add_member(
        self, project_id: uuid.UUID, payload: ProjectMemberIn, actor: User
    ) -> ProjectMemberOut:
        project = await self._require_project(project_id)
        await self._authz.require(Action.PROJECT_MANAGE_MEMBERS, project)
        if not payload.is_project_scoped_role:
            raise ValidationError("Only project-scoped roles can be assigned here.")
        if await self._users.get(payload.user_id) is None:
            raise NotFoundError("User not found.")
        existing = await self._repo.get_member(project_id, payload.user_id)
        if existing:
            existing.role = payload.role.value
            member = existing
        else:
            member = ProjectMember(
                project_id=project_id, user_id=payload.user_id, role=payload.role.value
            )
            self._repo.add_member(member)
        await self._s.flush()
        await audit.record(
            self._s,
            action="project.member_added",
            resource_type="project_member",
            resource_id=member.id,
            project_id=project_id,
            actor=actor,
            after={"user_id": str(payload.user_id), "role": payload.role.value},
        )
        row = ProjectMemberOut.model_validate(member)
        return row

    async def remove_member(
        self, project_id: uuid.UUID, user_id: uuid.UUID, actor: User
    ) -> None:
        project = await self._require_project(project_id)
        await self._authz.require(Action.PROJECT_MANAGE_MEMBERS, project)
        member = await self._repo.get_member(project_id, user_id)
        if member is None:
            raise NotFoundError("Membership not found.")
        await self._repo.delete_member(member)
        await audit.record(
            self._s,
            action="project.member_removed",
            resource_type="project_member",
            resource_id=member.id,
            project_id=project_id,
            actor=actor,
            before={"user_id": str(user_id), "role": member.role},
        )

    async def _require_project(self, project_id: uuid.UUID) -> Project:
        project = await self._repo.get(project_id)
        if project is None:
            raise NotFoundError("Project not found.")
        return project


async def portfolio_grants_for(session: AsyncSession, user_id: uuid.UUID) -> Sequence[RoleGrant]:
    from sqlalchemy import select

    return (
        (await session.execute(select(RoleGrant).where(RoleGrant.user_id == user_id)))
        .scalars()
        .all()
    )
