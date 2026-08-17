# Stranded onboarding — promo continuity 01

**Policy:** Scenario C is **not supported**. Recovery checkout never sets `allow_promotion_codes`.

## Source of truth

Pilot invite documents (`pilot_invite_service`) plus eligibility overrides (`manual_attach_promo` / `allow_promo_retry`). Stripe mapping remains coupon / promotion_code IDs on the invite (`stripe_session_discounts`).

## Admin recovery choices

If a validated invite is already on the attempt:

- Apply existing promo → Checkout `discounts` from that invite.
- Generate normal paid checkout → no discount.

If none exists:

- No promo.
- Yes — select from **active approved** invite codes (`list_invite_codes` status `active`, remaining uses > 0). Reason still required by governance.

Do not grant a promo because the customer claims they had one. Do not accept a free-typed discount.
