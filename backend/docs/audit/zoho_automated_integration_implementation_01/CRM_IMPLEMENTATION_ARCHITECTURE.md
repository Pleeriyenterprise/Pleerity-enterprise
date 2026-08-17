# CRM_IMPLEMENTATION_ARCHITECTURE

**Phase:** `PHASE_C_ZOHO_CRM_IMPLEMENTATION_01`  
**Date:** 2026-07-14  
**Reference:** Zoho Analytics operational pattern (same framework; no redesign)

---

## Authority chain (immutable)

```
Website → Pleerity Platform (SoR) → Governed Integration Layer → Zoho CRM
```

Never: Website → Zoho CRM → Pleerity. Inbound CRM webhooks remain rejected; Pleerity is never mutated by CRM.

## Lifecycle (deterministic)

```
Website lead → Pleerity lead → validation/dedup → maybe_enqueue_crm_sync
  → zoho_sync_queue → run_sync(crm) → payload validate
  → identity resolve → POST/PUT Zoho → persist zoho_external_keys
  → audit + sync_run → future updates / lead.lost (status mirror only)
```

## Identity resolution order

1. Local `zoho_external_keys` (crm + lead_id)  
2. Zoho search by **Pleerity_Lead_ID only** (requires `leads.READ`)  
3. Create (`POST`)  
4. Extract CRM record ID → persist external key → audit  

Forbidden: email, name, or heuristic matching.

## Create success contract

A create is **SUCCESS** only if all hold:

- Zoho returns 2xx  
- Record ID extracted  
- External key persisted  
- Sync result / audit records `external_id`  

Otherwise: recoverable **FAILED** → dead-letter → operator replay.

## Sync model

| Mode | Behaviour |
|---|---|
| Create | POST after identity miss |
| Update | PUT with bound external ID |
| Retry / Replay | Same identity order; no uncontrolled loops |
| Duplicate | Lookup / DUPLICATE recovery → bind + PUT |
| Conflict | Recover via Pleerity_Lead_ID lookup |
| Archive/lost | `lead.lost` updates CRM status fields only — **never** Zoho delete/archive |
| Manual | Admin `upsert_lead` / queue process — `force` none |

## Scheduling

**Manual-only.** No CRM cron in this phase.

## Production

Not modified. Not enabled.
