from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.common import ApiModel
from app.schemas.user import UserRef


class TaskOut(ApiModel):
    id: uuid.UUID
    project_id: uuid.UUID
    project_key: str | None = None
    parent_task_id: uuid.UUID | None = None
    seq: int
    ref: str | None = None  # "{project_key}-{seq}", filled by the service
    title: str
    description: str | None = None
    state_id: uuid.UUID
    state_name: str | None = None
    state_category: str | None = None
    priority: int = Field(ge=1, le=5)
    assignee: UserRef | None = None
    reporter: UserRef | None = None
    due_date: date | None = None
    estimate_hours: float | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    version: int
    subtask_count: int | None = None


class TaskDetailOut(TaskOut):
    subtasks: list[TaskOut] = []


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    state_id: uuid.UUID | None = None  # defaults to the project's default state
    priority: int = Field(default=3, ge=1, le=5)
    assignee_id: uuid.UUID | None = None
    parent_task_id: uuid.UUID | None = None
    due_date: date | None = None
    estimate_hours: float | None = Field(default=None, ge=0, le=9999)


class TaskUpdate(BaseModel):
    """All optional — PATCH semantics. Requires If-Match (spec §5.2)."""

    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    state_id: uuid.UUID | None = None
    priority: int | None = Field(default=None, ge=1, le=5)
    assignee_id: uuid.UUID | None = None
    due_date: date | None = None
    estimate_hours: float | None = Field(default=None, ge=0, le=9999)
    clear_assignee: bool = False
    clear_due_date: bool = False


class CommentOut(ApiModel):
    id: uuid.UUID
    task_id: uuid.UUID
    author: UserRef | None = None
    body: str
    mentioned_user_ids: list[uuid.UUID] = []
    created_at: datetime


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=10000)
    mentioned_user_ids: list[uuid.UUID] = []
