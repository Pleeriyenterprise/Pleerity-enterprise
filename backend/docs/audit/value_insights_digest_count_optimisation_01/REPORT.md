# VALUE-INSIGHTS-DIGEST-COUNT-OPTIMISATION-01-POST-DEPLOY

**Run:** `20260612T065647Z`  
**Fixture:** Nancy (`6fd5ac4c-3fd4-4112-ade7-156977deb49f`)  
**Classification:** `VERIFIED_OPERATIONALLY`

## Deploy proof

- `/api/version` commit: `ab588f05271612455cf4a62ccca901b4f1e9732d`
- Deploy match (ab588f05+): **True**
- `task_count_resolution` present: **True**

## Warm cache path

| Step | source_used | digest_ms | total_ms | urgent | upcoming |
|------|-------------|-----------|----------|--------|----------|
| After tasks/digest prime | cached_digest | 0.69 | 30002.67 | 136 | 10 |
| After Today | fallback_full_unified_tasks | 31244.69 | 56531.67 | 136 | 10 |
| After CC primary | fallback_full_unified_tasks | 31583.89 | 63962.21 | 136 | 10 |

Warm path pass: **True**

## Cold fallback path

| Step | source_used | fallback_reason | digest_ms | total_ms |
|------|-------------|-----------------|-----------|----------|
| First (no prime) | fallback_full_unified_tasks | no_cached_digest_or_command_center_summary | 30994.62 | 56643.04 |
| After 48s TTL | fallback_full_unified_tasks | no_cached_digest_or_command_center_summary | 32897.14 | 58374.44 |

Cold fallback pass: **True**

## Count authority

Baseline digest: urgent=136, upcoming=10  
All paths match: **True**

## Timing

Digest stage reduction (warm vs profiling baseline): **18182.02ms**

## Regression

- Backend pytest: PASS
- Frontend smoke: PASS

**Re-run:** `python value_insights_digest_count_optimisation_01_post_deploy_execute.py`
