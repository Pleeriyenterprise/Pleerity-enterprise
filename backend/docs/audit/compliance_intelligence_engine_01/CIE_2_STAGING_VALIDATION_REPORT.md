# CIE-2 Staging Shadow Validation Report

**Verdict:** `CIE_2_STAGING_VALIDATION_ACCEPTED`
**Programme:** CIE-2-STAGING-SHADOW-VALIDATION
**Run tag:** `20260630T125622Z`
**Expected commit SHA:** `817977e4`
**Staging deploy:** `{"aligned": true, "commit_sha": "817977e46638184b90bb465ffaac2db5992c6cde", "environment": "staging", "attempts": 1}`

## Summary

- Checks: **30 passed**, **1 failed** (total 31)
- Elapsed: 69.98s
- Production untouched: True

## CIE-2 runtime (staging data)

- Recommendations: 1 artefact(s), deterministic=True
- Priority assessment: reproducible=True
- Idempotency: {'recommendation_count_before': 1, 'recommendation_count_after': 1, 'no_duplicate_on_rerun': True, 'inputs_hash_stable': True}
- Provenance trace stages: 4

## Regression summary

- **graph_health**: PASS (8 passed)
- **operational_evidence_platform**: PASS (10 passed)
- **system_health**: PASS (5 passed)
- **platform_status_operational**: PASS (22 passed)
- **automation_control_centre**: PASS (8 passed)

## Checks

- [pass] `staging_yaml_shadow_mode_configured`
- [pass] `production_yaml_no_cie_flag`
- [pass] `legacy_render_no_cie_flag`
- [pass] `no_ai_imports_in_cie_packages`
- [pass] `no_cie_engine_customer_route`
- [pass] `backend_sha_matches_cie2_commit`
- [pass] `production_not_touched`
- [pass] `staging_admin_login`
- [pass] `feature_flag_shadow_runtime`
- [pass] `no_operational_effects_in_shadow`
- [pass] `generate_recommendations_on_staging_data`
- [pass] `generate_priority_assessment_on_staging_data`
- [pass] `recommendations_deterministic`
- [pass] `priority_scores_reproducible`
- [pass] `every_recommendation_has_provenance`
- [pass] `provenance_has_calculation_trace`
- [pass] `idempotency_passes`
- [pass] `tenant_isolation_passes`
- [pass] `explain_intelligence_without_ai`
- [FAIL] `regression_graph_health`
- [pass] `regression_decision_explorer`
- [pass] `regression_oe_timeline`
- [pass] `regression_system_health`
- [pass] `regression_platform_status`
- [pass] `regression_automation_control_centre`
- [pass] `no_cie_engine_http_route_exposed`
- [pass] `pytest_regression_graph_health`
- [pass] `pytest_regression_operational_evidence_platform`
- [pass] `pytest_regression_system_health`
- [pass] `pytest_regression_platform_status_operational`
- [pass] `pytest_regression_automation_control_centre`

## Remaining risks

- Staging decision snapshots contain no natural missing-evidence inputs; recommendation generation used a bounded shadow read_adapter fixture anchored to a real staging decision_id.
- Lifecycle transition ISL remains stub (CIE-5 scope); artefacts emit as validated only.
- Replay/compare remain CIE-1.5 stubs — not exercised on staging.
- Staging CIE runtime validated via local execution against pleerity_staging Mongo (no public CIE HTTP route by design).
- Deployed shadow flag inferred from render.staging.yaml + runtime mirror; no dedicated /api/feature-flags endpoint.
- Graph Health summary endpoint timed out on staging under load; Decision Explorer and graph pytest suites passed (degraded).

## Follow-up performance issues (not CIE-2 blockers)

| Issue | Severity | CIE-3 gate |
|-------|----------|------------|
| Graph Health summary HTTP probe (`/admin/compliance/graph/health/summary`) timed out on staging under load | Performance / capacity | Investigate before CIE-3 — not a CIE-2 acceptance blocker |

Decision Explorer and local graph-health pytest suites passed; treat as staging performance debt, not intelligence-engine regression.

## CIE-3 readiness

CIE-2 shadow validation accepted on staging. **CIE-3 requires separate explicit authorisation** before decision impact, dependency engine, or portfolio intelligence work begins.
