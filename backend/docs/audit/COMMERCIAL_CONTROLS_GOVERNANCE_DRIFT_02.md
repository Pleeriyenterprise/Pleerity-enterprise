# Commercial Controls — Governance Drift 02

**Audit ID:** `COMMERCIAL-CONTROLS-AUTHORITY-CORRECTION-AND-E2E-CERTIFICATION-02`  
**Date:** 2026-08-15  
**Failing test (exercise 01):** `test_registry_action_ids_match_exactly_and_cannot_drift_silently`

## Classification

**Intentional governed actions**, not accidental registry drift and not obsolete test expectations.

The five extra keys in `frontend/src/config/adminActionPolicyRegistry.json` (and `routes/admin_lifecycle_operations.py`) are the Admin Lifecycle Operations Centre actions:

| Action ID | Route / panel | Risk class | Step-up |
| --- | --- | --- | --- |
| `lifecycle_ops_refresh_runtime` | `AdminLifecycleOperationsPanel` | standard_operational | no |
| `lifecycle_ops_reconcile_stripe` | same | high_impact_operational | no |
| `lifecycle_ops_resume_subscription` | same | high_impact_operational | no |
| `lifecycle_ops_mark_support_review` | same | (registry) | no |
| `lifecycle_ops_export_support_bundle` | same | (registry) | no |

These are **not** Commercial Controls actions. They do not change commercial exception authority. `commercial_entitlement_execute` remains the sole commercial execute action and still requires step-up.

## Remediation

Updated `FULL_REGISTRY_ACTIONS` in `backend/tests/test_admin_action_governance_policy.py` to include the five keys, with an explicit comment that they are intentional Lifecycle Operations actions.

The allow-list was **not** expanded silently: the registry, admin routes, and UI panel pre-existed the Commercial Controls work.

## Effect on Commercial Controls certification

Does not block commercial action authority. Must not be ignored: the governance contract test is now aligned with the intentional registry.
