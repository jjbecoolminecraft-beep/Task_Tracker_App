# 4. English-first UI, i18n from the start

- Status: accepted
- Date: 2026-09-10

## Context

Spec §9 requires English and German at launch, all UI strings externalised. The
question was only which locale to build against first and how much German to
carry during feature work.

## Decision

- **English is the default locale.** All strings live in
  `frontend/src/i18n/en.json`; components never hold literal user-facing text.
- German (`de.json`) is maintained in parallel as a full mirror of the key set,
  but English is the source of truth during feature development. A CI check (to
  be added) fails on key drift between the two files.
- Locale is chosen by the viewer and remembered per browser; dates and numbers
  render with `Intl` in the active locale. Timestamps are stored UTC and rendered
  local (spec §9).

## Consequences

- One canonical string file to review; translation is a bounded follow-up per
  feature rather than double bookkeeping in every PR.
- The German mirror already exists, so "German at launch" is a completeness pass,
  not a retrofit.
- Works-council-facing wording (data transparency screens, export notices) gets
  reviewed German copy before pilot, not machine translation.
