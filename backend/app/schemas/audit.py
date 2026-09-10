from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from app.schemas.common import ApiModel


class AuditEventOut(ApiModel):
    id: int
    occurred_at: datetime
    actor_id: uuid.UUID | None = None
    actor_upn: str | None = None
    action: str
    resource_type: str
    resource_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    request_id: uuid.UUID | None = None
