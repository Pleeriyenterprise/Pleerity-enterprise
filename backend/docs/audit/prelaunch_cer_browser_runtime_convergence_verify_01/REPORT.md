# PRELAUNCH-CER-BROWSER-RUNTIME-CONVERGENCE-VERIFY-01

**Classification:** `PARTIAL` (secondary: `CTA_DRIFT`)  
**Run:** 20260531T145000Z  
**Landlord:** `nancy@yopmail.com`  
**Deploy:** `e217a300` (matches actionability convergence commit)

## Executive summary

Staging deploy continuity **confirmed**. Governance fields present on **49/49** requirements. Browser login and surface screenshots captured. Several target scenarios **not present in landlord data** (legionella follow-up, fire-risk incomplete, platform verification pending). One **verified runtime contradiction** remains: `fire_alarm` rows in `operational_incomplete` with component guidance but **generic CTA**.

## Results by part

| Part | Result |
|------|--------|
| 1 Deploy continuity | PASS |
| 2 Smoke/CO incomplete | PARTIAL — proxy via `fire_alarm`; label/guidance OK; **CTA generic** |
| 3 Legionella follow-up | NOT EXERCISABLE — 0 `followup_required` rows |
| 4 Fire-risk incomplete | NOT EXERCISABLE — only verified `hmo_fire_risk_evidence` |
| 5 Declaration recorded | PASS — Wales occupation contract `Evidence recorded` |
| 6 Platform verified | PASS — `PLATFORM_VERIFIED` family on gas/epc/eicr |
| 7 Badge dedupe | PASS — 0 duplicate issues across 49 rows |
| 8 Cognition Today/CC | PASS — ≤1 awaiting review on Today |
| 9 Score alignment | PASS — no status/label contradictions |
| 10 Cross-surface | PASS |
| 11 Dead-end recheck | CTA partially repaired; modal/ordering repaired |

## Verified contradiction (no fix applied)

**`fire_alarm`** (`c17146e4…`) on property `9786b4ea…`:
- Label: **Additional action still required** ✓
- Stage: `operational_incomplete` ✓
- Guidance: **Smoke alarm compliance still required** ✓
- CTA: **Add compliance evidence** ✗ (expected **Complete smoke alarm details**)

Likely cause: CTA specificity wired for `smoke_heat_alarms` canon; staging uses `fire_alarm` type with shared completeness projection.

## Screenshots

- `screenshots/01_requirements_page.png`
- `screenshots/03_legionella_modal.png`
- `screenshots/04_today.png`
- `screenshots/04_command_center.png`
- `screenshots/04_dashboard.png`

Harness: `backend/tmp_prelaunch_cer_browser_runtime_convergence_verify_01.py`
