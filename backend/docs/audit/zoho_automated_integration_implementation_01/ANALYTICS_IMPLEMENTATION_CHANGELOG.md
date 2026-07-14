# Analytics Implementation Changelog

**Programme:** PHASE_B_ANALYTICS_OPERATIONAL_HARDENING_01  
**Date (UTC):** 2026-07-14  

---

## Summary

Incremental operational hardening for Zoho Analytics export: preflight validation, same-period duplicate protection with `force_reexport`, persistence of reporting-period `result_summary`, Analytics soft-failure dead-lettering with replay resolution, and `analytics_ops` observability on the existing health summary.

---

## Behavioural changes

| Before | After |
|--------|--------|
| Repeated manual export for same UTC day appended duplicate rows | Skipped with `period_already_exported` unless `force_reexport=true` |
| Soft Zoho API failures left orphan `failed` sync runs | Analytics soft failures go to dead letter (replayable) |
| Dead-letter replay left `resolved=false` | Success/skip resolves DL; failure increments `replay_count` |
| Sync runs omitted period identifiers | `result_summary.period_start/end` stored on completion |
| Admin status hid target ID presence | `analytics_target` booleans + missing list |
| Health summary lacked Analytics ops detail | `analytics_ops` block (last success/fail, period, config, OAuth) |
| Payload/column issues discovered at Zoho | Local payload + config validation before HTTP |

---

## API / contract preservation

- Same 12-column aggregate schema  
- Same field names  
- `export_type=aggregated_daily`  
- Append-only Zoho import unchanged  
- Admin routes unchanged (additive status fields only)  
- Snapshot metrics behaviour unchanged  

---

## Operator notes

- Deliberate same-day re-export: pass `"force_reexport": true` on `POST /api/admin/integrations/zoho/sync` payload (or include in job path via sync service payload once wired).  
- Remote table column-type drift still requires Zoho console / metadata scope for live describe — local contract validates payload shape only.  
