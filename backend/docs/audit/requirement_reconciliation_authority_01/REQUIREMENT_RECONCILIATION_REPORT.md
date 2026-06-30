# REQUIREMENT-RECONCILIATION-AUTHORITY-01

**Mode:** execute
**Duration:** 6015.46 ms
**Duplicate families found:** 26
**Records to archive:** 27
**Records archived:** 27

## Metrics before

```json
{
  "total_rows": 613,
  "active_alias_family_rows": 161,
  "authority_superseded_rows": 0,
  "duplicate_active_groups": 26
}
```

## Metrics after

```json
{
  "total_rows": 613,
  "active_alias_family_rows": 134,
  "authority_superseded_rows": 27,
  "duplicate_active_groups": 0
}
```

## Idempotency verification

**Pass:** True

```json
{
  "second_run_archived": 0,
  "second_run_to_archive": 0,
  "pass": true
}
```

Evidence: `REQUIREMENT_RECONCILIATION_execute_20260630T150334Z.json`