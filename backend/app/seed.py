"""Development seed data.

Idempotent: if projects already exist it does nothing, so it is safe to run on
every container start. Pass ``--reset`` to wipe and rebuild.

The cast of users is chosen to exercise the authorization matrix — every role in
spec §2.2 appears, plus a user with no access at all so "deny by default" is
visible in the running app.
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select, text

from app.core.db import session_scope
from app.domain.enums import ProjectStatus, ProjectVisibility, Role, WorkflowCategory
from app.models import (
    AuditEvent,
    Comment,
    Label,
    Notification,
    Portfolio,
    Project,
    ProjectMember,
    RoleGrant,
    Task,
    TaskShare,
    User,
    WorkflowState,
)
from app.models.notification import NotificationKind

# Stable ids → reproducible logins across reseeds.
NS = uuid.UUID("11111111-0000-0000-0000-000000000000")


def _uid(name: str) -> uuid.UUID:
    return uuid.uuid5(NS, name)


TODAY = date.today()


# (key, display_name, department)
USERS = [
    ("anna.weber", "Anna Weber", "IT Platform"),
    ("bjoern.neumann", "Björn Neumann", "Internal Audit"),
    ("clara.schmidt", "Clara Schmidt", "Strategy Office"),
    ("david.fischer", "David Fischer", "Marketing"),
    ("elena.popova", "Elena Popova", "Engineering"),
    ("frank.mueller", "Frank Müller", "Marketing"),
    ("greta.lang", "Greta Lang", "Engineering"),
    ("hugo.bauer", "Hugo Bauer", "Facilities"),
]


# Fixed, code-controlled list — never user input (bandit B608 false positive).
_WIPE_ORDER = (
    "notifications",
    "task_shares",
    "task_labels",
    "comments",
    "tasks",
    "workflow_states",
    "labels",
    "project_members",
    "role_grants",
    "projects",
    "portfolios",
    "users",
)


async def _wipe() -> None:
    async with session_scope() as s:
        await s.execute(text("TRUNCATE audit_events RESTART IDENTITY"))
        for table in _WIPE_ORDER:
            await s.execute(text(f"DELETE FROM {table}"))  # nosec B608


async def _already_seeded() -> bool:
    async with session_scope() as s:
        return (await s.execute(select(Project.id).limit(1))).first() is not None


async def seed() -> None:
    async with session_scope() as s:
        users: dict[str, User] = {}
        for key, name, dept in USERS:
            u = User(
                id=_uid(f"user:{key}"),
                entra_object_id=_uid(f"oid:{key}"),
                upn=f"{key}@example.com",
                display_name=name,
                department=dept,
            )
            s.add(u)
            users[key] = u
        await s.flush()

        corporate = Portfolio(id=_uid("pf:corporate"), name="Corporate Programs")
        product = Portfolio(id=_uid("pf:product"), name="Product Portfolio")
        s.add_all([corporate, product])
        await s.flush()

        # --- global + portfolio role grants ---
        s.add_all(
            [
                RoleGrant(user_id=users["anna.weber"].id, role=Role.SYSTEM_ADMIN.value, scope_type="global"),
                RoleGrant(user_id=users["bjoern.neumann"].id, role=Role.AUDITOR.value, scope_type="global"),
                RoleGrant(
                    user_id=users["clara.schmidt"].id,
                    role=Role.PORTFOLIO_OWNER.value,
                    scope_type="portfolio",
                    scope_id=corporate.id,
                ),
            ]
        )

        # --- projects ---
        mktg = Project(
            id=_uid("proj:mktg"),
            portfolio_id=corporate.id,
            key="MKTG",
            name="Marketing Campaigns",
            description="Company-wide campaign planning and delivery.",
            visibility=ProjectVisibility.PRIVATE.value,
            status=ProjectStatus.ACTIVE.value,
            created_by=users["clara.schmidt"].id,
        )
        eng = Project(
            id=_uid("proj:eng"),
            portfolio_id=product.id,
            key="ENG",
            name="Engineering Platform",
            description="Internal developer platform workstream.",
            visibility=ProjectVisibility.PRIVATE.value,
            status=ProjectStatus.ACTIVE.value,
            created_by=users["elena.popova"].id,
        )
        ops = Project(
            id=_uid("proj:ops"),
            portfolio_id=corporate.id,
            key="OPS",
            name="Operations",
            description="Cross-team operational tasks. Internally visible to all staff.",
            visibility=ProjectVisibility.INTERNAL.value,
            status=ProjectStatus.ACTIVE.value,
            created_by=users["anna.weber"].id,
        )
        s.add_all([mktg, eng, ops])
        await s.flush()

        # --- per-project workflow states (deliberately different labels) ---
        states: dict[str, list[WorkflowState]] = {}
        state_specs = {
            "MKTG": [
                ("Ideas", WorkflowCategory.BACKLOG, True),
                ("Drafting", WorkflowCategory.IN_PROGRESS, False),
                ("Awaiting Approval", WorkflowCategory.IN_PROGRESS, False),
                ("Published", WorkflowCategory.DONE, False),
            ],
            "ENG": [
                ("Backlog", WorkflowCategory.BACKLOG, True),
                ("Building", WorkflowCategory.IN_PROGRESS, False),
                ("In Review", WorkflowCategory.IN_PROGRESS, False),
                ("Shipped", WorkflowCategory.DONE, False),
            ],
            "OPS": [
                ("To Do", WorkflowCategory.BACKLOG, True),
                ("In Progress", WorkflowCategory.IN_PROGRESS, False),
                ("Done", WorkflowCategory.DONE, False),
            ],
        }
        for proj in (mktg, eng, ops):
            rows: list[WorkflowState] = []
            for pos, (name, cat, is_default) in enumerate(state_specs[proj.key]):
                ws = WorkflowState(
                    id=_uid(f"ws:{proj.key}:{name}"),
                    project_id=proj.id,
                    name=name,
                    category=cat.value,
                    position=pos,
                    is_default=is_default,
                )
                rows.append(ws)
                s.add(ws)
            states[proj.key] = rows
        await s.flush()

        # --- memberships ---
        s.add_all(
            [
                ProjectMember(
                    project_id=mktg.id, user_id=users["clara.schmidt"].id, role=Role.PROJECT_ADMIN.value
                ),
                ProjectMember(
                    project_id=mktg.id, user_id=users["david.fischer"].id, role=Role.PROJECT_ADMIN.value
                ),
                ProjectMember(
                    project_id=mktg.id, user_id=users["elena.popova"].id, role=Role.CONTRIBUTOR.value
                ),
                ProjectMember(project_id=mktg.id, user_id=users["frank.mueller"].id, role=Role.VIEWER.value),
                ProjectMember(
                    project_id=eng.id, user_id=users["elena.popova"].id, role=Role.PROJECT_ADMIN.value
                ),
                ProjectMember(project_id=eng.id, user_id=users["greta.lang"].id, role=Role.CONTRIBUTOR.value),
                ProjectMember(
                    project_id=ops.id, user_id=users["david.fischer"].id, role=Role.CONTRIBUTOR.value
                ),
            ]
        )

        # --- labels ---
        labels = {
            "MKTG": [
                Label(project_id=mktg.id, name="social", color="#1C6EA4"),
                Label(project_id=mktg.id, name="event", color="#2E7D4F"),
            ],
            "ENG": [
                Label(project_id=eng.id, name="infra", color="#0A2C45"),
                Label(project_id=eng.id, name="dx", color="#4FA3D1"),
            ],
        }
        for group in labels.values():
            s.add_all(group)

        # --- tasks ---
        def mk_tasks(proj: Project, specs: list[dict], start_seq: int = 1) -> list[Task]:
            out: list[Task] = []
            by_cat = {ws.category: ws for ws in states[proj.key]}
            for i, spec in enumerate(specs):
                cat = spec.get("cat", WorkflowCategory.BACKLOG.value)
                st = by_cat.get(cat, states[proj.key][0])
                seq = start_seq + i
                completed = None
                if cat == WorkflowCategory.DONE.value:
                    # spread completions over the last weeks so the throughput
                    # chart has something to show
                    completed = datetime.now(UTC) - timedelta(days=spec.get("done_days_ago", 3))
                t = Task(
                    id=_uid(f"task:{proj.key}:{seq}"),
                    project_id=proj.id,
                    seq=seq,
                    title=spec["title"],
                    description=spec.get("desc"),
                    state_id=st.id,
                    priority=spec.get("priority", 3),
                    assignee_id=users[spec["assignee"]].id if spec.get("assignee") else None,
                    reporter_id=users[spec.get("reporter", "clara.schmidt")].id,
                    due_date=spec.get("due"),
                    estimate_hours=spec.get("estimate"),
                    completed_at=completed,
                )
                s.add(t)
                out.append(t)
            return out

        mktg_tasks = mk_tasks(
            mktg,
            [
                {
                    "title": "Q4 product launch campaign brief",
                    "cat": "in_progress",
                    "priority": 2,
                    "assignee": "david.fischer",
                    "reporter": "clara.schmidt",
                    "due": TODAY + timedelta(days=5),
                    "desc": "Draft the campaign brief covering channels, budget and timeline.",
                },
                {
                    "title": "Refresh brand landing page copy",
                    "cat": "backlog",
                    "priority": 3,
                    "assignee": "elena.popova",
                    "due": TODAY + timedelta(days=12),
                },
                {
                    "title": "Trade show booth logistics",
                    "cat": "in_progress",
                    "priority": 1,
                    "assignee": "david.fischer",
                    "due": TODAY - timedelta(days=2),
                    "desc": "Overdue — booth shipping deadline missed, needs escalation.",
                },
                {
                    "title": "Social media content calendar — November",
                    "cat": "backlog",
                    "priority": 3,
                    "assignee": "frank.mueller",
                },
                {
                    "title": "Customer testimonial video edit",
                    "cat": "in_progress",
                    "priority": 4,
                    "assignee": "elena.popova",
                    "due": TODAY + timedelta(days=20),
                },
                {
                    "title": "Press release: partnership announcement",
                    "cat": "done",
                    "priority": 2,
                    "assignee": "david.fischer",
                    "done_days_ago": 4,
                },
                {"title": "Email newsletter template redesign", "cat": "backlog", "priority": 5},
                {
                    "title": "Webinar recap blog post",
                    "cat": "done",
                    "priority": 3,
                    "assignee": "elena.popova",
                    "done_days_ago": 11,
                },
                {
                    "title": "Q3 campaign retrospective",
                    "cat": "done",
                    "priority": 3,
                    "assignee": "david.fischer",
                    "done_days_ago": 19,
                },
                {
                    "title": "Update media kit",
                    "cat": "done",
                    "priority": 4,
                    "assignee": "frank.mueller",
                    "done_days_ago": 25,
                },
                {
                    "title": "Partner co-marketing brief",
                    "cat": "done",
                    "priority": 3,
                    "assignee": "elena.popova",
                    "done_days_ago": 12,
                },
                {
                    "title": "Newsletter A/B test wrap-up",
                    "cat": "done",
                    "priority": 4,
                    "assignee": "david.fischer",
                    "done_days_ago": 6,
                },
            ],
        )
        # subtasks under the launch campaign brief
        launch = mktg_tasks[0]
        for j, sub in enumerate(
            ["Define target segments", "Set channel budget split", "Agree launch date"], start=1
        ):
            s.add(
                Task(
                    id=_uid(f"task:MKTG:sub:{j}"),
                    project_id=mktg.id,
                    parent_task_id=launch.id,
                    seq=100 + j,
                    title=sub,
                    state_id=states["MKTG"][0].id,
                    priority=3,
                    assignee_id=users["david.fischer"].id,
                    reporter_id=users["clara.schmidt"].id,
                )
            )

        mk_tasks(
            eng,
            [
                {
                    "title": "Introduce service template repo",
                    "cat": "in_progress",
                    "priority": 2,
                    "assignee": "elena.popova",
                    "reporter": "elena.popova",
                    "due": TODAY + timedelta(days=7),
                    "desc": "Scaffold a golden-path template with CI, linting and container build.",
                },
                {
                    "title": "Centralise structured logging library",
                    "cat": "backlog",
                    "priority": 3,
                    "assignee": "greta.lang",
                    "reporter": "elena.popova",
                },
                {
                    "title": "Self-service preview environments",
                    "cat": "in_progress",
                    "priority": 2,
                    "assignee": "greta.lang",
                    "reporter": "elena.popova",
                    "due": TODAY + timedelta(days=15),
                },
                {
                    "title": "Deprecate legacy build agents",
                    "cat": "done",
                    "priority": 3,
                    "assignee": "elena.popova",
                    "reporter": "elena.popova",
                },
                {
                    "title": "Platform docs portal MVP",
                    "cat": "backlog",
                    "priority": 4,
                    "reporter": "elena.popova",
                },
            ],
        )

        mk_tasks(
            ops,
            [
                {
                    "title": "Office move — desk allocation plan",
                    "cat": "in_progress",
                    "priority": 3,
                    "assignee": "david.fischer",
                    "reporter": "anna.weber",
                    "due": TODAY + timedelta(days=9),
                },
                {
                    "title": "Quarterly access review",
                    "cat": "backlog",
                    "priority": 2,
                    "reporter": "anna.weber",
                    "due": TODAY + timedelta(days=3),
                },
                {
                    "title": "Renew software licences",
                    "cat": "done",
                    "priority": 3,
                    "assignee": "david.fischer",
                    "reporter": "anna.weber",
                },
            ],
        )
        await s.flush()

        # --- a couple of comments (one with an @mention) ---
        s.add(
            Comment(
                task_id=launch.id,
                author_id=users["clara.schmidt"].id,
                body=f"@[David Fischer]({users['david.fischer'].id}) can you own the first draft by Friday?",
                mentioned_user_ids=[users["david.fischer"].id],
            )
        )
        s.add(
            Comment(
                task_id=mktg_tasks[2].id,
                author_id=users["david.fischer"].id,
                body="Carrier missed the pickup window. Rebooking for tomorrow, will update.",
                mentioned_user_ids=[],
            )
        )

        # --- Guest share: Greta (no MKTG role) gets one specific MKTG task ---
        s.add(
            TaskShare(
                task_id=mktg_tasks[4].id,
                user_id=users["greta.lang"].id,
                shared_by=users["david.fischer"].id,
            )
        )

        # --- a few unread notifications so the bell isn't empty on a fresh seed ---
        s.add(
            Notification(
                recipient_id=users["david.fischer"].id,
                kind=NotificationKind.COMMENT_MENTION.value,
                actor_id=users["clara.schmidt"].id,
                task_id=launch.id,
                project_id=mktg.id,
                context={
                    "actor_name": "Clara Schmidt",
                    "task_ref": f"{mktg.key}-{launch.seq}",
                    "snippet": "@David Fischer can you own the first draft by Friday?",
                },
                created_at=datetime.now(UTC) - timedelta(hours=3),
            )
        )
        for t in mktg_tasks[1:3]:
            if t.assignee_id and t.assignee_id != t.reporter_id:
                s.add(
                    Notification(
                        recipient_id=t.assignee_id,
                        kind=NotificationKind.TASK_ASSIGNED.value,
                        actor_id=t.reporter_id,
                        task_id=t.id,
                        project_id=mktg.id,
                        context={
                            "actor_name": "Clara Schmidt",
                            "task_ref": f"{mktg.key}-{t.seq}",
                            "task_title": t.title,
                        },
                        created_at=datetime.now(UTC) - timedelta(days=1),
                    )
                )

        # --- fix per-project task counters ---
        mktg.task_seq = len(mktg_tasks)
        eng.task_seq = 5
        ops.task_seq = 3

        s.add(
            AuditEvent(
                action="system.seeded",
                resource_type="system",
                resource_id=None,
                actor_id=users["anna.weber"].id,
                actor_upn=users["anna.weber"].upn,
                after={"users": len(USERS), "projects": 3},
            )
        )

    print(f"Seeded {len(USERS)} users, 2 portfolios, 3 projects.")  # noqa: T201


async def main() -> None:
    if "--reset" in sys.argv:
        await _wipe()
        print("Wiped existing data.")  # noqa: T201
    elif await _already_seeded():
        print("Database already seeded — nothing to do (use --reset to rebuild).")  # noqa: T201
        return
    await seed()


if __name__ == "__main__":
    asyncio.run(main())
