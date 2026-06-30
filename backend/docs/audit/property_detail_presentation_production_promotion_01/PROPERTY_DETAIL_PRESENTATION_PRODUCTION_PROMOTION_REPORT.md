# PROPERTY-DETAIL-PRESENTATION-PRODUCTION-PROMOTION-01

**Verdict:** `PRODUCTION_PROMOTION_SUCCESSFUL`  
**Run:** 20260630T225910Z

---

## Promotion summary

Scoped cherry-pick of two validated develop commits onto `main`. No develop merge.

| Field | SHA |
|-------|-----|
| Main before | `594f5727e3679f46fb58839c6f3c492ddddc7176` |
| Source develop (fix) | `6c3d2190` → main `e835ef5b` |
| Source develop (evidence) | `f16209fe` → main `9572933a` |
| Main after | `9572933a` |
| Production backend observed | `9572933ac906dfc2d4ad9b9714e6f00ef3c3ff9a` |

---

## Deployment

| Component | Action |
|-----------|--------|
| Backend | Auto-deploy from `main` push (Render production) |
| Frontend | `vercel deploy --prod` from validated main |

---

## Smoke validation

| Check | Result |
|-------|--------|
| Backend @ promoted SHA | True |
| Homepage loads | True |
| Valid for scoring in bundle | True |
| Requirements satisfied in bundle | True |
| Production API embedded | True |
| Staging API absent | True |
| lifecycle_satisfied_count on API (authenticated) | Skipped — prod client login unavailable; staging GO + backend SHA confirm deploy |
| status_valid on API (authenticated) | Skipped — same |
| Unauth compliance-detail 401 | True |
| RAOD/Today/CC/Dashboard unauth 401 | True |

---

## Regression verification (unauthenticated reachability)

All protected endpoints return **401** — no open regression surface. Presentation-only change; Requirement/Lifecycle/Risk/Today/Document Linkage authorities unchanged in promoted files.

---

## Remaining risks

- Authenticated production KPI spot-check deferred — use pilot landlord login to confirm `lifecycle_satisfied_count` vs `status_valid` on a mixed-evidence property.
- No DB migration; rollback is git/Vercel/Render only.

- `lifecycle-kpi-wip` and all other develop commits not cherry-picked
- Local `portfolio.py` / `reportingSemanticsLabels.js` WIP (not in approved commits)
- Production configuration unchanged

---

## Files excluded

Revert `main` to `594f5727e3679f46fb58839c6f3c492ddddc7176` or Vercel/Render rollback to prior deployment. No DB migration involved.

**Evidence JSON:** [PROPERTY_DETAIL_PRESENTATION_PRODUCTION_PROMOTION.json](./PROPERTY_DETAIL_PRESENTATION_PRODUCTION_PROMOTION.json)
