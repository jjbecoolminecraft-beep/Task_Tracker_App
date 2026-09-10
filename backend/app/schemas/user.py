from __future__ import annotations

import uuid

from app.schemas.common import ApiModel


class UserOut(ApiModel):
    id: uuid.UUID
    display_name: str
    upn: str
    department: str | None = None
    is_active: bool


class UserRef(ApiModel):
    """Compact user reference embedded in tasks/comments."""

    id: uuid.UUID
    display_name: str
