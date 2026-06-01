# STRIPE-ENVIRONMENT-CONVERGENCE-AUDIT-01

**Classification:** `STRIPE_ENVIRONMENT_GOVERNANCE_GAP`  
**Incident mechanism:** `MIXED_MODE_DATA_DRIFT`  
**Severity:** High  
**Hotfix safe:** No (without per-client data audit)  
**Full convergence repair:** Required  

---

## 1. Root cause

The upgrade/downgrade error:

> `No such subscription: 'sub_…'; a similar object exists in test mode, but a live mode key was used`

occurs because **Stripe mode is deployment-global**, while **subscription references are persisted without mode metadata**.

At runtime:

1. `STRIPE_MODE` (or legacy key inference) sets **one** global `stripe.api_key` via `configure_stripe_sdk()` in `stripe_mode_authority.py`.
2. `client_billing.stripe_subscription_id` is read and passed to `stripe.Subscription.retrieve()` with **no check** that the ID belongs to the active mode.
3. The deployment is using a **live** secret (`sk_live_*` / `STRIPE_MODE=live`), but the stored subscription was created under **test** Stripe (checkout/webhook when `STRIPE_MODE=test` or legacy `sk_test_*`).

This is **not** a single missing env var in isolation — governance docs exist (`STRIPE_MODE_GOVERNANCE.md`), but **entity-level mode is not authoritative** across Mongo persistence and several code paths still bypass mode authority.

---

## 2. Affected services and routes

### Upgrade/downgrade (failing path)

| Layer | Location |
|-------|----------|
| Frontend | `frontend/src/pages/BillingPage.js` → `POST /api/billing/checkout` with `plan_code` |
| Route | `backend/routes/billing.py` → `create_checkout()` |
| Service | `backend/services/stripe_service.py` → `create_upgrade_session()` |
| Stripe call | `stripe.Subscription.retrieve(stripe_subscription_id)` then `stripe.billing_portal.Session.create(..., flow_data=subscription_update_confirm)` |
| Error surface | `ValueError("Failed to create upgrade session: …")` (step-up password modal) |

`create_upgrade_session()` uses `_get_stripe_mode()` for **price** resolution only; it does **not** validate that `stripe_subscription_id` matches that mode before retrieve.

### Other billing / Stripe surfaces (convergence risk)

| Area | File(s) | Mode handling |
|------|---------|----------------|
| New checkout | `stripe_service.create_checkout_session` | `configure_stripe_sdk()` + `get_stripe_price_mappings(mode)` ✓ |
| Billing portal (client) | `routes/billing.py` `POST /portal` | **Legacy** `STRIPE_SECRET_KEY` / `STRIPE_API_KEY` only — bypasses authority |
| Subscription status / sync | `stripe_service.get_subscription_status`, `billing_stripe_sync_service.retrieve_stripe_subscription_dict` | Mixed: service uses authority at import; sync retrieve uses **legacy key fallback** |
| Webhooks | `stripe_webhook_service.py` | `resolve_webhook_secret()` + `assert_stripe_object_mode(livemode)` ✓ inbound only |
| Webhook persistence | `stripe_events` | Stores `event_id`, `type`, status — **no `livemode` / `stripe_mode` column** |
| Onboarding recovery checkout | `onboarding_recovery_execution_service.py` → `create_checkout_session` | Uses authority path ✓; persisted client rows still mode-blind |
| Onboarding continuation | `onboarding_continuation_service.py` | Same |
| Intake draft checkout | `intake_draft_service.py` | **Legacy** `stripe.api_key = STRIPE_SECRET_KEY` |
| Admin billing | `routes/admin_billing.py` | `configure_stripe_sdk()` at import; some flows use Stripe API |
| Renewal jobs | `services/jobs.py` | Sets `stripe.api_key` from raw env |
| Order receipts | `order_receipt_service.py` | Legacy key |
| Clearform product | `clearform/routes/*.py` | `STRIPE_API_KEY` |
| Commercial entitlement | `commercial_entitlement_stripe_convergence_service.py` | Platform-only reconcile; **does not** call Stripe or validate sub mode |
| Pilot invites | `pilot_invite_service.py` | Sets `stripe_environment` on **invite** records only |
| Startup | `server.py` → `log_startup_stripe_health()` | Logs mode + price IDs ✓ |

---

## 3. Stripe client resolution (audit §1)

### Canonical authority (good)

- **`services/stripe_mode_authority.py`**: `get_stripe_mode()`, `resolve_stripe_secret_key()`, `configure_stripe_sdk()`, webhook secret resolution, `assert_stripe_object_mode()`, `build_stripe_operational_config()`.
- **Single global SDK**: `stripe.api_key` set at import in `stripe_service.py`, `stripe_webhook_service.py`, and startup health check.
- **Selection model**: **Request-global / deployment-global** — not per-client, per-subscription, or per-checkout-session.

### Gaps

- **Not entity-aware**: No resolver like `get_stripe_client_for_client(client_id)` using stored `stripe_mode`.
- **Legacy bypasses** (can disagree with `STRIPE_MODE` if legacy key prefix differs from `STRIPE_SECRET_KEY_{MODE}`):
  - `routes/billing.py` (portal)
  - `billing_stripe_sync_service.retrieve_stripe_subscription_dict`
  - `intake_draft_service` checkout
  - `jobs.py`, `order_receipt_service`, Clearform routes, backfill scripts
- **`create_upgrade_session`**: Does not call `configure_stripe_sdk()` at entry (relies on module import); no pre-flight mode assertion on subscription ID.

---

## 4. Subscription persistence model (audit §2)

### Fields searched

| Field | On `clients` | On `client_billing` | On `checkout_sessions` | On `stripe_events` | On governance |
|-------|--------------|---------------------|------------------------|--------------------|---------------|
| `stripe_mode` | ✗ | ✗ | ✗ | ✗ | ✗ |
| `stripe_environment` | ✗ | ✗ | ✗ | ✗ | ✗ (pilot invite only) |
| `stripe_account_mode` | ✗ | ✗ | ✗ | ✗ | ✗ |
| `livemode` | ✗ | ✗ | ✗ | ✗ (only in logs / `raw_minimal` if present) | ✗ |
| `checkout_mode` | ✗ | ✗ | ✗ | ✗ | ✗ |

### What **is** stored

- `client_billing`: `stripe_customer_id`, `stripe_subscription_id`, optional `stripe_subscription_ids[]`, plan codes, lifecycle fields, `stripe_webhook_last_*`
- `clients`: mirror `stripe_customer_id`, `stripe_subscription_id`, `latest_checkout_session_id`, `latest_checkout_url`, recovery fields
- `checkout_sessions`: `session_id`, `plan_code`, `status`, amounts — **no Stripe mode**
- `stripe_events`: `event_id`, `type`, processing status, `raw_minimal` — **no indexed `livemode`**
- Pilot invites: `stripe_environment` at invite level (not propagated to client billing row on checkout)

**Gap:** Once `STRIPE_MODE` changes on a shared database (staging/prod cutover, Render env change, or legacy key swap), **all historical IDs remain mode-ambiguous**.

---

## 5. Runtime environment drift scenarios (audit §3)

| Scenario | Supported today? | Evidence |
|----------|------------------|----------|
| Test subscription queried with live key | **Yes — observed failure mode** | Upgrade retrieve + error message |
| Live subscription queried with test key | **Yes** | Symmetric Stripe API error |
| Webhook mode ≠ execute mode | **Partially blocked** | Webhook rejects `livemode` mismatch vs `STRIPE_MODE`; outbound API still uses global key |
| Customer created test, mutated live | **Yes** | Same `cus_*` IDs exist in both modes as different objects; DB stores one ID string only |
| Checkout in test, upgrade after `STRIPE_MODE=live` | **Yes** | Primary drift path for long-lived tenants |
| Portal route uses different key than checkout | **Possible** | `billing.py` portal uses legacy env only |

---

## 6. Upgrade/downgrade flow trace (audit §4)

```
User: Billing UI plan change + step-up password
  → POST /api/billing/checkout { plan_code }
  → client_route_guard + require_recent_step_up
  → stripe_service.create_upgrade_session(client_id, new_plan_code, origin_url)
       → client_billing.find_one → stripe_customer_id, stripe_subscription_id
       → if no customer → create_checkout_session (new checkout; mode-aware prices)
       → if no subscription_id → billing_portal.Session.create (customer only)
       → mode = get_stripe_mode()
       → new_price_id from STRIPE_{MODE}_PRICE_* env
       → stripe.Subscription.retrieve(stripe_subscription_id)  ← FAILURE HERE
       → stripe.billing_portal.Session.create(flow_data=subscription_update_confirm)
  → ValueError → HTTP 400 → UI "Failed to create upgrade session: …"
```

| Item | Value |
|------|--------|
| Subscription ID source | `client_billing.stripe_subscription_id` (and client mirror) |
| Active key | Whatever `configure_stripe_sdk()` set at process start (`STRIPE_MODE` → `STRIPE_SECRET_KEY_LIVE` or legacy matching key) |
| Mode inference | **Deployment** `STRIPE_MODE` only; subscription ID mode **not** inferred |
| Price IDs | Correctly mode-scoped via `get_stripe_price_mappings(mode)` |

---

## 7. Existing data drift (audit §5)

**Cannot run production/staging DB scans in this audit** (no Mongo in audit runner). Expected patterns from architecture:

| Pattern | Risk |
|---------|------|
| `sub_*` / `cus_*` from test checkouts in DB while `STRIPE_MODE=live` | **High** — matches reported incident |
| Same email with test + live customers after mode switch | Medium — duplicate customer risk |
| Stale `checkout_sessions` (`pending`) from opposite mode | Medium — recovery may regenerate wrong mode |
| `stripe_events` from test era while live webhooks active | Low–medium — idempotency by `event_id` only; cross-mode replay blocked at handler |
| Clients with `stripe_subscription_id` but `subscription_status` from webhook in other mode | High — status drift |

**Recommended operational query** (for ops, not run here):

- Sample `client_billing` where `stripe_subscription_id` exists; for each ID, call Stripe retrieve in **test** and **live** (read-only) or use Dashboard mode indicator.
- Compare `GET /api/admin/pilot-invites/operational-config` `stripe_mode` vs age of subscription rows.

---

## 8. Governance risk (audit §6)

| Risk | Severity | Notes |
|------|----------|-------|
| Live billing against test customer/sub | **Critical** if charges attempted | Upgrade path fails closed; other paths may differ |
| Entitlement without valid live billing | Medium | Commercial governance is platform-authoritative; Stripe convergence is lightweight and **does not** verify mode |
| Downgrade/upgrades wrong environment | **High** | Current incident class |
| Webhook replay cross-environment | Low | `livemode` assert on verified webhooks |
| Accidental dual subscriptions | Medium | `prevent_duplicate_subscription_risk` is ID-count only, not mode-aware |
| Admin plan change on wrong mode | High | Admin billing Stripe mutations use same global client |

---

## 9. Recommended architecture (audit §7)

### Authoritative model

- **`stripe_mode`** on every Stripe-linked entity: `client_billing` (required), `checkout_sessions`, optional denormalized on `clients`.
- Set at **write time** from `get_stripe_mode()` on checkout create, webhook handle, and admin provisioning.
- **Immutable** for the life of a subscription unless explicit migration job.

### Environment-aware resolver

```text
resolve_stripe_context(client_id) → { mode, secret_key, webhook_secret_scope }
  - Read client_billing.stripe_mode (fail if missing and stripe_subscription_id set)
  - configure_stripe_sdk(mode=stored_mode) OR dedicated StripeClient per mode (no global mutation)
```

### Migration strategy

1. **Inventory** — classify all rows with Stripe IDs by probing or inferring from creation era / `stripe_events.raw_minimal.livemode` if backfilled.
2. **Freeze** — document target `STRIPE_MODE` per environment (staging=test, production=live).
3. **Remediate per cohort**:
   - Test IDs on production DB → re-checkout in live **or** delete stale IDs and mark `PAYMENT_REQUIRED`.
   - Never flip `STRIPE_MODE` alone on a shared DB.
4. **Backfill** `stripe_mode` on `client_billing` + active `checkout_sessions`.
5. **Enforce** — pre-flight `assert_subscription_mode_matches_platform()` before any `Subscription.retrieve`.

### Drift detection

- Startup: already `build_stripe_operational_config()` — extend with **DB drift sample** job.
- Admin billing snapshot: flag `stripe_mode` missing or mismatched vs deployment.
- On `Subscription.retrieve` Stripe error containing "test mode" / "live mode", map to `STRIPE_OBJECT_ENVIRONMENT_DRIFT` (use `enhance_stripe_not_found_error` in authority).

### Safe fallback behaviour

- **Do not** silently switch `STRIPE_MODE`.
- Return **409/400** with `error_code: STRIPE_SUBSCRIPTION_MODE_DRIFT` and ops message.
- Offer **regenerate checkout** in current deployment mode only when no valid same-mode subscription exists.

### Operational diagnostics

- Extend admin operational config with: `deployment_stripe_mode`, `clients_missing_stripe_mode_count`, `suspected_mixed_mode_clients` (sample).
- Log on upgrade: `client_id`, `stripe_subscription_id`, `STRIPE_MODE`, key prefix (never full key).

---

## 10. Hotfix vs full repair

| Approach | Safe? | When |
|----------|-------|------|
| Toggle `STRIPE_MODE` globally to match majority of DB IDs | **Only** if entire environment is non-production test data | Staging-only |
| Clear `stripe_subscription_id` for affected client + new checkout | Per-client, with ops approval | Contained incident |
| Align legacy `STRIPE_SECRET_KEY` with `STRIPE_MODE` | Insufficient alone | Does not fix opposite-mode IDs |
| Remove legacy bypasses | Part of full repair | Required for convergence |

**Verdict:** **Full convergence repair required** (schema + resolver + backfill + remove legacy key paths + pre-flight guards).  

A **configuration-only hotfix** is unsafe on production without knowing each client’s subscription mode. The reported error indicates **data/env mismatch**, not a missing price ID.

---

## 11. Classification rationale

| Option | Fit |
|--------|-----|
| `SIMPLE_ENV_MISCONFIG` | Partial — wrong `STRIPE_MODE` on deploy could trigger this, but authority layer exists |
| `MIXED_MODE_DATA_DRIFT` | **Direct mechanism** for the error |
| `STRIPE_ENVIRONMENT_GOVERNANCE_GAP` | **Best programme label** — missing entity mode + legacy bypasses |
| `BILLING_CONVERGENCE_RISK` | Secondary — entitlement/commercial paths don’t enforce Stripe mode |
| `FAIL_OPERATIONAL` | Too broad — system partially enforces mode on webhooks/checkout prices |

**Selected:** `STRIPE_ENVIRONMENT_GOVERNANCE_GAP` with incident mechanism `MIXED_MODE_DATA_DRIFT`.

---

## 12. Implementation plan (recommended — not executed)

1. **Phase 0 — Ops**  
   - Confirm Render/production `STRIPE_MODE` and key prefixes via admin operational-config.  
   - Identify affected `client_id`(s) for `sub_1TXSZ9CF0O5oqdUzdUI7Xcu`.

2. **Phase 1 — Guardrails (small)**  
   - `create_upgrade_session` / `retrieve_stripe_subscription_dict`: call `configure_stripe_sdk()`; catch mode mismatch errors; return structured error.  
   - Remove legacy key assignment in `billing.py` portal (use authority).

3. **Phase 2 — Data model**  
   - Add `stripe_mode` to `client_billing`, `checkout_sessions`; backfill job.  
   - Persist `livemode` on `stripe_events`.

4. **Phase 3 — Resolver**  
   - Entity-aware Stripe client selection; forbid global `stripe.api_key` mutation in jobs/scripts without mode param.

5. **Phase 4 — Migration**  
   - Cohort remediation script (test→live re-subscribe or staging reset).  
   - Drift detection cron + admin UI warnings.

6. **Phase 5 — Entitlement**  
   - Commercial Stripe convergence: surface mode mismatch in drift assessment (read-only v1).

---

## 13. No code changes in this programme

Per scope: **audit only**. No fixes implemented.
