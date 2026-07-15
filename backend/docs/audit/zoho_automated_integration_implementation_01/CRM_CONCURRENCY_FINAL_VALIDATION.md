# CRM Concurrency Final Validation

**Programme:** `CRM_CONCURRENCY_HARDENING_01`  
**Date:** 2026-07-14  

## Verdict

### **CRM_CONCURRENCY_HARDENED_WITH_CONDITIONS**

## Proof checklist

| Proof | Status | Evidence |
|---|---|---|
| Exactly one CRM Lead per Pleerity lead (design) | PASS (code + prior live race) | Zoho unique + bind; prior Search count never >1 |
| Exactly one external binding | PASS (code) | Unique indexes + first-writer `store_external_key` |
| `DUPLICATE_DATA` converges without DL when CRM id supplied | PASS (unit) | `test_crm_duplicate_data_binds_from_duplicate_record_id_without_search` |
| Queue item not dual-processed | PASS (unit) | Atomic `find_one_and_update` claim |
| Abandoned claim recoverable | PASS (code) | `processing` + expired `lease_expires_at` reclaimable |
| No email/name heuristics | PASS | Criteria / identity path unchanged |
| Final state without manual repair (unit paths) | PASS | Bind + PUT on duplicate id |
| Production unchanged | PASS | No production deploy / config changes in this work |
| Live staging concurrency matrix post-hardening | **PENDING DEPLOY** | Condition |

## Conditions

1. **Staging redeploy required** — live concurrent matrix must re-run on CRM adapter `1.2.0` after Render staging picks up this commit.  
2. **Index bootstrap** — `zoho_id` unique index creation warns if historical duplicate bindings exist; clean per environment.  
3. **Per-lead create lock omitted by design** — residual create races rely on Zoho uniqueness + `duplicate_record.id` (documented evaluation).

## Recommended next step (ops)

1. Deploy `develop` (CRM 1.2.0) to staging only.  
2. Ensure Zoho indexes via app boot / `ensure_indexes`.  
3. Re-run `tmp_crm_concurrency_race_validation.py` + settle.  
4. Expect: concurrent drains claim disjoint items; duplicate responses bind without DL when `duplicate_record.id` present; production pin still `89217062…`.

## Authority preserved

Pleerity remains SoR. Zoho CRM remains downstream replica. Identity hierarchy and forbidden matchers unchanged.
