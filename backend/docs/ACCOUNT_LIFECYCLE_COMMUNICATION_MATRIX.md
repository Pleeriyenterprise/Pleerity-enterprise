# Account Lifecycle Communication Matrix (ILP-8)

**Policy version:** `account_customer_communication_v1`  
**Source:** Runtime Contract `communication_policy` via `resolve_communication_policy()`

---

## Channel matrix by portal mode

| Portal mode | email_operational | email_billing | sms | portal_notifications | template_family |
|-------------|-------------------|---------------|-----|----------------------|-----------------|
| FULL_ACCESS | ✓ | ✓ | ✓* | ✓ | operational |
| GRACE | ✓ | ✓ | ✓* | ✓ | payment_grace |
| BILLING_RECOVERY | ✗ | ✓ | ✗ | ✗ | subscription_ended |
| PAYMENT_REQUIRED | ✗ | ✓ | ✗ | ✗ | payment_required |
| READ_ONLY | ✓ | ✓ | ✗ | ✓ | read_only |
| SUSPENDED | ✗ | ✓ | ✗ | ✗ | suspended |
| ARCHIVED | ✗ | ✓ | ✗ | ✗ | archived |
| ACCOUNT_DELETED | ✗ | ✓ | ✗ | ✗ | deleted |

\* SMS additionally requires lifecycle in ACTIVE, TRIAL, GRACE_PERIOD, CANCELLATION_SCHEDULED.

---

## ILP-8 suppression overlay

Even when policy allows a channel, the Communication Authority may suppress:

| Surface | Suppressed when |
|---------|-----------------|
| Operational email | Billing recovery, suspended, archived, deleted |
| Operational SMS | READ_ONLY and restricted lifecycles |
| Upgrade / renewal spam | Billing recovery active (operational category) |

---

## Template category → policy key

| Template signal | Policy key |
|-----------------|------------|
| `email_category: compliance` | email_operational |
| `email_category: billing` | email_billing |
| `SUBSCRIPTION_RENEWAL_*` | email_billing |
| `channel: sms` | sms |
| in_app / push | portal_notifications |

---

## Lifecycle placeholders (templates)

| Placeholder | Content |
|-------------|---------|
| `lifecycle_message` | Governed explanation |
| `lifecycle_cta` | Primary CTA label |
| `lifecycle_status` | Current state label |
| `recovery_url` | Primary CTA route |
| `portal_mode` | Portal mode |
| `lifecycle_state` | Lifecycle state |

---

## Requirement-level vs account-level

| Layer | Module | Scope |
|-------|--------|-------|
| Account lifecycle | `account_customer_communication_authority` | Subscription, billing, portal mode |
| Requirement lifecycle | `lifecycle_communication/` | Compliance requirement families |

Both may apply to a single email (account shell + requirement body).
