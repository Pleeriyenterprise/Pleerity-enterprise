# Account Lifecycle Response Schema (ILP-7)

**Policy version:** `account_lifecycle_response_v1`  
**Contract version:** from Runtime Contract (`1.0.0`)

---

## Canonical shape

All lifecycle-aware HTTP error bodies (`detail` for 401/403) follow this schema:

```json
{
  "error": "capability_denied",
  "error_code": "read_only_blocked",
  "reason_code": "read_only_blocked",
  "message": "Your account is in read-only mode. Upgrade or reactivate to make changes.",
  "reason": "Your account is in read-only mode. Upgrade or reactivate to make changes.",

  "lifecycle_state": "READ_ONLY",
  "portal_mode": "READ_ONLY",
  "response_type": "read_only",

  "customer_experience": {
    "heading": "Read-only access",
    "explanation": "...",
    "current_state_label": "Read-only",
    "primary_cta": {
      "label": "Manage billing",
      "route": "/settings/billing"
    }
  },

  "recovery": {
    "route": "/settings/billing",
    "label": "Manage billing",
    "action": "reactivate_account",
    "eligible": true,
    "paths": ["billing_reactivation"],
    "restoration_scope": "full"
  },

  "lifecycle_redirect": {
    "route": "/settings/billing",
    "label": "Manage billing",
    "surface": "billing"
  },

  "runtime_version": 1847293012,
  "contract_version": "1.0.0",
  "policy_version": "account_lifecycle_response_v1",

  "capability": "CAP_PROP_EDIT",
  "capability_id": "CAP_PROP_EDIT",
  "grant": "DENY",
  "action": "write",
  "effective_semantic": "DENY",

  "support_reference": "ALR-1847293012-read_only-PROP_EDIT",
  "safe_to_retry": false
}
```

---

## Field reference

| Field | Required | Source |
|-------|----------|--------|
| `error` | ✓ | Top-level error category (`capability_denied`, `suspended`, …) |
| `error_code` | ✓ | Machine code (`read_only_blocked`, `lifecycle_access_denied`, …) |
| `reason_code` | ✓ | ILP-4 compatibility alias of `error_code` |
| `message` | ✓ | Safe customer string (from Runtime Contract CX) |
| `reason` | ✓ | Same as `message` unless override |
| `lifecycle_state` | lifecycle | ILP-1 resolver |
| `portal_mode` | lifecycle | APMA |
| `response_type` | ✓ | Governed category (see authority doc) |
| `customer_experience` | lifecycle | Subset of contract `customer_experience` |
| `recovery` | lifecycle | Central recovery metadata |
| `lifecycle_redirect` | lifecycle | Governed redirect (route, label, surface) |
| `runtime_version` | when available | ILP-2 contract |
| `contract_version` | ✓ | ILP-2 schema version |
| `policy_version` | ✓ | `account_lifecycle_response_v1` |
| `capability` / `capability_id` | capability | CAP_* id |
| `grant` | capability | Effective grant |
| `action` | capability | `read` or `write` |
| `effective_semantic` | capability | Normalized semantic |
| `support_reference` | ✓ | Stable support correlation id |
| `safe_to_retry` | ✓ | Boolean retry hint |

---

## Removed fields (ILP-7)

These must **not** appear in governed lifecycle responses:

| Legacy field | Replacement |
|--------------|-------------|
| `canonical_entitlement_state` | `lifecycle_state` + `portal_mode` |
| `SUBSCRIPTION_ACCESS_BLOCKED` | `lifecycle_access_denied` + `response_type` |
| Bare `recovery.route` without `lifecycle_redirect` | Both emitted; redirect is canonical |

---

## Redirect surfaces

| `lifecycle_redirect.surface` | Route prefix examples |
|-------------------------------|------------------------|
| `billing` | `/settings/billing` |
| `profile` | `/settings/profile` |
| `settings` | `/settings` |
| `support` | `/support` |
| `today` | `/today` |
| `dashboard` | `/dashboard` |
| `documents` | `/documents` |
| `portal` | `/properties`, `/onboarding-status`, `/reports` |

Surfaces are resolved centrally in `_redirect_surface()` — never hard-coded per route.

---

## Recovery actions

| `recovery.action` | Meaning |
|-------------------|---------|
| `complete_payment` | Billing recovery / payment required |
| `reactivate_account` | Read-only or cancelled reactivation |
| `contact_support` | Suspended/archived/deleted |
| `sign_in` | Authentication expired |
| `continue` | Default — follow primary CTA |

Full guidance: `ACCOUNT_LIFECYCLE_RECOVERY_GUIDANCE.md`.

---

## HTTP semantics

Payload shape is standardized. HTTP status codes are **preserved** from existing routes unless governance requires change:

| Scenario | Status |
|----------|--------|
| Capability denied | 403 |
| Lifecycle denied | 403 |
| Authentication expired | 401 |
| Session refresh | per ILP-5 route (409/403) |
| Not found / validation | unchanged (404, 422, …) |

---

## Frontend consumption

Consumers should prefer:

1. `lifecycle_redirect.route` for navigation
2. `recovery` for CTA labels and eligibility
3. `customer_experience` for inline messaging
4. `safe_to_retry` for retry UX (`parseApiError` in `frontend/src/api/client.js`)
5. `parseLifecycleResponseDetail()` / `lifecycleRedirectRouteFromDetail()` in `capabilityRuntime.js`
