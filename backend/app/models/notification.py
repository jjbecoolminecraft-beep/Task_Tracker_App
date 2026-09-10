"""In-app notifications (spec §3.1, F-10).

Structured, not pre-rendered: `kind` + a small denormalised `context` blob
(actor display name, task ref, comment snippet) so the item stays meaningful even
after the source task is deleted, while the UI renders the sentence per locale.

Retention: pruned after 90 days by the nightly job (see docs/compliance/
retention-and-deletion.md).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid_pk


class NotificationKind(StrEnum):
    TASK_ASSIGNED = "task.assigned"
    COMMENT_MENTION = "comment.mention"
    COMMENT_ADDED = "comment.added"
    TASK_DUE_SOON = "task.due_soon"


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_recipient_unread", "recipient_id", "read_at"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    recipient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    task_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id"))
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    context: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    @property
    def is_read(self) -> bool:
        return self.read_at is not None
