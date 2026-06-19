# Stage X — Twin Staging Operational Validation

**Generated:** 2026-06-19T06:40:24.956467Z
**Export provenance:** contract_cohort
**Export records:** 100

**Recommendation:** CONDITIONAL — Twin adapter path is operationally viable on staging (ingest, review, import, metrics, compliance, lifecycle validated without architectural exceptions). Operational value and production readiness require a real Twin workspace export with measured approval/import rates against business thresholds.

JSON: `backend\docs\audit\discovery_phase_1_launch_01\TWIN_STAGING_VALIDATION_RESULTS.json`

### PART_A_WORKSPACE — AMBER
- workspace manifest not supplied (contract cohort mode)
- agent_id present in manifest or export
- export_id: contract-cohort-stage-x-20260619064024
- export records array present (100 rows)
- TwinProvider payload contract: records[] + provider_reference mapping
- export provenance: contract_cohort

**Failures:**
- contract cohort — not a real Twin workspace export

### PART_B_EXPORT — GREEN
- record 1: 3 twin-only fields isolated to payload
- record 2: 3 twin-only fields isolated to payload
- record 3: 3 twin-only fields isolated to payload
- record 4: 3 twin-only fields isolated to payload
- record 5: 3 twin-only fields isolated to payload
- record 6: 3 twin-only fields isolated to payload
- record 7: 3 twin-only fields isolated to payload
- record 8: 3 twin-only fields isolated to payload
- record 9: 3 twin-only fields isolated to payload
- record 10: 3 twin-only fields isolated to payload
- record 11: 3 twin-only fields isolated to payload
- record 12: 3 twin-only fields isolated to payload

### PART_C_INGEST — GREEN
- ingest accepted=100 rejected=0 duplicates=0
- ingest success rate=100.0% failure rate=0.0%
- discovery_job_id=DJOB-20260619064034-445CFD
- PROSPECT_DISCOVERED audits=100
- prospects persisted=100
- review queue candidates=100
- content_hash generated on Twin prospects

### PART_D_REVIEW — GREEN
- sample reviewed=20
- approval_rate=25.0%
- rejection_rate=25.0%
- duplicate_rate=0.0%
- avg_quality_score=75.1
- avg_review_priority=24.9

### PART_E_IMPORT — GREEN
- imported lead_id=LEAD-20260619064212-6770DD
- discovery_import_v1 tag present
- source_metadata.discovery_provider=twin
- duplicate import idempotent
- unapproved import blocked
- LIA compliance block enforced
- suppression block enforced

### PART_F_METRICS — GREEN
- provider_metrics.twin reconciled
- campaign_metrics present (provider-neutral)
- import_metrics present (provider-neutral)
- metrics service uses provider-neutral aggregation

### PART_G_COMPLIANCE — GREEN
- compliance block rate (sample)=0.0%
- import eligibility rate (sample)=100.0%
- legal hold blocks import=True

### PART_H_LIFECYCLE — GREEN
- erasure_status=erased
- suppression_records=1
- retention_status=indefinite
- purge_eligible=False
- lifecycle identical path to CSV prospects (no Twin-specific service)

### PART_I_COST — GREEN
- twin_cost_gbp=150.0
- prospects_generated=100
- approved=9
- imported=1
- cost_per_prospect=1.5
- cost_per_approved=16.6667
- cost_per_imported=150.0

### PART_J_COMPARISON — GREEN
- approval_rate: Twin Better vs CSV baseline
- duplicate_rate: Twin Better vs CSV baseline
- avg_quality_score: Twin Better vs CSV baseline
- import_rate: Twin Equal vs CSV baseline

### PART_K_FAILURE_MATRIX — GREEN
- compliance_failure=PASS
- duplicate_twin_prospect=PASS
- import_retry=PASS
- invalid_confidence=PASS
- malformed_twin_payload=PASS
- missing_attribution=PASS
- missing_provider_reference=PASS
- suppression_match=PASS

### PART_L_READINESS — AMBER
- Twin Adapter: GREEN
- Twin Data Quality: GREEN
- Twin Compliance Compatibility: GREEN
- Twin Lifecycle Compatibility: GREEN
- Twin Metrics Compatibility: GREEN
- Twin Operational Value: AMBER
- Twin Production Readiness: RED
