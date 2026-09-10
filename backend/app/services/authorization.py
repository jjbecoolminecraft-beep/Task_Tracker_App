"""The single authorization policy layer (spec §2.3, §7.2, §12).

Rules:

* **Deny by default.** Nothing is permitted unless a rule below says so.
* **Scoped evaluation.** The caller's effective role is resolved for the *target*
  resource before any data is returned.
* **Admin ≠ reader.** System Admin configures the platform; it does not read task
  content. Auditor reads audit logs; nothing else.
* **Row-level filtering.** :meth:`AuthZ.accessible_project_ids` is resolved once
  per request and joined into every content query, so a missing check in a
  handler cannot leak data.

Every route handler calls :meth:`AuthZ.require`; no handler inspects roles itself.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AuthorizationError
from app.domain.enums import CONTENT_ROLES, WRITE_ROLES, Action, ProjectVisibility, Role
from app.models.project import Project, ProjectMember
from app.models.role_grant import RoleGrant
from app.models.task import Task, TaskShare
from app.models.user import User

# Actions that never touch task content — permitted for platform roles.
_PLATFORM_ACTIONS: frozenset[Action] = frozenset({Action.AUDIT_READ})


@dataclass(slots=True)
class ResolvedAccess:
    """The caller's standing in one project."""

    project_id: uuid.UUID
    role: Role | None  # effective project role, or None
    via_guest_task_ids: frozenset[uuid.UUID] = frozenset()

    @property
    def can_read(self) -> bool:
        return self.role in CONTENT_ROLES or bool(self.via_guest_task_ids)

    @property
    def can_write(self) -> bool:
        return self.role in WRITE_ROLES

    @property
    def is_project_admin(self) -> bool:
        return self.role == Role.PROJECT_ADMIN


class AuthZ:
    """Per-request authorization façade. Instantiated by a FastAPI dependency."""

    def __init__(self, session: AsyncSession, user: User) -> None:
        self._session = session
        self._user = user
        self._global_roles: set[Role] | None = None
        self._portfolio_owner_ids: set[uuid.UUID] | None = None
        self._accessible_ids: set[uuid.UUID] | None = None

    # ---- role resolution -------------------------------------------------

    async def _load_grants(self) -> None:
        if self._global_roles is not None:
            return
        rows = (
            await self._session.execute(
                select(RoleGrant).where(RoleGrant.user_id == self._user.id)
            )
        ).scalars()
        globals_: set[Role] = set()
        portfolios: set[uuid.UUID] = set()
        for grant in rows:
            if grant.scope_type == "global":
                globals_.add(grant.role_enum)
            elif grant.scope_type == "portfolio" and grant.scope_id is not None:
                if grant.role_enum == Role.PORTFOLIO_OWNER:
                    portfolios.add(grant.scope_id)
        self._global_roles = globals_
        self._portfolio_owner_ids = portfolios

    async def has_global_role(self, role: Role) -> bool:
        await self._load_grants()
        assert self._global_roles is not None
        return role in self._global_roles

    async def is_portfolio_owner(self, portfolio_id: uuid.UUID | None) -> bool:
        if portfolio_id is None:
            return False
        await self._load_grants()
        assert self._portfolio_owner_ids is not None
        return portfolio_id in self._portfolio_owner_ids

    async def effective_project_role(self, project: Project) -> Role | None:
        """Highest-privilege role the caller holds for ``project``."""
        # Portfolio Owner of the owning portfolio → acts as Project Admin.
        if await self.is_portfolio_owner(project.portfolio_id):
            return Role.PROJECT_ADMIN

        membership = (
            await self._session.execute(
                select(ProjectMember).where(
                    ProjectMember.project_id == project.id,
                    ProjectMember.user_id == self._user.id,
                )
            )
        ).scalars().all()
        roles = {m.role_enum for m in membership}
        for role in (Role.PROJECT_ADMIN, Role.CONTRIBUTOR, Role.VIEWER):
            if role in roles:
                return role

        # Internally-visible projects grant implicit read (spec §2.3).
        if project.visibility == ProjectVisibility.INTERNAL.value:
            return Role.VIEWER
        return None

    async def resolve(self, project: Project) -> ResolvedAccess:
        role = await self.effective_project_role(project)
        guest_task_ids: frozenset[uuid.UUID] = frozenset()
        if role is None:
            shared = (
                await self._session.execute(
                    select(TaskShare.task_id)
                    .join(Task, Task.id == TaskShare.task_id)
                    .where(Task.project_id == project.id, TaskShare.user_id == self._user.id)
                )
            ).scalars().all()
            if shared:
                guest_task_ids = frozenset(shared)
                role = Role.GUEST
        return ResolvedAccess(project_id=project.id, role=role, via_guest_task_ids=guest_task_ids)

    async def accessible_project_ids(self) -> set[uuid.UUID]:
        """All project ids whose content the caller may read. Cached per request."""
        if self._accessible_ids is not None:
            return self._accessible_ids

        await self._load_grants()
        assert self._portfolio_owner_ids is not None

        ids: set[uuid.UUID] = set()

        member_rows = (
            await self._session.execute(
                select(ProjectMember.project_id, ProjectMember.role).where(
                    ProjectMember.user_id == self._user.id
                )
            )
        ).all()
        ids.update(pid for pid, role in member_rows if Role(role) in CONTENT_ROLES)

        internal_rows = (
            await self._session.execute(
                select(Project.id).where(
                    Project.visibility == ProjectVisibility.INTERNAL.value
                )
            )
        ).scalars()
        ids.update(internal_rows)

        if self._portfolio_owner_ids:
            portfolio_rows = (
                await self._session.execute(
                    select(Project.id).where(
                        Project.portfolio_id.in_(self._portfolio_owner_ids)
                    )
                )
            ).scalars()
            ids.update(portfolio_rows)

        guest_rows = (
            await self._session.execute(
                select(Task.project_id)
                .join(TaskShare, TaskShare.task_id == Task.id)
                .where(TaskShare.user_id == self._user.id)
            )
        ).scalars()
        ids.update(guest_rows)

        self._accessible_ids = ids
        return ids

    # ---- the single gate ----------------------------------------------------

    async def require(self, action: Action, resource: object | None = None) -> ResolvedAccess | None:
        """Raise :class:`AuthorizationError` unless ``action`` is permitted.

        Returns the :class:`ResolvedAccess` when the decision hinged on a project
        role, so handlers can reuse it without a second lookup.
        """
        decision = await self._evaluate(action, resource)
        if decision is False:
            raise AuthorizationError(f"Not permitted: {action.value}")
        return decision if isinstance(decision, ResolvedAccess) else None

    async def _evaluate(
        self, action: Action, resource: object | None
    ) -> bool | ResolvedAccess:
        # Platform-only actions: audit reading is the Auditor's alone (spec §8.4.4).
        if action in _PLATFORM_ACTIONS:
            if action == Action.AUDIT_READ:
                return await self.has_global_role(Role.AUDITOR)
            return False  # pragma: no cover

        if action == Action.PROJECT_CREATE:
            portfolio_id = resource if isinstance(resource, uuid.UUID) else None
            if await self.has_global_role(Role.SYSTEM_ADMIN):
                return True
            return await self.is_portfolio_owner(portfolio_id)

        if isinstance(resource, Project):
            return await self._evaluate_project(action, resource)

        if isinstance(resource, Task):
            project = await self._session.get(Project, resource.project_id)
            if project is None:  # pragma: no cover - referential integrity
                return False
            return await self._evaluate_task(action, resource, project)

        return False

    async def _evaluate_project(self, action: Action, project: Project) -> bool | ResolvedAccess:
        access = await self.resolve(project)
        if action == Action.PROJECT_READ:
            return access if access.can_read else False
        if action in (Action.PROJECT_UPDATE, Action.PROJECT_ARCHIVE, Action.PROJECT_MANAGE_MEMBERS):
            return access if access.is_project_admin else False
        if action == Action.TASK_CREATE:
            return access if access.can_write else False
        return False

    async def _evaluate_task(
        self, action: Action, task: Task, project: Project
    ) -> bool | ResolvedAccess:
        access = await self.resolve(project)

        if access.role == Role.GUEST:
            # Guests are confined to the specific tasks shared with them.
            if task.id not in access.via_guest_task_ids:
                return False
            return access if action in (Action.TASK_READ, Action.COMMENT_READ) else False

        if action in (Action.TASK_READ, Action.COMMENT_READ):
            return access if access.can_read else False
        if action in (
            Action.TASK_UPDATE,
            Action.TASK_COMPLETE,
            Action.TASK_DELETE,
            Action.COMMENT_CREATE,
        ):
            return access if access.can_write else False
        return False
