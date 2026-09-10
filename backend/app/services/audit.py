"""Audit event recording (spec §3.3, §7.4, §12).

``record()`` adds the row to the *caller's* session, so the audit event and the
change it describes commit in one transaction — not a callback, not best-effort.
Append-only: the DB role has no UPDATE/DELETE on ``audit_events`` (initial migration).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.request_context import get_request_id
from app.models.audit_event import AuditEvent
from app.models.user import User

# Fields safe and useful to diff in the audit trail. Free-form long text
# (description, comment body) is referenced by change, not copied verbatim.
_AUDITABLE_TASK_FIELDS = (
    "title",
    "state_id",
    "priority",
    "assignee_id",
    "due_date",
    "estimate_hours",
    "completed_at",
    "deleted_at",
)


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, uuid.UUID | Decimal):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    return str(value)


def snapshot(obj: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    return {name: _jsonable(getattr(obj, name, None)) for name in fields}


def diff(before: dict[str, Any], after: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Keep only the keys that actually changed."""
    changed_before: dict[str, Any] = {}
    changed_after: dict[str, Any] = {}
    for key in before.keys() | after.keys():
        b, a = before.get(key), after.get(key)
        if b != a:
            changed_before[key] = b
            changed_after[key] = a
    return changed_before, changed_after


async def record(
    session: AsyncSession,
    *,
    action: str,
    resource_type: str,
    resource_id: uuid.UUID | None,
    actor: User | None,
    project_id: uuid.UUID | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> AuditEvent:
    request_id = get_request_id()
    event = AuditEvent(
        actor_id=actor.id if actor else None,
        actor_upn=actor.upn if actor else None,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        project_id=project_id,
        before=before or None,
        after=after or None,
        ip_address=ip_address,
        request_id=uuid.UUID(request_id) if request_id else None,
    )
    session.add(event)
    return event
