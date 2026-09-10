# Data Protection Impact Assessment — outline

**Likely mandatory** (spec §8.6): systematic processing of employee behavioural
data at scale. Complete with the DPO before pilot.

## 1. Description of processing

- **Purpose:** organise, assign and track project work company-wide; replace
  spreadsheets and mailboxes with one authoritative task state.
- **Nature:** hierarchical work items (Portfolio → Project → Task → Subtask) with
  assignment, status, due dates, comments, attachments; audit trail of all state
  changes; in-app / email / Teams notifications; project- and team-level
  dashboards.
- **Scope:** 500–5,000 named employees in one Entra ID tenant, EU regions only.
- **Context:** internal tool, no external/guest access, no customer-facing
  portal. Subject to co-determination.

## 2. Lawful basis

Art. 6(1)(f) legitimate interest (organising work), supported where applicable by
Art. 6(1)(b) (employment contract) and the collective agreement. **Consent is not
used** — the employment power imbalance makes it non-free.

## 3. Data categories (see RoPA)

Identity; activity/behaviour (assignments, state changes, timestamps); free-text
content (titles, descriptions, comments, attachments); technical (IP, request id,
user agent); audit (actor, action, before/after).

Principal risk: free-text fields will contain personal data about colleagues,
customers and third parties. Mitigation is guidance + policy, not technical
filtering (unreliable).

## 4. Necessity & proportionality

- Data minimisation: only what a task tracker needs. No mood tracking, no profile
  enrichment, no analytics SDK, no session replay.
- Purpose limitation enforced by the role model: platform administration and
  content access are separate privileges (break-glass, time-boxed, audited).
- Retention limited and automated (see retention concept).

## 5. Risks to data subjects and mitigations

| Risk | Mitigation |
|---|---|
| Behavioural profiling / performance monitoring | Excluded at data-model and API level — no per-person throughput, no leaderboards, no productivity score (spec §8.4.1). Reporting aggregated; any breakdown < 5 individuals suppressed. |
| Covert monitoring | None: no keystroke/active-time/screenshot/login-duration capture (spec §8.4.3). |
| Line-manager surveillance via audit logs | Audit access restricted to the Auditor role for defined purposes; managers have none (spec §8.4.4). |
| Excessive retention | Nightly retention jobs; archived projects purged after 24 months; soft-deleted tasks hard-deleted after 30 days; audit events 12 months. |
| Personal data in logs | Redaction filter + test; log ids, never names/emails/content (spec §7.4). |
| Bulk export abuse | Exports audited and alerted; an all-activity export for a named individual follows the security-investigation authorisation path (spec §8.4.6). |
| Re-identification of "former employee" | Pseudonymisation 90 days after Entra deactivation; stable placeholder, FKs intact. |

## 6. Consultation

DPO: _tbd_. Works council: involve at design stage (spec §8.4). Data subjects:
privacy notice + in-app transparency view ("what the system holds about me and
who accessed it").

## 7. Outcome

_To be completed: residual risk rating, sign-off, review date._
