# 6. Human-readable task references via a per-project counter

- Status: accepted
- Date: 2026-09-10

## Context

Spec §3.3: users cite task references in Teams and email; UUIDs are unusable in
conversation. Tasks need a stable `MKTG-142`-style reference, unique within a
project.

## Decision

- `projects.task_seq` is an integer counter on the project row. On task creation
  the task service does `SELECT task_seq ... FOR UPDATE`, increments, and writes
  the new value back **inside the same transaction** as the task insert. The task
  stores the resulting `seq`; `unique (project_id, seq)` enforces correctness.
- The display reference `{project.key}-{seq}` is computed at the API boundary,
  not stored.

## Consequences

- Gap-free, race-free sequences per project under concurrent creates (the
  `FOR UPDATE` serialises just the counter row).
- A dedicated PostgreSQL `SEQUENCE` per project was rejected — thousands of
  sequence objects, awkward to create/drop with projects, and sequences are
  explicitly allowed to have gaps.
- Bulk import must go through the same path (or take the project row lock once and
  allocate a range) to stay consistent.
