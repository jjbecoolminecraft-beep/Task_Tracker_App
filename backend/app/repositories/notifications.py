from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification


class NotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    def add(self, notification: Notification) -> None:
        self._s.add(notification)

    async def list_for(
        self,
        recipient_id: uuid.UUID,
        *,
        unread_only: bool,
        limit: int,
        before: datetime | None,
    ) -> Sequence[Notification]:
        stmt = select(Notification).where(Notification.recipient_id == recipient_id)
        if unread_only:
            stmt = stmt.where(Notification.read_at.is_(None))
        if before is not None:
            stmt = stmt.where(Notification.created_at < before)
        stmt = stmt.order_by(Notification.created_at.desc()).limit(limit)
        return (await self._s.execute(stmt)).scalars().all()

    async def unread_count(self, recipient_id: uuid.UUID) -> int:
        return int(
            await self._s.scalar(
                select(func.count())
                .select_from(Notification)
                .where(
                    Notification.recipient_id == recipient_id,
                    Notification.read_at.is_(None),
                )
            )
            or 0
        )

    async def get_for(self, recipient_id: uuid.UUID, notification_id: uuid.UUID) -> Notification | None:
        return (
            await self._s.execute(
                select(Notification).where(
                    Notification.id == notification_id,
                    Notification.recipient_id == recipient_id,
                )
            )
        ).scalar_one_or_none()

    async def mark_all_read(self, recipient_id: uuid.UUID) -> int:
        result = await self._s.execute(
            update(Notification)
            .where(
                Notification.recipient_id == recipient_id,
                Notification.read_at.is_(None),
            )
            .values(read_at=datetime.now(UTC))
            .execution_options(synchronize_session=False)
        )
        return int(result.rowcount)  # type: ignore[attr-defined]
