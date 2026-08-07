# Incident Postmortem — Checkout Double-Charge Bug

**Incident date:** 2026-07-16
**Severity:** SEV-1 (customer-impacting, financial)
**Author:** Tom Reyes
**Status:** Root cause fixed; remediation in progress

## Summary

Between 2026-07-16 03:12 UTC and 05:48 UTC, a retry-logic defect in the checkout service caused
approximately 340 customers to be charged twice for a single order when their payment provider
timed out and the client auto-retried. Total duplicate-charge value: approximately €18,600, since
refunded.

## Root Cause

The checkout retry path did not include an idempotency key, so a client-side retry after a
provider timeout created a second, distinct charge instead of being recognized as a duplicate of
the original request.

## Immediate Fix

The customer-facing retry button was disabled and replaced with an automatic server-side retry
that does not double-submit. This shipped same-day.

## Outstanding Remediation

The underlying fix — adding idempotency keys to the payment retry path across all checkout entry
points, not just the one that caused this incident — is tracked as NOV-204. **This ticket is not
yet assigned and has no target date.** Without it, the same class of bug can recur through a
different retry path (e.g. the mobile app's checkout flow, which was not affected this time but
shares the same underlying retry logic).

## Recommendation

NOV-204 should be prioritized before the September 1 Checkout Redesign launch, since the redesign
introduces two new retry paths (guest checkout and saved-payment-method checkout) that would
inherit the same defect if idempotency keys aren't in place first.
