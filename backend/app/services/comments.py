"""Comments with @mention resolution (spec F-07)."""

from __future__ import annotations

import re
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationError
from app.domain.enums import Action
from app.models.comment import Comment
from app.models.user import User
from app.repositories.comments import CommentRepository
from app.repositories.projects import ProjectRepository
from app.repositories.tasks import TaskRepository
from app.repositories.users import UserRepository
from app.schemas.task import CommentCreate, CommentOut
from app.schemas.user import UserRef
from app.services import audit
from app.services.authorization import AuthZ
from app.services.notifications import NotificationService

# Frontend inserts mentions as `@[Display Name](user-uuid)`.
_MENTION_RE = re.compile(r"@\[[^\]]+\]\(([0-9a-fA-F-]{36})\)")


class CommentService:
    def __init__(self, session: AsyncSession, authz: AuthZ) -> None:
        self._s = session
        self._authz = authz
        self._repo = CommentRepository(session)
        self._tasks = TaskRepository(session)
        self._projects = ProjectRepository(session)
        self._users = UserRepository(session)
        self._notify = NotificationService(session)

    async def list_for_task(self, task_id: uuid.UUID) -> list[CommentOut]:
        task = await self._tasks.get(task_id)
        if task is None or task.is_deleted:
            raise NotFoundError("Task not found.")
        await self._authz.require(Action.COMMENT_READ, task)
        comments = await self._repo.list_for_task(task_id)
        authors = await self._users.get_many([c.author_id for c in comments])
        out: list[CommentOut] = []
        for c in comments:
            row = CommentOut.model_validate(c)
            if (a := authors.get(c.author_id)) is not None:
                row.author = UserRef(id=a.id, display_name=a.display_name)
            out.append(row)
        return out

    async def create(self, task_id: uuid.UUID, payload: CommentCreate, actor: User) -> CommentOut:
        task = await self._tasks.get(task_id)
        if task is None or task.is_deleted:
            raise NotFoundError("Task not found.")
        await self._authz.require(Action.COMMENT_CREATE, task)

        mentioned = set(payload.mentioned_user_ids)
        mentioned.update(uuid.UUID(m) for m in _MENTION_RE.findall(payload.body))
        if mentioned:
            known = await self._users.get_many(list(mentioned))
            unknown = mentioned - known.keys()
            if unknown:
                raise ValidationError("One or more mentioned users are unknown.")

        comment = Comment(
            task_id=task_id,
            author_id=actor.id,
            body=payload.body,
            mentioned_user_ids=list(mentioned),
        )
        self._repo.add(comment)
        await self._s.flush()

        await audit.record(
            self._s,
            action="comment.created",
            resource_type="comment",
            resource_id=comment.id,
            project_id=task.project_id,
            actor=actor,
            after={"task_id": str(task_id), "mentions": len(mentioned)},
        )

        project = await self._projects.get(task.project_id)
        await self._notify.emit_comment(
            task=task,
            task_ref=f"{project.key}-{task.seq}" if project else str(task.seq),
            actor=actor,
            mentioned_user_ids=mentioned,
            snippet=payload.body,
        )
        # Email digest of these notifications is a worker job (app/workers/digest.py).

        row = CommentOut.model_validate(comment)
        row.author = UserRef(id=actor.id, display_name=actor.display_name)
        return row
