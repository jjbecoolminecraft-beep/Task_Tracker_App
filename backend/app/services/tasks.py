"""Task use-cases: CRUD, completion, soft delete, subtasks, optimistic
concurrency, and the personal "My tasks" view.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    NotFoundError,
    PreconditionFailedError,
    PreconditionRequiredError,
    ValidationError,
)
from app.core.pagination import Page
from app.domain.enums import Action, Role, WorkflowCategory
from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.models.workflow_state import WorkflowState
from app.repositories.projects import ProjectRepository
from app.repositories.tasks import TaskFilter, TaskRepository
from app.repositories.users import UserRepository
from app.schemas.task import TaskCreate, TaskDetailOut, TaskOut, TaskUpdate
from app.schemas.user import UserRef
from app.services import audit
from app.services.authorization import AuthZ

MAX_SUBTASK_DEPTH = 2  # spec §3.3


def etag_for(task: Task) -> str:
    return f'"{task.version}"'


class TaskService:
    def __init__(self, session: AsyncSession, authz: AuthZ) -> None:
        self._s = session
        self._authz = authz
        self._repo = TaskRepository(session)
        self._projects = ProjectRepository(session)
        self._users = UserRepository(session)

    # ---- serialization ----
    async def _to_out(
        self, task: Task, *, project: Project, state: WorkflowState, with_subtasks: bool = False
    ) -> TaskDetailOut:
        user_ids = {uid for uid in (task.assignee_id, task.reporter_id) if uid}
        users = await self._users.get_many(list(user_ids))
        out = TaskDetailOut.model_validate(task)
        out.project_key = project.key
        out.ref = f"{project.key}-{task.seq}"
        out.state_name = state.name
        out.state_category = state.category
        if task.assignee_id and (u := users.get(task.assignee_id)):
            out.assignee = UserRef(id=u.id, display_name=u.display_name)
        if (r := users.get(task.reporter_id)) is not None:
            out.reporter = UserRef(id=r.id, display_name=r.display_name)
        subtasks = await self._repo.list_subtasks(task.id)
        out.subtask_count = len(subtasks)
        if with_subtasks and subtasks:
            states = {s.id: s for s in await self._projects.list_workflow_states(project.id)}
            out.subtasks = [
                await self._to_out(st, project=project, state=states[st.state_id])
                for st in subtasks
            ]
        return out

    # ---- reads ----
    async def get(self, task_id: uuid.UUID) -> TaskDetailOut:
        task = await self._require_task(task_id)
        await self._authz.require(Action.TASK_READ, task)
        project = await self._projects.get(task.project_id)
        assert project is not None
        state = await self._projects.get_workflow_state(task.state_id)
        assert state is not None
        return await self._to_out(task, project=project, state=state, with_subtasks=True)

    async def list_for_project(
        self,
        project_id: uuid.UUID,
        *,
        filters: dict[str, object],
        limit: int | None,
        cursor: str | None,
    ) -> Page:
        project = await self._require_project(project_id)
        access = await self._authz.require(Action.PROJECT_READ, project)

        # A Guest may only ever see the specific tasks shared with them — never
        # the project's task list. Constrain the query, don't just trust the role.
        guest_scope: list[uuid.UUID] | None = None
        if access is not None and access.role == Role.GUEST:
            guest_scope = list(access.via_guest_task_ids)

        f = TaskFilter(
            project_ids=[project_id],
            task_ids=guest_scope,
            state_id=_as_uuid(filters.get("state_id")),
            assignee_id=_as_uuid(filters.get("assignee_id")),
            priority=_as_int(filters.get("priority")),
            top_level_only=bool(filters.get("top_level_only", True)),
            unassigned=bool(filters.get("unassigned", False)),
            sort=str(filters.get("sort") or "created_at"),
            search=_as_str(filters.get("search")),
        )
        page = await self._repo.paginate_page(f, limit=limit, cursor=cursor)
        page.items = await self._decorate(page.items)
        return page

    async def my_tasks(self, actor: User, *, limit: int | None, cursor: str | None) -> Page:
        project_ids = await self._authz.accessible_project_ids()
        if not project_ids:
            return Page(items=[], next_cursor=None)
        f = TaskFilter(
            project_ids=list(project_ids), assignee_id=actor.id, top_level_only=False, sort="due_date"
        )
        page = await self._repo.paginate_page(f, limit=limit, cursor=cursor)
        page.items = await self._decorate(page.items)
        return page

    async def search(
        self, actor: User, *, query: str, limit: int | None, cursor: str | None
    ) -> Page:
        """Full-text search scoped to the caller's accessible projects (spec F-09)."""
        project_ids = await self._authz.accessible_project_ids()
        if not project_ids:
            return Page(items=[], next_cursor=None)
        f = TaskFilter(
            project_ids=list(project_ids),
            top_level_only=False,
            sort="updated_at",
            search=query,
        )
        page = await self._repo.paginate_page(f, limit=limit, cursor=cursor)
        page.items = await self._decorate(page.items)
        return page

    async def _decorate(self, tasks: Sequence[Task]) -> list[TaskOut]:
        if not tasks:
            return []
        project_ids = {t.project_id for t in tasks}
        projects = {p.id: p for p in await self._projects.list_by_ids(project_ids, include_archived=True)}
        state_ids = {t.state_id for t in tasks}
        states: dict[uuid.UUID, WorkflowState] = {}
        for pid in project_ids:
            for s in await self._projects.list_workflow_states(pid):
                states[s.id] = s
        user_ids = {uid for t in tasks for uid in (t.assignee_id, t.reporter_id) if uid}
        users = await self._users.get_many(list(user_ids))

        rows: list[TaskOut] = []
        for t in tasks:
            project = projects.get(t.project_id)
            state = states.get(t.state_id)
            row = TaskOut.model_validate(t)
            if project:
                row.project_key = project.key
                row.ref = f"{project.key}-{t.seq}"
            if state:
                row.state_name = state.name
                row.state_category = state.category
            if t.assignee_id and (u := users.get(t.assignee_id)):
                row.assignee = UserRef(id=u.id, display_name=u.display_name)
            if (r := users.get(t.reporter_id)) is not None:
                row.reporter = UserRef(id=r.id, display_name=r.display_name)
            rows.append(row)
        return rows

    # ---- writes ----
    async def create(self, project_id: uuid.UUID, payload: TaskCreate, actor: User) -> TaskDetailOut:
        project = await self._require_project(project_id)
        await self._authz.require(Action.TASK_CREATE, project)

        parent: Task | None = None
        if payload.parent_task_id:
            parent = await self._repo.get(payload.parent_task_id)
            if parent is None or parent.project_id != project_id or parent.is_deleted:
                raise ValidationError("Parent task not found in this project.")
            if parent.parent_task_id is not None:
                raise ValidationError(
                    f"Subtasks may not be nested deeper than {MAX_SUBTASK_DEPTH} levels."
                )

        states = await self._projects.list_workflow_states(project_id)
        if not states:
            raise ValidationError("Project has no workflow states configured.")
        state = _pick_state(states, payload.state_id)
        if state is None:
            raise ValidationError("Unknown workflow state for this project.")

        if payload.assignee_id and await self._users.get(payload.assignee_id) is None:
            raise ValidationError("Assignee is not a known user.")

        seq = await self._repo.next_seq(project_id)
        task = Task(
            project_id=project_id,
            parent_task_id=payload.parent_task_id,
            seq=seq,
            title=payload.title,
            description=payload.description,
            state_id=state.id,
            priority=payload.priority,
            assignee_id=payload.assignee_id,
            reporter_id=actor.id,
            due_date=payload.due_date,
            estimate_hours=payload.estimate_hours,
            version=1,
        )
        self._repo.add(task)
        await self._s.flush()

        await audit.record(
            self._s,
            action="task.created",
            resource_type="task",
            resource_id=task.id,
            project_id=project_id,
            actor=actor,
            after={"seq": seq, "state_id": str(state.id), "priority": task.priority},
        )
        return await self._to_out(task, project=project, state=state, with_subtasks=True)

    async def update(
        self, task_id: uuid.UUID, payload: TaskUpdate, actor: User, *, if_match: str | None
    ) -> TaskDetailOut:
        task = await self._require_task(task_id)
        await self._authz.require(Action.TASK_UPDATE, task)
        self._check_precondition(task, if_match)

        project = await self._projects.get(task.project_id)
        assert project is not None

        before = _audit_snapshot(task)
        target_state: WorkflowState | None = None

        if payload.state_id is not None and payload.state_id != task.state_id:
            states = await self._projects.list_workflow_states(task.project_id)
            target_state = next((s for s in states if s.id == payload.state_id), None)
            if target_state is None:
                raise ValidationError("Unknown workflow state for this project.")
            task.state_id = target_state.id
            task.completed_at = (
                datetime.now(UTC) if target_state.category == WorkflowCategory.DONE.value else None
            )

        if payload.title is not None:
            task.title = payload.title
        if payload.description is not None:
            task.description = payload.description
        if payload.priority is not None:
            task.priority = payload.priority
        if payload.due_date is not None:
            task.due_date = payload.due_date
        if payload.clear_due_date:
            task.due_date = None
        if payload.estimate_hours is not None:
            task.estimate_hours = payload.estimate_hours
        if payload.assignee_id is not None:
            if await self._users.get(payload.assignee_id) is None:
                raise ValidationError("Assignee is not a known user.")
            task.assignee_id = payload.assignee_id
        if payload.clear_assignee:
            task.assignee_id = None

        task.version += 1
        await self._s.flush()

        b, a = audit.diff(before, _audit_snapshot(task))
        await audit.record(
            self._s,
            action="task.updated",
            resource_type="task",
            resource_id=task.id,
            project_id=task.project_id,
            actor=actor,
            before=b,
            after=a,
        )
        state = target_state or await self._projects.get_workflow_state(task.state_id)
        assert state is not None
        return await self._to_out(task, project=project, state=state, with_subtasks=True)

    async def complete(self, task_id: uuid.UUID, actor: User, *, if_match: str | None) -> TaskDetailOut:
        task = await self._require_task(task_id)
        await self._authz.require(Action.TASK_COMPLETE, task)
        self._check_precondition(task, if_match)

        states = await self._projects.list_workflow_states(task.project_id)
        done = next((s for s in states if s.category == WorkflowCategory.DONE.value), None)
        if done is None:
            raise ValidationError("Project has no 'done' workflow state.")
        project = await self._projects.get(task.project_id)
        assert project is not None

        before = _audit_snapshot(task)
        task.state_id = done.id
        task.completed_at = datetime.now(UTC)
        task.version += 1
        await self._s.flush()
        b, a = audit.diff(before, _audit_snapshot(task))
        await audit.record(
            self._s,
            action="task.completed",
            resource_type="task",
            resource_id=task.id,
            project_id=task.project_id,
            actor=actor,
            before=b,
            after=a,
        )
        return await self._to_out(task, project=project, state=done, with_subtasks=True)

    async def soft_delete(self, task_id: uuid.UUID, actor: User, *, if_match: str | None) -> None:
        task = await self._require_task(task_id)
        await self._authz.require(Action.TASK_DELETE, task)
        self._check_precondition(task, if_match)
        task.deleted_at = datetime.now(UTC)
        task.version += 1
        await audit.record(
            self._s,
            action="task.deleted",
            resource_type="task",
            resource_id=task.id,
            project_id=task.project_id,
            actor=actor,
            after={"deleted_at": task.deleted_at.isoformat()},
        )

    # ---- helpers ----
    def _check_precondition(self, task: Task, if_match: str | None) -> None:
        if if_match is None:
            raise PreconditionRequiredError(
                "If-Match header is required for this operation (optimistic concurrency)."
            )
        if if_match.strip().strip('"') not in {str(task.version), "*"}:
            raise PreconditionFailedError(
                "The task was modified by someone else. Reload and retry.",
                details={"current_version": task.version},
            )

    async def _require_task(self, task_id: uuid.UUID) -> Task:
        task = await self._repo.get(task_id)
        if task is None or task.is_deleted:
            raise NotFoundError("Task not found.")
        return task

    async def _require_project(self, project_id: uuid.UUID) -> Project:
        project = await self._projects.get(project_id)
        if project is None:
            raise NotFoundError("Project not found.")
        return project


def _pick_state(states: Sequence[WorkflowState], state_id: uuid.UUID | None) -> WorkflowState | None:
    if state_id is not None:
        return next((s for s in states if s.id == state_id), None)
    return next((s for s in states if s.is_default), states[0])


def _audit_snapshot(task: Task) -> dict[str, object]:
    return audit.snapshot(
        task,
        ("title", "state_id", "priority", "assignee_id", "due_date", "estimate_hours", "completed_at", "deleted_at"),
    )


def _as_uuid(value: object) -> uuid.UUID | None:
    if value in (None, ""):
        return None
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _as_int(value: object) -> int | None:
    return None if value in (None, "") else int(value)  # type: ignore[arg-type]


def _as_str(value: object) -> str | None:
    return None if value in (None, "") else str(value)
