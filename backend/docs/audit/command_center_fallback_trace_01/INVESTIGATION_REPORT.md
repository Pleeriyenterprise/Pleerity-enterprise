# Command Center Fallback Investigation — `6bcc43c0-16f4-46a5-adf4-26693a0919d0`

**Client:** David Miller (Wales E2E, PLAN_2_PORTFOLIO)  
**Environment:** `pleerity_staging`

## Summary

| Warning | Classification | Root cause |
|---------|----------------|------------|
| `operational_value_bundle_v1 failed` | **SERVICE_FAILURE** | 9s timeout exceeded (~15s sequential sub-bundle build) |
| `command_center_primary_urgent_summary fallback` | **Not reproduced** (latent timeout risk) | Primary gather succeeded (~11.5s / 12s budget) |

This is **not** an empty account, capability denial, or missing data issue. The client has 8 properties, 107 requirements, and 9 urgent Command Centre rows.

## `operational_value_bundle_v1 failed`

**Exact failure:** `asyncio.TimeoutError` (empty message → logged as `primary_timeout_or_failure:`)

**Dependency chain:**
1. `get_command_center_primary_bundle` → `asyncio.wait_for(build_operational_value_bundle_v1, 9.0)`
2. Sub-bundles were built **sequentially** (~14s total):
   - `assignment_execution_momentum` ~6.4s
   - `execution_capacity` ~3.9s
   - `closure_conversion` ~2.0s
   - `backlog_reduction` ~1.8s

**Not the cause:**
- Portfolio score null with `score_status: ok` — persisted headline fast path (counts deferred, not missing)
- Requirements exist (107 in Mongo)
- Priority stream returns 6–9 urgent actions
- Operational cognition / Today not involved in this failure path

## `command_center_primary_urgent_summary fallback`

Not triggered in staging trace for this client. Urgent slice (~11.5s) + compliance summary (~57ms) completed under the 12s gather budget.

If it does trigger, classification would be **SERVICE_FAILURE** (timeout on priority stream assembly), not empty state.

## Remediation applied

1. **Parallelize** the four operational value sub-bundles (`asyncio.gather`)
2. **Share inventory** load across compression / focus / KPIs (single Mongo read)
3. **Observable fallbacks:** `_format_degraded_exception`, `fallback_classification`, `pressure_fallback_classification` on API payload; INFO log level for `EXPECTED_EMPTY_STATE` only

**Post-fix:** `build_operational_value_bundle_v1` ~7.9s; primary bundle `pressure_degraded: false`.

## Tests

`tests/test_command_center_fallback_observability_01.py`
