# REGRESSION_TEST_RESULTS — Zoho CRM Phase C

**Date:** 2026-07-15  

## Concurrency hardening suite

```text
python -m pytest tests/integrations/zoho/test_zoho_crm.py \
  tests/integrations/zoho/test_zoho_crm_concurrency.py -q
```

**Result:** **18 passed** (2026-07-14)

Coverage:

- `duplicate_record.id` extraction and bind without Search  
- Search fallback when duplicate id absent  
- Atomic queue claim / process_queue uses claim  
- External-key first-writer + DuplicateKey re-read  
- Prior Phase C create/update/lookup/soft-fail paths  

## Broader Zoho suite (Phase C baseline)

```text
python -m pytest tests/integrations/zoho/test_zoho_crm.py \
  tests/integrations/zoho/test_zoho_operational_health.py \
  tests/integrations/zoho/test_zoho_integration.py \
  tests/integrations/zoho/test_zoho_phase_a.py \
  tests/integrations/zoho/test_zoho_oauth.py -q
```

**Result (historical baseline):** **60 passed** (2026-07-14, pre-1.2.0)

## Certification note

Final operational certification live matrix requires staging on CRM adapter **1.2.0** (post-deploy). See `CRM_FINAL_OPERATIONAL_CERTIFICATION.md`.
