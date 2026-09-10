# Record of Processing Activities (Art. 30) — draft entry

| Field | Value |
|---|---|
| Processing activity | Enterprise Project & Task Tracker |
| Controller | _Company legal entity_ |
| DPO contact | _tbd_ |
| Purpose(s) | Planning, assigning and tracking project work; cross-team visibility with access control; audit trail of state changes |
| Lawful basis | Art. 6(1)(f); supported by Art. 6(1)(b) and the collective agreement. Not consent. |
| Categories of data subjects | Employees (named users provisioned from Entra ID) |
| Categories of personal data | Identity (name, UPN, object id, department); activity/behaviour (assignments, state changes, timestamps); free-text content (task titles, descriptions, comments, attachments — potentially personal); technical (IP address, request id, user agent); audit (actor, action, before/after values) |
| Special categories | None intended. Free text may inadvertently contain them — addressed by user guidance and policy. |
| Recipients | Internal users per role-based access control; Microsoft (Azure) as processor under DPA |
| Third-country transfers | None. All resources in the EU Data Boundary (West Europe primary, North Europe paired). Azure Policy denies non-EU regions. |
| Retention | Active data while project active; archived projects purged 24 months after archival; soft-deleted tasks hard-deleted after 30 days; audit events 12 months; application logs 90 days hot / 12 months archive; deactivated users pseudonymised after 90 days |
| Technical & organisational measures | Entra ID SSO + MFA/Conditional Access; centralised `authorize()` policy layer + automated authz test suite; row-level query filtering; TLS 1.2+ / HSTS; encryption at rest; private endpoints only; managed identity (no secrets in config); append-only audit table; personal data excluded from logs; malware-scanned attachments; SDL gates in CI |
| Automated decision-making | None |
