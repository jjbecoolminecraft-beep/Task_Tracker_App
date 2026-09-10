# Enterprise Project & Task Tracker — Project Specification

**Status:** Draft v0.1 (foundation document for implementation)
**Deployment model:** Internal application, single corporate Entra ID tenant
**Target scale:** 500–5,000 named users
**Primary cloud:** Microsoft Azure (EU regions)
**Stack:** Python / FastAPI + React (TypeScript), Azure Container Apps

---

## 1. Purpose and Scope

### 1.1 Goal

Provide a single, company-wide system for planning, assigning, and tracking project work. It replaces the current spread of spreadsheets, mailboxes, and departmental tools with one authoritative source of task state, while remaining lightweight enough that non-technical teams adopt it voluntarily.

### 1.2 In scope

- Hierarchical work management: Portfolio → Project → Task → Subtask
- Assignment, due dates, status workflow, priority, effort estimates
- Cross-team visibility with enforced access control
- Comments, mentions, and file attachments on tasks
- Saved views, filtering, and full-text search
- Notifications (in-app, email digest, Microsoft Teams)
- Dashboards and reporting at project and portfolio level
- Full REST API for integrations and automation
- Audit trail of all state changes
- Import from CSV / existing tools; export to CSV and JSON

### 1.3 Explicitly out of scope (v1)

- Time tracking and billing
- Resource capacity planning and financial forecasting
- Gantt / dependency-based critical path scheduling
- Native mobile applications (responsive web only)
- Customer-facing portals or external guest access
- Individual productivity scoring, ranking, or performance analytics
  *(deliberately excluded — see §8.4 Works Council constraints)*

### 1.4 Success criteria

| Metric | Target |
|---|---|
| Adoption | ≥ 70% of target departments active within 6 months |
| Availability | 99.5% monthly during business hours |
| API p95 latency | < 400 ms for list/read operations |
| Search p95 latency | < 800 ms across full corpus |
| Onboarding effort | New user productive without training material |
| Security | Zero critical findings at penetration test before go-live |

---

## 2. Users, Roles and Permissions

### 2.1 Identity

All identities originate from corporate Entra ID. There is no local user registration, no local password store, and no separate credential lifecycle. Users are provisioned via SCIM or just-in-time on first successful sign-in, and deprovisioned when disabled in Entra ID.

### 2.2 Role model

Roles apply at a defined scope. A user may hold different roles in different scopes.

| Role | Scope | Capabilities |
|---|---|---|
| **System Admin** | Global | Configuration, role grants, retention settings, integrations. Cannot read task content by default. |
| **Auditor** | Global | Read-only access to audit logs. No task content access. |
| **Portfolio Owner** | Portfolio | Create/archive projects, view aggregate reporting across the portfolio |
| **Project Admin** | Project | Manage project settings, membership, workflow states, archive project |
| **Contributor** | Project | Create/edit/complete tasks, comment, attach files |
| **Viewer** | Project | Read-only access to tasks and comments |
| **Guest** | Task | Access limited to explicitly shared tasks (internal users only) |

### 2.3 Authorization principles

- **Deny by default.** No implicit organization-wide read access. A user sees a project only through explicit membership or an explicitly configured "internally visible" flag on that project.
- **Scoped evaluation.** Every request resolves the caller's effective role for the target resource before any data is returned. Authorization is enforced in the service layer, never only in the UI.
- **Group-driven membership.** Project membership may be bound to an Entra ID security group so that access follows the HR/org lifecycle automatically.
- **Admin ≠ reader.** Platform administration and content access are separate privileges. Elevation to read content requires a justified, time-boxed, and audited break-glass grant.

---

## 3. Domain Model

### 3.1 Core entities

```
Organization (single instance)
 └── Portfolio
      └── Project
           ├── Task
           │    ├── Subtask (self-referencing Task, parent_task_id)
           │    ├── Comment
           │    ├── Attachment
           │    └── TaskLabel  ──►  Label
           ├── ProjectMember  ──►  User / EntraGroup
           └── WorkflowState (per-project configurable)

User (mirrored from Entra ID)
AuditEvent (append-only, global)
Notification
SavedView
```

### 3.2 Key tables (PostgreSQL sketch)

```sql
-- Users mirrored from Entra ID; never a credential store.
users (
  id                uuid primary key,
  entra_object_id   uuid unique not null,
  upn               citext not null,
  display_name      text not null,
  department        text,
  is_active         boolean not null default true,
  deactivated_at    timestamptz,
  created_at        timestamptz not null default now()
)

projects (
  id                uuid primary key,
  portfolio_id      uuid references portfolios(id),
  key               citext unique not null,       -- e.g. "MKTG"
  name              text not null,
  description       text,
  visibility        text not null default 'private',  -- private | internal
  status            text not null default 'active',   -- active | archived
  created_by        uuid references users(id),
  created_at        timestamptz not null default now(),
  archived_at       timestamptz
)

tasks (
  id                uuid primary key,
  project_id        uuid not null references projects(id),
  parent_task_id    uuid references tasks(id),
  seq               bigint not null,              -- human ref: MKTG-142
  title             text not null,
  description       text,
  state_id          uuid not null references workflow_states(id),
  priority          smallint not null default 3,  -- 1 highest .. 5 lowest
  assignee_id       uuid references users(id),
  reporter_id       uuid not null references users(id),
  due_date          date,
  estimate_hours    numeric(6,2),
  search_vector     tsvector,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),
  completed_at      timestamptz,
  deleted_at        timestamptz,                  -- soft delete
  unique (project_id, seq)
)

audit_events (
  id            bigserial primary key,
  occurred_at   timestamptz not null default now(),
  actor_id      uuid,
  actor_upn     citext,
  action        text not null,        -- task.updated, project.member_added, ...
  resource_type text not null,
  resource_id   uuid,
  project_id    uuid,
  before        jsonb,
  after         jsonb,
  ip_address    inet,
  request_id    uuid
)
```

### 3.3 Modelling decisions

- **Subtasks reuse the task table** via `parent_task_id`. Depth is limited to 2 levels in v1 to avoid unbounded recursion in queries and UI.
- **Human-readable references** (`MKTG-142`) come from a per-project sequence. Users cite these in Teams and email; UUIDs alone are unusable in conversation.
- **Soft delete** everywhere (`deleted_at`). Hard deletion is a separate, audited retention job — see §8.3.
- **Workflow states are per-project rows**, not an enum. Engineering wants "In Review"; Marketing wants "Awaiting Approval". A hardcoded enum guarantees a migration within a year.
- **Full-text search via PostgreSQL `tsvector`** with GIN indexes. At 5,000 users this is more than sufficient; a dedicated search service is unwarranted complexity. Revisit only if corpus exceeds a few million tasks.
- **Audit events are append-only.** No UPDATE or DELETE grants on that table for the application role.

---

## 4. Functional Requirements

### 4.1 Phase 1 — MVP (must have)

| ID | Requirement |
|---|---|
| F-01 | SSO sign-in via Entra ID (OIDC authorization code + PKCE) |
| F-02 | Create, edit, archive projects; configure workflow states |
| F-03 | Create, edit, assign, complete, soft-delete tasks and subtasks |
| F-04 | Project membership management, incl. Entra group binding |
| F-05 | List view with filter, sort, and pagination |
| F-06 | Board (kanban) view grouped by workflow state |
| F-07 | Comments with `@mention` |
| F-08 | File attachments (Blob Storage, virus-scanned) |
| F-09 | Full-text search scoped to the caller's accessible projects |
| F-10 | In-app notifications and daily email digest |
| F-11 | Audit log of all mutations |
| F-12 | CSV import and CSV/JSON export |
| F-13 | Personal "My tasks" view across all accessible projects |

### 4.2 Phase 2 — Should have

| ID | Requirement |
|---|---|
| F-20 | Saved and shared views with custom filters |
| F-21 | Microsoft Teams notifications and task creation from Teams |
| F-22 | Project dashboards (throughput, state distribution, overdue count) |
| F-23 | Recurring tasks |
| F-24 | Task templates and project templates |
| F-25 | Bulk edit operations |
| F-26 | Simple task dependencies (blocks / blocked by) |
| F-27 | Real-time collaborative updates (WebSocket push) |

### 4.3 Phase 3 — Later

| ID | Requirement |
|---|---|
| F-30 | Portfolio-level roll-up reporting |
| F-31 | Custom fields per project |
| F-32 | Outlook / Microsoft 365 calendar integration for due dates |
| F-33 | Webhooks and automation rules |
| F-34 | Power BI dataset export for aggregated reporting |

---

## 5. Technical Concept

### 5.1 Stack

| Layer | Technology | Rationale |
|---|---|---|
| Frontend | React 18 + TypeScript, Vite | Standard, large talent pool |
| UI | Tailwind CSS + shadcn/ui | Fast, consistent, accessible primitives |
| Client state | TanStack Query + Zustand | Server-cache separation from UI state |
| Backend | Python 3.12, FastAPI | Chosen stack; async, typed, OpenAPI-native |
| ORM | SQLAlchemy 2.x (async) + Alembic | Mature migrations, explicit control |
| Validation | Pydantic v2 | Shared with FastAPI, generates the API schema |
| Database | Azure Database for PostgreSQL Flexible Server 16 | Relational fit, JSONB, native FTS, zone-redundant HA |
| Cache / pub-sub | Azure Cache for Redis | Session cache, rate limiting, WebSocket fan-out |
| Async jobs | Celery or ARQ + Redis broker | Digests, imports, exports, retention jobs |
| Object storage | Azure Blob Storage | Attachments, export artifacts |
| Compute | Azure Container Apps | Managed scale-to-zero, no Kubernetes operations burden |
| IaC | Bicep (or Terraform) | Reproducible environments, reviewable changes |
| CI/CD | GitHub Actions (or Azure DevOps) | Build, test, scan, deploy |

### 5.2 API design

- REST, versioned under `/api/v1`, OpenAPI 3.1 generated from FastAPI.
- Resource-oriented paths: `/projects/{id}/tasks`, `/tasks/{id}/comments`.
- Cursor-based pagination for all collections. Offset pagination degrades badly and is inconsistent under concurrent writes.
- `PATCH` with optimistic concurrency via `If-Match` / ETag on tasks, to prevent silent overwrite when two people edit simultaneously.
- Consistent error envelope: `{ "error": { "code", "message", "details", "request_id" } }`.
- Every response carries `X-Request-Id`, propagated into logs and audit events.
- Rate limiting per user and per client application, enforced at the API and at the gateway.

### 5.3 Frontend approach

- SPA served as static assets via Azure Static Web Apps behind Front Door.
- MSAL.js for the Entra ID authorization code flow; access tokens held in memory, refresh handled by MSAL. **No tokens in `localStorage`.**
- Optimistic UI updates for task state changes, reconciled against server response.
- Route-level code splitting; the board and list views are the only heavy bundles.
- WCAG 2.1 AA as the accessibility baseline — keyboard-navigable board, visible focus states, screen-reader labels on all interactive controls.

### 5.4 Background processing

| Job | Schedule | Purpose |
|---|---|---|
| Email digest | Daily, per-user timezone | Batched notifications |
| Entra sync | Hourly | User attribute and deactivation sync |
| Retention sweep | Nightly | Hard-delete records past retention period |
| Attachment scan | On upload | Malware scanning before availability |
| Import processor | On demand | Large CSV imports, off the request path |
| Search vector refresh | On write (trigger) | Maintain `tsvector` |

---

## 6. Azure Architecture

### 6.1 Component topology

```
                    Internet
                       │
            ┌──────────▼───────────┐
            │  Azure Front Door    │  TLS termination, WAF (OWASP ruleset),
            │  + WAF Policy        │  DDoS protection, geo-filtering
            └──────────┬───────────┘
                       │
        ┌──────────────┴──────────────┐
        │                             │
┌───────▼─────────┐        ┌──────────▼────────────┐
│ Static Web App  │        │  Container Apps Env    │
│ (React SPA)     │        │  (VNet-integrated)     │
└─────────────────┘        │  ├── api  (FastAPI)    │
                           │  ├── worker (jobs)     │
                           │  └── scheduler         │
                           └──────────┬─────────────┘
                                      │  private endpoints only
        ┌────────────┬────────────────┼──────────────┬─────────────┐
        │            │                │              │             │
┌───────▼──────┐ ┌───▼────────┐ ┌─────▼──────┐ ┌─────▼─────┐ ┌─────▼──────┐
│ PostgreSQL   │ │ Redis      │ │ Blob       │ │ Key Vault │ │ App        │
│ Flexible Srv │ │ Cache      │ │ Storage    │ │           │ │ Insights   │
│ Zone-redund. │ │            │ │ (private)  │ │           │ │            │
└──────────────┘ └────────────┘ └────────────┘ └───────────┘ └────────────┘

Cross-cutting: Entra ID (auth), Managed Identity (service auth),
Defender for Cloud, Azure Policy, Log Analytics, Azure Backup
```

### 6.2 Network design

- Single VNet per environment with dedicated subnets: `snet-aca` (Container Apps delegated), `snet-data` (private endpoints), `snet-mgmt`.
- **All PaaS data services reachable only via private endpoints.** Public network access is disabled on PostgreSQL, Redis, Blob Storage, and Key Vault.
- Private DNS zones for name resolution to private endpoints.
- Only Front Door reaches the ingress; the Container Apps environment accepts traffic exclusively from the Front Door private link origin.
- No public IP on any compute resource. No jump box with standing access — administrative access via Entra Privileged Identity Management with just-in-time elevation.

### 6.3 Identity and secrets

- **Managed Identity for every service-to-service call.** The API authenticates to PostgreSQL, Blob Storage, Redis, and Key Vault with its user-assigned managed identity.
- **No connection strings or passwords in application configuration.** Entra ID authentication for PostgreSQL; RBAC data-plane roles for Blob Storage.
- Key Vault holds only secrets that genuinely cannot be replaced by managed identity (third-party API keys, signing keys). Soft-delete and purge protection enabled.
- Key rotation automated; secrets referenced by Key Vault reference, never copied into environment variables at build time.

### 6.4 Data residency

- All resources deployed in **West Europe** with paired region **North Europe** for backups and disaster recovery. Both are within the EU Data Boundary.
- Application Insights and Log Analytics workspaces pinned to the same EU region.
- No resource type is provisioned that lacks EU regional availability. Any service that would process data outside the EU is rejected at architecture review.
- Azure Policy denies resource creation outside the approved region list.

### 6.5 Environments

| Environment | Purpose | Data |
|---|---|---|
| `dev` | Developer integration | Synthetic only |
| `test` | QA, automated E2E | Synthetic only |
| `staging` | Pre-production, perf tests | Anonymized subset or synthetic |
| `prod` | Live | Real |

**Production data is never copied to lower environments.** Test data is generated, not extracted. This removes an entire class of GDPR and audit findings.

### 6.6 Resilience and continuity

| Aspect | Target / Approach |
|---|---|
| RPO | ≤ 15 minutes (PostgreSQL PITR + geo-redundant backup) |
| RTO | ≤ 4 hours |
| Database HA | Zone-redundant high availability, automatic failover |
| Backups | Automated daily, 35-day PITR retention, geo-redundant |
| Restore testing | Quarterly documented restore drill |
| Deployment | Blue/green via Container Apps revisions, traffic-weighted rollout |
| Rollback | Revert traffic to prior revision; migrations must be backward-compatible |

### 6.7 Cost outline (indicative, monthly, ~2,000 active users)

| Component | Approximate range |
|---|---|
| Container Apps (3 apps, autoscaled) | €150 – €400 |
| PostgreSQL Flexible Server (GP, zone-redundant HA) | €350 – €600 |
| Redis Cache (Standard C1) | €50 – €90 |
| Blob Storage + egress | €30 – €100 |
| Front Door Premium + WAF | €280 – €350 |
| Log Analytics / App Insights | €80 – €250 |
| Static Web App (Standard) | €15 |
| **Total** | **≈ €950 – €1,800** |

Front Door Premium is the largest fixed line item; Front Door Standard is a viable reduction if the private-link origin and advanced WAF rules are not required. Verify current pricing with the Azure pricing calculator before budgeting.

---

## 7. Security Concept (SOC 2 / ISO 27001 alignment)

### 7.1 Authentication

- OIDC authorization code flow with PKCE against Entra ID. No implicit flow.
- MFA and Conditional Access enforced at the Entra ID level — the application inherits corporate policy rather than reimplementing it.
- Access tokens short-lived (≤ 60 min); refresh handled by MSAL.
- Service-to-service authentication exclusively via managed identity.
- Service principals for automation use certificate credentials, rotated automatically, scoped to the minimum required permissions.

### 7.2 Authorization

- Centralized policy layer: a single `authorize(actor, action, resource)` function that every endpoint calls. No permission logic scattered across route handlers.
- Row-level filtering applied at the query layer so a missing check cannot leak data — accessible project IDs are resolved once per request and joined into every content query.
- Automated test suite asserting that each endpoint rejects each role that should not have access. This suite is the primary control evidence for access-control audits.

### 7.3 Data protection

| Control | Implementation |
|---|---|
| Encryption in transit | TLS 1.2 minimum, TLS 1.3 preferred, HSTS enforced |
| Encryption at rest | Azure platform encryption; customer-managed keys in Key Vault where policy requires |
| Attachment scanning | Malware scan before the blob becomes downloadable |
| Attachment access | Short-lived user-delegation SAS; no public container access |
| Input validation | Pydantic models on every request body and query parameter |
| Injection defense | Parameterized queries via SQLAlchemy; no string-built SQL |
| XSS defense | React auto-escaping; sanitize any rendered rich text; strict CSP |
| CSRF | Bearer-token API with no cookie-based session |
| Secrets in code | Pre-commit secret scanning + GitHub secret scanning + push protection |

### 7.4 Logging, monitoring, detection

- Structured JSON logs with correlation IDs, shipped to Log Analytics.
- **Personal data is never written to application logs.** Log user IDs, not names, emails, or task content. Enforce with a log-redaction filter and a test.
- Security-relevant events routed to Microsoft Sentinel: failed authorizations, privilege grants, break-glass elevation, bulk exports, mass deletion, anomalous access volume.
- Alerting on error rate, latency, failed logins, and unusual export activity.
- Log retention: 90 days hot, 1 year archived — aligned with the incident investigation window.

### 7.5 Secure development lifecycle

| Gate | Tooling |
|---|---|
| Dependency vulnerabilities | Dependabot + `pip-audit` + `npm audit` in CI |
| Static analysis | Bandit (Python), ESLint security plugin, CodeQL |
| Container scanning | Microsoft Defender for Containers / Trivy on every image |
| IaC scanning | Checkov or PSRule for Azure |
| Secret scanning | Pre-commit + CI + GitHub push protection |
| Code review | Mandatory PR review, no direct push to `main` |
| Penetration test | External test before go-live, annually thereafter |

**CI fails the build on any high or critical finding.** A warning that nobody reads is not a control.

### 7.6 Operational controls

- Least-privilege Azure RBAC; no standing Owner or Contributor on production.
- Privileged Identity Management for time-boxed, approved, audited elevation.
- All infrastructure changes via IaC pull request. Manual portal changes in production are prohibited and detected via drift scanning.
- Documented incident response plan with named roles, severity classification, and a 72-hour GDPR breach-notification path.
- Change management: every production deployment traceable to a reviewed, approved commit.

### 7.7 Control mapping (evidence anchors)

| ISO 27001 Annex A | Implementation reference |
|---|---|
| A.5.15 Access control | §2.3, §7.2 |
| A.5.16 Identity management | §2.1, Entra ID lifecycle |
| A.5.17 Authentication information | §7.1, managed identity, Key Vault |
| A.8.2 Privileged access rights | §7.6, PIM |
| A.8.5 Secure authentication | §7.1, MFA via Conditional Access |
| A.8.9 Configuration management | §6.5, IaC, Azure Policy |
| A.8.12 Data leakage prevention | §7.3, §7.4, export monitoring |
| A.8.15 Logging | §7.4 |
| A.8.16 Monitoring activities | §7.4, Sentinel |
| A.8.24 Use of cryptography | §7.3 |
| A.8.25–8.28 Secure development | §7.5 |
| A.8.32 Change management | §7.6 |

---

## 8. Data Protection (GDPR) and Employee Representation

### 8.1 Processing basis

Processing of employee personal data is grounded in legitimate interest (Art. 6(1)(f) GDPR) for organizing work, and where applicable in the employment contract (Art. 6(1)(b)) and in the collective agreement concluded with the works council. **Consent is not a valid basis in an employment context** — the imbalance of power makes it non-free.

### 8.2 Data inventory

| Category | Examples | Sensitivity |
|---|---|---|
| Identity | Name, UPN, object ID, department | Personal |
| Activity | Task assignments, state changes, timestamps | Personal — behaviour |
| Content | Task titles, descriptions, comments, attachments | Potentially personal (free text) |
| Technical | IP address, request ID, user agent | Personal |
| Audit | Actor, action, before/after values | Personal — behaviour |

Free-text fields are the principal risk: users will inevitably enter personal data about colleagues, customers, and third parties. Address this through user guidance and an explicit policy, not through technical filtering — filtering free text reliably is not achievable.

### 8.3 Retention and deletion

| Data | Retention | Mechanism |
|---|---|---|
| Active tasks and projects | While project active | — |
| Archived projects | 24 months after archival, then purge | Nightly retention job |
| Soft-deleted tasks | 30 days, then hard delete | Nightly retention job |
| Comments | With parent task | Cascade |
| Attachments | With parent task | Blob lifecycle policy |
| Audit events | 12 months | Partitioned table, monthly drop |
| Application logs | 90 days hot / 12 months archive | Log Analytics retention |
| Deactivated users | Pseudonymized 90 days after Entra deactivation | Sync job |

**Leaver handling:** on deactivation in Entra ID the account loses access immediately. After 90 days, the user record is pseudonymized — display name replaced with a stable placeholder ("Former employee #1234") while foreign keys remain intact. This preserves project history without retaining an identifiable profile.

### 8.4 Works council / co-determination constraints

This system processes data about employee work behaviour and is therefore subject to co-determination. These constraints are **product requirements, not optional policy**, and must be visible in the code:

1. **No individual performance metrics.** No throughput-per-person charts, no completion-rate leaderboards, no comparative rankings, no "productivity score". This is excluded at the data-model and API level, not merely hidden in the UI.
2. **Reporting is aggregated.** Dashboards report at project and team level. Any breakdown resolving to fewer than five individuals is suppressed.
3. **No covert monitoring.** No keystroke capture, no active-time tracking, no screenshotting, no login-duration surveillance.
4. **Restricted audit access.** Audit logs are visible only to the Auditor role and only for defined purposes (security investigation, compliance). Line managers have no audit access to their reports' activity.
5. **Transparency.** Users can see what data the system holds about them and who has accessed it.
6. **Export controls.** Bulk exports are audited and alerted. An export of all activity for a named individual requires the same authorization path as a security investigation.
7. **Documented agreement.** A works agreement (Betriebsvereinbarung) covering purpose, data categories, retention, access, and the exclusion of performance monitoring must be concluded **before production rollout**, not retrofitted.

Involve the works council at design stage. Retrofitting co-determination after launch is the most common cause of an otherwise finished internal tool never going live.

### 8.5 Data subject rights

| Right | Implementation |
|---|---|
| Access (Art. 15) | Self-service export of all records referencing the user |
| Rectification (Art. 16) | Users edit their own content; identity attributes correct via Entra ID |
| Erasure (Art. 17) | Pseudonymization workflow; balanced against retention obligations |
| Restriction (Art. 18) | Account flag suspending processing pending resolution |
| Portability (Art. 20) | JSON export of user-authored content |
| Objection (Art. 21) | Documented process routed to the DPO |

Target response time: 30 days, with an internal target of 10 working days.

### 8.6 Required documentation

- [ ] Record of Processing Activities (Art. 30) entry
- [ ] Data Protection Impact Assessment — **likely mandatory**: systematic processing of employee behavioural data at scale
- [ ] Technical and organizational measures documentation (Art. 32)
- [ ] Data Processing Agreement with Microsoft (Azure) on file
- [ ] Subprocessor list and review
- [ ] Privacy notice for employees
- [ ] Works agreement with the works council
- [ ] Deletion and retention concept
- [ ] Incident response and breach notification procedure

### 8.7 Privacy by design decisions

- Data minimization: collect only what a task tracker needs. No mood tracking, no optional profile enrichment, no analytics SDK.
- No third-party analytics or session-replay tooling. Product telemetry, if any, is aggregate and self-hosted in Azure.
- Personal data excluded from logs by design (§7.4).
- Pseudonymization as the default deletion strategy, preserving referential integrity.
- Purpose limitation enforced by the role model: administration and content access are separate.

---

## 9. Non-Functional Requirements

| Category | Requirement |
|---|---|
| Availability | 99.5% monthly, business hours 07:00–19:00 CET |
| API latency | p95 < 400 ms read, < 700 ms write |
| Search latency | p95 < 800 ms |
| Concurrency | 500 concurrent active sessions without degradation |
| Data volume | Design for 2M tasks, 10M comments, 5M audit events |
| Scalability | Horizontal API scaling; DB vertical scaling with read replica option |
| Browser support | Current and prior version of Edge, Chrome, Firefox, Safari |
| Accessibility | WCAG 2.1 AA |
| Localization | English and German at launch; all UI strings externalized |
| Timezone | Store UTC; render in user's local timezone |
| Maintainability | ≥ 80% test coverage on service and authorization layers |
| Observability | Distributed tracing across API, worker, and database |

---

## 10. Delivery Plan

| Phase | Duration | Deliverable |
|---|---|---|
| **0 — Foundations** | 3 weeks | Azure landing zone, IaC, CI/CD, Entra app registration, DPIA started, works council engaged |
| **1 — Core domain** | 6 weeks | Data model, migrations, auth, authorization layer, project + task CRUD API |
| **2 — Web application** | 6 weeks | SPA shell, list and board views, task detail, comments, search |
| **3 — Collaboration** | 4 weeks | Attachments, notifications, email digest, audit log UI, import/export |
| **4 — Hardening** | 4 weeks | Performance testing, penetration test, accessibility audit, DR drill, documentation |
| **5 — Pilot** | 4 weeks | One department, ~50 users, feedback loop, iteration |
| **6 — Rollout** | 8 weeks | Staged department-by-department, training material, support process |

**Gate before rollout:** DPIA signed, works agreement concluded, penetration test findings remediated, restore drill successful.

Run the compliance workstream in parallel from Phase 0. It has a longer lead time than the software and is the more common cause of delay.

---

## 11. Open Decisions

These need answers before or during Phase 0. They are deliberately left open rather than assumed.

| # | Decision | Options | Impact |
|---|---|---|---|
| D-01 | Attachment storage limit per project | 5 GB / 50 GB / unlimited | Cost, lifecycle policy |
| D-02 | Front Door tier | Standard vs Premium (private link, advanced WAF) | ~€200/month, network design |
| D-03 | IaC tooling | Bicep vs Terraform | Team skills, existing standard |
| D-04 | CI/CD platform | GitHub Actions vs Azure DevOps | Existing corporate standard |
| D-05 | User provisioning | SCIM vs JIT on first login | Sync complexity, leaver latency |
| D-06 | Default project visibility | Private vs internal-readable | Adoption vs least privilege |
| D-07 | Teams integration depth | Notifications only vs full bot | Phase 2 scope |
| D-08 | Customer-managed keys | Platform keys vs CMK in Key Vault | Compliance posture, key ops burden |
| D-09 | Audit retention | 12 vs 24 months | Storage, audit expectations |
| D-10 | Real-time transport | WebSocket vs polling | Complexity vs UX in Phase 2 |
| D-11 | Support model | Internal IT vs dedicated product team | Long-term ownership |
| D-12 | Migration source systems | Which tools, how much history | Import scope, Phase 3 effort |

---

## 12. Repository and Implementation Conventions

Intended starting structure for the Claude Code project.

```
task-tracker/
├── README.md
├── docs/
│   ├── spec.md                 # this document
│   ├── adr/                    # architecture decision records
│   └── compliance/             # DPIA, RoPA, works agreement drafts
├── infra/
│   ├── modules/                # Bicep modules
│   ├── envs/{dev,test,staging,prod}/
│   └── policy/                 # Azure Policy definitions
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/v1/             # routers
│   │   ├── core/               # config, security, auth, logging
│   │   ├── domain/             # entities, value objects
│   │   ├── services/           # business logic + authorize()
│   │   ├── repositories/       # data access
│   │   ├── models/             # SQLAlchemy
│   │   ├── schemas/            # Pydantic
│   │   └── workers/            # background jobs
│   ├── migrations/             # Alembic
│   ├── tests/{unit,integration,authz}/
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── features/           # feature-sliced: projects, tasks, search
│   │   ├── components/
│   │   ├── lib/                # api client, auth, hooks
│   │   └── routes/
│   └── package.json
└── .github/workflows/
```

### Conventions

- **Authorization in one place.** All access decisions route through `services/authorization.py`. A route handler never inspects roles directly.
- **Repositories return domain objects**, not ORM rows. Keeps SQLAlchemy out of the service layer.
- **Every mutation writes an audit event** in the same transaction as the change. Not in a callback, not best-effort.
- **Migrations are backward-compatible.** Expand, migrate, contract — never a breaking schema change in a single deployment.
- **`tests/authz/` is a first-class suite**, not an afterthought. Each endpoint × each role, asserting allow or deny. This is both a control and the audit evidence.
- **No personal data in logs.** Enforced by a redaction filter with a test that fails if the filter is bypassed.
- **ADRs for every significant choice.** Auditors ask why; a dated decision record answers in seconds.

---

## 13. Getting Started with Claude Code

Suggested opening sequence once this document is in `docs/spec.md`:

1. Scaffold the repository structure and tooling (linting, formatting, pre-commit, CI skeleton).
2. Implement the data model and Alembic migrations from §3.
3. Build the authentication layer: Entra ID OIDC validation, token verification, user provisioning.
4. Build the authorization layer and its test suite **before any feature endpoints**. Retrofitting authorization onto existing endpoints reliably leaves gaps.
5. Implement project and task CRUD against the authorization layer.
6. Add the audit event mechanism as transactional middleware.
7. Scaffold the frontend with MSAL authentication and the API client.
8. Build views feature by feature.

Work through §11 in parallel — each resolved decision becomes an ADR in `docs/adr/`.

---

*This document is the foundation, not the final word. Update it as decisions resolve; keep it in the repository so it is versioned alongside the code it describes.*
