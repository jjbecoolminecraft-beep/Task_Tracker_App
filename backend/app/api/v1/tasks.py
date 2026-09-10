"""Task, comment, "my tasks" and search endpoints (spec F-03, F-05, F-07, F-09, F-13)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Header, Query, Response, status

from app.api.v1.deps import CommentServiceDep, TaskServiceDep
from app.core.auth import CurrentUser
from app.core.pagination import Page
from app.schemas.common import PageMeta, Paginated
from app.schemas.task import (
    CommentCreate,
    CommentOut,
    TaskCreate,
    TaskDetailOut,
    TaskOut,
    TaskUpdate,
)
from app.services.tasks import etag_for

router = APIRouter(tags=["tasks"])

IfMatch = Annotated[str | None, Header(alias="If-Match")]
_SORTS = ("created_at", "updated_at", "due_date", "priority", "seq")


def _paginated(page: Page) -> Paginated[TaskOut]:
    return Paginated[TaskOut](
        items=list(page.items),
        page=PageMeta(next_cursor=page.next_cursor, limit=len(page.items)),
    )


@router.get("/projects/{project_id}/tasks", response_model=Paginated[TaskOut])
async def list_project_tasks(
    project_id: uuid.UUID,
    service: TaskServiceDep,
    _: CurrentUser,
    state_id: uuid.UUID | None = None,
    assignee_id: uuid.UUID | None = None,
    unassigned: bool = False,
    priority: int | None = Query(default=None, ge=1, le=5),
    sort: str = Query(default="created_at"),
    q: str | None = Query(default=None, description="Full-text search within the project"),
    include_subtasks: bool = Query(default=False),
    limit: int | None = Query(default=None, ge=1, le=200),
    cursor: str | None = None,
) -> Paginated[TaskOut]:
    if sort not in _SORTS:
        sort = "created_at"
    page = await service.list_for_project(
        project_id,
        filters={
            "state_id": state_id,
            "assignee_id": assignee_id,
            "unassigned": unassigned,
            "priority": priority,
            "sort": sort,
            "search": q,
            "top_level_only": not include_subtasks,
        },
        limit=limit,
        cursor=cursor,
    )
    return _paginated(page)


@router.post(
    "/projects/{project_id}/tasks",
    response_model=TaskDetailOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_task(
    project_id: uuid.UUID,
    payload: TaskCreate,
    service: TaskServiceDep,
    user: CurrentUser,
    response: Response,
) -> TaskDetailOut:
    task = await service.create(project_id, payload, user)
    response.headers["ETag"] = f'"{task.version}"'
    return task


@router.get("/tasks/{task_id}", response_model=TaskDetailOut)
async def get_task(
    task_id: uuid.UUID, service: TaskServiceDep, _: CurrentUser, response: Response
) -> TaskDetailOut:
    task = await service.get(task_id)
    response.headers["ETag"] = f'"{task.version}"'
    return task


@router.patch("/tasks/{task_id}", response_model=TaskDetailOut)
async def update_task(
    task_id: uuid.UUID,
    payload: TaskUpdate,
    service: TaskServiceDep,
    user: CurrentUser,
    response: Response,
    if_match: IfMatch = None,
) -> TaskDetailOut:
    task = await service.update(task_id, payload, user, if_match=if_match)
    response.headers["ETag"] = f'"{task.version}"'
    return task


@router.post("/tasks/{task_id}/complete", response_model=TaskDetailOut)
async def complete_task(
    task_id: uuid.UUID,
    service: TaskServiceDep,
    user: CurrentUser,
    response: Response,
    if_match: IfMatch = None,
) -> TaskDetailOut:
    task = await service.complete(task_id, user, if_match=if_match)
    response.headers["ETag"] = f'"{task.version}"'
    return task


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: uuid.UUID,
    service: TaskServiceDep,
    user: CurrentUser,
    if_match: IfMatch = None,
) -> Response:
    await service.soft_delete(task_id, user, if_match=if_match)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/tasks/{task_id}/comments", response_model=list[CommentOut])
async def list_comments(
    task_id: uuid.UUID, service: CommentServiceDep, _: CurrentUser
) -> list[CommentOut]:
    return await service.list_for_task(task_id)


@router.post(
    "/tasks/{task_id}/comments",
    response_model=CommentOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_comment(
    task_id: uuid.UUID, payload: CommentCreate, service: CommentServiceDep, user: CurrentUser
) -> CommentOut:
    return await service.create(task_id, payload, user)


@router.get("/me/tasks", response_model=Paginated[TaskOut])
async def my_tasks(
    service: TaskServiceDep,
    user: CurrentUser,
    limit: int | None = Query(default=None, ge=1, le=200),
    cursor: str | None = None,
) -> Paginated[TaskOut]:
    page = await service.my_tasks(user, limit=limit, cursor=cursor)
    return _paginated(page)


@router.get("/search", response_model=Paginated[TaskOut])
async def search_tasks(
    service: TaskServiceDep,
    user: CurrentUser,
    q: str = Query(min_length=1, description="Full-text query, scoped to accessible projects"),
    limit: int | None = Query(default=None, ge=1, le=200),
    cursor: str | None = None,
) -> Paginated[TaskOut]:
    page = await service.search(user, query=q, limit=limit, cursor=cursor)
    return _paginated(page)
