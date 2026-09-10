"""Personal notification feed (spec F-10). Everything here is scoped to the
caller — a user only ever sees and mutates their own notifications.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Query, Response, status

from app.api.v1.deps import SessionDep
from app.core.auth import CurrentUser
from app.schemas.notification import NotificationOut, UnreadCount
from app.services.notifications import NotificationService

router = APIRouter(prefix="/me/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
async def list_notifications(
    session: SessionDep,
    user: CurrentUser,
    unread: bool = Query(default=False),
    limit: int = Query(default=30, ge=1, le=100),
    before: datetime | None = Query(default=None, description="Return items created before this"),
) -> list[NotificationOut]:
    return await NotificationService(session).feed(user, unread_only=unread, limit=limit, before=before)


@router.get("/unread-count", response_model=UnreadCount)
async def unread_count(session: SessionDep, user: CurrentUser) -> UnreadCount:
    return UnreadCount(unread=await NotificationService(session).unread_count(user))


@router.post("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_read(notification_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> Response:
    await NotificationService(session).mark_read(user, notification_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/read-all", response_model=UnreadCount)
async def mark_all_read(session: SessionDep, user: CurrentUser) -> UnreadCount:
    await NotificationService(session).mark_all_read(user)
    return UnreadCount(unread=0)
