# CRM Concurrency Hardening Report

**Programme:** `CRM_CONCURRENCY_HARDENING_01`  
**Date:** 2026-07-14  
**Adapter version:** `crm` **1.1.0 → 1.2.0**  
**Production:** untouched (no production changes)

---

## Summary

Hardened the validated Zoho CRM outbound path against concurrent create / queue / replay / manual upsert races **without** redesigning the integration framework, adding CRM cron, or changing identity hierarchy.

| Item | Status |
|---|---|
| 1. `DUPLICATE_DATA` → `duplicate_record.id` bind | **Implemented** |
| 2. External-key unique indexes + first-writer re-read | **Implemented** |
| 3. Atomic queue claim (`pending`→`processing` + lease) | **Implemented** |
| 4. Per-lead create lock | **Not implemented** (residual risk absorbed by 1–3) |

---

## 1. DUPLICATE_DATA convergence

**Files:** `adapters/crm.py`, `client.py` (error body returned on HTTP failure)

On Lead `POST` failure:

1. Detect Zoho `DUPLICATE_DATA` / duplicate semantics.
2. Extract `details.duplicate_record.id` (from structured error body or error JSON text).
3. `store_external_key` bind → optional `PUT` update of the intended payload.
4. Identity source: `duplicate_record_id`.
5. If id absent → fall back to `Pleerity_Lead_ID` Search (`duplicate_conflict_lookup`).
6. Dead-letter only if neither mechanism resolves identity.

This closes the Search-lag window observed in concurrency validation (losers got `DUPLICATE_DATA` but Search still returned empty).

---

## 2. External-key integrity

**Files:** `sync_store.py`, `database.py` (startup `ensure_indexes`)

| Constraint | Index |
|---|---|
| One Pleerity lead → one CRM binding | unique `(integration, pleerity_id, resource_type)` |
| One CRM id → one Pleerity lead | unique `(integration, zoho_id, resource_type)` |

`store_external_key` now:

- Returns authoritative `zoho_id`.
- **First-writer wins** (existing binding immutable).
- On `DuplicateKeyError`, re-reads the winning binding.
- Refuses to steal a CRM id already owned by another Pleerity lead.

---

## 3. Atomic queue claiming

**Files:** `sync_store.py`, `service.py`, `types.py` (`ZOHO_QUEUE_LEASE_SECONDS=120`)

Workers call `claim_pending_queue` (not plain `find`):

- Filter: `status=pending` **or** (`status=processing` and `lease_expires_at <= now`)
- Atomic `find_one_and_update` → `processing` + `claim_id` + `claimed_at` + `lease_expires_at`
- Loop up to `limit`; two workers cannot claim the same `queue_id`
- `mark_queue_done` / `mark_queue_failed` clear claim fields; failed remains auditable
- Abandoned claims reclaimable after lease expiry (worker crash / restart safe)

`fetch_pending_queue` remains for observability only.

---

## 4. Per-lead create lock — evaluation

| Residual race | Mitigated by |
|---|---|
| Concurrent POSTs before local key | Zoho unique `Pleerity_Lead_ID` + `duplicate_record.id` bind |
| Concurrent queue drains | Atomic claim |
| External-key insert race | Unique indexes + re-read |
| Search lag on recovery | Prefer `duplicate_record.id` over Search |

**Decision:** do **not** add a per-lead DB lock. It would add lease/ownership complexity without materially reducing residual risk after 1–3.

---

## Preserved governance

- Identity order: local external key → `Pleerity_Lead_ID` Search → create → persist  
- No email / name / phone heuristics  
- Event-driven enqueue unchanged; manual-only CRM (no cron)  
- Soft-fail dead-letter policy retained for **unresolved** failures  
- Analytics run-lock pattern left as Analytics-only  

---

## Risks / ops notes

- Staging must **redeploy** `develop` with CRM adapter 1.2.0 before live concurrency re-proof.
- Unique index on `zoho_id` will fail to create if historical duplicate bindings exist — logs a warning; clean data before enforcing in each environment.
- Induced `lead_not_found` DLs from prior race tooling may still sit unresolved until classified/resolved separately.
