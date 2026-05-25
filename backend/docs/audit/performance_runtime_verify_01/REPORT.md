# PRELAUNCH-PERFORMANCE-RUNTIME-VERIFY-01

**Run:** `performance_runtime_verify_01`  
**Date:** 2026-05-25  
**Classification:** `PARTIAL`

## Root cause analysis

1. **Full-page spinners** hid route chrome until the slowest fetch in a `Promise.all` (or sole dashboard gate) completed.
2. **Wrong endpoints** — Properties used full `GET /client/dashboard` (~24s) instead of `GET /client/properties` (~1.8s).
3. **Waterfalls** — Requirements blocked on documents; Today blocked on requirements; Rent re-fetched all tabs on every tab change.
4. **Duplicate cold fetches** — Same requirements/command-center/compliance-summary re-requested across surfaces with no session dedupe.
5. **Backend latency** — `/today/items` (~30s, 1.6MB) and `/client/command-center` (~75s) dominate true response time (out of scope for this frontend bundle).

## Optimization approach (bounded)

- Shared `clientOperationalFetch.js`: in-flight dedupe + 45s stale-while-refresh with `PortalStaleRefreshBanner`.
- Progressive shells: `PortalPageShell`, `PortalSectionSkeleton`, widget-level loading.
- Per-surface primary/deferred split (see `progressive_rendering_matrix.json`).

## Tests

| Suite | Result |
|-------|--------|
| `clientOperationalFetch.test.js` | PASS |
| `ClientCommandCenterPage.test.js` | PASS |
| `ClientRentOperationsPage.test.js` | PASS |

## Authority / coherence

- No suppression of errors, jurisdiction gates, or compliance outcome listeners.
- Stale data explicitly labelled while refreshing.

## Commit / push

Pending commit in this run.

## Not `VERIFIED_OPERATIONALLY`

Browser navigation timings not captured; deploy required to validate perceived UX on staging.
