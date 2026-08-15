# Commercial Controls — Root Cause

**Audit ID:** `COMMERCIAL-CONTROLS-END-TO-END-REMEDIATION-01`  
**Document:** `COMMERCIAL_CONTROLS_ROOT_CAUSE_01.md`  
**Date:** 2026-08-15  
**Branch:** `develop` (not merged to `main`; not deployed this exercise)

## Observed defect

Commercial Control modals open, accept valid input, and enter a submit spinner that never terminates. The operator never receives success, error, or refreshed commercial state.

The captured case was **Suspend billing** on an account whose displayed commercial state was:

| Surface | Value |
| --- | --- |
| Governance state | `TERMINATION_PENDING` |
| Canonical access | `CANCELLED` |
| Access policy | `full_access` |
| Last webhook | `customer.subscription.deleted` |
| Billing sync | `ok` / Stripe summary `Up to date` |

All seven action buttons were available despite cancelled canonical access.

## Where execution stopped

The submit spinner is `CommercialEntitlementExecuteDialog.loading`. It stays true until `onSubmit` (`handleExecute`) settles.

`handleExecute` does:

1. `stepUp.request(fn)` — first call has **no** `X-Step-Up-Token`
2. `runGovernedAdminMutation` issues `X-Admin-Confirmation-Token`
3. `POST /api/admin/clients/{id}/commercial-entitlement/execute`
4. Backend `enforce_governed_admin_action` consumes the confirmation token, then `require_recent_step_up`
5. Missing step-up returns **403** `{ error_code: "STEP_UP_REQUIRED" }`
6. `useStepUpApi.request` catches that 403 and returns a **Promise that waits for the password modal**
7. `CommercialEntitlementControls` **never rendered `stepUp.modal`**

Classification: **frontend promise never resolving** because the step-up UI was not mounted.

This is not:

- a request that was never dispatched (the execute POST is sent)
- a backend deadlock
- a Stripe hang (execute does not call Stripe)
- a missing endpoint

Sibling panels (`OnboardingRecoveryAssessmentPanel`, `AdminLifecycleOperationsPanel`) already render `{stepUp.modal}`. Commercial Controls omitted that host.

Secondary contributors (would matter after the modal is shown):

| Item | Effect |
| --- | --- |
| Axios has no default timeout | A later hung execute would also spin forever |
| Parent `loadPanel()` sets `loading=true` | Whole control panel unmounts on refresh |
| UI duration `max=90` vs grace max 30 | Over-max grace would 400 after step-up, not hang |
| Email/recon after persist | Could delay response; now isolated with timeouts in code |

## Architecture inventory (Phase 1)

| Layer | Location |
| --- | --- |
| Frontend components | `frontend/src/components/admin/commercial/CommercialEntitlementControls.jsx` mounted from `AdminClientControlPanelPage.js` (billing tab) |
| Modal | `CommercialEntitlementExecuteDialog.jsx` |
| Submit handler | `handleExecute` → `useStepUpApi` → `runGovernedAdminMutation` |
| API client | `adminAPI.executeCommercialEntitlement` → `POST /admin/clients/{id}/commercial-entitlement/execute` |
| Routes | `backend/routes/admin_commercial_entitlement.py` |
| Request schema | `CommercialEntitlementExecuteBody` (reason min 10, duration 1–365 at schema; authority caps tighter) |
| Service | `apply_governed_entitlement_action` |
| Authority | `validate_entitlement_authority`, `validate_transition`, `derive_customer_access_state` |
| State machine | `commercial_entitlement_service.py` governance states + `_derive_executable_actions` |
| MongoDB | `commercial_entitlement_governance`, `_audit`, `_metrics`; client/billing canonical fields |
| Stripe | `reconcile_entitlement_billing_state` — **no Stripe mutation in v1** |
| Email | `send_commercial_continuity_email` via `notification_orchestrator` (`ADMIN_MANUAL`, event `commercial_entitlement_continuity`) |
| Audit | `commercial_entitlement_audit` + `create_audit_log` |
| Expiry job | `commercial_entitlement_expiry` daily 04:10 UTC (`process_commercial_entitlement_expiry`) |
| Feature flags | none |
| Idempotency | application `prevent_duplicate_active_exception`; unique partial index added in this remediation (not yet live) |
| RBAC | `admin_route_guard` + `require_owner_or_admin`; policy `commercial_entitlement_execute` requires reason, confirmation, step-up |

## Control matrix (as implemented)

| Control | Frontend handler | API endpoint | Service | State mutation | Stripe effect | Email | Expiry/recovery | Audit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Grant grace period | `handleExecute` / `grant_grace_period` | `POST .../execute` | `apply_governed_entitlement_action` | `GRACE_PERIOD` + `grace_extension` row | `NO_STRIPE_ACTION` (lightweight recon) | Optional continuity if checkbox | `entitlement_expiry_at`; daily expiry job | `commercial_granted` |
| Suspend billing | `suspend_billing` | same | same | `BILLING_SUSPENDED` + `billing_suspension` | **Not** `pause_collection` | Optional | duration 1–90d; expiry job | same |
| Sponsored access | `grant_sponsored_access` | same | same | `SPONSORED_ACCESS`; review required | `NO_STRIPE_ACTION` | Optional | expiry + review_at | same |
| Retention extension | `retention_extension` | same | same | `RETENTION_EXTENSION` | `NO_STRIPE_ACTION` | Optional | 1–30d | same |
| Waive onboarding fee | `waive_onboarding_fee` | same | same + `onboarding_fee_waived` flags (this fix) | `WAIVED` | checkout skips setup fee via existing flags; no invoice rewrite | Optional | exception expires; **waiver flags remain** | same |
| Recovery compensation | `apply_recovery_compensation` | same | same | `RECOVERY_CONTINUITY` (time-bound access, **not** a Stripe credit) | `NO_STRIPE_ACTION` | Optional | 1–30d | same |
| Restrict entitlement | `restrict_entitlement` | same | same | `RESTRICTED` / `suspended` access policy; canonical `SUSPENDED` | `NO_STRIPE_ACTION` | Optional | 1–30d | same |

Revoke/resume (`resume_billing`, `revoke_commercial_exception`) appear only while an exception is active.

## One-active-exception invariant

UI copy: “one active exception per account”.

Before this remediation:

- Enforced in `validate_transition` / `prevent_duplicate_active_exception`
- Index was `(client_id, status)` **non-unique**
- Concurrent dual-submit could race two `active` rows

This remediation adds unique partial index `uniq_client_active_commercial_governance` on `client_id` where `status=active`, and maps `DuplicateKeyError` to `ACTIVE_EXCEPTION_EXISTS`. **Not live until backend deploy.**

## Lifecycle legality (not silently redesigned)

`_derive_executable_actions` returns all seven actions whenever there is **no** active governance, including `CANCELLED` / `TERMINATION_PENDING`.

`derive_customer_access_state` **does not restore** `ENABLED` when baseline canonical is `CANCELLED`. So Suspend billing / grace on the observed account would record an exception but leave access `CANCELLED`.

This is existing v1 authority. Restricting which actions are legal from `CANCELLED` would change commercial policy. Operator warnings were added (`lifecycle_action_warnings`); buttons were **not** removed.

## Stripe / billing truth

`billing_collection_paused` is a preview flag only. No billing job or Stripe call consumes it. v1 comments explicitly forbid `pause_collection`.

Operator `billing_impact` previously said “Billing collection paused.” while Stripe could still collect on a live subscription. Copy was corrected in code to state that Stripe is not mutated in v1.

Customer continuity copy still says billing is paused. Changing that promise, or adding Stripe pause, is a **commercial authority decision**.

## Staging runtime this exercise

Admin login to staging returned **423 Locked**. No live execute/email/Stripe object capture was completed in this run. Prior Phase 2C closeout (2026-06-01) proved API execute + expiry on staging Mongo for a different programme.

## Soak interaction

No backend or frontend deploy was performed. The MongoDB operational soak was **not** reset by this change set.
