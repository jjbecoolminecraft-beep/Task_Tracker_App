"""Per-project workflow states (spec §3.3).

Not an enum. Engineering wants "In Review"; Marketing wants "Awaiting Approval".
Each row carries a coarse ``category`` so the board, completion checks and
reporting work without hardcoding labels.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import WorkflowCategory
from app.models.base import Base, TimestampMixin, uuid_pk


class WorkflowState(Base, TimestampMixin):
    __tablename__ = "workflow_states"
    __table_args__ = (UniqueConstraint("project_id", "name", name="workflow_state_unique_name"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    category: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text(f"'{WorkflowCategory.BACKLOG.value}'")
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

    project: Mapped[Project] = relationship(  # noqa: F821
        back_populates="workflow_states", lazy="raise"
    )

    @property
    def is_done(self) -> bool:
        return self.category == WorkflowCategory.DONE.value
