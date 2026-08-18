# Stranded onboarding — root cause 01

**Programme:** `STRANDED-ONBOARDING-RECOVERY-AND-PROMO-CONTINUITY-01`  
**Branch:** `develop` only. Production not modified.

## What was already true

A governed recovery engine already existed (`onboarding_recovery_service` / `execute`). Admin CCP already diagnosed `EXPIRED_CHECKOUT` and could generate a Stripe Checkout Session. June closeout (`prelaunch_onboarding_recovery_orchestration_01`) verified checkout regenerate, promo preserve, and duplicate **block**.

## Why pending setup was still not recoverable

1. **Email uniqueness treated every `clients` row as live.** `client_email_taken()` did not distinguish a stranded unpaid attempt from a provisioned account. Incomplete signups reserved the address forever.
2. **No release/restart action.** Resume is explicitly not a restart. There was no governed way to free the reservation without deleting the customer.
3. **Dropout was not a stage ladder.** Operators saw `INTAKE_PENDING` and had to reconstruct checkout/promo/password from raw fields.
4. **Prior Checkout Sessions were not expired** on regenerate (`prior_session_id` stored only).
5. **Promo choice was a default-true checkbox**, not preserve-vs-paid vs select-approved-promo.
6. **Pending Setup** was `onboarding_status ≠ PROVISIONED`, so released/historical attempts would have stayed in the queue if we had only marked a flag without excluding it.

## What this change does

Extends the existing engine. Does not delete users. Does not enable customer-entered Stripe promotion codes. Does not weaken duplicate-email rules for active identities.
