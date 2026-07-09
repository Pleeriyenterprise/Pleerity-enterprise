# Authoritative Field Decisions — Runtime Contract State Matrix

**Programme:** P0-RUNTIME-CONTRACT-STATE-MATRIX-VALIDATION-01  
**Date:** 2026-07-07

This document records which fields are authoritative, derived, mirror, or cache in the Runtime Contract authority chain. Decisions are enforced in `account_lifecycle_state_resolver.py` and `account_lifecycle_runtime_contract.py`.

---

## Decision summary

| Category | Fields | Rule |
|----------|--------|------|
| **Authoritative (billing)** | `client_billing.subscription_status`, `billing_lifecycle_state`, `grace_period_ends_at`, `cancel_at_period_end`, `read_only_retention` | Preferred over all client mirrors via `_pick(prefer_billing=True)` |
| **Authoritative (org terminal)** | `purged_at`, `is_deleted`, `client_lifecycle_status` (SUSPENDED/ARCHIVED) | Terminal overrides — billing cannot restore access |
| **Authoritative (provisioning)** | `onboarding_status` | Gates legacy funnel; determines PAYMENT_PENDING when no billing |
| **Legacy mirror (lowest)** | `lifecycle_status` | May drift; must not override provisioned active accounts |
| **Client mirror (fallback)** | `clients.subscription_status`, `clients.billing_lifecycle_state` | Used only when `client_billing` row absent or field null |
| **Derived (never input)** | `account_lifecycle_state`, `portal_mode`, `capabilities`, `runtime_version` | Output of resolver/contract assembly only |
| **Request cache** | `request.state.runtime_contract`, `user.runtime_contract` | Single resolution per authenticated request |
| **Drift audit only** | `canonical_entitlement_state`, `entitlement_status` | Compared post-resolution; not resolver inputs |

---

## Resolver precedence (highest first)

1. **`purged_at`** → `ACCOUNT_DELETED` (confidence: HIGH)
2. **`is_deleted` / `client_lifecycle_status` ARCHIVED / PURGE_ELIGIBLE / legacy `archived`** → `ARCHIVED`
3. **`client_lifecycle_status` SUSPENDED** → `SUSPENDED` (overrides ACTIVE billing)
4. **Legacy `lifecycle_status: pending_payment`** → `PAYMENT_PENDING` *unless*:
   - `onboarding_status = PROVISIONED` AND `subscription_status ∈ {ACTIVE, TRIALING}`, OR
   - `client_lifecycle_status = ACTIVE` AND `subscription_status ∈ {ACTIVE, TRIALING}`
5. **Legacy `lifecycle_status: abandoned`** (non-provisioned) → `LEGACY`
6. **No billing + onboarding funnel states** → `PAYMENT_PENDING`
7. **`read_only_retention` tier** → `READ_ONLY`
8. **Billing-derived states** (trial, grace, cancel scheduled, cancelled, expired, active)
9. **Contradictory billing facts** → `UNKNOWN` (e.g., ACTIVE subscription + cancelled billing_lifecycle)
10. **Unmapped combination** → `UNKNOWN`

---

## Field-by-field decisions

### subscription_status

- **Authoritative source:** `client_billing` (preferred), `clients` (fallback)
- **Role:** Primary billing fact for lifecycle band selection
- **May drift:** Client mirror may lag Stripe sync — billing row wins when present
- **Must never:** Be overridden by `lifecycle_status` mirror when provisioned active

### billing_lifecycle_state

- **Authoritative source:** `client_billing` (preferred), computed via `compute_billing_lifecycle_state` when absent
- **Role:** Distinguishes grace, past_due, cancel_at_period_end, cancelled, expired
- **May drift:** Stored value may differ from recomputed — warning emitted, recomputed value used when stored absent
- **Must never:** Override org SUSPENDED or ARCHIVED terminal states

### lifecycle_status (legacy)

- **Authoritative source:** None — legacy intake funnel mirror on `clients`
- **Role:** Fallback for pre-billing funnel detection only
- **May drift:** Yes — commonly stale (`pending_payment` after provisioned active)
- **Must never:** Override PROVISIONED + ACTIVE/TRIALING or ACTIVE org + ACTIVE/TRIALING
- **Validated:** 5 mirror drift scenarios in matrix tests

### client_lifecycle_status

- **Authoritative source:** `clients` (org-level ops state)
- **Role:** Terminal override for SUSPENDED and ARCHIVED
- **May drift:** Org ACTIVE mirror may disagree with TRIALING billing — billing wins for lifecycle band (except SUSPENDED/ARCHIVED)
- **Must never:** Be used alone to grant ACTIVE when billing is terminal cancelled/expired

### onboarding_status

- **Authoritative source:** `clients`
- **Role:** Provisioning gate; determines PAYMENT_PENDING when no billing
- **Must never:** Be ignored when evaluating pending_payment legacy override

### portal_mode

- **Derived from:** `lifecycle_state` + `read_only_retention` override
- **Special rules:**
  - `PAYMENT_FAILED` → `FULL_ACCESS` (pre-grace recovery UX)
  - `SUBSCRIPTION_EXPIRED` + `read_only_retention` → `READ_ONLY` portal override
- **Must never:** Be set independently by routes or frontend from raw subscription fields

### capabilities

- **Derived from:** `_BASE_CAPABILITY_MATRIX[lifecycle_column]` → portal overlay → plan feature gates
- **Must never:** Be inferred by individual routes from subscription_status or lifecycle_status

### request.state.runtime_contract

- **Cache scope:** Single authenticated request
- **Set by:** `apply_session_runtime_validation`
- **Consumed by:** Capability gating, profile routes, lifecycle bootstrap
- **Must never:** Be re-resolved per CAP_* check (was root cause of staging split authority)

---

## Legitimate drift vs forbidden override

### May legitimately drift (warnings only)

- `clients.lifecycle_status` stale funnel values
- `clients.subscription_status` lag behind Stripe
- `canonical_entitlement_state` band labels vs resolved lifecycle
- Missing `client_billing` row (warning: `missing_billing_record`)

### Must never override canonical authority

- Stale `lifecycle_status` must not downgrade active paying customers
- Client subscription mirror must not override `client_billing` when billing row exists
- Routes must not establish independent subscription/lifecycle/permission authority
- UNKNOWN must not be returned for valid PROVISIONED + ACTIVE accounts

---

## UNKNOWN policy

UNKNOWN is returned only when:

1. No client or billing facts at all (`empty_input`)
2. Hard billing contradiction (`ACTIVE` subscription + `cancelled`/`expired`/`limited` billing lifecycle)
3. Unmapped subscription status (e.g., `WEIRD_STATUS`)

UNKNOWN is **never** returned for:

- PROVISIONED + ACTIVE subscription (even with stale `pending_payment` mirror)
- ACTIVE org + ACTIVE subscription
- Any mirror drift scenario in the validated matrix

---

## Data preservation invariant

Lifecycle transitions affect **access policy only** (capabilities, portal mode, background processing). Domain collections (properties, requirements, documents, evidence, reports, notifications, audit history, maintenance, contractors, tenancies, settings, profile) are **not deleted** by the resolver or contract assembly. Retention tier (`STANDARD`, `READ_ONLY_WINDOW`, `PURGE_ELIGIBLE`) governs eventual purge eligibility — not lifecycle resolution itself.

Resubscription restores functionality through Runtime Contract regeneration alone. No data recreation. No special-case scripts.
