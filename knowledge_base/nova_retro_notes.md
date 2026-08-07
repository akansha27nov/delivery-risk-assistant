# Sprint 22 Retro Notes — Team Nova

**Date:** 2026-07-24
**Facilitator:** Tom Reyes

## What went well

- CI pipeline flakiness (tracked in NOV-175) that plagued Sprint 20 and 21 is now fully resolved.
  Build times back to normal, no flaky test failures in the last 9 days.
- Good incident response turnaround on the double-charge bug — same-day mitigation.

## What didn't go well

- The Payments v2 API deprecation (2026-08-20) came as a surprise mid-sprint even though, per
  Raj, it had apparently been "communicated org-wide" — it hadn't reached this team through any
  channel we'd normally check. Action item: get Nova added to the Payments platform team's
  release/deprecation announcement list.
- NOV-204 (idempotency key remediation) sat unassigned for over a week after the postmortem was
  published. Action item: postmortem remediation items should get an owner within 48 hours,
  not left to fall through sprint planning.

## Action items

1. Raj to confirm Payments v3 migration completion date and compare against 2026-08-20 deprecation
   deadline; escalate if there's a gap.
2. Tom to assign an owner to NOV-204 before Sprint 23 planning.
3. No action needed on CI flakiness — closed, monitoring only.
