"""Project and ProjectMember (spec §3.1, §3.2)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import CITEXT, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import ProjectStatus, ProjectVisibility, Role
from app.models.base import Base, TimestampMixin, uuid_pk


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = uuid_pk()
    portfolio_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portfolios.id"), index=True
    )
    key: Mapped[str] = mapped_column(CITEXT(), unique=True, nullable=False)  # e.g. "MKTG"
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(4000))

    visibility: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text(f"'{ProjectVisibility.PRIVATE.value}'")
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text(f"'{ProjectStatus.ACTIVE.value}'")
    )

    # Per-project counter for human-readable task refs (MKTG-142). Incremented
    # inside the task-create transaction (spec §3.3, docs/adr/0005).
    task_seq: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    portfolio: Mapped["Portfolio | None"] = relationship(  # noqa: F821
        back_populates="projects", lazy="raise"
    )
    members: Mapped[list["ProjectMember"]] = relationship(
        back_populates="project", lazy="raise", cascade="all, delete-orphan"
    )
    workflow_states: Mapped[list["WorkflowState"]] = relationship(  # noqa: F821
        back_populates="project", lazy="raise", cascade="all, delete-orphan"
    )


class ProjectMember(Base, TimestampMixin):
    """A user's role within one project.

    ``entra_group_id`` binds membership to an Entra ID security group so access
    follows the HR/org lifecycle (spec §2.3, F-04). When set, ``user_id`` rows for
    that group are reconciled by the hourly Entra sync job.
    """

    __tablename__ = "project_members"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="project_member_unique"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    entra_group_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    role: Mapped[str] = mapped_column(String(30), nullable=False)  # Role value, project-scoped

    project: Mapped["Project"] = relationship(back_populates="members", lazy="raise")

    @property
    def role_enum(self) -> Role:
        return Role(self.role)
