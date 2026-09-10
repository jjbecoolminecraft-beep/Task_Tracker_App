from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.enums import ProjectVisibility, Role, WorkflowCategory
from app.schemas.common import ApiModel

KEY_PATTERN = r"^[A-Z][A-Z0-9]{1,9}$"


class WorkflowStateOut(ApiModel):
    id: uuid.UUID
    name: str
    category: WorkflowCategory
    position: int
    is_default: bool


class WorkflowStateIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    category: WorkflowCategory = WorkflowCategory.BACKLOG
    position: int = 0


class ProjectOut(ApiModel):
    id: uuid.UUID
    key: str
    name: str
    description: str | None = None
    visibility: ProjectVisibility
    status: str
    portfolio_id: uuid.UUID | None = None
    created_at: datetime
    archived_at: datetime | None = None
    # Populated by the service from the caller's resolved access.
    my_role: Role | None = None
    open_task_count: int | None = None


class ProjectCreate(BaseModel):
    key: str = Field(pattern=KEY_PATTERN, description="Uppercase key, e.g. MKTG")
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    portfolio_id: uuid.UUID
    visibility: ProjectVisibility = ProjectVisibility.PRIVATE
    workflow_states: list[WorkflowStateIn] | None = None


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    visibility: ProjectVisibility | None = None


class ProjectMemberOut(ApiModel):
    id: uuid.UUID
    user_id: uuid.UUID | None = None
    entra_group_id: uuid.UUID | None = None
    role: Role
    display_name: str | None = None


class ProjectMemberIn(BaseModel):
    user_id: uuid.UUID
    role: Role

    @property
    def is_project_scoped_role(self) -> bool:
        return self.role in {Role.PROJECT_ADMIN, Role.CONTRIBUTOR, Role.VIEWER}
