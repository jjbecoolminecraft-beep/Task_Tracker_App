"""Project, workflow-state and membership endpoints (spec F-02, F-04)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, Response, status

from app.api.v1.deps import ProjectServiceDep
from app.core.auth import CurrentUser
from app.schemas.project import (
    ProjectCreate,
    ProjectMemberIn,
    ProjectMemberOut,
    ProjectOut,
    ProjectUpdate,
    WorkflowStateOut,
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectOut])
async def list_projects(
    service: ProjectServiceDep,
    _: CurrentUser,
    include_archived: bool = Query(default=False),
) -> list[ProjectOut]:
    return await service.list_visible(include_archived=include_archived)


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate, service: ProjectServiceDep, user: CurrentUser
) -> ProjectOut:
    return await service.create(payload, user)


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: uuid.UUID, service: ProjectServiceDep, _: CurrentUser
) -> ProjectOut:
    return await service.get(project_id)


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: uuid.UUID, payload: ProjectUpdate, service: ProjectServiceDep, user: CurrentUser
) -> ProjectOut:
    return await service.update(project_id, payload, user)


@router.post("/{project_id}/archive", response_model=ProjectOut)
async def archive_project(
    project_id: uuid.UUID, service: ProjectServiceDep, user: CurrentUser
) -> ProjectOut:
    return await service.archive(project_id, user)


@router.get("/{project_id}/workflow-states", response_model=list[WorkflowStateOut])
async def list_workflow_states(
    project_id: uuid.UUID, service: ProjectServiceDep, _: CurrentUser
) -> list[WorkflowStateOut]:
    return await service.list_workflow_states(project_id)


@router.get("/{project_id}/members", response_model=list[ProjectMemberOut])
async def list_members(
    project_id: uuid.UUID, service: ProjectServiceDep, _: CurrentUser
) -> list[ProjectMemberOut]:
    return await service.list_members(project_id)


@router.post(
    "/{project_id}/members",
    response_model=ProjectMemberOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_member(
    project_id: uuid.UUID,
    payload: ProjectMemberIn,
    service: ProjectServiceDep,
    user: CurrentUser,
) -> ProjectMemberOut:
    return await service.add_member(project_id, payload, user)


@router.delete("/{project_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    project_id: uuid.UUID, user_id: uuid.UUID, service: ProjectServiceDep, user: CurrentUser
) -> Response:
    await service.remove_member(project_id, user_id, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
