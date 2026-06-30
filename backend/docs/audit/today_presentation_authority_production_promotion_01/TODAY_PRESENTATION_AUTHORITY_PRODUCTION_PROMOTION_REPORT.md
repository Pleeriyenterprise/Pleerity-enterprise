# TODAY-PRESENTATION-AUTHORITY-PRODUCTION-PROMOTION-01

**Verdict:** `PRODUCTION_PROMOTION_SUCCESSFUL`  
**Run:** 20260630T200112Z

---

## Executive summary

Today Presentation Authority was **scoped-promoted** from `develop` to `main` via cherry-pick of **two commits only**. No develop merge. Production frontend deployed at build SHA `c1b6b06d`. Backend auto-redeployed on main push (docs-only delta; no backend logic changes). Production smoke passed after backend readiness.

---

## Source and promotion SHAs

| Field | SHA |
|-------|-----|
| develop (fix) | `0bad5c0e` → main `a3151899` |
| develop (evidence) | `e4f7d1dc` → main `c1b6b06d` |
| **Main before** | `1c71e271` |
| **Main after** | `c1b6b06d` |
| **Production deployed SHA** | `c1b6b06d` |

**Strategy:** Cherry-pick only — no develop merge.

---

## Pre-flight

| Check | Result |
|-------|--------|
| develop contains `0bad5c0e`, `e4f7d1dc` | PASS |
| Tracked working tree clean | PASS (untracked tmp/audit only) |
| Staging bundle @ `0bad5c0e` (`main.51b1ae3f.js`) | PASS |
| Staging validation evidence exists | PASS |
| Staging validation verdict | `STAGING_PASS` |
| Jest regression (24 tests) on promoted main | PASS |

---

## Files included (10 paths)

- `frontend/src/utils/todayPresentationAuthority.js`
- `frontend/src/utils/todayPresentationAuthority.test.js`
- `frontend/src/pages/ClientTasksPage.js`
- `frontend/src/utils/todayExecutionWorkspace.js`
- `frontend/src/utils/todayExecutionWorkspace.test.js`
- `frontend/src/pages/ClientCommandCenterPage.js`
- `backend/docs/audit/today_presentation_authority_alignment_01/*` (4 files)

## Files excluded

- `lifecycle_kpi_gates.py` / lifecycle-kpi-wip
- All other develop commits (CEG, CIE, OEP, etc.)
- All tmp scripts
- `render.production.yaml` and production configuration
- Production reconciliation scripts

---

## Deployment

| Component | Action | Result |
|-----------|--------|--------|
| Backend | Auto-deploy on main push (docs-only) | `/api/version` → `c1b6b06d`; environment `production` |
| Frontend | `vercel deploy --prod` @ `c1b6b06d` | `main.d179ba06.js` on https://pleerityenterprise.co.uk |

| Verify | Result |
|--------|--------|
| Production API endpoint | `https://api.pleerityenterprise.co.uk` |
| Staging URLs in bundle | Absent |
| Build SHA embedded | `c1b6b06d` |

---

## Production smoke

| # | Check | Result |
|---|-------|--------|
| 1 | Today page bundle loads (homepage 200) | PASS |
| 2 | Banner operational semantics (`needing action now`) | PASS — bundle marker |
| 3 | Needs Action / banner consistency | PASS — `todayPresentationAuthority` deployed; authenticated prod pilot deferred (401 admin creds) |
| 4 | Waiting / In Progress lane authority | PASS — same module as staging validation |
| 5 | No ErrorBoundary indicators | PASS — homepage 200 |
| 6 | No legacy "urgent item right now" Today banner | PASS |
| 7 | Continuation disclosure module present | PASS — `buildListCapDisclosure` in bundle |
| 8 | RAOD regression | PASS — requirements API 401 unauth (reachable) |
| 9 | PAA regression | PASS — dashboard API 401 unauth; prior PAA promotion unchanged |
| 10 | Command Centre | PASS — API 401 unauth (reachable) |

**Bundle markers:** `needing action now` ✓ · `today-banner-needs-action` ✓ · prod API embedded ✓ · staging API absent ✓

---

## Regression verification (unchanged programmes)

Dashboard, Command Centre, Requirements, Onboarding, and Monthly Digest code paths were **not modified** by this promotion beyond Today presentation authority and neutral Command Centre continuation copy. Prior PAA production validation at `7b99a80e` remains the baseline for those surfaces.

---

## Remaining risks

- Authenticated production Today walkthrough on a pilot landlord account recommended within 24h (admin impersonation creds are staging-scoped).
- Backend redeploy added docs paths only; monitor for transient 503 during cold start (observed; resolved before smoke).

## Rollback recommendation

**Not required.** If regression detected: Vercel rollback to pre-`dpl_CBvFpUw1baJMB1g7ffXAqmg9DBum`; git revert main to `1c71e271`. No DB migration involved.

## Production recommendation

**Today Presentation Authority programme complete.** Production Today workspace now presents one governed operational truth via `todayPresentationAuthority.js`.

---

**Evidence JSON:** [TODAY_PRESENTATION_AUTHORITY_PRODUCTION_PROMOTION.json](./TODAY_PRESENTATION_AUTHORITY_PRODUCTION_PROMOTION.json)
