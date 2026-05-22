# repairing_standard — Scotland OPS browser attestation (`ec0b091b` / `def23b30`)

## Programme

`PRELAUNCH-OPS-VERIFY-CONDITION-STANDARD-01` — same-run browser attestation **2026-05-22**

## Runtime environment (Step 1)

| Item | Value |
|------|--------|
| Git commit | `564c34bf24650f00e382f7c3303139740629f2d6` |
| Backend | `http://127.0.0.1:8002` (uvicorn, current code) |
| Frontend | `http://127.0.0.1:3000` (CRA, `REACT_APP_BACKEND_URL=http://127.0.0.1:8002`) |
| Stale listener | `:8000` ghost PID `70520` (not used) |
| Mongo DB | `pleerity_staging` |
| Bundle | `ops_verify_03_runtime_environment.json` |

**Deployment lesson:** Frontend must proxy to the API process running **current** code; Playwright must target the same API URL. Compliance tab selector is `data-testid="property-tab-compliance"` (not `role=tab`).

## API preflight (Step 2)

**Pass** — `ops_verify_03_api_preflight.json`

- `inclusion_reason`: `condition_standard_pilot_runtime_legitimate`
- `workflow_family`: `CONDITION_STANDARD_ACTIVE_STANDARD`
- `semantic_state`: `OPERATIONALLY_OPEN`
- Primary CTA: `Manage related issues`
- Disclosure present (API payload)

## Browser attestation (Steps 3–7)

Evidence: `ops_verify_03_browser_attestation.json`, screenshots in `screenshots/`

| Check | Result |
|-------|--------|
| A. Matrix visibility | **Pass** — `repairing_standard` row visible; operational subline |
| B. CTA coherence | **Pass** — intel primary `Manage related issues`; not upload-primary |
| C. Inspect panel | **Pass** — operational summary + disclosure in panel |
| D. `?open=resolve` | **Fail** — query consumed; no navigation to issues/guided/intel |
| E. Refresh persistence | **Pass** — row + operational wording persist after hard reload |
| Operational mutations (prior run) | **Pass** — CS-O1/O2/O6 |
| Upload regression (prior run) | **Pass** — CS-O5, CS-O11 |
| Forbidden certificate wording | **Pass** |

## Classification

**`IMPLEMENTED_NOT_VERIFIED`** (honest; not `VERIFIED_OPERATIONALLY`)

Resolve deeplink remains unproven in browser. All other same-run browser/API gates pass.

## FFHH

**Not run.** Blocked until `repairing_standard` achieves `VERIFIED_OPERATIONALLY` or explicit governance sign-off on remaining resolve gap.

## Remaining watchlist

1. Investigate `?open=resolve` for condition-standard rows (navigate to `/operations/issues` expected; currently no-op in Playwright attestation).
2. Clear/rebind stale `:8000` listener before local OPS.
3. Optional: post-issue matrix refresh attestation (`matrix_post_issue` step).
