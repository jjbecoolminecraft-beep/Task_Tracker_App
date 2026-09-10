from __future__ import annotations

import uuid

from pydantic import BaseModel

from app.schemas.common import ApiModel


class DevUserOut(ApiModel):
    """A seeded identity offered on the dev login screen."""

    id: uuid.UUID
    display_name: str
    upn: str
    department: str | None = None
    roles_summary: list[str] = []


class DevLoginRequest(BaseModel):
    user_id: uuid.UUID


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"  # noqa: S105 - not a secret, the scheme name
    expires_in: int


class SessionRole(BaseModel):
    role: str
    scope_type: str
    scope_id: uuid.UUID | None = None
    scope_label: str | None = None


class SessionInfo(ApiModel):
    id: uuid.UUID
    display_name: str
    upn: str
    department: str | None = None
    roles: list[SessionRole] = []
