# Pilot invite & promo code governance

## Architecture

| Layer | Responsibility |
|-------|----------------|
| `pilot_invite_code_generation.py` | Normalize, reserved prefixes, charset-safe generation, collision retry |
| `pilot_invite_code_governance.py` | Public entry, campaign status, abuse rules, validation attempt log |
| `pilot_invite_service.py` | CRUD, campaign validation, checkout validation, Stripe wiring, redeemed snapshots, usage increment after provisioning |
| `pilot_lifecycle_service.py` | Account-level lifecycle overrides and reconciliation projection |
| `pilot_commercial_truth.py` | Offer copy and pricing overlay (billing truth separate from Stripe coupon) |

**Rule:** The frontend never allocates final codes. Use `POST /api/admin/pilot-invites/generate` or create with `auto_generate: true`.

## Campaign/account separation

Campaign truth, redeemed truth, and account override truth are separate:

- **Campaign configuration:** stored on `pilot_invite_codes`. This controls future redemptions only.
- **Redeemed campaign snapshot:** stored in `pilot_redeemed_campaign_snapshots` and mirrored on the client after completed provisioning. It captures code, code type, campaign version, discount, onboarding policy, allowed plan, Stripe coupon/promotion IDs, analytics family, launch visibility, and timestamps.
- **Account overrides:** stored in `pilot_account_overrides` and projected onto client lifecycle fields for compatibility. Extensions, expiry overrides, comps, pauses, resumes, and onboarding overrides do not mutate campaign defaults.

Already-redeemed accounts must not silently change when an admin edits a campaign. If mutable commercial campaign fields change after completed redemptions, `campaign_config_version` is advanced and the mutation is marked `future_redemptions_only`.

## Code types

| Type | Generation style | Public manual entry |
|------|------------------|---------------------|
| `private_invite` | `PREFIX-XXXX` secure suffix | No (link / optional manual if configured) |
| `public_promo` | `CAMPAIGNYYYY` or slug + suffix | Yes when `public_entry_enabled` + `is_publicly_enterable` |
| `referral` | `REF-NAME-XXX` | Campaign-governed |
| `partner` | `PARTNER-ORG-XXX` | Campaign-governed |
| `internal_test` | `PILOTINT-SLUG-XXXX` | Never public; controlled link only |

Private invite codes remain manually redeemable if legitimately known, but they are not public-discoverable or public-listed.

## Campaign governance fields

Campaign records support:

- `campaign_state`: `draft`, `active`, `paused`, `expired`, `archived`
- `launch_visibility`: `private`, `restricted`, `public`, `internal`
- `campaign_config_version`, `campaign_locked_at`, `campaign_launched_at`
- `analytics_family`
- `max_uses_per_account`
- `internal_live_test`
- `is_publicly_enterable`, `public_entry_enabled`

`campaign_status` remains for compatibility and is derived from/kept aligned with `campaign_state`.

## Internal live/test strategy

`internal_test` is allowed in both Stripe test and live modes. Backend restrictions are enforced before persistence and validation:

- `max_uses` defaults to `5`
- `max_uses` is hard-capped at `10`
- onboarding is always waived
- `public_entry_enabled=false`
- `is_publicly_enterable=false`
- `launch_visibility=internal`
- `analytics_family=internal_test`

Internal-test redemptions are excluded from public launch analytics and require controlled link entry.

## Normalization

- Uppercase, trim, collapse invalid characters to `-`
- Charset for generated suffixes: `ABCDEFGHJKLMNPQRSTUVWXYZ` + `23456789` (no O/0/I/1)
- Reserved prefixes (manual codes rejected): `ADMIN`, `SYSTEM`, `STRIPE`, `TEST`, `INTERNAL`, `ROOT`

## Usage accounting

`used_count` increments only in `complete_redemption_after_provisioning` after successful provisioning (idempotent on `checkout_session_id`). Validation attempts do **not** increment usage.

Redeemed campaign snapshots are also written from this completion path, preserving webhook/provisioning authority.

## Abuse controls (server-side)

- First-time customer only
- Per-email / per-customer / per-payment-method redemption caps
- Optional `max_uses_per_account`
- Daily redemption cap (`max_uses_per_day`)
- Allowed / blocked email domains
- Validation attempts logged to `pilot_invite_validation_attempts`
- Audit actions: `PILOT_INVITE_CODE_VALIDATED`, `PILOT_INVITE_CODE_VALIDATION_FAILED`, `PILOT_INVITE_ABUSE_BLOCKED`, `PILOT_INVITE_REDEMPTION_COMPLETED`

## Admin API

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/admin/pilot-invites/generate` | Authoritative unique code |
| POST | `/api/admin/pilot-invites` | Create (`auto_generate` optional) |
| POST | `/api/admin/pilot-invites/{code}/duplicate` | Clone campaign config + new code |
| POST | `/api/admin/pilot-invites/{code}/regenerate` | New code if zero usage |
| GET | `/api/admin/pilot-invites/{code}/metrics` | Operational metrics |
| GET | `/api/admin/pilot-invites/{code}/validation-attempts` | Failed/success validations |

## Validation-before-persistence

Invite/campaign updates build a complete candidate configuration and validate it before writing:

- Stripe coupon/promotion alignment
- campaign governance rules
- onboarding policy rules
- internal-test restrictions
- discount shape

No invite update should persist if any of those validations fail.

## Public promo readiness checklist

1. Create code type `public_promo` with Stripe coupon aligned in Dashboard  
2. Set `campaign_state=active`, `launch_visibility=public`, `public_entry_enabled=true`, `is_publicly_enterable=true`  
3. Configure abuse flags (`one_redemption_per_email`, etc.)  
4. Verify intake “Have a code?” flow and commercial truth overlay  
5. Monitor metrics endpoint before broad launch  

## Operational workflows

- **Private founding pilot:** distribute invite URL (`/intake/start?invite=CODE&plan=...`); private codes may validate manually if known and restrictions pass
- **Launch campaign:** generate human-readable code, enable public entry, pause via `campaign_state=paused`
- **Account extension:** extend the account in pilot operations; do not change campaign duration
- **Internal test:** use `internal_test`; distribute only controlled links; monitor under `analytics_family=internal_test`
- **Retire:** disable or archive (`archived=true` sets `campaign_state=archived`)
