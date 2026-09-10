# Retention & deletion concept — draft

Mirrors spec §8.3. Implemented by nightly background jobs (spec §5.4) and Blob
lifecycle policies; nothing relies on manual cleanup.

| Data | Retention | Mechanism |
|---|---|---|
| Active tasks & projects | While project active | — |
| Archived projects | 24 months after archival, then purge | Nightly retention job |
| Soft-deleted tasks (`deleted_at`) | 30 days, then hard delete | Nightly retention job |
| Comments | With parent task | Cascade delete |
| Attachments | With parent task | Blob lifecycle policy |
| Audit events | 12 months | Monthly-partitioned table, drop oldest partition |
| Application logs | 90 days hot / 12 months archive | Log Analytics retention |
| Deactivated users | Pseudonymised 90 days after Entra deactivation | Entra sync job |

## Leaver handling

On deactivation in Entra ID the account loses access immediately (hourly sync;
Conditional Access revokes sooner). After 90 days the `users` row is
pseudonymised: `display_name` → a stable placeholder (`Former employee #NNNN`),
`is_pseudonymized = true`, foreign keys intact. Project history is preserved
without retaining an identifiable profile.

## Data subject rights (spec §8.5)

| Right | Implementation |
|---|---|
| Access (Art. 15) | Self-service export of all records referencing the user |
| Rectification (Art. 16) | Users edit own content; identity attributes flow from Entra ID |
| Erasure (Art. 17) | Pseudonymisation workflow, balanced against retention obligations |
| Restriction (Art. 18) | Account flag suspending processing pending resolution |
| Portability (Art. 20) | JSON export of user-authored content |
| Objection (Art. 21) | Documented process routed to the DPO |

Target response: 30 days; internal target 10 working days.

## Verification

- Quarterly documented restore drill (spec §6.6).
- A test asserts the retention job selects the right rows and never touches
  in-window data. _(to be added alongside the worker implementation)_
