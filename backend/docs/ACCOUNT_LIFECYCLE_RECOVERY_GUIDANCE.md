# Account Lifecycle Recovery Guidance (ILP-7)

**Authority:** `services/account_lifecycle_response_authority.py`  
**Policy version:** `account_lifecycle_response_v1`

---

## Purpose

Recovery metadata tells the customer **what to do next** when lifecycle or capability restrictions block an action. All recovery payloads are generated centrally — routes consume them; they do not construct recovery objects.

---

## Recovery object shape

```json
{
  "route": "/settings/billing",
  "label": "Manage billing",
  "action": "complete_payment",
  "eligible": true,
  "paths": ["billing_checkout", "payment_method_update"],
  "restoration_scope": "full"
}
```

| Field | Source |
|-------|--------|
| `route`, `label` | Runtime Contract `customer_experience.primary_cta` or capability decision recovery |
| `action` | `_recovery_action()` mapping |
| `eligible`, `paths`, `restoration_scope` | Contract `reactivation_policy` |

---

## Recovery actions by lifecycle

| Lifecycle / portal mode | `recovery.action` | Typical route |
|-------------------------|-------------------|---------------|
| `BILLING_RECOVERY`, `PAYMENT_REQUIRED` | `complete_payment` | `/settings/billing` |
| `CANCELLED_IMMEDIATE`, `SUBSCRIPTION_EXPIRED` | `complete_payment` | `/settings/billing` |
| `GRACE_PERIOD`, `PAYMENT_FAILED`, `TRIAL_EXPIRED` | `complete_payment` | `/settings/billing` |
| `READ_ONLY` | `reactivate_account` | `/settings/billing` |
| `SUSPENDED` | `contact_support` | `/support` |
| `ARCHIVED`, `ACCOUNT_DELETED` | `contact_support` | `/support` |
| Active / trial (capability deny) | `continue` | Primary CTA from CX |

---

## Customer messaging alignment

Messages come from Runtime Contract `customer_experience` — not handwritten route strings.

| Avoid (route-local) | Use (governed) |
|---------------------|----------------|
| "Upgrade required" | CX `heading` / `explanation` |
| "Plan restriction" | `error_code: plan_denied` + CX message |
| "Subscription inactive" | `response_type: billing_recovery` + CX |
| "Account blocked" | `response_type: suspended` + CX |

---

## Lifecycle redirect vs recovery

Both are emitted on every governed denial:

| Object | Purpose |
|--------|---------|
| `lifecycle_redirect` | SPA navigation target + surface id |
| `recovery` | CTA metadata + reactivation eligibility |

Frontend should prefer `lifecycle_redirect.route` for redirects; use `recovery` for button labels and eligibility checks.

---

## Billing recovery read-tier

Billing routes under `/api/billing` and `/api/client/billing` remain accessible when lifecycle guard blocks other client APIs (SUSPENDED/CANCELLED canonical states). Recovery payloads point customers to `/settings/billing` for self-service where policy allows.

---

## Authentication recovery

| Response | Redirect | Action |
|----------|----------|--------|
| `authentication_expired` | `/login` | `sign_in` |
| `session_refresh_required` | `/today` (refresh shell) | implicit refresh |

---

## Support reference

Every governed response includes `support_reference` (format: `ALR-{runtime_version}-{response_type}-{capability}`) for customer support correlation without exposing internal entitlement fields.
