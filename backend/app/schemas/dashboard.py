from __future__ import annotations

import uuid

from app.domain.enums import WorkflowCategory
from app.schemas.common import ApiModel


class StateBucket(ApiModel):
    state_id: uuid.UUID
    name: str
    category: WorkflowCategory
    position: int
    count: int


class PriorityBucket(ApiModel):
    priority: int
    count: int


class WeekBucket(ApiModel):
    week: str  # ISO year-week, e.g. "2026-W36"
    label: str  # short human label, e.g. "Sep 1"
    completed: int


class ProjectDashboard(ApiModel):
    """Aggregated project reporting (spec §4.2 F-22).

    Deliberately contains **no** per-person breakdown (spec §8.4.1): no
    throughput-per-assignee, no completion-rate ranking. Only project- and
    team-level figures. ``contributor_count`` is a scalar headcount, not a
    breakdown.
    """

    total: int
    open: int
    done: int
    overdue: int
    unassigned: int
    contributor_count: int
    avg_open_age_days: float | None

    by_state: list[StateBucket]
    by_priority: list[PriorityBucket]
    throughput: list[WeekBucket]
