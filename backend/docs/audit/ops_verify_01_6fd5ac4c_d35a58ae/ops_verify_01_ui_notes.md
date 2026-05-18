# OPS-VERIFY-01 UI notes — Journey A

**Run:** `ops_verify_01_6fd5ac4c_d35a58ae` · **Verifier:** cursor-ops-verify-01 · **Final browser walkthrough:** 2026-05-18

## Environment

- **DB:** `pleerity_staging` (pilot `6fd5ac4c…` / `d35a58ae…`)
- **API:** local `http://127.0.0.1:8000` → staging Mongo
- **UI:** local `http://127.0.0.1:3000` (`REACT_APP_BACKEND_URL=http://127.0.0.1:8000`)
- **Portal user:** `nancy@yopmail.com` (ROLE_CLIENT_ADMIN)

## Requirement

- **ID:** `488269bb-1be7-47e7-a030-98accf6dffc4` (`occupation_contract`, Wales, `GUIDED_DECLARATION`)
- **Mode:** **Existing-CER re-submit** (prior `cer_799b0c6abff04bb6a8d51ec63ec904a0`; new browser CER `cer_979c123533804653a9e20b2f6008b7f6`)
- **Not a clean first-submit** — only guided requirement on pilot property; greenfield first submit remains watchlist.

## Journey A — Guided structured evidence submit (browser)

### Preconditions

- [x] Authenticated client session (JWT)
- [x] Requirement visible in browser (accordion expand)
- [x] Baseline capture before submit

### Submit path (final run)

- [x] Guided modal opened via property deep-link `?open=resolve&requirement_id=…` (row CTA was “View submission” when CER on file)
- [x] **Submit evidence** in browser (not API-direct)
- [x] **Submission recorded** summary from returned `evidence_record`
- [x] Post-submit + convergence captures

### TRUST-01 UI

- [x] **Your submission** visible in requirement details modal
- [x] CER payload visible (STRUCTURED_DECLARATION, PENDING REVIEW)
- [x] **View submission** scroll in modal
- [x] Hard refresh — panel persists

### Async convergence

- Submit ~`2026-05-18T15:45:08Z`
- Queue correlation → **DONE** ~17s
- Convergence capture `2026-05-18T15:49:26Z`; `score_converged_observable: true`

### Screenshots / browser log

- `ops_verify_01_journey_a_final_ui.png`
- `ops_verify_01_browser_journey_a_final.json`

### Classification

**`VERIFIED_OPERATIONALLY`** (Journey A only; OPS-VERIFY-01 unit remains IN_PROGRESS / PARTIAL).
