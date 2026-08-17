# CRM Concurrency Regression Results

**Programme:** `CRM_CONCURRENCY_HARDENING_01`  
**Date:** 2026-07-14  
**Command:** `pytest tests/integrations/zoho/test_zoho_crm.py tests/integrations/zoho/test_zoho_crm_concurrency.py -q`

## Result

**18 passed**

## Coverage mapping

| Requirement | Test |
|---|---|
| `duplicate_record.id` extraction | `test_extract_duplicate_crm_record_id_from_body`, `…_from_error_text` |
| DUPLICATE_DATA binds without Search | `test_crm_duplicate_data_binds_from_duplicate_record_id_without_search` |
| Fallback Search when id absent | `test_crm_duplicate_data_falls_back_to_search_when_id_absent` |
| Create persists external key | `test_crm_create_persists_external_key` |
| Identity lookup before create | `test_crm_identity_lookup_before_create` |
| External key first | `test_crm_update_uses_external_key_first` |
| Soft-fail → DL | `test_crm_soft_fail_enters_dead_letter` |
| Atomic queue claim | `test_claim_pending_queue_atomic_find_one_and_update` |
| Queue process uses claim | `test_process_queue_uses_claim_not_fetch` |
| External-key first-writer / DuplicateKey re-read | `test_store_external_key_first_writer_wins_on_duplicate`, `…_immutable_existing` |
| No email heuristics in criteria | `test_search_criteria_uses_pleerity_lead_id_only` |

## Pre-hardening live race evidence (baseline)

Prior staging run (`CRM_CONCURRENCY_RACE_VALIDATION.md`):

- Concurrent creates produced Zoho `DUPLICATE_DATA` on `Pleerity_Lead_ID`
- Unique field prevented second CRM Lead
- Losers often dead-lettered because Search lag broke old recovery
- After settle: exactly one CRM id + one external key per lead

Hardening targets that residual DL path specifically.

## Live staging re-matrix

**Deferred until staging deploy of adapter 1.2.0.** Unit regression is green against the new code paths.
