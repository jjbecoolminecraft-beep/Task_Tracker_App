from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy import Select, and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import Cursor, Page, clamp_limit
from app.models.task import Task

# Sortable columns → (column, direction). Every sort is made total by appending id.
_SORTS: dict[str, tuple[str, str]] = {
    "created_at": ("created_at", "desc"),
    "updated_at": ("updated_at", "desc"),
    "due_date": ("due_date", "asc"),
    "priority": ("priority", "asc"),
    "seq": ("seq", "desc"),
}


@dataclass(slots=True)
class TaskFilter:
    project_ids: Sequence[uuid.UUID]
    # Hard allow-list of task ids (Guest scope: only explicitly shared tasks).
    task_ids: Sequence[uuid.UUID] | None = None
    state_id: uuid.UUID | None = None
    assignee_id: uuid.UUID | None = None
    priority: int | None = None
    parent_task_id: uuid.UUID | None = None
    top_level_only: bool = False
    include_deleted: bool = False
    due_before: date | None = None
    unassigned: bool = False
    sort: str = "created_at"
    search: str | None = None


@dataclass(slots=True)
class TaskListResult:
    items: list[Task] = field(default_factory=list)
    next_cursor: str | None = None


class TaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, task_id: uuid.UUID) -> Task | None:
        return await self._s.get(Task, task_id)

    async def next_seq(self, project_id: uuid.UUID) -> int:
        """Atomically bump the per-project counter and return the new value."""
        from app.models.project import Project

        value = await self._s.scalar(
            select(Project.task_seq).where(Project.id == project_id).with_for_update()
        )
        new_value = int(value or 0) + 1
        await self._s.execute(update(Project).where(Project.id == project_id).values(task_seq=new_value))
        return new_value

    def add(self, task: Task) -> None:
        self._s.add(task)

    async def list_subtasks(self, parent_id: uuid.UUID) -> Sequence[Task]:
        return (
            (
                await self._s.execute(
                    select(Task)
                    .where(Task.parent_task_id == parent_id, Task.deleted_at.is_(None))
                    .order_by(Task.seq)
                )
            )
            .scalars()
            .all()
        )

    async def count_open_by_state(self, project_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, int]:
        if not project_ids:
            return {}
        rows = (
            await self._s.execute(
                select(Task.state_id, func.count())
                .where(Task.project_id.in_(set(project_ids)), Task.deleted_at.is_(None))
                .group_by(Task.state_id)
            )
        ).tuples()
        return dict(rows.all())

    def _base_query(self, f: TaskFilter) -> Select[tuple[Task]]:
        stmt = select(Task).where(Task.project_id.in_(set(f.project_ids)))
        if f.task_ids is not None:
            stmt = stmt.where(Task.id.in_(set(f.task_ids)))
        if not f.include_deleted:
            stmt = stmt.where(Task.deleted_at.is_(None))
        if f.state_id:
            stmt = stmt.where(Task.state_id == f.state_id)
        if f.assignee_id:
            stmt = stmt.where(Task.assignee_id == f.assignee_id)
        if f.unassigned:
            stmt = stmt.where(Task.assignee_id.is_(None))
        if f.priority:
            stmt = stmt.where(Task.priority == f.priority)
        if f.due_before:
            stmt = stmt.where(Task.due_date.is_not(None), Task.due_date <= f.due_before)
        if f.parent_task_id is not None:
            stmt = stmt.where(Task.parent_task_id == f.parent_task_id)
        elif f.top_level_only:
            stmt = stmt.where(Task.parent_task_id.is_(None))
        if f.search:
            stmt = stmt.where(Task.search_vector.op("@@")(func.websearch_to_tsquery("english", f.search)))
        return stmt

    async def list(self, f: TaskFilter, *, limit: int | None, cursor: str | None) -> TaskListResult:
        page_size = clamp_limit(limit)
        stmt = self._base_query(f)

        col_name, direction = _SORTS.get(f.sort, _SORTS["created_at"])
        sort_col = getattr(Task, col_name)
        descending = direction == "desc"

        order = [sort_col.desc(), Task.id.desc()] if descending else [sort_col.asc(), Task.id.asc()]
        stmt = stmt.order_by(*order)

        if cursor:
            cur = Cursor.decode(cursor)
            sort_value = _coerce(cur.sort_value, sort_col.type.python_type)
            last_id = uuid.UUID(cur.last_id)
            if descending:
                stmt = stmt.where(
                    or_(
                        sort_col < sort_value,
                        and_(sort_col == sort_value, Task.id < last_id),
                    )
                )
            else:
                stmt = stmt.where(
                    or_(
                        sort_col > sort_value,
                        and_(sort_col == sort_value, Task.id > last_id),
                    )
                )

        rows = list((await self._s.execute(stmt.limit(page_size + 1))).scalars().all())
        next_cursor: str | None = None
        if len(rows) > page_size:
            rows = rows[:page_size]
            tail = rows[-1]
            next_cursor = Cursor(sort_value=getattr(tail, col_name), last_id=str(tail.id)).encode()
        return TaskListResult(items=rows, next_cursor=next_cursor)

    async def paginate_page(self, f: TaskFilter, *, limit: int | None, cursor: str | None) -> Page:
        res = await self.list(f, limit=limit, cursor=cursor)
        return Page(items=list(res.items), next_cursor=res.next_cursor)


def _coerce(value: object, py_type: type) -> object:
    if value is None:
        return None
    if py_type is datetime and isinstance(value, str):
        return datetime.fromisoformat(value)
    if py_type is date and isinstance(value, str):
        return date.fromisoformat(value)
    return value
