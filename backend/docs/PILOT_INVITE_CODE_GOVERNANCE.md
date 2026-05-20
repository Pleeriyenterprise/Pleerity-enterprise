# Pilot invite & promo code governance

## Architecture

| Layer | Responsibility |
|-------|----------------|
| `pilot_invite_code_generation.py` | Normalize, reserved prefixes, charset-safe generation, collision retry |
| `pilot_invite_code_governance.py` | Public entry, campaign status, abuse rules, validation attempt log |
| `pilot_invite_service.py` | CRUD, campaign validation, checkout validation, Stripe wiring, redeemed snapshots, invite distribution/send rendering, usage increment after provisioning |
| `notification_orchestrator.py` | Centralized transactional email delivery for direct invite sends |
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

`used_count` increments only in `complete_redemption_after_provisioning` after successful provisioning (idempotent on `checkout_session_id`). Validation attempts and direct invite sends do **not** increment usage.

Redeemed campaign snapshots are also written from this completion path, preserving webhook/provisioning authority.

## Redemption lifecycle (recovery-aware)

Each checkout attempt is tracked in `pilot_invite_redemptions` with explicit status:

| Status | Meaning | Consumes first-time / duplicate caps? |
|--------|---------|--------------------------------------|
| `pending` | Paid checkout; awaiting provisioning | Only within retry grace window (default 72h, `PILOT_REDEMPTION_RETRY_GRACE_HOURS`) |
| `payment_started` | Optional checkout-session created | Same as pending (grace) |
| `payment_failed` | Abandoned/failed checkout | No — user may retry automatically |
| `provisioning_failed` | Provisioning exhausted | No — user may retry automatically |
| `redeemed` | Provisioned successfully (`completed` legacy alias) | **Yes** |
| `expired` | Stale incomplete past grace | No |
| `revoked` | Admin released for retry | No |

**First-time customer semantics:** `first_time_customer_only` blocks only after a **successful redeemed/provisioned** pilot promo for that email (or a client with `pilot_redeemed_campaign_snapshot_id`). Intake-only client rows, failed payments, and failed provisioning do **not** permanently block retry.

**Automatic recovery:** stale `pending` rows older than the grace window are expired during validation and lifecycle reconciliation so abandoned checkouts do not strand users.

## Eligibility overrides (account-scoped)

Overrides are stored separately in `pilot_redemption_eligibility_overrides` (not campaign mutation):

- `bypass_first_time` — allow existing customers when campaign requires first-time
- `allow_promo_retry` — bypass duplicate pending/redeemed reservation checks
- `manual_attach_promo` — auditable admin attach (paired with lifecycle override)
- `recover_onboarding` — support recovery workflows

Fields: `scope`, `scope_value`, `override_type`, `override_reason`, `override_actor`, `override_created_at`, `override_expires_at`, optional `invite_code` / `invite_code_id`, `revoked_at`.

## Abuse controls (server-side)

- First-time customer only (redeemed/provisioned definition — see above)
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
| GET | `/api/admin/pilot-invites/{code}/distribution` | Canonical `/intake/start` link plus copy/email message templates |
| POST | `/api/admin/pilot-invites/{code}/send` | Direct founding pilot invite email via `notification_orchestrator.send()` |
| GET | `/api/admin/pilot-invites/{code}/redemptions` | Redemption attempts with retry eligibility |
| GET | `/api/admin/pilot-invites/{code}/eligibility-overrides` | Active/historical eligibility overrides |
| POST | `/api/admin/pilot-invites/{code}/eligibility-overrides` | Grant controlled exception (step-up) |
| DELETE | `/api/admin/pilot-invites/eligibility-overrides/{override_id}` | Revoke override (step-up) |
| POST | `/api/admin/pilot-invites/redemptions/{redemption_id}/allow-retry` | Revoke incomplete attempt + optional retry override (step-up) |
| GET | `/api/admin/pilot-lifecycle/accounts/{client_id}/redemptions` | Client redemption history + overrides |

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
- **Manual copy/share:** use the admin detail page to copy the canonical invite link, a plain message, an email-style message, or code only. The `/intake` route is legacy; generated links must use `/intake/start`.
- **Direct send:** use the admin detail page “Send invite” action with recipient email, optional name/note, and selected plan. The backend validates the invite and plan, URL-encodes `invite` and `plan`, renders HTML plus plain-text fallback, and sends through `notification_orchestrator.send()` only using template key `PILOT_INVITE_SEND`.
- **CTA email behavior:** direct-send emails include the commercial summary from `pilot_commercial_truth.py`, onboarding-waived wording when applicable, invite code, the CTA button text “Start your founding pilot access”, and a raw fallback link.
- **Send audit:** each direct-send attempt is recorded in `pilot_invite_send_attempts` with invite code, recipient, selected plan, actor, status, provider message ID, and failure reason when present. Send audit records are operational logs only and never reserve or consume usage.
- **Launch campaign:** generate human-readable code, enable public entry, pause via `campaign_state=paused`
- **Account extension:** extend the account in pilot operations; do not change campaign duration
- **Stranded onboarding recovery:** review invite redemptions (`pending` / `provisioning_failed`), use **Allow retry** to revoke incomplete attempts; grant `bypass_first_time` or `allow_promo_retry` overrides for goodwill/support cases
- **Internal test:** use `internal_test`; distribute only controlled links; monitor under `analytics_family=internal_test`
- **Retire:** disable or archive (`archived=true` sets `campaign_state=archived`)
