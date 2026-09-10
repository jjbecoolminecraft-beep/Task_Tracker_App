"""CSV / JSON export and CSV import of a project's tasks (spec F-12).

Export is audited and (in Azure) alerted — spec §8.4.6: bulk exports are a
co-determination concern. Import runs synchronously with a hard row cap; large
imports belong on the worker (spec §5.4 "Import processor — off the request
path"), which is not built yet.
"""

from __future__ import annotations

import csv
import io
import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationError
from app.domain.enums import Action
from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.repositories.projects import ProjectRepository
from app.repositories.tasks import TaskFilter, TaskRepository
from app.repositories.users import UserRepository
from app.schemas.import_export import ImportResult, ImportRowError
from app.schemas.task import TaskCreate
from app.services import audit
from app.services.authorization import AuthZ
from app.services.tasks import TaskService

EXPORT_COLUMNS = [
    "ref",
    "title",
    "description",
    "state",
    "category",
    "priority",
    "assignee_upn",
    "reporter_upn",
    "due_date",
    "estimate_hours",
    "parent_ref",
    "created_at",
    "completed_at",
]

MAX_IMPORT_ROWS = 500


class ImportExportService:
    def __init__(self, session: AsyncSession, authz: AuthZ) -> None:
        self._s = session
        self._authz = authz
        self._projects = ProjectRepository(session)
        self._tasks = TaskRepository(session)
        self._users = UserRepository(session)

    async def _require_project(self, project_id: uuid.UUID) -> Project:
        project = await self._projects.get(project_id)
        if project is None:
            raise NotFoundError("Project not found.")
        return project

    async def _rows(self, project: Project) -> list[dict[str, object]]:
        states = {s.id: s for s in await self._projects.list_workflow_states(project.id)}
        result = await self._tasks.list(
            TaskFilter(project_ids=[project.id], top_level_only=False, sort="seq"),
            limit=200,
            cursor=None,
        )
        tasks = list(result.items)
        # follow the cursor to gather every task (projects are small; no UI paging here)
        while result.next_cursor:
            result = await self._tasks.list(
                TaskFilter(project_ids=[project.id], top_level_only=False, sort="seq"),
                limit=200,
                cursor=result.next_cursor,
            )
            tasks.extend(result.items)

        by_id = {t.id: t for t in tasks}
        user_ids = {uid for t in tasks for uid in (t.assignee_id, t.reporter_id) if uid}
        users = await self._users.get_many(list(user_ids))

        rows: list[dict[str, object]] = []
        for t in sorted(tasks, key=lambda x: x.seq):
            state = states.get(t.state_id)
            parent = by_id.get(t.parent_task_id) if t.parent_task_id else None
            rows.append(
                {
                    "ref": f"{project.key}-{t.seq}",
                    "title": t.title,
                    "description": t.description or "",
                    "state": state.name if state else "",
                    "category": state.category if state else "",
                    "priority": t.priority,
                    "assignee_upn": users[t.assignee_id].upn if t.assignee_id in users else "",
                    "reporter_upn": users[t.reporter_id].upn if t.reporter_id in users else "",
                    "due_date": t.due_date.isoformat() if t.due_date else "",
                    "estimate_hours": float(t.estimate_hours) if t.estimate_hours is not None else "",
                    "parent_ref": f"{project.key}-{parent.seq}" if parent else "",
                    "created_at": t.created_at.isoformat(),
                    "completed_at": t.completed_at.isoformat() if t.completed_at else "",
                }
            )
        return rows

    async def export(self, project_id: uuid.UUID, *, fmt: str, actor: User) -> tuple[str, str, str]:
        """Return (content, media_type, filename)."""
        project = await self._require_project(project_id)
        await self._authz.require(Action.PROJECT_READ, project)
        rows = await self._rows(project)

        await audit.record(
            self._s,
            action="project.exported",
            resource_type="project",
            resource_id=project.id,
            project_id=project.id,
            actor=actor,
            after={"format": fmt, "task_count": len(rows)},
        )

        stamp = date.today().isoformat()
        if fmt == "json":
            import json

            return (
                json.dumps({"project": project.key, "tasks": rows}, indent=2),
                "application/json",
                f"{project.key}-tasks-{stamp}.json",
            )

        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=EXPORT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
        return buf.getvalue(), "text/csv", f"{project.key}-tasks-{stamp}.csv"

    async def import_csv(self, project_id: uuid.UUID, *, content: bytes, actor: User) -> ImportResult:
        project = await self._require_project(project_id)
        await self._authz.require(Action.TASK_CREATE, project)

        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValidationError("File must be UTF-8 encoded CSV.") from exc

        reader = list(csv.DictReader(io.StringIO(text)))
        if not reader:
            raise ValidationError("CSV has no data rows.")
        if len(reader) > MAX_IMPORT_ROWS:
            raise ValidationError(
                f"Import is limited to {MAX_IMPORT_ROWS} rows; split the file or use the API."
            )

        states = await self._projects.list_workflow_states(project.id)
        state_by_name = {s.name.lower(): s for s in states}
        default_state = next((s for s in states if s.is_default), states[0] if states else None)
        if default_state is None:
            raise ValidationError("Project has no workflow states.")

        # resolve upns -> user ids once
        upns = {
            (r.get("assignee_upn") or "").strip().lower()
            for r in reader
            if (r.get("assignee_upn") or "").strip()
        }
        users_by_upn: dict[str, uuid.UUID] = {}
        if upns:
            rows = (await self._s.execute(select(User.id, User.upn).where(User.upn.in_(upns)))).all()
            users_by_upn = {upn.lower(): uid for uid, upn in rows}

        svc = TaskService(self._s, self._authz)
        created: list[str] = []
        errors: list[ImportRowError] = []

        for i, raw in enumerate(reader, start=2):  # row 1 is the header
            title = (raw.get("title") or "").strip()
            if not title:
                errors.append(ImportRowError(row=i, reason="missing title"))
                continue

            state = state_by_name.get((raw.get("state") or "").strip().lower(), default_state)

            priority_raw = (raw.get("priority") or "3").strip()
            try:
                priority = int(priority_raw)
            except ValueError:
                errors.append(ImportRowError(row=i, reason=f"invalid priority '{priority_raw}'"))
                continue
            if priority not in range(1, 6):
                errors.append(ImportRowError(row=i, reason="priority must be 1..5"))
                continue

            assignee_id: uuid.UUID | None = None
            upn = (raw.get("assignee_upn") or "").strip().lower()
            if upn:
                assignee_id = users_by_upn.get(upn)
                if assignee_id is None:
                    errors.append(ImportRowError(row=i, reason=f"unknown assignee '{upn}'"))
                    continue

            due: date | None = None
            due_raw = (raw.get("due_date") or "").strip()
            if due_raw:
                try:
                    due = date.fromisoformat(due_raw)
                except ValueError:
                    errors.append(ImportRowError(row=i, reason=f"invalid due_date '{due_raw}'"))
                    continue

            parent_id: uuid.UUID | None = None
            parent_ref = (raw.get("parent_ref") or "").strip()
            if parent_ref:
                try:
                    parent_seq = int(parent_ref.rsplit("-", 1)[1])
                except (IndexError, ValueError):
                    errors.append(ImportRowError(row=i, reason=f"bad parent_ref '{parent_ref}'"))
                    continue
                parent = (
                    await self._s.execute(
                        select(Task).where(
                            Task.project_id == project.id,
                            Task.seq == parent_seq,
                            Task.deleted_at.is_(None),
                        )
                    )
                ).scalar_one_or_none()
                if parent is None:
                    errors.append(ImportRowError(row=i, reason=f"parent {parent_ref} not found"))
                    continue
                if parent.parent_task_id is not None:
                    errors.append(ImportRowError(row=i, reason=f"parent {parent_ref} is itself a subtask"))
                    continue
                parent_id = parent.id

            try:
                task = await svc.create(
                    project.id,
                    TaskCreate(
                        title=title,
                        description=(raw.get("description") or "").strip() or None,
                        state_id=state.id,
                        priority=priority,
                        assignee_id=assignee_id,
                        due_date=due,
                        parent_task_id=parent_id,
                    ),
                    actor,
                )
                created.append(task.ref or "")
            except ValidationError as exc:
                errors.append(ImportRowError(row=i, reason=str(exc)))

        await audit.record(
            self._s,
            action="project.imported",
            resource_type="project",
            resource_id=project.id,
            project_id=project.id,
            actor=actor,
            after={"created": len(created), "skipped": len(errors)},
        )
        return ImportResult(created=len(created), refs=created, skipped=errors)
