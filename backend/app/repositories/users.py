from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, user_id: uuid.UUID) -> User | None:
        return await self._s.get(User, user_id)

    async def get_by_entra_oid(self, oid: uuid.UUID) -> User | None:
        return (await self._s.execute(select(User).where(User.entra_object_id == oid))).scalar_one_or_none()

    async def list_active(self, limit: int = 500) -> Sequence[User]:
        return (
            (
                await self._s.execute(
                    select(User).where(User.is_active.is_(True)).order_by(User.display_name).limit(limit)
                )
            )
            .scalars()
            .all()
        )

    async def get_many(self, ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, User]:
        if not ids:
            return {}
        rows = (await self._s.execute(select(User).where(User.id.in_(set(ids))))).scalars().all()
        return {u.id: u for u in rows}
