# Phase 2C — Commercial Entitlement Governance

## Status
**IMPLEMENTED_PENDING_OPERATIONAL_VERIFICATION**

Backend services, admin API, Commercial Controls UI, regression tests, and expiry job hook are in place. Staging browser proof (scenarios A–F) is required before `VERIFIED_OPERATIONALLY`.

## Delivered components

| Part | Artifact |
|------|----------|
| 1 | `services/commercial_entitlement_service.py` |
| 5 | `services/commercial_entitlement_execution_service.py` |
| 6 | `services/commercial_entitlement_stripe_convergence_service.py` |
| 7 | `services/commercial_entitlement_notification_service.py` |
| 8 | `routes/admin_commercial_entitlement.py` + `CommercialEntitlementControls.jsx` |
| 10 | `services/commercial_entitlement_expiry_service.py` + `commercial_entitlement_expiry` job |
| 11 | `services/commercial_entitlement_observability_service.py` |
| 12 | `tests/test_commercial_entitlement_governance.py` |

## Governance rules enforced in code

1. `derive_customer_access_state()` is the sole bridge from commercial governance to canonical access bands.
2. Stripe reconciliation is lightweight (`reconcile_stripe_vs_platform_state`, no aggressive subscription mutation).
3. One active row per client (`prevent_duplicate_active_exception`).
4. `access_policy` preserves compliance/evidence continuity on billing suspension.
5. Sponsored access requires sponsor reference + duration/expiry; review flagged on expiry job.
6. `derive_customer_impact_preview()` mandatory before execute (API + admin dialog).

## Next steps

1. Deploy backend + frontend to staging.
2. `python scripts/staging_commercial_entitlement_verify.py --client-id <id> --write-audit`
3. Exercise Commercial Controls on `/admin/clients/{id}` (Billing tab).
4. Update `browser_runtime.json` and set `classifications.json` to `VERIFIED_OPERATIONALLY` when proof is complete.
