"""Task (and self-referencing Subtask) plus Guest task shares (spec §3.2, §3.3)."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, uuid_pk


class Task(Base, TimestampMixin):
    __tablename__ = "tasks"
    __table_args__ = (
        UniqueConstraint("project_id", "seq", name="task_seq_unique"),
        CheckConstraint("priority between 1 and 5", name="priority_range"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True
    )
    # Subtasks reuse this table via parent_task_id. Depth capped at 2 in the
    # service layer (spec §3.3) to keep queries and UI bounded.
    parent_task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id"), index=True
    )
    seq: Mapped[int] = mapped_column(nullable=False)  # human ref: {project.key}-{seq}

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    state_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_states.id"), nullable=False, index=True
    )
    priority: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("3")
    )
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    reporter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    due_date: Mapped[date | None] = mapped_column(Date)
    estimate_hours: Mapped[float | None] = mapped_column(Numeric(6, 2))

    # Maintained by a DB trigger (spec §5.4 "Search vector refresh — on write").
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR)

    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    # ETag source for optimistic concurrency (spec §5.2, If-Match / 412).
    version: Mapped[int] = mapped_column(nullable=False, server_default=text("1"))

    project: Mapped["Project"] = relationship(lazy="raise")  # noqa: F821
    state: Mapped["WorkflowState"] = relationship(lazy="raise")  # noqa: F821
    # Subtasks are queried explicitly (parent_task_id == id) rather than via a
    # self-referential relationship — keeps the mapper config simple and the
    # depth-2 cap lives in the service layer anyway.
    comments: Mapped[list["Comment"]] = relationship(  # noqa: F821
        back_populates="task", lazy="raise", cascade="all, delete-orphan"
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


class TaskShare(Base, TimestampMixin):
    """Guest access: a named internal user granted access to one explicit task."""

    __tablename__ = "task_shares"
    __table_args__ = (
        UniqueConstraint("task_id", "user_id", name="task_share_unique"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    shared_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
