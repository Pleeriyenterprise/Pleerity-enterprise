# Lifecycle Communication Authority — Staging Validation

**Outcome:** `STAGING_VALIDATION_GO`
**Commit:** `2911dd95a3f37e6f758b598356e7f4d1c06284b9`
**Generated:** 2026-07-02T10:43:10.498612+00:00
**Staging API:** https://pleerity-enterprise.onrender.com/api

## Checks

- **local_pytest_pass:** `True`
- **local_render_and_leakage_pass:** `True`
- **staging_deployed_expected_sha:** `True`
- **staging_health_ok:** `True`
- **staging_api_pass:** `True`
- **reminder_timing_routing_unchanged:** `True`

## Local matrix

### reminder_review_email
- has_review_due_on: `True`
- no_renewal: `True`
- no_expiry_heading: `True`

### declaration_enablement
- reason_has_declaration: `True`
- no_expires_in_reason: `True`
- no_renewal_in_what: `True`

### grouped_headings
- certificate_heading_governed: `True`
- other_heading_governed: `True`
- legacy_misleading_absent: `True`

### digest_review_posture
- label_not_renewal_approaching: `True`
- has_review: `True`

### risk_electrical
- not_certificate_only: `True`
- mentions_electrical: `True`

### sms_review
- mentions_review: `True`
- not_generic_compliance_items_only: `True`

### reminder_routing_unchanged
- default_mode_not_active: `True`
- mode: `off`

## Staging API

```json
{
  "checks": {
    "requirements_api_ok": true,
    "customer_communication_present": true,
    "authority_version_on_api": true,
    "structured_model_fields": true,
    "no_wording_leakage_in_sample": true,
    "risk_card_governed_copy": true,
    "staging_api_pass": true
  },
  "requirements_status": 200,
  "requirements_total": 49,
  "requirements_with_customer_communication": 49,
  "sample_communication_keys": [
    "attention_kind",
    "authority_version",
    "channel",
    "completion_wording",
    "due_date",
    "evidence_expectation",
    "heading",
    "how_text",
    "is_overdue",
    "lifecycle_family",
    "lifecycle_verb",
    "next_step",
    "primary_action",
    "primary_cta",
    "property_address",
    "reason",
    "requirement_name",
    "secondary_cta",
    "supporting_explanation",
    "surface",
    "surface_variants",
    "template_context",
    "tone",
    "urgency",
    "when_text"
  ],
  "leakage_failures": [],
  "risk_signals_status": 200,
  "risk_card_note": "Persisted signal may predate LCA deploy; local_matrix risk_electrical governs new copy."
}
```