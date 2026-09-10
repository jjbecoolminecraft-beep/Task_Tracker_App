# Enterprise Project & Task Tracker

Internal, company-wide system for planning, assigning and tracking project work.
Foundation document: [`docs/spec.md`](docs/spec.md).

**Stack** (spec §5.1): Python 3.12 / FastAPI · SQLAlchemy 2 async · PostgreSQL 16
· React 18 + TypeScript + Vite · Tailwind · TanStack Query + Zustand · Azure
Container Apps (Bicep IaC).

**Design language:** "KB‑Standard" — the Knorr‑Bremse‑style system in
`Design-system.pdf` (deep petrol‑navy, a mid‑blue accent, generous whitespace,
geometric type, restrained colour). Tokens live in
[`frontend/tailwind.config.ts`](frontend/tailwind.config.ts).

---

## Phase 1 — what's built

A runnable MVP vertical slice:

| Area | Included |
|---|---|
| Auth | Local dev stub mirroring Entra ID tokens + roles ([ADR 0002](docs/adr/0002-local-dev-auth-stub.md)); real MSAL/Entra path wired but inert |
| Authorization | Central `authorize()` layer, deny‑by‑default, scoped roles, row‑level query filtering, `tests/authz/` endpoint × role matrix ([ADR 0005](docs/adr/0005-authorization-layer-design.md)) |
| Domain | Portfolio → Project → Task → Subtask, per‑project workflow states, comments + `@mention`, labels, guest task shares, audit trail |
| API | Project & task CRUD, board/list, `My tasks`, full‑text search (Postgres `tsvector`), cursor pagination, optimistic concurrency (`If-Match`/`ETag`), error envelope + `X-Request-Id`, OpenAPI at `/api/v1/docs` |
| Audit (F‑11) | Every mutation writes an `audit_events` row in the same transaction; table is append‑only (DB trigger); `GET /api/v1/audit` + an **Audit log** page are Auditor‑only (spec §8.4.4) with a before→after diff view |
| Notifications (F‑10) | In‑app feed for task assignment and comment `@mention` / activity; created in the same transaction, scoped strictly to the recipient, never for the actor's own action. Email digest is a worker job (stubbed) |
| Import / export (F‑12) | CSV + JSON export of a project's tasks (audited, §8.4.6); CSV import via the normal task‑create path (per‑row validation report, parent‑ref → subtask). Large async imports are a worker job (not built) |
| Dashboards (F‑22) | Per‑project aggregates: KPI tiles, tasks by workflow state / priority, weekly throughput. **No per‑person figures** — excluded at the API, not just the UI (spec §8.4.1); a `MIN_GROUP` guard is in the service for any future breakdown (§8.4.2) |
| Web | Login (identity picker), Projects, Project **List** + **Board** (drag + keyboard) + **Dashboard**, Task detail drawer (inline edit, comments, subtasks), My tasks, Search, notification bell, CSV/JSON export + import dialog, Auditor‑only Audit log — English/German i18n (key parity checked in CI) |
| Infra | `infra/` Bicep: VNet + private endpoints, PostgreSQL Flexible Server (Entra auth, zone‑redundant HA), Redis, Blob, Key Vault, Container Apps, Static Web App, Front Door + WAF, EU‑only Azure Policy |
| Compliance | DPIA outline, RoPA entry, retention concept, works‑agreement outline in `docs/compliance/` |

Not yet: email digests, Teams, import/export, attachments upload, dashboards,
saved views, real Entra wiring, running worker/scheduler processes.

---

## Run it locally

**Prerequisites:** Docker Desktop, Python 3.12, Node 20+.

```bash
# 1. data services
docker compose up -d db redis

# 2. backend
cd backend
python -m venv .venv && .venv/Scripts/pip install -e ".[dev]"   # Windows
#                       source .venv/bin/activate && pip install -e ".[dev]"   # macOS/Linux
cp ../.env.example .env
.venv/Scripts/python -m alembic upgrade head
.venv/Scripts/python -m app.seed --reset
.venv/Scripts/python -m uvicorn app.main:app --reload            # http://127.0.0.1:8000

# 3. frontend (new terminal)
cd frontend
npm install
npm run dev                                                      # http://127.0.0.1:5173
```

Or run the whole backend in a container: `docker compose up --build`.

### Seeded identities (dev login screen)

| User | Role(s) |
|---|---|
| Anna Weber | System Admin (global) — admin, **not** a content reader |
| Björn Neumann | Auditor (global) — audit log only |
| Clara Schmidt | Portfolio Owner (Corporate) — owns MKTG + OPS |
| David Fischer | Project Admin (MKTG), Contributor (OPS) |
| Elena Popova | Project Admin (ENG), Contributor (MKTG) |
| Frank Müller | Viewer (MKTG) |
| Greta Lang | Contributor (ENG), Guest on one MKTG task |
| Hugo Bauer | no roles — sees only the internally‑visible OPS project |

---

## Tests

```bash
cd backend
docker compose up -d db                       # tests use a throwaway "tracker_test" DB
.venv/Scripts/python -m pytest                # unit + integration + authz matrix
.venv/Scripts/python -m scripts.smoke         # fast end-to-end check against a running API
```

`tests/authz/` is the control evidence for access‑control audits: each endpoint ×
each role, asserting allow or deny, plus row‑level‑filtering tests.

```bash
cd frontend
npm run typecheck && npm run lint && npm run build
```

```bash
# infra
bicep build infra/main.bicep
```

---

## Layout

```
backend/    FastAPI app, Alembic migrations, tests (unit / integration / authz)
frontend/   React SPA — features/ (auth, projects, tasks, my-tasks, search), components/ui (KB design system)
infra/      Bicep — main.bicep + modules/ + envs/{dev,test,staging,prod} + policy/
docs/       spec.md · adr/ · compliance/
```

Conventions: [`docs/spec.md` §12](docs/spec.md). Decisions: [`docs/adr/`](docs/adr/).
