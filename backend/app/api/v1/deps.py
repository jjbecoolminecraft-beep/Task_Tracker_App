"""Shared FastAPI dependencies for v1 routers."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_session
from app.services.authorization import AuthZ
from app.services.comments import CommentService
from app.services.projects import ProjectService
from app.services.tasks import TaskService

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_authz(session: SessionDep, user: CurrentUser) -> AuthZ:
    return AuthZ(session, user)


AuthZDep = Annotated[AuthZ, Depends(get_authz)]


def get_project_service(session: SessionDep, authz: AuthZDep) -> ProjectService:
    return ProjectService(session, authz)


def get_task_service(session: SessionDep, authz: AuthZDep) -> TaskService:
    return TaskService(session, authz)


def get_comment_service(session: SessionDep, authz: AuthZDep) -> CommentService:
    return CommentService(session, authz)


ProjectServiceDep = Annotated[ProjectService, Depends(get_project_service)]
TaskServiceDep = Annotated[TaskService, Depends(get_task_service)]
CommentServiceDep = Annotated[CommentService, Depends(get_comment_service)]
