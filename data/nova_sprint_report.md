# Sprint 22 Report — Team Nova
**Project:** Checkout Redesign
**Sprint dates:** 2026-07-13 to 2026-07-24
**Prepared by:** Tom Reyes, Delivery Lead
**Overall status:** 🟢 On Track

## Summary

Team Nova delivered 31 of 33 committed story points this sprint. Overall project RAG status
remains green heading into the final two sprints before the September 1st launch.

## Ticket Highlights

- NOV-201 ("Fix double-charge bug on checkout retry") is marked P0 following last week's
  production incident. Root cause fix is merged; the remediation ticket to add idempotency keys
  to the payment retry path (NOV-204) is still open and unassigned.
- NOV-190 ("Migrate to Payments v3 API") is in progress. No blocking issues reported this sprint.
- CI pipeline flakiness that affected Sprint 20 and 21 has been resolved as of 2026-07-15
  (see NOV-175, closed).

## Team Notes

Good momentum overall. QA sign-off on the checkout flow is expected by end of Sprint 23.

## Next Sprint

Sprint 23 planning is scheduled for 2026-07-27. No blockers currently flagged for the September 1 launch date.
