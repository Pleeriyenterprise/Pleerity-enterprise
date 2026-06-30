# REQUIREMENT-AUTHORITY-ONBOARDING-DRIFT-STAGING-VALIDATION-01

**Verdict:** `SHADOW_ACCEPTED_PRE_DEPLOY_HTTP_BASELINE`
**Run:** 20260630T142001Z
**Primary client:** 2c972bea-2e87-494a-9853-b2d9d38e88e3 (PLE-CVP-2026-000003)
**Duplicate occupation client:** 6bcc43c0-16f4-46a5-adf4-26693a0919d0 (PLE-CVP-2026-000040)
**Staging deploy SHA:** 817977e46638184b90bb465ffaac2db5992c6cde

## Summary

| Check | Result |
|-------|--------|
| Local pytest (5 tests) | PASS |
| Shadow occupation dedupe (000040) | PASS |
| Shadow count semantics (000003) | PASS |
| Shadow EICR no premature risk | PASS |
| HTTP fixes deployed on staging | NO — pre-deploy baseline |
| Reconcile job required before prod | **YES** |

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
- Setup-status HTTP (pre-deploy): raw `requirements_count` only = 18
- Semantic fields on HTTP: False

### Duplicate occupation client PLE-CVP-2026-000040 (shadow dedupe proof)

- Raw Mongo: 107 | Shadow tracked: 64
- HTTP requirements rows (pre-deploy, **still shows duplicate**): occupation count = 4
- Legacy active electrical risk in Mongo (pre-deploy): see `duplicate_occupation_shadow.eicr_electrical_risk_checks`

### Wales occupation checks (000040)

```json
[]
```

```json
[
  {
    "property_id": "3a69dcbd-74fd-4291-839b-3d52750598a1",
    "property_name": "3a69dcbd-74fd-4291-839b-3d52750598a1",
    "raw_occupation_row_count": 2,
    "raw_occupation_types": [
      "occupation_contract",
      "wales_occupation_contract"
    ],
    "runtime_visible_occupation_count": 1,
    "runtime_visible_occupation_types": [
      "occupation_contract"
    ],
    "pass_one_visible": true,
    "raw_duplicate_pair": true
  },
  {
    "property_id": "68f8755a-e7d8-4572-b7fc-6f79ad5b430c",
    "property_name": "68f8755a-e7d8-4572-b7fc-6f79ad5b430c",
    "raw_occupation_row_count": 1,
    "raw_occupation_types": [
      "occupation_contract"
    ],
    "runtime_visible_occupation_count": 1,
    "runtime_visible_occupation_types": [
      "occupation_contract"
    ],
    "pass_one_visible": true,
    "raw_duplicate_pair": false
  },
  {
    "property_id": "73cad925-c2bd-481f-8026-a38ea3e212d5",
    "property_name": "73cad925-c2bd-481f-8026-a38ea3e212d5",
    "raw_occupation_row_count": 1,
    "raw_occupation_types": [
      "occupation_contract"
    ],
    "runtime_visible_occupation_count": 1,
    "runtime_visible_occupation_types": [
      "occupation_contract"
    ],
    "pass_one_visible": true,
    "raw_duplicate_pair": false
  }
]
```

### Reconcile assessment

**Production reconcile required:** True

```json
{
  "clients_with_raw_occupation_duplicate_pairs": 0,
  "properties_needing_reconcile": []
}
```

Duplicate-client reconcile:

```json
{
  "clients_with_raw_occupation_duplicate_pairs": 1,
  "properties_needing_reconcile": [
    {
      "property_id": "3a69dcbd-74fd-4291-839b-3d52750598a1",
      "property_name": "3a69dcbd-74fd-4291-839b-3d52750598a1",
      "raw_types": [
        "occupation_contract",
        "wales_occupation_contract"
      ],
      "runtime_deduped_to": 1,
      "reconcile_recommended": true,
      "reason": "Raw Mongo retains duplicate rows; runtime dedupe hides in client surfaces"
    }
  ]
}
```

**Production recommendation:** Run a reconcile job to archive superseded `occupation_contract` rows where `wales_occupation_contract` exists for the same property. Runtime dedupe is sufficient for client surfaces but Mongo authority remains duplicated until reconcile.

## HTTP validation (live staging API)

- Deployed fixes on HTTP: False
- Setup-status sample: `{"client_id": "6bcc43c0-16f4-46a5-adf4-26693a0919d0", "customer_reference": "PLE-CVP-2026-000040", "crn": "PLE-CVP-2026-000040", "client_name": "David Miller", "billing_plan": "PLAN_2_PORTFOLIO", "intake_submitted": true, "payment_state": "paid", "subscription_status": "ACTIVE", "provisioning_status": "COMPLETED", "provisioning_state": "completed", "portal_user_exists": true, "portal_user_created": true, "portal_user_created_at": "2026-05-15T20:43:12.807000", "activation_email_status": "SENT", "activation_email_sent_at": "2026-05-15T20:43:18.427000", "activation_email_last_sent_at": "2026-05-15T20:43:18.427000", "activation_email_to_masked": "dav***@yo***", "masked_email": "dav***@yo***", "activation_email_error": null, "password_set": true, "password_reset_sent": true, "password_state": "`
- HTTP occupation visible count: 4
- HTTP tracked attention: 65

**Expected pre-deploy HTTP drift:** Shadow tracked count is 64 (alias dedupe applied locally); live staging API returns 65 rows — confirms fixes are not yet deployed (`817977e4`).

## Commit readiness

| Gate | Status |
|------|--------|
| Shadow validation (local develop + pleerity_staging Mongo) | **PASS** |
| Local regression tests | **PASS (5/5)** |
| Live HTTP acceptance (setup-status semantics, occupation dedupe on API) | **Pending deploy after commit** |
| Reconcile job before production | **Required** (at least 1 property on PLE-CVP-2026-000040) |

**Recommendation:** Safe to **commit on develop**. Do not promote to production until post-deploy HTTP re-validation passes and reconcile job runs.

## Checks

```json
{
  "local_pytest": true,
  "shadow_wales_one_occupation": true,
  "shadow_duplicate_client_dedupe": true,
  "shadow_count_semantics": true,
  "shadow_eicr_no_premature_risk": true,
  "http_tracked_aligns_shadow": false,
  "http_dashboard_stats_present": true,
  "http_occupation_pre_deploy_duplicate_visible": true,
  "http_setup_status_semantic_fields_absent_pre_deploy": true
}
```
