from __future__ import annotations

import uuid
from collections.abc import Iterable, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import ProjectStatus
from app.models.project import Project, ProjectMember
from app.models.workflow_state import WorkflowState


class ProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, project_id: uuid.UUID) -> Project | None:
        return await self._s.get(Project, project_id)

    async def get_by_key(self, key: str) -> Project | None:
        return (await self._s.execute(select(Project).where(Project.key == key))).scalar_one_or_none()

    async def list_by_ids(
        self, ids: Iterable[uuid.UUID], *, include_archived: bool = False
    ) -> Sequence[Project]:
        id_set = set(ids)
        if not id_set:
            return []
        stmt = select(Project).where(Project.id.in_(id_set))
        if not include_archived:
            stmt = stmt.where(Project.status == ProjectStatus.ACTIVE.value)
        stmt = stmt.order_by(Project.name)
        return (await self._s.execute(stmt)).scalars().all()

    def add(self, project: Project) -> None:
        self._s.add(project)

    # ---- members ----
    async def list_members(self, project_id: uuid.UUID) -> Sequence[ProjectMember]:
        return (
            (await self._s.execute(select(ProjectMember).where(ProjectMember.project_id == project_id)))
            .scalars()
            .all()
        )

    async def get_member(self, project_id: uuid.UUID, user_id: uuid.UUID) -> ProjectMember | None:
        return (
            await self._s.execute(
                select(ProjectMember).where(
                    ProjectMember.project_id == project_id,
                    ProjectMember.user_id == user_id,
                )
            )
        ).scalar_one_or_none()

    def add_member(self, member: ProjectMember) -> None:
        self._s.add(member)

    async def delete_member(self, member: ProjectMember) -> None:
        await self._s.delete(member)

    # ---- workflow states ----
    async def list_workflow_states(self, project_id: uuid.UUID) -> Sequence[WorkflowState]:
        return (
            (
                await self._s.execute(
                    select(WorkflowState)
                    .where(WorkflowState.project_id == project_id)
                    .order_by(WorkflowState.position)
                )
            )
            .scalars()
            .all()
        )

    async def get_workflow_state(self, state_id: uuid.UUID) -> WorkflowState | None:
        return await self._s.get(WorkflowState, state_id)

    def add_workflow_state(self, state: WorkflowState) -> None:
        self._s.add(state)
