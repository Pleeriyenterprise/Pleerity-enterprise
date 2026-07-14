# Analytics Regression Results

**Programme:** PHASE_B_ANALYTICS_OPERATIONAL_HARDENING_01  
**Date (UTC):** 2026-07-14  
**Command:** `python -m pytest tests/integrations/zoho/ -q`  

---

## Result

```
57 passed
```

---

## Coverage exercised

| Area | Tests |
|------|--------|
| Analytics import path / append CONFIG | `test_zoho_analytics_import.py` |
| Duplicate period skip + force override | `test_adapter_skips_duplicate_period_unless_forced` |
| Payload midnight validation | `test_validate_analytics_export_payload_rejects_sliding_window` |
| Config missing view | `test_adapter_skips_when_view_id_missing` → `CONFIG_INVALID` |
| Reporting window helper | `test_resolve_daily_reporting_period_*` |
| OAuth Option B / Phase A / health | Remaining Zoho suite |

---

## Not executed in this run

- Live staging export (hardening not yet deployed)  
- Production traffic  

---

## Verdict for regression gate

**PASS** — Zoho integration automated suite green after hardening changes.  
