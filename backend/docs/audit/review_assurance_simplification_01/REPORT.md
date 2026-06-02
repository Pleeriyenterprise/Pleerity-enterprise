# REVIEW-ASSURANCE-SIMPLIFICATION-01

**Classification:** `VERIFIED_OPERATIONALLY`  
**Verified at:** 2026-06-02T21:06:17.846266+00:00

## Summary

Removed the organisation review assurance model. The platform now exposes three tiers only:

1. **SELF_RECORDED** — declarations and structured evidence recorded on file without org Verify/Reject.
2. **PLATFORM_REVIEWED** — escalation and platform-admin review queues.
3. **VERIFIED_DOCUMENT** — existing certificate verification path.

## Changes

- Backend: `cer_governance_presentation` remaps former org-reviewed codes to `GF_SELF`; `derive_assurance_tier`; org queue match always false.
- Backend: `review_queue_service.list_org_review_queue` returns deprecated empty payload.
- Frontend: removed org operator Verify/Reject; assurance panel in requirement modal; deprecated org compliance review page.
- Fixed: `pickPendingOrgReviewCer` reference removed from modal CER load (runtime error).

## Regression

Backend and frontend unit tests pass for assurance and queue invariants.

## Watchlist

See `watchlist.md`.
