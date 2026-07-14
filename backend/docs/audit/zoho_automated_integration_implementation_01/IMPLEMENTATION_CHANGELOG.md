# IMPLEMENTATION_CHANGELOG — Zoho CRM Phase C

**Date:** 2026-07-14  
**Phase:** `PHASE_C_ZOHO_CRM_IMPLEMENTATION_01`

## Changes

- Hardened `ZohoCrmAdapter`: payload preflight; identity order External Key → `Pleerity_Lead_ID` lookup → create → persist; create fails closed without CRM ID; duplicate conflict recovery
- Added `ZohoCRM.modules.leads.READ` to CRM expected OAuth scope (not ALL)
- Extended HTTP client to treat Zoho `204` search empty as success
- Soft CRM API failures enter shared dead-letter + replay path
- `crm_target` + `crm_ops` observability; Control Centre warning/degraded/incident
- `lead.lost` enqueues status-only CRM update (no delete/archive)
- Adapter version CRM `1.1.0`
- Regression tests: `tests/integrations/zoho/test_zoho_crm.py`

## Non-changes

- No CRM scheduler/cron  
- No production enablement  
- No inbound CRM authority  
- No framework redesign  
