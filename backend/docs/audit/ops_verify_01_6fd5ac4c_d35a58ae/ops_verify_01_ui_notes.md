# OPS-VERIFY-01 UI notes — pilot `6fd5ac4c_d35a58ae`

**Run:** `ops_verify_01_6fd5ac4c_d35a58ae` · **Verifier:** cursor-ops-verify-01 · **Executed:** 2026-05-18 – 2026-05-20

**Bundle note:** Shared `baseline` / `post_submit` / `convergence` JSON reflect the **Journey C** terminal DB capture. Journeys A and B retain per-journey browser artefacts (`ops_verify_01_browser_journey_a_final.json`, `ops_verify_01_browser_journey_b.json`) and were classified against their journey-specific capture snapshots (commits `091c2848`, `15570386`).

## Preconditions
- [x] Real client login on staging (`nancy@yopmail.com`, local UI `127.0.0.1:3000` + `pleerity_staging` DB)
- [x] Pilot property `d35a58ae-3c81-491c-9694-1d021dd3b8ad`

## Journey A — Guided structured evidence submit
- **Requirement:** occupation_contract `488269bb-1be7-47e7-a030-98accf6dffc4`
- **Path:** existing-CER **re-submit** via property `?open=resolve` deep-link (row CTA “View submission”); TRUST-01 inspect panel + persisted submission presentation
- **Submit observed (Y/N):** Y
- **Refresh persisted (Y/N):** Y
- **Classification:** **VERIFIED_OPERATIONALLY**
- **Watchlist:** clean **first-submit** (greenfield guided requirement) not attested on pilot property

## Journey B — Primary document upload
- **Requirement:** fire_alarm `69fc66fe-e196-44d4-a20e-3fe68d316f7f` (EICR excluded — `NOT_APPLICABLE`, not in upload dropdown)
- **Path:** `/documents?property_id=…&requirement_id=…&focus=upload` (cleared inferred `document_type` before submit)
- **Document visible in vault (Y/N):** Y
- **Classification:** **VERIFIED_OPERATIONALLY**
- **Screenshot:** `ops_verify_01_journey_b_ui.png`

## Journey C — Supporting-upload-only (post TRUST remediation)
- **Requirement:** occupation_contract `488269bb-1be7-47e7-a030-98accf6dffc4`
- **Path:** guided modal supporting files only (no Submit evidence)
- **Upload succeeded (Y/N):** Y · **No authoritative POST (Y/N):** Y · **CER delta:** 0
- **Truthful copy (Y/N):** Y — “Supporting added”, “Submission on file”, static supporting banner, attribution subline
- **Classification:** **VERIFIED_OPERATIONALLY** (post frontend remediation)
- **Screenshot:** `ops_verify_01_journey_c_ui.png`

## Journey D — Verify/review (optional)
- **Status:** **NOT_STARTED** — waived for A/B/C operational closure

## Roll-up classifications
| Journey | Classification |
|---------|----------------|
| A | VERIFIED_OPERATIONALLY |
| B | VERIFIED_OPERATIONALLY |
| C | VERIFIED_OPERATIONALLY |
| D | NOT_STARTED (optional) |
