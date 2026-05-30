# PRELAUNCH-QUOTE-NEGOTIATION-WORKFLOW-01

**Classification:** VERIFIED_OPERATIONALLY  
**Closeout captured:** 2026-05-30T14:12:58Z  
**Backend deploy SHA:** `d9c42f25de2402ccd6450e46d60e0aa7b276b3cb`  
**Frontend bundle:** `/static/js/main.4d32f901.js` (Vercel; includes `c8002313` ESLint fix)

## Summary

Quote negotiation is governed end-to-end on staging: revision request preserves assignment and lineage, contractor resubmit works, approval authorises work, and explicit final decline is available without cancelling the work order.

## Runtime proof

| Step | Result |
|------|--------|
| Contractor submits quote v1 | `QUOTED`, history v1 |
| Landlord requests revision | `REVISION_REQUESTED`, contractor retained |
| Contractor submits quote v2 | `QUOTED`, history grows |
| Landlord approves v2 | `APPROVED` / work authorised |
| Final decline (separate WO) | `REJECTED_FINAL` |
| Duplicate work orders | None |
| Frontend bundle markers | `request-quote-revision`, `Request changes`, `Submit revised quote` |
| Landlord UX authority | `request_quote_revision` in `next_actions` at `QUOTED` (+ deployed bundle) |

## Upgrade from PARTIAL

Initial closeout (2026-05-30T13:45Z) was **PARTIAL** because Vercel had not deployed the frontend (`main.23bfdc0f.js`). After `c8002313` fixed the CI build and Vercel shipped `main.4d32f901.js`, re-run passed all checks.

## Failed checks

None.
