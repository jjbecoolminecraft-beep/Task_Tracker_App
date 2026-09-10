"""Notification creation and the personal notification feed (spec F-10).

`emit_*` helpers are called from the task and comment services, inside the same
transaction as the change — a notification and the event that caused it commit
together. No notification is ever created for an action the recipient took
themselves.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models.notification import Notification, NotificationKind
from app.models.task import Task
from app.models.user import User
from app.repositories.notifications import NotificationRepository
from app.repositories.users import UserRepository
from app.schemas.notification import NotificationOut

MAX_LIMIT = 100

# `@[Display Name](uuid)` -> "@Display Name" for human-readable snippets/digests.
_MENTION_MARKUP = re.compile(r"@\[([^\]]+)\]\([0-9a-fA-F-]{36}\)")


def _plain(text: str) -> str:
    return _MENTION_MARKUP.sub(r"@\1", text).strip()


class NotificationService:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session
        self._repo = NotificationRepository(session)
        self._users = UserRepository(session)

    # ---- creation (called from other services) ----

    def _add(
        self,
        *,
        recipient_id: uuid.UUID,
        kind: NotificationKind,
        actor: User | None,
        task: Task,
        context_extra: dict[str, object] | None = None,
    ) -> None:
        context: dict[str, object] = {
            "actor_name": actor.display_name if actor else None,
            "task_ref": context_extra.pop("task_ref", None) if context_extra else None,
            "task_title": task.title,
        }
        if context_extra:
            context.update(context_extra)
        self._repo.add(
            Notification(
                recipient_id=recipient_id,
                kind=kind.value,
                actor_id=actor.id if actor else None,
                task_id=task.id,
                project_id=task.project_id,
                context=context,
            )
        )

    async def emit_task_assigned(
        self, *, task: Task, task_ref: str, assignee_id: uuid.UUID, actor: User
    ) -> None:
        if assignee_id == actor.id:
            return
        self._add(
            recipient_id=assignee_id,
            kind=NotificationKind.TASK_ASSIGNED,
            actor=actor,
            task=task,
            context_extra={"task_ref": task_ref},
        )

    async def emit_comment(
        self,
        *,
        task: Task,
        task_ref: str,
        actor: User,
        mentioned_user_ids: set[uuid.UUID],
        snippet: str,
    ) -> None:
        recipients: dict[uuid.UUID, NotificationKind] = {}
        for uid in mentioned_user_ids:
            if uid != actor.id:
                recipients[uid] = NotificationKind.COMMENT_MENTION
        # The assignee also hears about new comments, unless they wrote it or were
        # already @mentioned (mention wins).
        if task.assignee_id and task.assignee_id != actor.id:
            recipients.setdefault(task.assignee_id, NotificationKind.COMMENT_ADDED)

        clean = _plain(snippet)[:140]
        for uid, kind in recipients.items():
            self._add(
                recipient_id=uid,
                kind=kind,
                actor=actor,
                task=task,
                context_extra={"task_ref": task_ref, "snippet": clean},
            )

    # ---- personal feed ----

    async def _decorate(self, rows: list[Notification]) -> list[NotificationOut]:
        actor_ids = {n.actor_id for n in rows if n.actor_id}
        actors = await self._users.get_many(list(actor_ids))
        out: list[NotificationOut] = []
        for n in rows:
            row = NotificationOut.model_validate(n)
            if n.actor_id and (a := actors.get(n.actor_id)):
                row.actor_name = a.display_name
            elif isinstance(n.context.get("actor_name"), str):
                row.actor_name = str(n.context["actor_name"])
            row.task_ref = n.context.get("task_ref") if isinstance(n.context.get("task_ref"), str) else None
            row.snippet = n.context.get("snippet") if isinstance(n.context.get("snippet"), str) else None
            row.is_read = n.read_at is not None
            out.append(row)
        return out

    async def feed(
        self,
        user: User,
        *,
        unread_only: bool,
        limit: int | None,
        before: datetime | None,
    ) -> list[NotificationOut]:
        capped = min(limit or 30, MAX_LIMIT)
        rows = list(await self._repo.list_for(user.id, unread_only=unread_only, limit=capped, before=before))
        return await self._decorate(rows)

    async def unread_count(self, user: User) -> int:
        return await self._repo.unread_count(user.id)

    async def mark_read(self, user: User, notification_id: uuid.UUID) -> None:
        n = await self._repo.get_for(user.id, notification_id)
        if n is None:
            raise NotFoundError("Notification not found.")
        if n.read_at is None:
            n.read_at = datetime.now(UTC)

    async def mark_all_read(self, user: User) -> int:
        return await self._repo.mark_all_read(user.id)
