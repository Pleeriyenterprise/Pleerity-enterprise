# Watchlist — PRELAUNCH onboarding recovery closeout

**Classification:** `VERIFIED_OPERATIONALLY`

## Post-closeout (ops, non-blocking)

- Complete manual Stripe payment on a yopmail recovery checkout to prove paid → webhook → provisioning → portal activation on staging.
- Optional: dedicated `ONBOARDING_RECOVERY_EMAIL` notification template (`requires_provisioned: false`) to avoid reliance on `ADMIN_MANUAL` + event_type bypass.
- Branded recovery email template (currently `ADMIN_MANUAL` HTML body from recovery notification service).

## Verified (no action)

- Governed execute (step-up + confirmation + reason)
- Pre-provisioning recovery email delivery
- Secure continuation landing
- Promo preservation via invite code / eligibility override
- Duplicate recovery guard
