# IMPLEMENTATION_CHANGELOG — Zoho CRM Phase C

**Date:** 2026-07-15  
**Phase:** `PHASE_C_ZOHO_CRM_IMPLEMENTATION_01` / `CRM_CONCURRENCY_HARDENING_01`

## Changes

### Phase C baseline (1.1.0)

- Hardened `ZohoCrmAdapter`: payload preflight; identity order External Key → `Pleerity_Lead_ID` lookup → create → persist; create fails closed without CRM ID; duplicate conflict recovery
- Added `ZohoCRM.modules.leads.READ` to CRM expected OAuth scope (not ALL)
- Extended HTTP client to treat Zoho `204` search empty as success
- Soft CRM API failures enter shared dead-letter + replay path
- `crm_target` + `crm_ops` observability; Control Centre warning/degraded/incident
- `lead.lost` enqueues status-only CRM update (no delete/archive)
- Adapter version CRM `1.1.0`
- Regression tests: `tests/integrations/zoho/test_zoho_crm.py`

### Concurrency hardening (1.2.0) — 2026-07-14/15

- `DUPLICATE_DATA` convergence via `details.duplicate_record.id` bind + optional PUT; Search fallback only if id absent
- HTTP client returns parsed error body on failed Zoho responses (supports structured duplicate recovery)
- External-key first-writer-wins + unique indexes `(integration,pleerity_id,resource_type)` and `(integration,zoho_id,resource_type)`; `DuplicateKeyError` re-reads winner
- Atomic queue claim: `pending` / expired-`processing` → `processing` with `claim_id` + lease (`ZOHO_QUEUE_LEASE_SECONDS=120`)
- Adapter version CRM `1.2.0`
- Tests: `test_zoho_crm.py` + `test_zoho_crm_concurrency.py` (18 passed for CRM concurrency suite)

## Non-changes

- No CRM scheduler/cron  
- No production enablement  
- No inbound CRM authority  
- No framework redesign  
- No per-lead create lock (residual create races covered by Zoho unique + duplicate_record.id + queue claim)  
