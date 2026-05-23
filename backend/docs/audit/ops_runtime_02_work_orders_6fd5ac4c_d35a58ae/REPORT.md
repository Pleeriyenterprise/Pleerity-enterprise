# PRELAUNCH-OPS-RUNTIME-VERIFY-01 — Family 2 Work orders (`ops_runtime_02_work_orders`)

**Latest run:** `20260523T144750Z` (post-remediation staging rerun)  
**Classification:** `FAIL_SYSTEM` + `TRUST_RISK_PRESENT`  
**Authoritative owner:** `ops_runtime_02_work_orders`  
**Proof mode:** `operational_browser`  
**F1 dependency:** `ops_runtime_01_issues_6fd5ac4c_d35a58ae/07_classification.json`

## Pilot
- client_id: `6fd5ac4c-3fd4-4112-ade7-156977deb49f`
- property_id: `d35a58ae-3c81-491c-9694-1d021dd3b8ad`

## Remediation applied (2026-05-23)
### Part A — G9 WO idempotency
- Backend: `services/maintenance_wo_from_issue_idempotency.py` (90s fingerprint dedupe + existing issue↔WO replay)
- Route: `POST /client/maintenance/issues/{id}/create-work-order` returns `idempotent_replay: true` on duplicate
- Frontend submit guards: `ClientIssueDetailPage.js`, `ClientIssuesPage.js`, `PropertyDetailPage.js`

### Part B — Lifecycle enablement
- Staging fixture: `scripts/f2_ops_runtime_pilot_contractor_fixture.py`
- Contractor: `a1f2e3b4-c5d6-4789-a012-3456789abcde` (heating/maintenance, Wales/W8, vetted, portal enabled)
- Harness quote path: assign → submit quote → client approve → start → complete (no gate bypass)

### G10 — terminal reopen guard (bounded)
- `maintenance_service.update_work_order` blocks client downgrade from COMPLETED/VERIFIED/CLOSED/CANCELLED
- Admin path retains `allow_terminal_reopen=True`

## Latest same-run results (staging API — pre-deploy)
| Checkpoint | Result |
|------------|--------|
| Preflight | PASS |
| Full API lifecycle (issue→WO→assign→quote→start→complete) | **PASS** |
| Browser surfaces + refresh | **PASS** |
| G9 idempotency | **FAIL** (staging API not yet deployed with remediation) |
| G10 completed WO reopen blocked | **FAIL** (staging API not yet deployed with terminal guard) |
| Convergence terminal COMPLETED | **FAIL** (G10 probe reopened WO to OPEN on staging) |

## Classification delta
| Run | Classification | Notes |
|-----|----------------|-------|
| `20260523T120033Z` | FAIL_SYSTEM | G9 duplicate WO; no assignable contractor |
| `20260523T144750Z` | FAIL_SYSTEM | Lifecycle + browser PASS; G9/G10 pending deploy |

## F3 proceed
**NO** — F2 not `VERIFIED_OPERATIONALLY`. Post-deploy same-run rerun required.

## Next step
Deploy backend remediation to staging, rerun `tmp_ops_runtime_02_work_orders_execute.py` against `pleerity-enterprise.onrender.com`.
