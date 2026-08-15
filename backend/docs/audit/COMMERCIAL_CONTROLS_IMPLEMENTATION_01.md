# Commercial Controls — Implementation

**Audit ID:** `COMMERCIAL-CONTROLS-END-TO-END-REMEDIATION-01`  
**Document:** `COMMERCIAL_CONTROLS_IMPLEMENTATION_01.md`  
**Date:** 2026-08-15

## Scope of change

Smallest authoritative fixes for the proven spinner hang and adjacent execution-safety defects. No Stripe `pause_collection`. No change to which lifecycle states may execute which actions.

## 1. Indefinite spinner (authoritative UI fix)

`CommercialEntitlementControls` now mounts `{stepUp.modal}` in `data-testid="commercial-step-up-modal-host"`.

Lifecycle after fix:

```text
IDLE → SUBMITTING
  → 403 STEP_UP_REQUIRED
  → password modal (z-index 220)
  → retry with X-Step-Up-Token + new confirmation token
  → SUCCESS (close modal, toast, reload assessment + parent billing panel)
  or ERROR (spinner stops, fields preserved, retry allowed)
```

Also:

- Execute POST `timeout: 60000` (axios)
- Dialog ignores overlay-close while submitting
- Double-submit ignored while `loading`
- Timeout/abort surfaces a message that **does not assume success**
- Parent `loadPanel({ silent: true })` refreshes billing fields without unmounting the page

## 2. Duration caps

Frontend `ACTION_DURATION_MAX_DAYS` matches backend `_MAX_DURATION_DAYS`. Invalid duration is rejected in the form before submit.

## 3. Persistence / concurrency

- Unique partial index `uniq_client_active_commercial_governance`
- `DuplicateKeyError` → `ACTIVE_EXCEPTION_EXISTS`
- Failed attempts record `commercial_rejected` (no success governance row)

## 4. Side-effect isolation

After the governance row is committed:

- Continuity email runs with 25s timeout; failure sets `customer_notification_status=failed` and does **not** roll back the exception
- Stripe reconciliation runs with 20s timeout; failure is returned as `RECONCILIATION_FAILED` without undoing the exception
- Frontend warns if email was requested but not confirmed sent

Notification policy used: **success-with-notification-warning** (existing orchestrator; no parallel mailer).

## 5. Email idempotency

Idempotency key is `commercial_entitlement_{client_id}_{governance_id}_{action}` so retries of the same exception do not mint a new UUID per attempt.

Checkbox `send_customer_email=false` still skips send (`customer_notification_status=skipped` at insert).

## 6. Waive onboarding fee

Execute now sets the existing `onboarding_fee_waived` / `onboarding_fee_policy` fields used by checkout (`stripe_service` + `pilot_onboarding_fee`). Idempotent `$set`. Expiry of the commercial row does **not** clear the waiver (onboarding waiver is permanent in the existing fee authority). Recurring subscription prices are not waived.

## 7. Operator copy

Suspend/sponsor operator `billing_impact` now states platform pause + Stripe not mutated in v1.

Cancelled-account `lifecycle_action_warnings` are returned on assessment and shown in the modal.

## 8. What was not changed (authority)

| Topic | Decision |
| --- | --- |
| Stripe `pause_collection` | Not added. Requires commercial/billing contract decision. |
| Blocking Suspend billing on `CANCELLED` | Not blocked. Warnings only. |
| Restoring `ENABLED` from `CANCELLED` via exception | Still not restored (existing `derive_customer_access_state`). |
| Recovery compensation as Stripe credit / account credit | Still a time-bound `RECOVERY_CONTINUITY` exception only. |
| Deploy / merge to `main` | Not done. |

## Files

- `frontend/src/components/admin/commercial/CommercialEntitlementControls.jsx`
- `frontend/src/components/admin/commercial/CommercialEntitlementExecuteDialog.jsx`
- `frontend/src/utils/commercialEntitlementAdmin.js`
- `frontend/src/pages/AdminClientControlPanelPage.js`
- `frontend/src/components/admin/commercial/CommercialEntitlementControls.test.js`
- `backend/services/commercial_entitlement_execution_service.py`
- `backend/services/commercial_entitlement_service.py`
- `backend/services/commercial_entitlement_notification_service.py`
- `backend/services/commercial_entitlement_observability_service.py`
- `backend/routes/admin_commercial_entitlement.py`
- `backend/database.py`
- `backend/models/core.py`
- `backend/tests/test_commercial_entitlement_governance.py`
- `backend/scripts/commercial_controls_e2e_certification_01.py`

## Tests run locally

- `pytest tests/test_commercial_entitlement_governance.py` — passed (expiry integration skipped without Mongo)
- `craco test CommercialEntitlementControls.test.js` — 5 passed

`test_admin_action_governance_policy.py` has a **pre-existing** registry drift failure (`lifecycle_ops_*` actions). Not introduced by this change.

## Deploy / soak

No Render deploy. Mongo operational soak remains valid for this exercise. A later backend deploy **will** require recording a new soak start if that soak’s rules treat scheduler restart as a break.
