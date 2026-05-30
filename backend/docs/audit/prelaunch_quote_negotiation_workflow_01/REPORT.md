# PRELAUNCH-QUOTE-NEGOTIATION-WORKFLOW-01

**Classification:** PARTIAL  
**Captured:** 2026-05-30T13:45:05Z  
**Backend deploy SHA:** `1adb8f7348089afb555ceab5baf9d6491cbf134c`

## Summary

Quote negotiation lifecycle is implemented and **verified end-to-end on staging API**: submit v1 → request revision → resubmit v2 → approve → work authorised, with full `quote_negotiation_history` lineage and contractor assignment preserved throughout. Final quote decline tested on a separate work order.

**Remaining gap:** production frontend bundle (`main.23bfdc0f.js`) had not yet picked up landlord/contractor UI changes at closeout time — browser markers for `Request changes` and `request-quote-revision` were absent.

## Root cause (pre-remediation)

- Binary `REJECTED` status conflated quote decline with workflow termination semantics.
- No structured quote lineage; resubmit overwrote flat fields.
- No revision reason codes or contractor notification on landlord response.
- Landlord UI used a single “Reject quote” CTA.

## Remediation delivered

| Area | Change |
|------|--------|
| Lifecycle | `REVISION_REQUESTED`, `REJECTED_FINAL`; legacy `reject-quote` → revision request |
| Lineage | `quote_negotiation_history[]` on work orders |
| API | `POST /jobs/{id}/request-quote-revision`, `POST /jobs/{id}/reject-quote-final` |
| Landlord UX | Separate “Approve and authorise work”, “Request changes”, “Decline quote (final)” |
| Contractor UX | Revision feedback panel, quote history, “Submit revised quote” CTA |
| Notifications | Contractor email on revision request |

## Staging API proof (work order `7218a511-f0a4-4f9c-b29b-3b2031c2df9f`)

1. v1 submitted @ £320 — `QUOTED`, history v1 submitted
2. Revision requested — `REVISION_REQUESTED`, reason `price_too_high`, assignment retained
3. v2 resubmitted @ £275 — `QUOTED`, history 3 entries
4. Approved — `APPROVED` / “Work authorised”, history 4 entries including approved event
5. Final decline on separate WO — `REJECTED_FINAL`, contractor retained
6. No duplicate work orders from negotiation replay

## Failed closeout checks

- Frontend bundle marker `request-quote-revision`
- Landlord browser page “Request changes” copy

## Watchlist

Re-run `tmp_prelaunch_quote_negotiation_workflow_01.py` after frontend deploy completes to upgrade classification to **VERIFIED_OPERATIONALLY**.
