# Works agreement (Betriebsvereinbarung) — outline

Spec §8.4: this system processes data about employee work behaviour and is
therefore subject to co-determination. A works agreement covering purpose, data
categories, retention, access and the **exclusion of performance monitoring**
must be concluded **before production rollout**, not retrofitted. Involve the
works council at design stage.

The seven constraints below are **product requirements, not policy** — they are
enforced in the data model and API, and covered by tests.

## Proposed clauses

1. **Purpose limitation.** The system is for organising and tracking project
   work. It may not be used, directly or indirectly, for individual performance
   assessment, behavioural evaluation or disciplinary evidence-gathering.

2. **No individual performance metrics.** No throughput-per-person charts, no
   completion-rate leaderboards, no comparative rankings, no "productivity
   score". Excluded at the data-model and API level.
   *Evidence:* no such endpoint or aggregate exists; reporting code produces
   project/team-level figures only.

3. **Aggregated reporting only.** Dashboards report at project and team level.
   Any breakdown resolving to fewer than five individuals is suppressed.

4. **No covert monitoring.** No keystroke capture, active-time tracking,
   screenshotting or login-duration surveillance. No third-party analytics or
   session-replay tooling.

5. **Restricted audit access.** Audit logs are visible only to the Auditor role,
   only for security investigation and compliance. Line managers have no audit
   access to their reports' activity.
   *Evidence:* `GET /api/v1/audit` gated on the global Auditor grant; authz
   matrix asserts every other role is denied.

6. **Transparency.** Employees can see what data the system holds about them and
   who has accessed it (in-app view; self-service export).

7. **Export controls.** Bulk exports are audited and alerted. An export of all
   activity for a named individual requires the same authorisation path as a
   security investigation.

8. **Retention.** As per the retention & deletion concept; deactivated users
   pseudonymised after 90 days.

9. **Change control.** Material changes to data categories, retention, access
   model or reporting require renewed consultation with the works council.

10. **Review.** Joint review of the agreement and its technical implementation at
    _[interval, e.g. annually]_.

## Sign-off

_Works council chair · Employer representative · Date_
