"""Project dashboard (spec F-22) — aggregated reporting, no per-person metrics."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.v1.deps import AuthZDep, SessionDep
from app.core.auth import CurrentUser
from app.schemas.dashboard import ProjectDashboard
from app.services.dashboards import DashboardService

router = APIRouter(prefix="/projects/{project_id}", tags=["dashboards"])


def _service(session: SessionDep, authz: AuthZDep) -> DashboardService:
    return DashboardService(session, authz)


ServiceDep = Annotated[DashboardService, Depends(_service)]


@router.get("/dashboard", response_model=ProjectDashboard)
async def project_dashboard(project_id: uuid.UUID, service: ServiceDep, _: CurrentUser) -> ProjectDashboard:
    return await service.project_dashboard(project_id)
