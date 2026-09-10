# 5. Central authorization layer

- Status: accepted
- Date: 2026-09-10

## Context

Spec §7.2 / §12: every access decision routes through one place; no route handler
inspects roles directly; row-level filtering is applied at the query layer so a
missing check cannot leak data; an automated suite asserts each endpoint rejects
each role that should not have access.

## Decision

- `app/services/authorization.py` exposes an `AuthZ` object, instantiated once per
  request via a FastAPI dependency. Route handlers call `await authz.require(action, resource)`
  and nothing else; a raise becomes a `403` through the error-envelope handler.
- **Deny by default.** `_evaluate()` returns `False` unless a rule explicitly
  permits the action.
- **Scoped role resolution.** `effective_project_role(project)` folds together:
  Portfolio Owner of the owning portfolio → acts as Project Admin; explicit
  `project_members` rows; `internal` visibility → implicit Viewer; a Guest
  `task_shares` row → Guest confined to those task ids.
- **Admin ≠ reader.** System Admin and Auditor hold *no* content roles. Auditor
  is the only role that passes `AUDIT_READ`.
- **Row-level filtering.** `accessible_project_ids()` is resolved once per request
  and joined into every list/search query. A Guest's project task list is
  additionally constrained to the shared task ids — the role check alone is not
  trusted.
- `tests/authz/` is a first-class suite: an endpoint × role matrix of
  allow/deny, plus row-level-filtering tests. It is the control evidence for
  access-control audits.

## Consequences

- One file to read to understand the whole policy; one file to change it.
- A widening of access fails the matrix loudly in CI.
- Slightly more per-request DB work (role + accessible-id resolution); cached on
  the `AuthZ` instance for the request's lifetime.
