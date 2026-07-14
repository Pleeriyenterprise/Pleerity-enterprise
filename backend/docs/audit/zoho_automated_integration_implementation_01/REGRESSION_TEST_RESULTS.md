# REGRESSION_TEST_RESULTS — Zoho CRM Phase C

**Date:** 2026-07-14  

## Command

```text
python -m pytest tests/integrations/zoho/test_zoho_crm.py \
  tests/integrations/zoho/test_zoho_operational_health.py \
  tests/integrations/zoho/test_zoho_integration.py \
  tests/integrations/zoho/test_zoho_phase_a.py \
  tests/integrations/zoho/test_zoho_oauth.py -q
```

## Result

**60 passed**

## Coverage highlights

- Payload required fields / unexpected columns  
- Create persists external key  
- Create without ID → failure (not success)  
- Identity lookup before create (duplicate prevention)  
- External key preferred over lookup  
- Soft fail → dead letter  
- Scope includes READ, not ALL  
- Existing Zoho Phase A/OAuth/integration suites remain green  
