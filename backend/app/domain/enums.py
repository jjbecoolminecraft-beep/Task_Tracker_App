"""Domain enumerations.

Deliberately small and closed. Workflow *states* are NOT here — they are
per-project rows (spec §3.3): Engineering wants "In Review", Marketing wants
"Awaiting Approval", and a hardcoded enum guarantees a migration within a year.
"""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    """Roles from spec §2.2. Each applies at a defined scope."""

    SYSTEM_ADMIN = "system_admin"  # global; configuration only, no task content
    AUDITOR = "auditor"  # global; audit logs only, no task content
    PORTFOLIO_OWNER = "portfolio_owner"  # portfolio scope
    PROJECT_ADMIN = "project_admin"  # project scope
    CONTRIBUTOR = "contributor"  # project scope
    VIEWER = "viewer"  # project scope
    GUEST = "guest"  # task scope; explicitly shared tasks only


# Roles that grant a view onto task *content* within their scope.
CONTENT_ROLES: frozenset[Role] = frozenset(
    {Role.PORTFOLIO_OWNER, Role.PROJECT_ADMIN, Role.CONTRIBUTOR, Role.VIEWER, Role.GUEST}
)

# Roles that can mutate tasks within their scope.
WRITE_ROLES: frozenset[Role] = frozenset({Role.PROJECT_ADMIN, Role.CONTRIBUTOR})


class Action(StrEnum):
    """Verbs passed to ``authorize(actor, action, resource)`` (spec §7.2)."""

    PROJECT_CREATE = "project.create"
    PROJECT_READ = "project.read"
    PROJECT_UPDATE = "project.update"
    PROJECT_ARCHIVE = "project.archive"
    PROJECT_MANAGE_MEMBERS = "project.manage_members"

    TASK_CREATE = "task.create"
    TASK_READ = "task.read"
    TASK_UPDATE = "task.update"
    TASK_COMPLETE = "task.complete"
    TASK_DELETE = "task.delete"

    COMMENT_CREATE = "comment.create"
    COMMENT_READ = "comment.read"

    AUDIT_READ = "audit.read"


class ProjectVisibility(StrEnum):
    PRIVATE = "private"  # membership only
    INTERNAL = "internal"  # any authenticated internal user may read (spec §2.3)


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class TaskPriority:
    """1 highest .. 5 lowest (spec §3.2). Kept as a small int, not an enum."""

    HIGHEST = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4
    LOWEST = 5
    RANGE = range(1, 6)


class WorkflowCategory(StrEnum):
    """Coarse bucket every per-project workflow state maps to.

    Lets the board, "is complete?" checks and reporting work without hardcoding
    state names. Individual state labels stay fully configurable.
    """

    BACKLOG = "backlog"
    IN_PROGRESS = "in_progress"
    DONE = "done"
