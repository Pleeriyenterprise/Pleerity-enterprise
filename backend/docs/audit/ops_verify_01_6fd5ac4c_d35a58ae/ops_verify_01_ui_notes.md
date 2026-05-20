# OPS-VERIFY-01 UI notes — Journey B

**Run:** `ops_verify_01_6fd5ac4c_d35a58ae` · **Verifier:** cursor-ops-verify-01 · **Executed:** 2026-05-20

## Preconditions
- [x] Real client login on staging (`nancy@yopmail.com`, local UI + `pleerity_staging` DB)
- [x] Requirement: fire_alarm `69fc66fe-e196-44d4-a20e-3fe68d316f7f` (clean baseline: 0 docs, 0 CERs)
- **Selection note:** Selected fire_alarm (ACTION_REQUIRED, 0 docs/0 CERs). EICR/ePC/hmo_license are NOT_APPLICABLE in client lifecycle and do not appear in Documents upload dropdown.
- [x] Baseline capture completed before upload

## Journey B — Primary document upload
- **Surfaces visited:** `/requirements?highlight=…`, `/documents?property_id=…&requirement_id=…&focus=upload`
- **Upload mode:** documents page deep-link + form submit
- **Document visible in vault (Y/N):** Y
- **Requirement linkage coherent (Y/N):** Y
- **Screenshot:** `C:\pleerity-workspace\Pleerity-enterprise\backend\docs\audit\ops_verify_01_6fd5ac4c_d35a58ae\ops_verify_01_journey_b_ui.png`

## Async convergence observation
- **T+0:** 2026-05-20T19:07:00.000000+00:00
- **T+SLA (~95s):** 2026-05-20T19:16:38.670481+00:00
- **Score headline updated (Y/N):** Y
- **Queue terminal (Y/N):** Y
- **Partial signals:** {"pending_flag": false, "queue_pending_or_running": false, "no_terminal_queue_row": false}

## Classification
- **Journey B:** VERIFIED_OPERATIONALLY
- **Reasons:** 
