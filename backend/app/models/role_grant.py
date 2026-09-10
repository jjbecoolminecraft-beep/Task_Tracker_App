"""Global and portfolio-scoped role grants (spec §2.2).

Project-scoped roles live in ``project_members``; task-scoped Guest access lives
in ``task_shares``. This table covers the rest:

* ``scope_type = 'global'``  → System Admin, Auditor  (scope_id is NULL)
* ``scope_type = 'portfolio'`` → Portfolio Owner       (scope_id = portfolio id)
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import Role
from app.models.base import Base, TimestampMixin, uuid_pk


class RoleGrant(Base, TimestampMixin):
    __tablename__ = "role_grants"
    __table_args__ = (
        UniqueConstraint("user_id", "role", "scope_type", "scope_id", name="role_grant_unique"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(20), nullable=False)  # global | portfolio
    scope_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)

    @property
    def role_enum(self) -> Role:
        return Role(self.role)
