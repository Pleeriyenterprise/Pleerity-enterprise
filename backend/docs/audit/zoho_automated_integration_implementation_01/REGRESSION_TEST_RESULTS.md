# Zoho Integration Hardening — Regression Test Results

**Programme:** ZOHO INTEGRATION REFINEMENT  
**Date:** 2026-07-09  
**Verdict:** **PASS** (scoped regression + targeted observability suite)

---

## Test execution

### Zoho + governance (required)

```bash
cd backend && python -m pytest tests/integrations/zoho/ tests/test_control_centre_outcome_family_governance.py -q
```

| Result | Count |
|--------|-------|
| **Passed** | 31 |
| Failed | 0 |

**Evidence:** H-01 governance alignment verified — `REGISTRY_JOB_OUTCOME_FAMILY` includes all four Zoho jobs.

### Observability + control centre (targeted regression)

```bash
cd backend && python -m pytest \
  tests/integrations/zoho/ \
  tests/test_control_centre_outcome_family_governance.py \
  tests/test_control_centre_outcome_aggregation.py \
  tests/test_control_centre_no_expected_outcome_flag.py \
  tests/test_execution_jobs_outcome_metrics_control_centre.py \
  tests/test_compliance_recalc_queue_stabilization_phase1.py \
  -q
```

| Result | Count |
|--------|-------|
| **Passed** | 69 |
| Failed | 0 |

---

## New test coverage

| Test | Validates |
|------|-----------|
| `test_integration_layer_version_on_status_snapshot` | H-02 |
| `test_analytics_export_metrics_include_total_leads_and_payload_version` | H-03 |
| `test_build_analytics_export_includes_payload_version` | H-03 runtime |
| `test_sync_run_versions_block` | Version metadata |
| `test_sync_store_create_run_includes_versions` | Sync run persistence |
| `test_operational_snapshot_dormant_when_disabled` | Dormant posture |
| `test_health_summary_includes_zoho_integration_health` | System Health integration |

---

## Full suite notes

Full `pytest tests/` was attempted. Pre-existing collection/run blockers **unrelated to this change**:

| Issue | File |
|-------|------|
| Missing module | `tests/test_discovery_staging_e2e_validation.py` → `tests.discovery_staging_harness` |
| Unrelated failure | `tests/test_account_capability_enforcement_backend_completion.py` (guard count assertion) |

No regressions identified in Zoho, control centre governance, or observability test paths.

---

## Manual verification checklist (post-deploy)

| Check | Expected when flags off |
|-------|-------------------------|
| `GET /api/admin/observability/health-summary` | `integrations.zoho.overall_status` = `dormant` |
| `GET /api/admin/control-centre/snapshot` | `system.integrations.zoho.overall_status` = `dormant` |
| `GET /api/admin/integrations/zoho/status` | **404** (flag off) |
| Platform `overall_health` | Unchanged vs pre-change when Zoho dormant |

---

## Constraints confirmed

- [x] No Zoho flags enabled
- [x] No OAuth credentials configured
- [x] No staging/production env changes
- [x] No cron wiring
- [x] No breaking API changes (additive JSON fields only)
