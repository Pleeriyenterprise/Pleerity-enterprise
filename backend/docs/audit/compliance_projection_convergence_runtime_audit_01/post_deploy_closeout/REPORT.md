# COMPLIANCE-PROJECTION-CONVERGENCE-POST-DEPLOY-CLOSEOUT-01

**Classification:** `SCORE_DRIFT`  
**Deploy commit:** `103649d4` — fix(compliance): converge operational projections and score aggregation  
**Target:** Sophie Walker (`PLE-CVP-2026-000023`, `10b2ddba-e952-4484-91d1-a8f0299d0824`)  
**Environment:** staging (`pleerityenterprise.co.uk` / Render API)  
**Generated:** 2026-06-06T22:16:37Z  
**Auth:** admin impersonation (step-up verified)

## Executive summary

Post-deploy runtime verification on the Sophie Walker portfolio confirms the **primary operational projection fixes landed**:

- Properties page: **Valid / GREEN** (no false “Attention needed”)
- Requirements page: **10/10 lifecycle valid**, 0 action required
- Today API: **0 urgent** operational tasks; no satisfied-requirement leaks
- Property RAG API ↔ dashboard: **aligned** (both GREEN)

**Remaining drift** is concentrated on **score aggregation counts** (8 tracked vs 10 visible requirements) and **assurance-review surfacing** on Today / quick actions / score recommendations. The **93/100** score appears **intentional** (assurance confidence), but UI still mixes compliance-valid counts with assurance-improvement cards.

## Part-by-part results

### PART 1 — Target account verification

| Check | Result |
|-------|--------|
| 2 properties (Brixton Hill, Willow Grove) | ✓ |
| 10 visible requirements | ✓ |
| 10 satisfied (requirements API) | ✓ |
| Properties GREEN (live RAG) | ✓ |
| 0 overdue / 0 expiring | ✓ |
| Score stats satisfied = total | ✗ (8/8, not 10/10) |

**Artifact:** `target_account_runtime_snapshot.json`

### PART 2 — Today page closeout

| Check | API | Browser |
|-------|-----|---------|
| No urgent operational leaks | ✓ (urgent_count=0) | — |
| No false “Do this next” for satisfied reqs | ✓ (no satisfied leaks) | ✗ “DO THIS NEXT” card present |
| No stale “Need action” | — | ✗ “Needs action: 1” |
| No operational urgency banners | — | ✗ assurance review card surfaced |

API passes; browser shows **1 needs-action** and **4 in-progress** assurance-review items (document confirmation). These are non-operational assurance tasks, but still visible in the operational inbox header counts.

**Artifact:** `today_page_closeout_runtime.json`  
**Screenshot:** `screenshots/05_today.png`

### PART 3 — Property page closeout

| Check | Result |
|-------|--------|
| No false “Attention needed” | ✓ (0 attention, 2 valid) |
| GREEN / compliant operational state | ✓ |

**Artifact:** `property_page_closeout_runtime.json`  
**Screenshot:** `screenshots/02_properties.png`

### PART 4 — Compliance score closeout

| Check | Result |
|-------|--------|
| Satisfied count alignment (10) | ✗ (8 valid tracked) |
| Valid count alignment | ✗ (8 vs 10 requirements) |
| Tracked obligations alignment | ✗ |
| Portfolio totals convergence | ✗ (dashboard: 8 compliant; requirements: 10 valid) |
| 93/100 intentional (assurance) | ✓ likely — score drivers empty; assurance copy present |
| UI distinguishes compliance vs confidence | partial — subtext on dashboard quick actions; score page still lists HIGH assurance actions |

**Artifact:** `compliance_score_closeout_runtime.json`  
**Screenshot:** `screenshots/04_compliance_score.png`

### PART 5 — Quick actions closeout

| Check | Result |
|-------|--------|
| Stale self-recorded operational cards | ✓ (none matched stale filter) |
| Assurance items labeled | partial (dashboard subtext; score page HIGH priority) |
| No dead-action surfaces | ✓ (cards clickable) |
| Clean when all satisfied | ✗ (4 assurance recommendations remain) |

**Artifact:** `quick_actions_closeout_runtime.json`  
**Screenshot:** `screenshots/01_dashboard.png`

### PART 6 — Live projection convergence

| Surface | Expected | Actual |
|---------|----------|--------|
| Requirements | 10 satisfied | ✓ |
| Today | No urgent operational action | partial (API ✓, UI assurance card) |
| Properties | Compliant / valid | ✓ |
| Dashboard | Consistent counts | ✗ (8 vs 10) |
| Score page | Consistent aggregation | ✗ (8 tracked) |
| Quick actions | No stale operational drift | partial (assurance cards only) |

**Artifact:** `live_projection_convergence_runtime.json`

### PART 7 — Cache / job refresh verification

| Check | Result |
|-------|--------|
| Properties API RAG = dashboard RAG | ✓ |
| portfolio_score_pending | null (not stuck) |
| Stale DB compliance_status on properties | ✓ resolved (live projection) |

**Artifact:** `projection_refresh_closeout_runtime.json`

### PART 8 — Browser runtime proof

Screenshots captured for dashboard, properties, requirements, compliance score, and today while impersonating Sophie Walker.

**Artifact:** `projection_browser_closeout_runtime.json`  
**Screenshots:** `screenshots/01_dashboard.png` … `05_today.png`

### PART 9 — Regression sanity

49 targeted tests passed (property RAG, attention eligibility, client runtime surface, today projection).

**Artifact:** `projection_closeout_regression_runtime.json`

### PART 10 — Classification

**`SCORE_DRIFT`** — operational property/requirement projections converged; score aggregation and assurance surfacing still diverge from the 10/10 satisfied portfolio truth.

## Harness note

Closeout harness updated to perform admin step-up before impersonation (`auth/step-up/verify`). Prior 403 was auth-only, not a data issue.
