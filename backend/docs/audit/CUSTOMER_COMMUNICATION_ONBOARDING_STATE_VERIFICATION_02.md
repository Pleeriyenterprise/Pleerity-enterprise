# Onboarding state verification 02

## Design

Day 0–7 sequence was **not** redesigned. Existing `check_onboarding_state` signals (`has_added_property`, `has_uploaded_certificate`, `monitoring_enabled`) plus `jurisdiction_label` / `jurisdiction_known` are passed into send context.

Subjects and CTAs adapt:

| Event | No property | Property already added |
| --- | --- | --- |
| Day 0 | “Add your first property…” | “Continue setting up…” / CTA “View your properties” |
| Day 1 | “Complete your setup” | “Review your property in Compliance Vault Pro” |
| Day 7 | “Activate monitoring” | Recap / dashboard if monitoring already on |

Day 1 body: England may still list CP12/EICR/EPC. Scotland or unknown uses neutral “safety certificates, registrations and records that apply to your property”. No second rules engine.

Monitoring still **cancels remaining** queue rows (pre-existing).

## Live staging

`onboarding_sequence_processing` was run **portfolio-wide** only after confirming the due queue contained **one yopmail row** (`elena@yopmail.com`, Day 1) and **zero non-test recipients**.

| Field | Value |
| --- | --- |
| template_key | `ONBOARDING_DAY1_SETUP_REMINDER` |
| message_id | `e1a9824b-d757-4bcd-b28d-4d22f8f68f6a` |
| idempotency_key | `ONBOARDING_ONBOARDING_DAY1_SETUP_REMINDER_b8705b33-…` |
| provider | `637c2ee4-4f05-46cd-a472-7c4371dad832` |
| status | **DELIVERED** |
| subject | Review your property in Compliance Vault Pro |

Elena has properties (8 upcoming requirements). Subject/CTA did **not** say “Add your first property” or “Continue setup” as if nothing existed.

A prior Day 0 for Elena (2026-08-17, pre-remediation) still shows the old subject in history; that is not this SHA.
