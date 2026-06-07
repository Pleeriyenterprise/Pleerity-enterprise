# PLAN-BASED-BUSINESS-OUTCOME-FIXTURE-CLOSEOUT-01

**Classification:** `PLAN_FIXTURE_GAP`  
**Marker:** `PLAN-FIXTURE-CLOSEOUT-20260607T163807Z`  
**Prior:** `PLAN-BASED-BUSINESS-OUTCOME-RUNTIME-AUDIT-01` (PARTIAL)

## Executive summary

Deterministic fixture discovery ran against staging with resilient pacing and fresh step-up per browser target. **Partial and entitlement outcomes are proven**; **exact all-satisfied fixtures per plan matrix are not available on staging** without new seed accounts.

Browser proof captured for 4 resolved/reference personas (28 screenshots). Regression **50 tests pass**.

**Not `VERIFIED_OPERATIONALLY`** — missing exact fixtures for Solo 1-prop all-satisfied, Portfolio 5-prop all-satisfied, Portfolio mixed all-satisfied, and Professional all-satisfied scenarios.

## Fixture resolution (Part 1)

| ID | Scenario | Resolved | Client | Pass |
|----|----------|----------|--------|------|
| A | Solo 1 prop all satisfied | Best-effort | Sophie Walker `10b2ddba…` | No — 2 props; Today in_progress=4 |
| B | Solo partial | Yes | David Harrison `616258a5…` | **Yes** |
| C | Solo property limit | Local | max 2 | **Yes** |
| D | Portfolio 5 all satisfied | No | — | No |
| E | Portfolio mixed all satisfied | No | — | No |
| F | Portfolio mixed partial | Yes | David Miller `6bcc43c0…` | **Yes** |
| G | Professional 3–5 all satisfied | No | Nancy partial only | No |
| H | Professional mixed all satisfied | No | — | No |
| I | Professional mixed partial | Yes | Nancy `6fd5ac4c…` | **Yes** |

### Sophie Walker reference (PLE-CVP-2026-000023)

- Plan: **PLAN_1_SOLO**
- 2 properties, England, score **93**
- Requirements: 10/10 dashboard, 8/8 score API — all satisfied
- Properties: 2 GREEN
- **Today not calm:** in_progress=4 (USER_OUTCOME_DRIFT for all-satisfied calm expectation)

## Satisfaction paths (Part 2)

Verified via live API probe — no fake status patching. Sophie Walker satisfaction through valid evidence/declaration paths (prior convergence programme).

## Entitlements (Part 6) — **PASS**

Billing plan matches API entitlements for Solo B, Portfolio F, Professional I (10 / 18 / 29 features enabled).

## Cross-surface (Part 7) — **PARTIAL**

- Sophie A/E: dashboard/score parity within tolerance
- Portfolio F / Professional G–I: dashboard vs requirement count drift (registry semantics)

## Browser proof (Part 8) — **PASS**

Screenshots in `closeout_screenshots/`:

- `solo_all_ref_*` — Sophie Walker
- `solo_partial_*` — David Harrison
- `portfolio_partial_*` — David Miller
- `pro_partial_*` — Nancy (Professional)

## Regression (Part 10) — **PASS**

50 targeted tests.

## Harness (Part 9)

`backend/scripts/plan_based_business_outcome_fixture_closeout_01_execute.py`  
`backend/scripts/plan_fixture_browser_capture_01.py`
