from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.comment import Comment


class CommentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def list_for_task(self, task_id: uuid.UUID) -> Sequence[Comment]:
        return (
            (
                await self._s.execute(
                    select(Comment)
                    .where(Comment.task_id == task_id)
                    .order_by(Comment.created_at)
                )
            )
            .scalars()
            .all()
        )

    def add(self, comment: Comment) -> None:
        self._s.add(comment)
