"""initial schema

Domain model from spec §3. Beyond the tables, this migration installs three
pieces of behaviour the spec calls for explicitly:

* ``citext`` extension — case-insensitive ``upn`` / project ``key`` (spec §3.2).
* ``tasks.search_vector`` maintained by a trigger + GIN index — PostgreSQL
  full-text search, "search vector refresh on write" (spec §3.3, §5.4, F-09).
* ``audit_events`` made append-only by a trigger that rejects UPDATE/DELETE
  (spec §3.3 "no UPDATE or DELETE grants … for the application role"). In Azure
  this is reinforced by not granting those privileges to the app's DB role.

Revision ID: 0001
Revises:
Create Date: 2026-09-10
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SEARCH_VECTOR_FN = """
CREATE OR REPLACE FUNCTION tasks_search_vector_refresh() RETURNS trigger AS $$
BEGIN
  NEW.search_vector :=
      setweight(to_tsvector('english', coalesce(NEW.title, '')), 'A') ||
      setweight(to_tsvector('english', coalesce(NEW.description, '')), 'B');
  RETURN NEW;
END
$$ LANGUAGE plpgsql;
"""

AUDIT_GUARD_FN = """
CREATE OR REPLACE FUNCTION reject_audit_mutation() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'audit_events is append-only (spec 3.3 / 8.4)';
END
$$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")

    op.create_table(
        "audit_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("actor_id", sa.UUID(), nullable=True),
        sa.Column("actor_upn", postgresql.CITEXT(), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("resource_type", sa.String(length=40), nullable=False),
        sa.Column("resource_id", sa.UUID(), nullable=True),
        sa.Column("project_id", sa.UUID(), nullable=True),
        sa.Column("before", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("request_id", sa.UUID(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_events")),
    )
    op.create_index(op.f("ix_audit_events_actor_id"), "audit_events", ["actor_id"])
    op.create_index(op.f("ix_audit_events_occurred_at"), "audit_events", ["occurred_at"])
    op.create_index(op.f("ix_audit_events_project_id"), "audit_events", ["project_id"])
    op.create_index(op.f("ix_audit_events_request_id"), "audit_events", ["request_id"])
    op.create_index(op.f("ix_audit_events_resource_id"), "audit_events", ["resource_id"])

    op.create_table(
        "portfolios",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_portfolios")),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("entra_object_id", sa.UUID(), nullable=False),
        sa.Column("upn", postgresql.CITEXT(), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("department", sa.String(length=200), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_pseudonymized", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("entra_object_id", name=op.f("uq_users_entra_object_id")),
    )
    op.create_index(op.f("ix_users_upn"), "users", ["upn"])

    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("portfolio_id", sa.UUID(), nullable=True),
        sa.Column("key", postgresql.CITEXT(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=4000), nullable=True),
        sa.Column("visibility", sa.String(length=20), server_default=sa.text("'private'"), nullable=False),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'active'"), nullable=False),
        sa.Column("task_seq", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_projects_created_by_users")),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"], name=op.f("fk_projects_portfolio_id_portfolios")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_projects")),
        sa.UniqueConstraint("key", name=op.f("uq_projects_key")),
    )
    op.create_index(op.f("ix_projects_portfolio_id"), "projects", ["portfolio_id"])

    op.create_table(
        "role_grants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(length=30), nullable=False),
        sa.Column("scope_type", sa.String(length=20), nullable=False),
        sa.Column("scope_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_role_grants_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_role_grants")),
        sa.UniqueConstraint("user_id", "role", "scope_type", "scope_id", name="role_grant_unique"),
    )
    op.create_index(op.f("ix_role_grants_scope_id"), "role_grants", ["scope_id"])
    op.create_index(op.f("ix_role_grants_user_id"), "role_grants", ["user_id"])

    op.create_table(
        "labels",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("color", sa.String(length=9), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_labels_project_id_projects"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_labels")),
        sa.UniqueConstraint("project_id", "name", name="label_unique_name"),
    )
    op.create_index(op.f("ix_labels_project_id"), "labels", ["project_id"])

    op.create_table(
        "project_members",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("entra_group_id", sa.UUID(), nullable=True),
        sa.Column("role", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_project_members_project_id_projects"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_project_members_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_project_members")),
        sa.UniqueConstraint("project_id", "user_id", name="project_member_unique"),
    )
    op.create_index(op.f("ix_project_members_entra_group_id"), "project_members", ["entra_group_id"])
    op.create_index(op.f("ix_project_members_project_id"), "project_members", ["project_id"])
    op.create_index(op.f("ix_project_members_user_id"), "project_members", ["user_id"])

    op.create_table(
        "workflow_states",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("category", sa.String(length=20), server_default=sa.text("'backlog'"), nullable=False),
        sa.Column("position", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_workflow_states_project_id_projects"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_states")),
        sa.UniqueConstraint("project_id", "name", name="workflow_state_unique_name"),
    )
    op.create_index(op.f("ix_workflow_states_project_id"), "workflow_states", ["project_id"])

    op.create_table(
        "tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("parent_task_id", sa.UUID(), nullable=True),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("state_id", sa.UUID(), nullable=False),
        sa.Column("priority", sa.SmallInteger(), server_default=sa.text("3"), nullable=False),
        sa.Column("assignee_id", sa.UUID(), nullable=True),
        sa.Column("reporter_id", sa.UUID(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("estimate_hours", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("priority between 1 and 5", name=op.f("ck_tasks_priority_range")),
        sa.ForeignKeyConstraint(["assignee_id"], ["users.id"], name=op.f("fk_tasks_assignee_id_users")),
        sa.ForeignKeyConstraint(["parent_task_id"], ["tasks.id"], name=op.f("fk_tasks_parent_task_id_tasks")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_tasks_project_id_projects")),
        sa.ForeignKeyConstraint(["reporter_id"], ["users.id"], name=op.f("fk_tasks_reporter_id_users")),
        sa.ForeignKeyConstraint(["state_id"], ["workflow_states.id"], name=op.f("fk_tasks_state_id_workflow_states")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tasks")),
        sa.UniqueConstraint("project_id", "seq", name="task_seq_unique"),
    )
    op.create_index(op.f("ix_tasks_assignee_id"), "tasks", ["assignee_id"])
    op.create_index(op.f("ix_tasks_deleted_at"), "tasks", ["deleted_at"])
    op.create_index(op.f("ix_tasks_parent_task_id"), "tasks", ["parent_task_id"])
    op.create_index(op.f("ix_tasks_project_id"), "tasks", ["project_id"])
    op.create_index(op.f("ix_tasks_state_id"), "tasks", ["state_id"])
    op.create_index(
        "ix_tasks_search_vector", "tasks", ["search_vector"], postgresql_using="gin"
    )

    op.create_table(
        "comments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.UUID(), nullable=False),
        sa.Column("author_id", sa.UUID(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("mentioned_user_ids", postgresql.ARRAY(sa.UUID()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], name=op.f("fk_comments_author_id_users")),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], name=op.f("fk_comments_task_id_tasks"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_comments")),
    )
    op.create_index(op.f("ix_comments_task_id"), "comments", ["task_id"])

    op.create_table(
        "task_labels",
        sa.Column("task_id", sa.UUID(), nullable=False),
        sa.Column("label_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["label_id"], ["labels.id"], name=op.f("fk_task_labels_label_id_labels"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], name=op.f("fk_task_labels_task_id_tasks"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("task_id", "label_id", name=op.f("pk_task_labels")),
    )

    op.create_table(
        "task_shares",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("shared_by", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["shared_by"], ["users.id"], name=op.f("fk_task_shares_shared_by_users")),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], name=op.f("fk_task_shares_task_id_tasks"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_task_shares_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task_shares")),
        sa.UniqueConstraint("task_id", "user_id", name="task_share_unique"),
    )
    op.create_index(op.f("ix_task_shares_task_id"), "task_shares", ["task_id"])
    op.create_index(op.f("ix_task_shares_user_id"), "task_shares", ["user_id"])

    # --- full-text search maintenance ---
    op.execute(SEARCH_VECTOR_FN)
    op.execute(
        "CREATE TRIGGER trg_tasks_search_vector "
        "BEFORE INSERT OR UPDATE OF title, description ON tasks "
        "FOR EACH ROW EXECUTE FUNCTION tasks_search_vector_refresh()"
    )

    # --- audit trail is append-only ---
    op.execute(AUDIT_GUARD_FN)
    op.execute(
        "CREATE TRIGGER trg_audit_events_append_only "
        "BEFORE UPDATE OR DELETE ON audit_events "
        "FOR EACH ROW EXECUTE FUNCTION reject_audit_mutation()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_events_append_only ON audit_events")
    op.execute("DROP FUNCTION IF EXISTS reject_audit_mutation()")
    op.execute("DROP TRIGGER IF EXISTS trg_tasks_search_vector ON tasks")
    op.execute("DROP FUNCTION IF EXISTS tasks_search_vector_refresh()")

    op.drop_table("task_shares")
    op.drop_table("task_labels")
    op.drop_table("comments")
    op.drop_index("ix_tasks_search_vector", table_name="tasks")
    op.drop_table("tasks")
    op.drop_table("workflow_states")
    op.drop_table("project_members")
    op.drop_table("labels")
    op.drop_table("role_grants")
    op.drop_table("projects")
    op.drop_table("users")
    op.drop_table("portfolios")
    op.drop_table("audit_events")
    op.execute("DROP EXTENSION IF EXISTS citext")
