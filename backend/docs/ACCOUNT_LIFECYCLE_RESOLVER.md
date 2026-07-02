# Account Lifecycle State Resolver (ILP-1)

**Programme:** ILP-1-LIFECYCLE-STATE-RESOLVER-01  
**Policy version:** `account_lifecycle_policy_v1`  
**Resolver version:** `ilp1_lifecycle_state_resolver_v1`  
**Module:** `services/account_lifecycle_state_resolver.py`

---

## Purpose

The Account Lifecycle State Resolver is a **pure, read-only** backend service that maps existing platform facts into the governed `account_lifecycle_state` enum defined by Account Lifecycle Policy Authority (ALPA).

ILP-1 materialises approved governance into deterministic code. It does **not** enforce access, mutate data, or change runtime behaviour.

---

## Inputs

Facts are read from existing collections and fields only:

| Source | Fields consumed |
|--------|-----------------|
| `client_billing` (preferred) | `subscription_status`, `billing_lifecycle_state`, `canonical_entitlement_state`, `entitlement_status`, `cancel_at_period_end`, `grace_period_ends_at`, `current_period_end`, `payment_failed_at`, `read_only_retention`, `account_lifecycle_read_only`, `retention_tier` |
| `clients` (mirror / org) | Same billing mirror fields plus `client_lifecycle_status`, `lifecycle_status`, `onboarding_status`, `is_deleted`, `purged_at`, `pilot_status` |

When `billing_lifecycle_state` is absent or stale, the resolver recomputes it via `compute_billing_lifecycle_state()` from `subscription_lifecycle_service` (read-only derivation; no persistence).

Optional async entry points:

- `load_client_and_billing(db, client_id)` — Mongo read
- `resolve_for_client_id(db, client_id)` — load + resolve

---

## Output

```json
{
  "account_lifecycle_state": "ACTIVE",
  "source_facts": { "...": "..." },
  "reason": "active_subscription",
  "confidence": "HIGH",
  "policy_version": "account_lifecycle_policy_v1",
  "resolver_version": "ilp1_lifecycle_state_resolver_v1",
  "resolved_at": "2026-06-15T12:00:00+00:00",
  "warnings": []
}
```

Confidence levels: `HIGH` (single clear path), `MEDIUM` (legacy/onboarding/mirror fallback), `LOW` (UNKNOWN/contradictions).

Schema aligns with `ACCOUNT_RUNTIME_SCHEMA.md` lifecycle fields; ILP-1 emits **lifecycle_state only** (full Runtime Contract API is ILP-2).

---

## Precedence (highest first)

| Tier | Condition | Resolved state |
|------|-----------|----------------|
| 1 | `purged_at` set on client | `ACCOUNT_DELETED` |
| 2 | `is_deleted`, org `ARCHIVED`/`PURGE_ELIGIBLE`, legacy `lifecycle_status=archived` | `ARCHIVED` |
| 3 | Org `client_lifecycle_status=SUSPENDED` | `SUSPENDED` |
| 4 | Legacy `pending_payment` | `PAYMENT_PENDING` |
| 5 | Legacy `abandoned` (not provisioned) | `LEGACY` |
| 6 | Onboarding without billing/subscription | `PAYMENT_PENDING` |
| 7 | Stripe `INCOMPLETE` | `PAYMENT_PENDING` |
| 8 | Read-only retention markers | `READ_ONLY` |
| 9 | Billing-derived (see mapping table) | per Stripe + billing lifecycle |
| 10 | Hard billing contradictions | `UNKNOWN` + warnings |
| 11 | Unmapped combination | `UNKNOWN` |

Org/archive/deletion states **always** beat subscription status (e.g. archived org with Stripe `ACTIVE` → `ARCHIVED`).

`client_billing` facts **preferred** over `clients` mirror for billing fields.

---

## State mapping table

| Resolved state | Primary fact signals |
|----------------|---------------------|
| `ACTIVE` | Stripe `ACTIVE`, billing `active`/`renewing` |
| `TRIAL` | Stripe `TRIALING`, billing active path |
| `TRIAL_EXPIRED` | `INCOMPLETE_EXPIRED` or trialing + expired billing |
| `PAYMENT_PENDING` | `INCOMPLETE`, legacy `pending_payment`, onboarding without billing |
| `PAYMENT_FAILED` | `PAST_DUE` pre-grace / billing `past_due` |
| `GRACE_PERIOD` | billing `grace_period` or `PAST_DUE` within grace window |
| `CANCELLATION_SCHEDULED` | `cancel_at_period_end` + `ACTIVE`/`TRIALING` access |
| `CANCELLED_IMMEDIATE` | Stripe `CANCELED` / billing `cancelled` |
| `SUBSCRIPTION_EXPIRED` | Stripe `UNPAID` / billing `expired` |
| `READ_ONLY` | `read_only_retention`, `account_lifecycle_read_only`, `retention_tier=READ_ONLY` |
| `SUSPENDED` | Org suspension, billing `limited` (post-grace), Stripe `PAUSED` |
| `ARCHIVED` | Soft delete / archived org lifecycle |
| `ACCOUNT_DELETED` | `purged_at` on client record |
| `LEGACY` | Unmapped legacy funnel (`abandoned`, pilot without billing) |
| `UNKNOWN` | Contradictory or unmapped facts |

---

## Unsupported / deferred (ILP-1)

- Portal mode derivation (ILP-3 / APMA)
- Capability enforcement (ILP-4 / ACA)
- Session invalidation (ILP-7)
- Background job scheduling changes (ILP-8)
- Event emission (ILP-9)
- Replacing `canonical_entitlement_state` writes
- Retention timer automation for `READ_ONLY` (requires explicit retention markers today)

---

## Relation to governance documents

| Document | I = ILP-1 usage |
|----------|----------------|
| **ALPA** + Policy Matrix | Defines the 15 lifecycle states and customer experience bands |
| **APMA** | Not consumed in ILP-1 (portal mode is ILP-3) |
| **ACA** + Capability Catalog | Not enforced in ILP-1 |
| **Runtime Contract** + Schema | Output shape reference; full contract API is ILP-2 |
| **Transition / Event / Reactivation Authority** | Inform mapping; transitions not executed in ILP-1 |

---

## What ILP-1 does not enforce

- Middleware route guards
- Frontend routing / `ProtectedRoute`
- `EntitlementsContext`
- Stripe webhook writes
- Notification or report access
- Billing UI behaviour
- Subscription cancellation behaviour

---

## What ILP-2 will consume

ILP-2 (Runtime Contract API) will expose resolver output as the authoritative `account_lifecycle_state` field alongside version metadata, without replacing existing stored bands until a controlled migration programme.

---

## Diagnostics

Read-only drift comparison:

```bash
python scripts/account_lifecycle_state_drift_diagnostic.py --fixture
python scripts/account_lifecycle_state_drift_diagnostic.py --client-id <id>
```

`compare_resolution_with_existing_fields()` compares resolved state against stored `canonical_entitlement_state`, `billing_lifecycle_state`, and `entitlement_status`.

---

## Tests

```bash
pytest tests/test_account_lifecycle_state_resolver.py -v
```

32 unit tests cover all approved states, precedence, boundaries, contradictions, idempotency, and malformed input.
