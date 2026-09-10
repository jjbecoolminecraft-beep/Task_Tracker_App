# 3. PostgreSQL locally + Azure IaC (Bicep) from Phase 0

- Status: accepted
- Date: 2026-09-10
- Resolves: spec §11 D-03 (IaC tooling)

## Context

Two options were open: (a) start on SQLite and switch to PostgreSQL later, or
(b) run PostgreSQL from the first commit. Similarly, the Azure architecture (§6)
could be documented now and coded later, or built as Bicep alongside the app.

The domain model leans on PostgreSQL-specific features — `citext`, `tsvector`
full-text search, `jsonb` audit blobs, `inet`, partitioned audit table. SQLite
would mean a parallel, lower-fidelity schema and migrations that don't match
production.

## Decision

- **PostgreSQL 16 from the start**, via `docker compose` locally and Azure
  Database for PostgreSQL Flexible Server in Azure. Migrations are Alembic,
  authored against real PostgreSQL. The initial migration installs the `citext`
  extension, the `tasks.search_vector` trigger + GIN index, and an append-only
  guard trigger on `audit_events`.
- **Bicep** for IaC (over Terraform): first-class Azure support, no state store to
  operate, `az deployment ... what-if` for plan review. `infra/` carries one
  orchestrating `main.bicep`, per-resource modules, and `envs/{dev,test,staging,prod}`
  parameter files. `infra/policy/allowed-locations.json` denies non-EU regions.

## Consequences

- No "it worked on SQLite" surprises; local and prod exercise the same engine,
  extensions and triggers.
- Local onboarding needs Docker. Documented in the README; the API can also run
  fully in a container.
- Infra is reviewable from Phase 0 and the security posture (private endpoints,
  no public network access, managed identity, zone-redundant HA) is visible in
  code, not just prose.
- The Bicep is not yet deployed against a live subscription; `bicep build`
  validates it in CI. First real deployment is a Phase-0 landing-zone task.
