# DASHBOARD-PAA-STAGING-CRASH-FIX-01

**Verdict:** `STAGING_CRASH_FIX_ACCEPTED_PAA_RERUN_PARTIAL`  
**Branch:** develop only  
**Run:** 20260630T174500Z

---

## Root cause

`/dashboard` crashed with React ErrorBoundary:

```
TypeError: slaStateLabel is not a function
```

**Component:** `frontend/src/pages/ClientDashboard.js` (lines 1773, 1776)

The maintenance-workflows SLA KPI cards call `slaStateLabel('breached')` and `slaStateLabel('near_breach')`, but only `riskTypeLabelClient` was imported from `../domain/presentDomain.js`. The helper exists and is tested in `presentDomain.js`; it was simply not imported.

This is **not** a Presentation Authority regression — PAA did not modify `slaStateLabel` or the SLA KPI block.

---

## Fix

```javascript
// Before
import { riskTypeLabelClient } from '../domain/presentDomain';

// After
import { riskTypeLabelClient, slaStateLabel } from '../domain/presentDomain';
```

### Regression tests added

| File | Coverage |
|------|----------|
| `ClientDashboard.slaKpi.test.js` | Dashboard renders SLA KPI labels without ErrorBoundary when `maintenance_workflows` enabled |
| `presentDomain.requirementDisplay.test.js` | `slaStateLabel('breached')` → "SLA deadline missed"; `near_breach` → "Near SLA deadline" |

### Tests run

- Frontend Jest: **23 passed** (SLA + PAA helpers)
- Backend pytest (PAA + RAOD): **9 passed**

---

## Staging deploy

| | Value |
|---|--------|
| Bundle (before) | `main.55db8672.js` |
| Bundle (after) | `main.5adb0544.js` |
| Alias | https://pleerity-enterprise-9jjg.vercel.app |
| Action | `vercel alias set …e9q7y3tr5… → pleerity-enterprise-9jjg.vercel.app` |

Bundle probe: legacy **"Overdue — affecting compliance"** absent; PAA copy strings present.

---

## Post-fix browser verification

| Check | Result |
|-------|--------|
| `/dashboard` ErrorBoundary | **PASS** — no `slaStateLabel` crash |
| Checklist `setup_presentation` (API) | **PASS** — `documents_step_recommended: false`, authority `onboarding_checklist` |
| `needsDocumentsStep` FE inference | **Not reintroduced** |
| Onboarding semantic counts | **PASS** (probe: 20 tracked / 79 identified + footnote) |
| Command Centre triage lens | **PASS** |
| Requirements tracked labels | **PASS** |
| RAOD regression | **PASS** |

Screenshot: `screenshots/02_dashboard_retry.png`

---

## Fresh monthly digest

Triggered on staging via `POST /api/admin/clients/{id}/actions/monthly-digest`:

- **Digest ID:** `c69fbdb1-6ffb-438d-8b81-ee19f6ded355`
- **Generated:** 30 June 2026 17:33 UTC
- **Legacy suffix** ` — missing evidence`: **absent**
- **Governed suffix** ` — urgent`: present on work-order urgent lines
- **` — evidence required` / ` — calendar overdue`:** not in top-5 urgent lines for this OPS pilot (urgent section dominated by SLA work orders, not upload_evidence tasks)

**Status:** PARTIAL — assembly at deployed backend SHA uses `lifecycle_authority_copy.digest_action_line_suffix`; browser preview of governed requirement suffixes still pending a cohort where upload_evidence tasks rank in digest urgent items.

---

## Recommendation

**Dashboard crash fix: accepted on staging.**

Do **not** promote to production until:

1. Full PAA walkthrough PASS including stable dashboard render under authenticated session, and  
2. Monthly digest preview confirms governed **evidence required** or **calendar overdue** suffix on a fresh post-PAA digest (or documented cohort limitation resolved).
