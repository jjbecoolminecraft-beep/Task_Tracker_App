"""Project dashboard use-case (spec F-22).

Reporting is aggregated to project / team level (spec §8.4.2). There is no
per-person breakdown anywhere in this service; the only individual-level figure
is ``contributor_count`` — a headcount, not a ranking. Any future breakdown that
would resolve to fewer than ``MIN_GROUP`` people must be suppressed.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.domain.enums import Action, WorkflowCategory
from app.models.project import Project
from app.repositories.dashboards import DashboardRepository
from app.repositories.projects import ProjectRepository
from app.schemas.dashboard import (
    PriorityBucket,
    ProjectDashboard,
    StateBucket,
    WeekBucket,
)
from app.services.authorization import AuthZ

MIN_GROUP = 5  # spec §8.4.2: breakdowns resolving to fewer people are suppressed
THROUGHPUT_WEEKS = 8


class DashboardService:
    def __init__(self, session: AsyncSession, authz: AuthZ) -> None:
        self._s = session
        self._authz = authz
        self._repo = DashboardRepository(session)
        self._projects = ProjectRepository(session)

    async def project_dashboard(self, project_id: uuid.UUID) -> ProjectDashboard:
        project = await self._projects.get(project_id)
        if project is None:
            raise NotFoundError("Project not found.")
        await self._authz.require(Action.PROJECT_READ, project)

        return await self._build(project)

    async def _build(self, project: Project) -> ProjectDashboard:
        now = datetime.now(UTC)
        today = now.date()
        # Window covers the current ISO week plus the previous THROUGHPUT_WEEKS-1.
        since = now - timedelta(weeks=THROUGHPUT_WEEKS)
        series_start = now - timedelta(weeks=THROUGHPUT_WEEKS - 1)

        states = await self._projects.list_workflow_states(project.id)
        agg = await self._repo.aggregates(project.id, today=today, since=since)

        done_ids = {s.id for s in states if s.category == WorkflowCategory.DONE.value}
        total = sum(agg.by_state.values())
        done = sum(n for sid, n in agg.by_state.items() if sid in done_ids)

        by_state = [
            StateBucket(
                state_id=s.id,
                name=s.name,
                category=WorkflowCategory(s.category),
                position=s.position,
                count=agg.by_state.get(s.id, 0),
            )
            for s in sorted(states, key=lambda x: x.position)
        ]
        by_priority = [PriorityBucket(priority=p, count=agg.by_priority.get(p, 0)) for p in range(1, 6)]
        throughput = self._weekly_series(agg.completed_by_week, series_start)

        return ProjectDashboard(
            total=total,
            open=total - done,
            done=done,
            overdue=agg.overdue,
            unassigned=agg.unassigned_open,
            contributor_count=agg.contributor_count,
            avg_open_age_days=agg.avg_open_age_days,
            by_state=by_state,
            by_priority=by_priority,
            throughput=throughput,
        )

    @staticmethod
    def _weekly_series(completed: dict[str, int], since: datetime) -> list[WeekBucket]:
        """Zero-filled, chronological list of the last THROUGHPUT_WEEKS ISO weeks."""
        buckets: list[WeekBucket] = []
        cursor = since.date()
        for _ in range(THROUGHPUT_WEEKS):
            iso_year, iso_week, _ = cursor.isocalendar()
            key = f"{iso_year}-W{iso_week:02d}"
            buckets.append(
                WeekBucket(
                    week=key,
                    label=f"{cursor:%b} {cursor.day}",
                    completed=completed.get(key, 0),
                )
            )
            cursor += timedelta(weeks=1)
        return buckets
