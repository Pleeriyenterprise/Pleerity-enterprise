# PLAN-OUTCOME-FIXTURE-SEEDING-AND-CLOSEOUT-01

**Classification:** `PLAN_FIXTURE_GAP`  
**Marker:** `PLAN-OUTCOME-SEED-CLOSEOUT-20260607T180254Z`  
**Prior:** PLAN-BASED-BUSINESS-OUTCOME-FIXTURE-CLOSEOUT-01

## Summary

Staging discovery found **no exact all-satisfied fixtures** for scenarios A, D, E, G, H. Partial fixtures **B, F, I** reconfirmed for operational urgency. Entitlements, browser proof (5/6 personas with client), and regression (58 tests) pass. Sophie Walker Today `in_progress=4` root-caused as **stale compliance-gap bridge issues**; global suppression fix implemented locally (pending deploy).

## All-satisfied fixture seed (0/5 exact)

| ID | Best candidate | Gap |
|----|----------------|-----|
| A | Sophie Walker `10b2ddba…` | 2 properties; Today not calm |
| D | `80f83edd…` | 1 property; not all satisfied |
| E | — | No match in scan |
| G | — | Impersonation/session exhaustion |
| H | — | No match in scan |

## Sophie Walker Today investigation

- Requirements: 8/8 score-tracked satisfied; properties GREEN
- Today: `urgent_count=0`, `in_progress_count=4`
- Tasks: 4 open `issue` rows (document review/upload) — **stale gap-bridge issues**, not assurance-only
- Gap engine: 5 open LOW `MISSING_EVIDENCE` gaps despite satisfied requirements
- **Fix (code):** `_suppress_stale_compliance_issue_tasks` + Today filter-before-compact metadata

## Partial reconfirmation

| ID | Client | Result |
|----|--------|--------|
| B | David Harrison `616258a5…` | PASS — real action, routing |
| F | David Miller `6bcc43c0…` | PASS — mixed jurisdiction urgency |
| I | Nancy `6fd5ac4c…` | PASS — Professional partial urgency |

## Count semantics (F, I)

Dashboard `lifecycle_satisfied` / `visible_registry` (71 / 49) differs from score-tracked obligations (48 / 43). **Verdict:** registry vs score-tracked — labels must stay separate; not a logic bug for partial outcomes.

## Browser proof

6 slugs targeted; 5 captured with client (solo_partial re-captured for B). Screenshots in `closeout_screenshots/`.

## Regression

58 tests pass including `test_today_projection_quality` and `test_assurance_actionability_service`.
