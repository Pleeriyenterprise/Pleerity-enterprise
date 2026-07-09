# Account Portal Mode Authority

**Programme:** ACCOUNT-LIFECYCLE-POLICY-AUTHORITY-01  
**Authority version:** `account_lifecycle_policy_v1`  
**Parent:** `ACCOUNT_LIFECYCLE_POLICY_AUTHORITY.md`

---

## Purpose

Portal Mode is the **single customer-facing contract** between backend lifecycle policy and the frontend shell.

**The frontend must consume Portal Mode — never raw Stripe fields, `canonical_entitlement_state`, or `billing_lifecycle_state` directly.**

---

## Governed portal modes

| Portal mode | Lifecycle states served | Customer intent |
|-------------|------------------------|-----------------|
| `FULL_ACCESS` | ACTIVE, TRIAL, PAYMENT_FAILED (warning), CANCELLATION_SCHEDULED, GRACE (optional full) | Normal operation |
| `READ_ONLY` | READ_ONLY, LEGACY (pre-migration) | View and export; no changes |
| `BILLING_RECOVERY` | CANCELLED_IMMEDIATE, SUBSCRIPTION_EXPIRED, UNKNOWN | Restore subscription |
| `PAYMENT_REQUIRED` | PAYMENT_PENDING, TRIAL_EXPIRED | Complete payment |
| `GRACE` | GRACE_PERIOD | Pay before suspension |
| `SUSPENDED` | SUSPENDED | Account blocked |
| `ARCHIVED` | ARCHIVED | Account closed |
| `ACCOUNT_DELETED` | ACCOUNT_DELETED | Account removed |

---

## Lifecycle state → portal mode resolver (policy)

```
account_lifecycle_state ──► portal_mode
```

| `account_lifecycle_state` | `portal_mode` |
|---------------------------|---------------|
| ACTIVE | FULL_ACCESS |
| TRIAL | FULL_ACCESS |
| TRIAL_EXPIRED | PAYMENT_REQUIRED |
| PAYMENT_PENDING | PAYMENT_REQUIRED |
| PAYMENT_FAILED | FULL_ACCESS (banner) or GRACE if in grace window |
| GRACE_PERIOD | GRACE |
| CANCELLATION_SCHEDULED | FULL_ACCESS |
| CANCELLED_IMMEDIATE | BILLING_RECOVERY |
| SUBSCRIPTION_EXPIRED | BILLING_RECOVERY (default) or READ_ONLY (tier) |
| READ_ONLY | READ_ONLY |
| SUSPENDED | SUSPENDED |
| ARCHIVED | ARCHIVED |
| ACCOUNT_DELETED | ACCOUNT_DELETED |
| UNKNOWN | BILLING_RECOVERY |
| LEGACY | READ_ONLY |

---

## Portal mode contract (API shape — policy)

Future endpoint: `GET /api/client/lifecycle-contract`

```json
{
  "account_lifecycle_state": "CANCELLED_IMMEDIATE",
  "portal_mode": "BILLING_RECOVERY",
  "state_label": "Subscription ended",
  "state_reason": "cancelled_immediate",
  "primary_cta": { "label": "Resubscribe", "route": "/billing" },
  "secondary_cta": { "label": "Contact support", "route": "/support" },
  "available_features": ["billing", "profile", "support", "data_export"],
  "locked_features": ["dashboard", "properties", "requirements", "reports", "today"],
  "read_only_features": ["properties", "requirements", "reports"],
  "messaging": {
    "heading": "Your subscription has ended",
    "explanation": "Your data is preserved. Resubscribe to restore full access.",
    "support_guidance": "Contact support if you need help restoring your account."
  },
  "polling_policy": { "enabled": false, "reason": "lifecycle_terminal" },
  "entitlements_version": 42,
  "session_policy": { "force_refresh": false }
}
```

**Policy:** All client shell providers (`EntitlementsContext`, `ClientPortalLayout`, `ProtectedRoute`) consume this contract.

---

## Per-mode UI authority

### FULL_ACCESS

| Surface | Behaviour |
|---------|-----------|
| Landing page | `/today` or last route |
| Sidebar | Full Navigation Authority tree |
| Navigation | Unrestricted per nav policy |
| Locked pages | Plan-gated only (not lifecycle) |
| Read-only pages | None (lifecycle) |
| Upgrade prompts | Trial conversion if TRIAL |
| Renewal prompts | CANCELLATION_SCHEDULED banner |
| Recovery messaging | None |
| Dashboard | Full |
| Requirements | Full |
| Reports | Full per RPA |
| Documents | Full |
| Billing | Full |
| Profile | Full |
| Error handling | Standard; no lifecycle errors |
| Primary CTA | Contextual (Today tasks) |
| Secondary CTA | — |
| Support messaging | Standard |

---

### GRACE

| Surface | Behaviour |
|---------|-----------|
| Landing page | `/today` with persistent grace banner |
| Sidebar | Full |
| Navigation | Full |
| Locked pages | None (yet) |
| Read-only pages | None |
| Upgrade prompts | — |
| Renewal prompts | Payment update |
| Recovery messaging | “Update payment by {date}” |
| Dashboard | Full |
| Requirements | Limited edits per matrix |
| Reports | Full |
| Documents | Full |
| Billing | Prominent payment CTA |
| Profile | Full |
| Error handling | No 403 on entitled routes |
| Primary CTA | Update payment method |
| Secondary CTA | View invoice |
| Support messaging | Payment assistance |

---

### BILLING_RECOVERY

| Surface | Behaviour |
|---------|-----------|
| Landing page | `/billing/recovery` (dedicated lifecycle screen) |
| Sidebar | Billing, Profile, Support, Export only |
| Navigation | Hard redirect from locked routes |
| Locked pages | Dashboard, Today, Properties, Requirements, Reports |
| Read-only pages | Properties, Requirements, Reports (view/export) |
| Upgrade prompts | Resubscribe |
| Renewal prompts | Resubscribe |
| Recovery messaging | State-specific copy from Customer Experience Authority |
| Dashboard | Lifecycle screen (not empty/broken) |
| Requirements | Read-only or hidden per tier |
| Reports | Read-only download |
| Documents | Read-only |
| Billing | Full |
| Profile | Full |
| Error handling | **No 403 storms**; routes never mount entitled APIs |
| Primary CTA | Resubscribe |
| Secondary CTA | Export data / Contact support |
| Support messaging | Recovery guidance |

**Current gap:** Frontend mounts full shell → 403 storm — **PORTAL_MODE_GAP** (ALC-002, ALC-003).

---

### PAYMENT_REQUIRED

| Surface | Behaviour |
|---------|-----------|
| Landing page | `/billing/checkout` or onboarding resume |
| Sidebar | Onboarding + Billing |
| Navigation | Onboarding funnel only |
| Locked pages | All operational until payment |
| Read-only pages | None |
| Upgrade prompts | Complete payment |
| Renewal prompts | — |
| Recovery messaging | Trial expired / complete setup |
| Dashboard | Onboarding progress |
| Requirements | Onboarding scope only |
| Reports | Hidden |
| Documents | Onboarding scope |
| Billing | Checkout |
| Profile | Limited |
| Error handling | Guided funnel |
| Primary CTA | Complete payment |
| Secondary CTA | Contact support |
| Support messaging | Onboarding help |

---

### READ_ONLY

| Surface | Behaviour |
|---------|-----------|
| Landing page | `/dashboard` read-only |
| Sidebar | View routes only; edit actions hidden |
| Navigation | Read routes |
| Locked pages | Create/edit routes |
| Read-only pages | All data surfaces |
| Upgrade prompts | Subscribe to edit |
| Renewal prompts | Subscribe |
| Recovery messaging | “View-only access” |
| Dashboard | Read-only widgets |
| Requirements | View only |
| Reports | View/download existing |
| Documents | View only |
| Billing | Full (upgrade path) |
| Profile | Full |
| Error handling | Mutations return friendly read-only message |
| Primary CTA | Upgrade subscription |
| Secondary CTA | Export data |
| Support messaging | Upgrade guidance |

---

### SUSPENDED

| Surface | Behaviour |
|---------|-----------|
| Landing page | `/account/suspended` |
| Sidebar | Support (+ Billing if payment-related) |
| Navigation | Minimal |
| Locked pages | All operational |
| Read-only pages | None (unless admin-granted) |
| Upgrade prompts | Per suspension class |
| Renewal prompts | If payment suspension |
| Recovery messaging | Suspension reason |
| Dashboard | Suspension screen |
| Requirements | Hidden |
| Reports | Hidden |
| Documents | Hidden |
| Billing | If payment suspension |
| Profile | Read |
| Error handling | No API polling |
| Primary CTA | Resolve suspension / Contact support |
| Secondary CTA | — |
| Support messaging | Ops or payment guidance |

---

### ARCHIVED

| Surface | Behaviour |
|---------|-----------|
| Landing page | `/account/archived` (pre-auth or post-auth deny) |
| Sidebar | None |
| Navigation | None |
| Locked pages | All |
| Read-only pages | None |
| Upgrade prompts | None |
| Renewal prompts | None |
| Recovery messaging | “Account archived — contact support” |
| Dashboard | N/A |
| Requirements | N/A |
| Reports | N/A |
| Documents | N/A |
| Billing | N/A |
| Profile | N/A |
| Error handling | Sign-in blocked with explanation |
| Primary CTA | Contact support |
| Secondary CTA | — |
| Support messaging | Reinstatement request |

---

### ACCOUNT_DELETED

| Surface | Behaviour |
|---------|-----------|
| Landing page | `/account/deleted` |
| Sidebar | None |
| Authentication | Denied |
| Recovery messaging | “This account has been deleted” |
| Primary CTA | Create new account / Contact support |
| Support messaging | Deletion is irreversible |

---

## Frontend consumption rules

1. **`LifecycleProtectedRoute`** wraps all `/client/*` routes; reads `portal_mode` before mount.
2. **No route may call entitled APIs** when `portal_mode` locks that surface.
3. **`EntitlementsContext`** refetches lifecycle contract on focus/resume; respects `polling_policy`.
4. **Structured API errors must never render as React children** — map to lifecycle screens.
5. **Billing page** is a subset of portal mode, not a parallel authority.
6. **Navigation Authority** receives `portal_mode` to filter sidebar items.
7. **Today / Command Centre** check portal mode before data fetch.

---

## Portal mode vs existing fields (drift inventory)

| Field | Must frontend use? |
|-------|-------------------|
| `portal_mode` | **Yes** (policy) |
| `canonical_entitlement_state` | **No** (implementation detail) |
| `billing_lifecycle_state` | **No** |
| `subscription_status` (Stripe) | **No** |
| `entitlement_status` | **No** (feature matrix input only) |
| `isActive` from entitlements | **No** (audit: unused) |

---

**Outcome:** `ACCOUNT_PORTAL_MODE_AUTHORITY_COMPLETE`
