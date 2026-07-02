# Account Customer Experience Authority

**Programme:** ACCOUNT-LIFECYCLE-POLICY-AUTHORITY-01  
**Authority version:** `account_lifecycle_policy_v1`  
**Parent:** `ACCOUNT_LIFECYCLE_POLICY_AUTHORITY.md`

---

## Purpose

Every lifecycle state and portal mode must deliver an **intentional customer experience**. The customer must never encounter implementation artefacts.

---

## Prohibited customer experiences (global)

The platform must **never** present:

| Defect | Root cause (audit) | Policy remedy |
|--------|-------------------|---------------|
| React Error Boundaries | Structured 403 `detail` rendered in JSX | Lifecycle screen + safe string messages |
| 403 storms | Shell polls entitled APIs when blocked | Portal mode guard stops polling |
| 401 loops | Session/lifecycle race | Deterministic session policy |
| Infinite polling | portal-context retry without circuit breaker | `polling_policy.enabled: false` |
| Broken navigation | JWT-only route guard | `LifecycleProtectedRoute` |
| Blank dashboards | APIs 403 but UI mounts | Dedicated lifecycle screens |
| Repeated login prompts | session_version race | Single re-auth flow |
| Dead-end screens | No CTA on terminal states | Primary + secondary CTA required |
| Unexpected redirects | Competing authorities | Portal mode landing map |
| Partial rendering | Mixed 200/403 | Atomic lifecycle contract fetch |
| Generic server errors | Unmapped lifecycle | Customer Experience copy per mode |

---

## Experience template (per mode)

Each mode defines:

- Heading
- Explanation
- Reason (human-readable)
- Current account state label
- Available features (explicit list)
- Unavailable features (explicit list)
- Primary CTA
- Secondary CTA
- Recovery guidance
- Support guidance
- Expected next step

---

## FULL_ACCESS (ACTIVE / TRIAL / CANCELLATION_SCHEDULED)

| Field | Copy policy |
|-------|-------------|
| Heading | None (normal app) |
| Explanation | — |
| Reason | — |
| Current account state | “Active” / “Trial” / “Cancellation scheduled for {date}” |
| Available features | All plan features |
| Unavailable features | Plan-gated only |
| Primary CTA | Contextual |
| Secondary CTA | — |
| Recovery guidance | — |
| Support guidance | Standard help |
| Expected next step | Continue work |

**CANCELLATION_SCHEDULED banner:**

| Field | Copy |
|-------|------|
| Heading | “Cancellation scheduled” |
| Explanation | “You have full access until {period_end_date}.” |
| Primary CTA | “Keep subscription” → resume |
| Secondary CTA | “View billing” |

---

## GRACE

| Field | Copy |
|-------|------|
| Heading | “Payment required” |
| Explanation | “We couldn't process your latest payment. Update your payment method by {grace_end_date} to avoid interruption.” |
| Reason | “Your account is in a grace period.” |
| Current account state | “Grace period” |
| Available features | View and manage compliance data; update payment |
| Unavailable features | None yet (limited side-effects per matrix) |
| Primary CTA | “Update payment method” → `/billing` |
| Secondary CTA | “View invoice” |
| Recovery guidance | “Pay outstanding balance before {date}.” |
| Support guidance | “Contact support if you believe this is an error.” |
| Expected next step | Payment updated → return to normal |

---

## BILLING_RECOVERY (CANCELLED_IMMEDIATE / SUBSCRIPTION_EXPIRED)

| Field | Copy |
|-------|------|
| Heading | “Your subscription has ended” |
| Explanation | “Your compliance data is preserved. Resubscribe to restore full access to your portfolio, requirements, and reports.” |
| Reason | “Subscription cancelled” or “Billing period ended” |
| Current account state | “Inactive subscription” |
| Available features | Billing, profile, support, data export, read-only views (tier) |
| Unavailable features | Editing properties, requirements, uploads, new reports |
| Primary CTA | “Resubscribe” → `/billing` |
| Secondary CTA | “Export my data” / “Contact support” |
| Recovery guidance | “Choose a plan to reactivate your account.” |
| Support guidance | “Our team can help with billing questions.” |
| Expected next step | Successful payment → full access restored |

**Current defect:** User sees Properties with “subscription inactive” + 403 storm — **CUSTOMER_EXPERIENCE_GAP** (ALC-001–003).

---

## PAYMENT_REQUIRED (TRIAL_EXPIRED / PAYMENT_PENDING)

| Field | Copy |
|-------|------|
| Heading | “Complete your setup” / “Your trial has ended” |
| Explanation | “Subscribe to continue using Compliance Vault Pro.” |
| Reason | “Payment required” |
| Current account state | “Trial expired” / “Setup incomplete” |
| Available features | Billing, onboarding steps, support |
| Unavailable features | Full compliance workspace |
| Primary CTA | “Choose a plan” → checkout |
| Secondary CTA | “Contact support” |
| Recovery guidance | “Select a plan and enter payment details.” |
| Support guidance | “We can help you choose the right plan.” |
| Expected next step | Checkout success → FULL_ACCESS |

---

## READ_ONLY

| Field | Copy |
|-------|------|
| Heading | “View-only access” |
| Explanation | “You can view and export your data. Subscribe to make changes.” |
| Reason | “Subscription lapsed — read-only retention period” |
| Current account state | “Read-only” |
| Available features | View properties, requirements, reports; export; billing |
| Unavailable features | Edit, upload, generate new reports |
| Primary CTA | “Subscribe to edit” |
| Secondary CTA | “Export data” |
| Recovery guidance | “Renew your subscription to restore editing.” |
| Support guidance | Standard |
| Expected next step | Subscription → FULL_ACCESS |

---

## SUSPENDED

| Field | Copy |
|-------|------|
| Heading | “Account suspended” |
| Explanation | “Your account access has been restricted.” |
| Reason | Payment: “Outstanding payment after grace period.” Ops: “Administrative suspension.” |
| Current account state | “Suspended” |
| Available features | Support; billing (if payment-related) |
| Unavailable features | All operational features |
| Primary CTA | Payment: “Resolve payment” / Ops: “Contact support” |
| Secondary CTA | — |
| Recovery guidance | Per suspension class |
| Support guidance | “Contact support to discuss reinstatement.” |
| Expected next step | Reinstatement → FULL_ACCESS |

---

## ARCHIVED

| Field | Copy |
|-------|------|
| Heading | “Account archived” |
| Explanation | “This account has been closed.” |
| Reason | “Archived by administrator” |
| Current account state | “Archived” |
| Available features | None (customer) |
| Unavailable features | All |
| Primary CTA | “Contact support” |
| Secondary CTA | — |
| Recovery guidance | “Request reinstatement through support.” |
| Support guidance | Support ticket / email |
| Expected next step | Admin reactivation |

---

## ACCOUNT_DELETED

| Field | Copy |
|-------|------|
| Heading | “Account not found” |
| Explanation | “This account has been permanently deleted.” |
| Reason | “Account deleted” |
| Primary CTA | “Create new account” |
| Secondary CTA | “Contact support” |
| Recovery guidance | “Deletion is irreversible.” |
| Expected next step | New registration |

---

## Route → experience map

| Route | FULL_ACCESS | BILLING_RECOVERY | SUSPENDED |
|-------|-------------|------------------|-----------|
| `/today` | Today dashboard | Lifecycle screen | Suspension screen |
| `/properties` | Property list | Read-only or redirect | Redirect |
| `/requirements` | Requirements | Read-only or redirect | Redirect |
| `/reports` | Reports | Read-only download | Redirect |
| `/billing` | Billing | Billing (primary) | Billing if payment |
| `/dashboard` | Dashboard | Recovery overview | Suspension |

**Policy:** Locked routes render lifecycle component — they do **not** mount data hooks that call entitled APIs.

---

## API error presentation policy

| HTTP | Customer sees |
|------|---------------|
| 401 | Login screen with “Session expired” |
| 403 lifecycle | Redirect to portal mode screen — **never** raw `detail` object |
| 403 plan | “Upgrade required” — safe string |
| 429 | “Please wait” — backoff, no retry storm |
| 5xx | “Something went wrong” + support link |

**Forbidden:** Rendering `{ error_code, message, canonical_entitlement_state }` in React children.

---

## Polling and loading policy

| Portal mode | Entitlements poll | Portal-context poll | Notifications poll |
|-------------|-------------------|---------------------|-------------------|
| FULL_ACCESS | On focus | On focus | Normal |
| GRACE | On focus | On focus | Normal |
| BILLING_RECOVERY | **Off** | **Off** | Billing only |
| SUSPENDED | **Off** | **Off** | **Off** |
| ARCHIVED | **Off** | **Off** | **Off** |

Circuit breaker: after 2 consecutive lifecycle 403s, stop polling until manual refresh or mode change.

---

## Cross-channel consistency

Portal headings must match email subject families (via Lifecycle Communication Authority glossary):

| Portal mode | Email family |
|-------------|--------------|
| GRACE | `payment_grace` |
| BILLING_RECOVERY | `subscription_ended` |
| SUSPENDED | `account_suspended` |
| TRIAL_EXPIRED | `trial_ended` |

---

**Outcome:** `ACCOUNT_CUSTOMER_EXPERIENCE_AUTHORITY_COMPLETE`
