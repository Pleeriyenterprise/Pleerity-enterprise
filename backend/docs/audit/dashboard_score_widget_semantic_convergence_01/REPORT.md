# DASHBOARD-SCORE-WIDGET-SEMANTIC-CONVERGENCE-01

**Classification: COUNT_CONVERGENCE_DRIFT** (with EXPIRY_COGNITION_DRIFT pattern on 2-property UI example)

## Executive answer

The Quick Actions widget is **not wrong in backend math**, but **mislabeled** relative to the Requirements registry:

| Metric | Widget source | Registry source | Why they differ |
|--------|---------------|-----------------|-----------------|
| Requirements | `stats.total_requirements` — portal runtime + **alias dedupe** | FE tracked attention rows — **no dedupe** | 11 vs 13 (2-property UI) / 43 vs 49 (staging probe) |
| Valid | `stats.compliant` — status COMPLIANT/VALID | Lifecycle VERIFIED / SATISFIED_UNVERIFIED | 4 vs 12 (UI) / 1 vs 3 (staging) |
| Days to next | Min future `due_date` on selected statuses | N/A | Can show 1709d estimated renewal while Expiring Soon = 0 |

Scoring logic does **not** need redesign. **Label + tooltip convergence** is required.

## Derivation summary

See `derivation_trace.json` and `governance_model_runtime.json`.

## Staging probe (nancy@yopmail.com, 7 properties)

- Widget: 43 requirements, 1 valid, 5 days to next expiry
- Registry tracked: 49
- Delta: 6 rows (alias dedupe + runtime gates)

## User-observed 2-property example

- 11 Requirements / 4 Valid / 1709 Days — consistent with:
  - **6 alias/excluded rows** between 13 tracked and 11 score-projected
  - **Valid** using different status semantics
  - **1709 days** = far-future estimated `effective_expiry` / `due_date`, not an active “expiring soon” obligation

## Recommended minimal fixes

See `recommended_convergence_runtime.json` — label changes only, no count inflation.

## Regression

All targeted suites passed (`regression_runtime.json`).
