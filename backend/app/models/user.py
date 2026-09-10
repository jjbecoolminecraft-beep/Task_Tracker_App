"""Users, mirrored from Entra ID. Never a credential store (spec §2.1, §3.2)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, text
from sqlalchemy.dialects.postgresql import CITEXT, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    entra_object_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, nullable=False)
    upn: Mapped[str] = mapped_column(CITEXT(), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    department: Mapped[str | None] = mapped_column(String(200))

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Leaver handling (spec §8.3): 90 days after Entra deactivation the record is
    # pseudonymized — display_name becomes "Former employee #NNNN", FKs stay intact.
    is_pseudonymized: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<User {self.id}>"
