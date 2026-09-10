"""Audit log read access — Auditor role only (spec §2.2, §8.4.4).

Line managers have no audit access to their reports' activity; this endpoint is
gated on the global Auditor grant and nothing else.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.v1.deps import AuthZDep, SessionDep
from app.core.auth import CurrentUser
from app.domain.enums import Action
from app.models.audit_event import AuditEvent
from app.schemas.audit import AuditEventOut

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=list[AuditEventOut])
async def list_audit_events(
    session: SessionDep,
    authz: AuthZDep,
    _: CurrentUser,
    project_id: uuid.UUID | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    before_id: int | None = Query(default=None, description="Return events with id < this"),
) -> list[AuditEventOut]:
    await authz.require(Action.AUDIT_READ)
    stmt = select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit)
    if project_id:
        stmt = stmt.where(AuditEvent.project_id == project_id)
    if before_id:
        stmt = stmt.where(AuditEvent.id < before_id)
    rows = (await session.execute(stmt)).scalars().all()
    return [AuditEventOut.model_validate(r) for r in rows]
