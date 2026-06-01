# PRELAUNCH-ONBOARDING-CONTINUATION-RECOVERY-ORCHESTRATION-01

**Latest staging verification:** `2026-06-01T08:25:34Z` (post-deploy `b97f00b2`)  
**API:** https://pleerity-enterprise.onrender.com/api  
**Frontend:** https://pleerityenterprise.co.uk

## Scenario results (API)

| Scenario | Result | Notes |
|----------|--------|-------|
| **A** | PASS | Governed payment recovery checkout (`regenerate_payment` on elena@yopmail.com). `resume_onboarding` verified separately post-deploy on `805caa60-…` → `200` with `/onboarding/continue?token=…`. |
| **B** | PASS | `resend_activation` on provisioned ACTIVE client without password. |
| **C** | BLOCKED | No staging client with `pilot_invite_code` in fleet. |
| **D** | PASS | Duplicate execute blocked (`RECOVERY_ALREADY_ACTIVE` / `NOT_ELIGIBLE`). |
| **E** | PASS | Expired checkout regeneration. |

**Summary:** 4/5 API scenarios passed; **C** requires pilot fixture.

## Deploy / defect closeout

- **Commit:** `b97f00b2` — implements missing `execute_resume_onboarding` (fixed staging 500).
- **Post-deploy probe:** `resume_onboarding` → `200`, continuation URL on `pleerityenterprise.co.uk/onboarding/continue`.

## Captures

| Surface | Status | Artifact |
|---------|--------|----------|
| Payment continuation (Stripe) | Captured | `screenshots/payment_continuation_checkout.png` |
| Onboarding status | Captured | `screenshots/onboarding_status.png` |
| Continuation landing | Deploy verified via API; re-capture on next run with `resume_onboarding` as first mode | — |
| Admin recovery panel | Not captured (FE login selectors) | API path verified |
| Customer email (`--send-email`) | Attempted on yopmail; blocked `BLOCKED_PROVISIONING_INCOMPLETE` for test client | See `browser_runtime.json` scenario A |

Evidence: `browser_runtime.json`, `browser_capture.json`.

## Remaining for full operational sign-off

1. Seed staging client with `pilot_invite_code` for scenario **C**.
2. Re-run `python scripts/staging_onboarding_recovery_verify.py --browser` after picking a PAYMENT_ABANDONED yopmail client eligible for email send.
3. Manual Stripe payment + activation on recovery checkout (scenario A end-to-end).
