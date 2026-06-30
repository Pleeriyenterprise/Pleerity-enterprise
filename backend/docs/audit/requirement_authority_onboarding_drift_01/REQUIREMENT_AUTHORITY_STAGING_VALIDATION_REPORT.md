# REQUIREMENT-AUTHORITY-ONBOARDING-DRIFT-STAGING-VALIDATION-01

**Verdict:** `STAGING_VALIDATION_ACCEPTED`
**Run:** 20260630T151457Z
**Primary client:** 2c972bea-2e87-494a-9853-b2d9d38e88e3 (PLE-CVP-2026-000003)
**Duplicate occupation client:** 6bcc43c0-16f4-46a5-adf4-26693a0919d0 (PLE-CVP-2026-000040)
**Staging deploy SHA:** c93a014b7da2f724900a72c5ef9e6e10eec760d2

## Summary

| Check | Result |
|-------|--------|
| Local pytest (5 tests) | PASS |
| Shadow occupation dedupe (000040) | PASS |
| Shadow count semantics (000003) | PASS |
| Shadow EICR no premature risk | PASS |
| HTTP fixes deployed on staging | YES |
| Duplicate active groups (staging) | 0 |
| Authority-superseded rows (staging) | 27 |
| Reconcile job required before prod | **NO** |

## Commands

```bash
cd backend
python -m pytest tests/test_requirement_authority_onboarding_drift_01.py -v --tb=line
python tmp_requirement_authority_staging_validation_01.py
```

## Local pytest

- Exit code: 0
- Passed: True

## Shadow validation (local develop code + pleerity_staging Mongo)

- Raw requirements: 18
- Runtime visible: 12
- Tracked attention: 12
- Semantics: `{"requirements_runtime_visible_count": 12, "requirements_tracked_attention_count": 12, "requirements_count_semantics": "tracked_attention_document_job_excludes_obligation"}`
- Wales occupation pass: None
- EICR electrical pass: True

### Primary CRN PLE-CVP-2026-000003

- Raw Mongo: 18 | Shadow tracked: 12 | Shadow visible: 12
- Setup-status HTTP: raw `requirements_count` = 18
- Semantic fields on HTTP: True

### Duplicate occupation client PLE-CVP-2026-000040 (shadow dedupe proof)

- Raw Mongo: 107 | Shadow tracked: 64
- HTTP occupation visible count: 3

### Authority reconciliation (staging Mongo)

```json
{
  "scope": "pleerity_staging",
  "metrics": {
    "total_rows": 613,
    "active_alias_family_rows": 134,
    "authority_superseded_rows": 27,
    "duplicate_active_groups": 0
  }
}
```

### Reconcile assessment (active duplicates only)

**Production reconcile required:** False
 (duplicate_active_groups=0)

```json
{
  "duplicate_active_groups": 0,
  "authority_superseded_rows": 3,
  "clients_with_active_occupation_duplicate_pairs": 0,
  "clients_with_historical_raw_occupation_duplicate_pairs": 1,
  "properties_needing_reconcile": [],
  "historical_properties_with_superseded_duplicates": [
    {
      "property_id": "3a69dcbd-74fd-4291-839b-3d52750598a1",
      "property_name": "3a69dcbd-74fd-4291-839b-3d52750598a1",
      "historical_raw_types": [
        "occupation_contract",
        "wales_occupation_contract"
      ],
      "active_occupation_types": [
        "wales_occupation_contract"
      ],
      "authority_superseded_in_pair": true
    }
  ]
}
```

## HTTP validation (live staging API)

- Deployed fixes on HTTP: True
- Setup-status sample: `{"client_id": "6bcc43c0-16f4-46a5-adf4-26693a0919d0", "customer_reference": "PLE-CVP-2026-000040", "crn": "PLE-CVP-2026-000040", "client_name": "David Miller", "billing_plan": "PLAN_2_PORTFOLIO", "intake_submitted": true, "payment_state": "paid", "subscription_status": "ACTIVE", "provisioning_status": "COMPLETED", "provisioning_state": "completed", "portal_user_exists": true, "portal_user_created": true, "portal_user_created_at": "2026-05-15T20:43:12.807000", "activation_email_status": "SENT", "activation_email_sent_at": "2026-05-15T20:43:18.427000", "activation_email_last_sent_at": "2026-05-15T20:43:18.427000", "activation_email_to_masked": "dav***@yo***", "masked_email": "dav***@yo***", "activation_email_error": null, "password_set": true, "password_reset_sent": true, "password_state": "`
- HTTP occupation visible count: 3
- HTTP tracked attention: 64

## Checks

```json
{
  "local_pytest": true,
  "shadow_wales_one_occupation": true,
  "shadow_duplicate_client_dedupe": true,
  "shadow_count_semantics": true,
  "shadow_eicr_no_premature_risk": true,
  "http_tracked_aligns_shadow": true,
  "http_dashboard_stats_present": true,
  "http_occupation_pre_deploy_duplicate_visible": true,
  "http_setup_status_semantic_fields_absent_pre_deploy": false
}
```
