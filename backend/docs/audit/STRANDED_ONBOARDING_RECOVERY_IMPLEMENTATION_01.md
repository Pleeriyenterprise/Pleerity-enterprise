# Stranded onboarding — implementation 01

## Surfaces

- Assessment: `GET /api/admin/clients/{id}/onboarding-recovery/assessment` now includes `diagnostic` and `promo_recovery`.
- Execute: `POST …/onboarding-recovery/execute` modes: `regenerate_payment`, `resume_onboarding`, `resend_activation`, **`release_and_restart`**.
- Approved promos: `GET …/onboarding-recovery/approved-promos`.
- Intake: `check-email` / `submit` use uniqueness that ignores released identities; new clients may set `restarted_from_client_id`.

## Release guards (reject)

Paid/active subscription, provisioned onboarding, portal password set, non-terminal Stripe subscription, already released.

## Checkout regenerate

Expires previous Stripe Checkout Session before creating the replacement. Promo is server-applied only.

## Files (primary)

- `backend/utils/client_email.py`
- `backend/services/onboarding_recovery_service.py`
- `backend/services/onboarding_recovery_execution_service.py`
- `backend/routes/admin_onboarding_recovery.py`
- `backend/routes/admin.py` (pending_setup filter)
- `backend/routes/intake.py`
- `frontend/src/components/admin/pilot/OnboardingRecoveryAssessmentPanel.jsx`
- `frontend/src/components/admin/pilot/OnboardingRecoveryExecuteDialog.jsx`
