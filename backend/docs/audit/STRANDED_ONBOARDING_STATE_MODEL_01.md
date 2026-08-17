# Stranded onboarding — state model 01

## Identity axis (`onboarding_identity_status`)

| Value | Uniqueness | Pending Setup | History |
| --- | --- | --- | --- |
| `ACTIVE` (default / missing) | Email blocks new intake | Eligible if not `PROVISIONED` | Live attempt |
| `RELEASED_FOR_RESTART` | Not uniqueness-blocking | Excluded | Preserved; email stored on `released_canonical_email` |

At most one **active** onboarding or provisioned identity per canonical email. Multiple released historical attempts may retain the same email in `released_canonical_email`.

The unique Mongo index on `clients.email` is vacated on release by moving the live `email` to `released.{client_id}@released.invalid`. Historical evidence remains on `released_canonical_email`.

## Dropout diagnostic (assessment.diagnostic)

| Field | Meaning |
| --- | --- |
| `last_successful_stage` | Highest completed ladder step |
| `next_required_stage` | Next required step |
| `blocking_reason` | Recovery classification |
| `payment_state` / `promo_state` / `email_identity_state` / `provisioning_state` / `password_state` | Facets |
| `recommended_recovery` | Safe mode |
| `customer_entered_promo_supported` | Always `false` in this implementation |

## Classifications added

- `EMAIL_RESERVED_NO_CHECKOUT`
- `PROMO_CONTEXT_LOST`

Existing classes (`EXPIRED_CHECKOUT`, `ACTIVATION_INCOMPLETE`, …) remain.

## Pending Setup

Queue predicate: not `PROVISIONED` **and** identity not `RELEASED_FOR_RESTART`. Terminal success remains `PROVISIONED`.
