# PRELAUNCH-OPS-RUNTIME-VERIFY-01 — Family 5 Client Sync (`ops_runtime_05_client_sync`)

**Run:** `20260523T184731Z`  
**Classification:** `VERIFIED_OPERATIONALLY`  
**Owner:** `ops_runtime_05_client_sync`  
**Proof mode:** `operational_browser`

## Pilot

| Field | Value |
|-------|-------|
| client_id | `6fd5ac4c-3fd4-4112-ade7-156977deb49f` |
| property_id | `d35a58ae-3c81-491c-9694-1d021dd3b8ad` |
| issue (this run) | `225fd14f-eaab-4daa-bc6e-2507c5b1e4dd` |
| work_order (this run) | `45068cd8-52c3-47c3-85fb-731fbe5dd941` |

## Dependency bundles (F1–F4)

All `VERIFIED_OPERATIONALLY` — see `pilot_selection.json` / `shared_dependency_bundle_ids` in `run_manifest.json`.

## Same-run proof

- Baseline projections captured (dashboard, protection-snapshot, open-count, command-center, tasks digest)
- Issue create → open-count `40→41`; marker issue visible in list
- WO create + contractor quote/accept/complete → `COMPLETED` in client API
- G9: repeated open-count reads stable (`41,41,41`); duplicate protection-snapshot and tasks-digest PASS
- G10: completed WO not shown open; no duplicate WO rows; issue not falsely closed; open count coherent
- Browser (form login): dashboard, issues, work-orders, risk-signals, issue detail, job detail, refresh persistence, property page — PASS
- Convergence (60s): queues OK; final projections stable; marker issue open + marker WO completed

## F6 may proceed

**YES** (F5 owner bundle `VERIFIED_OPERATIONALLY`; F6 still subject to its own charter)
