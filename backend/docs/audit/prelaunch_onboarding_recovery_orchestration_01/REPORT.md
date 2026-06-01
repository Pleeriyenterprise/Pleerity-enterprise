# PRELAUNCH-ONBOARDING-CONTINUATION-RECOVERY-ORCHESTRATION-01

**Staging verification run:** `2026-06-01T07:49:10Z`  
**API:** https://pleerity-enterprise.onrender.com/api  
**Frontend:** https://pleerityenterprise.co.uk  
**Marker:** `PRELAUNCH-ONBOARDING-RECOVERY-STAGING-VERIFY-01`

## Scenario results (API)

| Scenario | Result | Notes |
|----------|--------|-------|
| **A** | PASS | Governed `regenerate_payment` on `4009e752-74e9-4949-a971-1e25ea8678a8` (vic@yopmail.com); Stripe checkout + observability `continuation_delivered`. `resume_onboarding` returns **500** on staging until deploy of missing `execute_resume_onboarding` implementation (fixed locally). |
| **B** | PASS | `resend_activation` on `1af75ae2-1ea5-43e5-a680-1c349a307166` (johnsmith@yahoo.com, PROVISIONED / ACTIVE). |
| **C** | BLOCKED | No staging client with `pilot_invite_code` in fleet (43 admin clients + pending intake scanned). Promo preservation cannot be exercised operationally until a pilot fixture exists. |
| **D** | PASS | Second execute on post-recovery client → `RECOVERY_ALREADY_ACTIVE` / `NOT_ELIGIBLE` (duplicate blocked). |
| **E** | PASS | `regenerate_payment` on `EXPIRED_CHECKOUT` client `20bc2fec-a724-4280-860f-ced9e7f3d3fa`. |

**Summary:** 4/5 API scenarios passed; **C** blocked on data fixture, not logic regression.

## Captures

| Surface | Status | Artifact |
|---------|--------|----------|
| Admin recovery panel | Not captured (FE admin login selectors differ; API path verified) | `browser_capture.json` → `admin_control_panel_error` |
| Customer continuation email | Skipped (`send_customer_email: false` to avoid live inbox spam) | Re-run with flag on designated test client |
| Continuation landing (`/onboarding/continue`) | Blocked until `resume_onboarding` deployed | — |
| Payment continuation (Stripe) | Captured | `screenshots/payment_continuation_checkout.png` |
| Onboarding status | Captured | `screenshots/onboarding_status.png` |
| Activation continuation | API verified (B); no email send in this run | `browser_runtime.json` → scenarios.B |

Full machine evidence: `browser_runtime.json`, `browser_capture.json`.

## Defect found during verification

`execute_onboarding_recovery` called `execute_resume_onboarding` but the function was **not implemented** in `onboarding_recovery_execution_service.py`, causing staging **500** for Mode A resume. Implementation added locally; **deploy required** before resume/landing path is operable on staging.

## Manual follow-up (Scenario A end-to-end)

1. Deploy backend with `execute_resume_onboarding`.
2. Re-run governed execute with `send_customer_email: true` on a yopmail test client.
3. Complete Stripe test payment on recovery checkout URL.
4. Confirm webhook → provisioning → portal activation (`set_password`).

## Operational status

Governed recovery orchestration is **verified on staging** for payment regeneration, activation resend, duplicate guard, and expired-checkout regeneration. Promo preservation and secure continuation landing remain **pending deploy + pilot fixture**.
