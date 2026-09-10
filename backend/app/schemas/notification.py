from __future__ import annotations

import uuid
from datetime import datetime

from app.schemas.common import ApiModel


class NotificationOut(ApiModel):
    id: uuid.UUID
    kind: str
    task_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    actor_name: str | None = None
    task_ref: str | None = None
    snippet: str | None = None
    is_read: bool = False
    created_at: datetime


class UnreadCount(ApiModel):
    unread: int
