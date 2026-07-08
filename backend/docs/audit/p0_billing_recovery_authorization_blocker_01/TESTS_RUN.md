# Tests run — P0-BILLING-RECOVERY-AUTHORIZATION-BLOCKER-01

## Backend (targeted)

```bash
cd backend
python -m pytest \
  tests/test_p0_billing_recovery_portal_authorization_01.py \
  tests/test_account_capability_enforcement_billing_client.py::TestBillingRecoveryNotBlocked \
  tests/test_billing_recovery_operations.py::test_create_upgrade_session_mode_unverified_uses_deployment_checkout \
  tests/test_step_up_sensitive_routes.py \
  -q
```

**60 passed** (2026-07-08)

## Frontend (targeted)

```bash
cd frontend
npm test -- --testPathPattern="BillingPage.capability|billingCapabilityAccess|ilp4Closeout.lifecycleJourney" --watchAll=false
```

**28 passed** (2026-07-08)

## Not run

- Full backend/frontend regression (per task scope)
- Platform-Wide Release Readiness Audit
