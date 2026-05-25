# PRELAUNCH-PERFORMANCE-RUNTIME-VERIFY-01

**Run:** `performance_runtime_verify_01`  
**Post-deploy browser verify:** `2026-05-25T16:04:47Z`  
**Commit:** `cb14b437`  
**Classification:** `PARTIAL` (+ `PERFORMANCE_DEGRADATION` on backend-heavy surfaces)

## Deploy continuity

| Check | Result |
|-------|--------|
| `origin/main` | `cb14b437` |
| Staging bundle | `/static/js/main.2865d241.js` |
| `portal-stale-refresh-banner` in bundle | Yes |
| `portal-section-skeleton` in bundle | Yes |
| Stale copy string in bundle | Yes |

## Browser results (landlord `nancy@yopmail.com`, staging)

| Surface | Shell (ms) | Primary (ms) | Full-page spinner only |
|---------|------------|--------------|------------------------|
| P1 Today | 334 | 3,148 | No |
| P2 Command Centre | 580 | 96,824 | No |
| P3 Dashboard | 218 | 25,044 | No |
| P4 Properties | 199 | 2,558 | No |
| P5 Requirements | 192 | 24,132 | No |
| P6 Documents | 200 | 22,396 | No |
| P7 Rent | 236 (chrome) | 2,610 (tab body spinner) | No |

**Material improvement:** All surfaces show route chrome/skeleton in **&lt;600ms**. Legacy full-page blocking spinner **eliminated** on every surface.

**Remaining truth:** P2 primary content still waits on slow command-center API (~97s browser). P3/P5/P6 primary still **20–25s**. Backend latency is **not hidden** — users see shell immediately but operational blocks still load slowly.

## Truth checks

- Auth token cleared → redirect to `/login/client` (no fake dashboard).
- No full-page-only loading without shell.
- Stale-refresh banner **not observed** in automated probes (fresh cache revisits; banner code deployed).
- Warm Properties revisit **~2.3s** primary (cache working).

## Tests (unchanged from implementation commit)

`clientOperationalFetch.test.js`, `ClientCommandCenterPage.test.js`, `ClientRentOperationsPage.test.js` — PASS.

## Classification rationale

Not `VERIFIED_OPERATIONALLY` because:

1. Charter requires stale-while-refresh **disclosed in browser** — not captured (code present).
2. Command Centre primary wait remains **unacceptable** (~97s) despite progressive shell — `PERFORMANCE_DEGRADATION`.

Partial pass because frontend goals for progressive loading and full-page blocking reduction are **confirmed on deployed staging**.

## Commit / push

No new code commit (audit-only updates in bundle folder). Implementation already pushed: `cb14b437`.
