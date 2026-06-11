# VALUE-INSIGHTS-DIGEST-COUNT-OPTIMISATION-01

**Run:** `20260611T203206Z`  
**Fixture:** Nancy (`6fd5ac4c-3fd4-4112-ade7-156977deb49f`)  
**Classification:** `VERIFIED_OPERATIONALLY`

## Summary

Value insights now resolves `urgent_count` / `upcoming_count` via `resolve_value_insights_task_counts`, preferring operational surface cache before falling back to full `get_unified_tasks_digest`.

## Count authority

| Source | urgent | upcoming |
|--------|--------|----------|
| Baseline full digest | 136 | 10 |
| Optimised value insights | 136 | 10 |
| Match baseline | True | |

Warm resolve: **cached_digest** in **0.05ms** (was ~18182.71ms digest stage).

## Regression

- pytest: PASS
- Local digest stage wall: 0.01ms

## HTTP

{
  "attempted": true,
  "value_insights_cold": {
    "status": 200,
    "duration_ms": 58005.65,
    "task_count_resolution": {},
    "at_risk": {
      "overdue_requirements": 0,
      "expiring_soon_requirements": 0,
      "command_centre_urgent_open": 136,
      "command_centre_upcoming_open": 10
    }
  },
  "value_insights_warm": {
    "status": 200,
    "duration_ms": 25420.53,
    "task_count_resolution": {},
    "at_risk": {
      "overdue_requirements": 0,
      "expiring_soon_requirements": 0,
      "command_centre_urgent_open": 136,
      "command_centre_upcoming_open": 10
    }
  }
}

## Artifacts

- `before_after_runtime.json`
- `count_authority_comparison.json`
- `fallback_behavior.json`
- `regression_runtime.json`
- `classifications.json`

**Re-run:** `python value_insights_digest_count_optimisation_01_execute.py`
