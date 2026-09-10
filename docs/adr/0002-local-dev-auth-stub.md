# 2. Local development authentication stub

- Status: accepted
- Date: 2026-09-10

## Context

Production authentication is Entra ID (OIDC authorization code + PKCE via MSAL),
spec §5.3 / §7.1. Standing up a tenant and app registration is a Phase-0
compliance task with a long lead time. Meanwhile the authorization layer, the
`tests/authz/` matrix and the whole SPA need a working notion of "who is the
caller and what roles do they hold" from day one.

## Decision

Ship a **local development auth stub**, active only when `DEV_AUTH_ENABLED=true`:

- `POST /api/v1/auth/dev-login` mints a short-lived HS256 JWT shaped like an
  Entra ID access token (`oid`, `preferred_username`, `name`, `iss`, `aud`,
  `exp`). `GET /api/v1/auth/dev-users` lists seeded identities for a picker.
- `app/core/auth.py` has one `_decode()` with two branches. The stub branch
  validates the HS256 token; the real branch (JWKS + `iss`/`aud` checks against
  the tenant) is wired but raises until enabled. Everything downstream receives a
  provisioned `User` and never knows which path ran.
- The SPA holds the access token **in memory only** (never `localStorage`,
  spec §5.3). It remembers *which* seeded user was chosen in `sessionStorage`
  and silently re-mints on reload — the token itself is never persisted.

## Consequences

- The authorization layer and its audit-grade test suite are built and exercised
  before the Entra integration exists — the spec's stated ordering (§13.4).
- Swapping to real Entra ID is a config change plus finishing `_decode()`'s real
  branch; no route handler or service changes.
- The stub endpoints are not mounted when `DEV_AUTH_ENABLED=false`, so a
  misconfigured production deploy cannot expose them.
- Risk: the stub secret is symmetric. It exists only for local dev, is a
  non-secret default in `.env.example`, and CI/prod set `DEV_AUTH_ENABLED=false`.
