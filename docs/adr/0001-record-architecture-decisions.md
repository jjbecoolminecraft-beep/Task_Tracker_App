# 1. Record architecture decisions

- Status: accepted
- Date: 2026-09-10

## Context

Auditors and new engineers repeatedly ask *why* a choice was made. The spec
(§12) calls for an ADR per significant decision so the answer is a dated record,
not tribal knowledge.

## Decision

We keep Architecture Decision Records in `docs/adr/`, one Markdown file per
decision, numbered sequentially, using a lightweight MADR-style template:
context → decision → consequences. An ADR is immutable once accepted; a later
decision that changes it gets its own file and supersedes the earlier one.

## Consequences

- Every non-obvious choice is traceable to a reviewed commit.
- The open decisions in spec §11 each become an ADR as they resolve.
- Minimal overhead: a few paragraphs, written when the decision is made.
