# ANALYTICS_SCHEDULER_REGRESSION_RESULTS

**Phase:** `PHASE_B_ANALYTICS_SCHEDULED_OPERATION_01`  
**Date:** 2026-07-14  
**Command:**

```text
python -m pytest tests/integrations/zoho/test_zoho_analytics_schedule.py \
  tests/integrations/zoho/test_zoho_operational_health.py \
  tests/integrations/zoho/test_zoho_analytics_import.py \
  tests/integrations/zoho/test_zoho_phase_a.py -q
```

## Result

**36 passed**

## Coverage exercised

| Area | Tests |
|---|---|
| Dual ISO + BSON period filters | `test_period_timestamp_filter_covers_iso_and_bson`, updated `test_build_analytics_export_includes_payload_version` |
| Staging-only registration gate | `test_analytics_schedule_registration_staging_only` |
| Incident policy thresholds | `test_analytics_incident_policy_levels` |
| Kill-switch / disabled skip (success outcome) | `test_run_zoho_analytics_export_skips_kill_switch`, `..._skips_when_disabled` |
| Run-lock skip | `test_run_zoho_analytics_export_skips_when_lock_held` |
| No `force_reexport` + duplicate skip metrics + lock release | `test_run_zoho_analytics_export_no_force_reexport_and_releases_lock` |
| Lock acquire / reject | `test_acquire_lock_insert_and_reject_second` |
| Next 02:15 UTC helper | `test_next_daily_run_utc` |
| Existing import / duplicate / Phase A health | prior suites still green |

## Not claimed

- Live Zoho POST success was **not** fabricated in unit tests.
- Staging deploy validation (restart uniqueness, live DL replay) is tracked in `ANALYTICS_STAGING_SCHEDULE_VALIDATION.md`.
