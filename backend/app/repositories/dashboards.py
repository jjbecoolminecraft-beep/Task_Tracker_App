"""Read-only aggregation queries for the project dashboard (spec F-22).

No query here groups by ``assignee_id`` — per-person reporting is excluded at the
data-access level (spec §8.4.1), not just hidden in the UI.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task
from app.models.workflow_state import WorkflowState


@dataclass(slots=True)
class DashboardAggregates:
    by_state: dict[uuid.UUID, int] = field(default_factory=dict)
    by_priority: dict[int, int] = field(default_factory=dict)
    overdue: int = 0
    unassigned_open: int = 0
    contributor_count: int = 0
    avg_open_age_days: float | None = None
    completed_by_week: dict[str, int] = field(default_factory=dict)


class DashboardRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def aggregates(self, project_id: uuid.UUID, *, today: date, since: datetime) -> DashboardAggregates:
        agg = DashboardAggregates()
        base = Task.project_id == project_id
        alive = Task.deleted_at.is_(None)

        done_state_ids = select(WorkflowState.id).where(
            WorkflowState.project_id == project_id,
            WorkflowState.category == "done",
        )

        by_state = (
            await self._s.execute(
                select(Task.state_id, func.count()).where(base, alive).group_by(Task.state_id)
            )
        ).tuples()
        agg.by_state = dict(by_state.all())

        by_priority = (
            await self._s.execute(
                select(Task.priority, func.count()).where(base, alive).group_by(Task.priority)
            )
        ).tuples()
        agg.by_priority = dict(by_priority.all())

        agg.overdue = int(
            await self._s.scalar(
                select(func.count())
                .select_from(Task)
                .where(
                    base,
                    alive,
                    Task.due_date.is_not(None),
                    Task.due_date < today,
                    Task.state_id.not_in(done_state_ids),
                )
            )
            or 0
        )

        agg.unassigned_open = int(
            await self._s.scalar(
                select(func.count())
                .select_from(Task)
                .where(base, alive, Task.assignee_id.is_(None), Task.state_id.not_in(done_state_ids))
            )
            or 0
        )

        agg.contributor_count = int(
            await self._s.scalar(
                select(func.count(func.distinct(Task.assignee_id))).where(
                    base, alive, Task.assignee_id.is_not(None)
                )
            )
            or 0
        )

        avg_age = await self._s.scalar(
            select(func.avg(func.extract("epoch", func.now() - Task.created_at))).where(
                base, alive, Task.state_id.not_in(done_state_ids)
            )
        )
        agg.avg_open_age_days = round(float(avg_age) / 86400, 1) if avg_age is not None else None

        week = func.to_char(Task.completed_at, 'IYYY"-W"IW')
        completed = (
            await self._s.execute(
                select(week, func.count())
                .where(base, alive, Task.completed_at.is_not(None), Task.completed_at >= since)
                .group_by(week)
            )
        ).tuples()
        agg.completed_by_week = dict(completed.all())

        return agg
