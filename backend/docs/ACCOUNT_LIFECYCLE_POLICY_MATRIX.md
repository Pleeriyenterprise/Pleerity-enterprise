# Account Lifecycle Policy Matrix

**Programme:** ACCOUNT-LIFECYCLE-POLICY-AUTHORITY-01  
**Authority version:** `account_lifecycle_policy_v1`  
**Parent:** `ACCOUNT_LIFECYCLE_POLICY_AUTHORITY.md`

---

## Permission legend

| Code | Meaning |
|------|---------|
| **FULL** | Normal entitled operation |
| **READ** | View/export only; no mutations |
| **DENY** | Not available; intentional lifecycle screen (not API storm) |
| **BILLING** | Billing/subscription surfaces only |
| **LIMITED** | Plan-gated subset; grace side-effects blocked |
| **ADMIN** | Admin console only |
| **N/A** | Not applicable in this state |

---

## Policy matrix by lifecycle state

### ACTIVE

| Capability | Policy |
|------------|--------|
| Authentication | FULL |
| Portal access | FULL |
| Navigation | FULL (Navigation Authority) |
| Sidebar visibility | FULL |
| Dashboard visibility | FULL |
| Property visibility | FULL |
| Property editing | FULL |
| Requirement viewing | FULL |
| Requirement editing | FULL |
| Document upload | FULL |
| Document viewing | FULL |
| Evidence viewing | FULL |
| Evidence download | FULL |
| Report viewing | FULL |
| Report generation | FULL |
| Report download | FULL |
| Timeline viewing | FULL |
| Audit history | FULL |
| Score visibility | FULL (Score Authority) |
| Risk visibility | FULL |
| Compliance monitoring | Continue |
| Notifications | FULL |
| Reminder generation | Continue |
| Scheduled reports | Continue |
| Monthly digest | Continue |
| Automation | Continue |
| Background processing | Continue |
| Queue processing | Continue |
| Billing | FULL |
| Invoices | FULL |
| Subscription management | FULL |
| Exports | FULL |
| Support actions | FULL |
| AI features | Per plan |
| API access | FULL |
| Admin visibility | ADMIN |
| Reactivation eligibility | N/A |
| Data retention | Standard |
| Recovery options | N/A |

**Portal mode:** `FULL_ACCESS`

---

### TRIAL

| Capability | Policy |
|------------|--------|
| Authentication | FULL |
| Portal access | FULL |
| Navigation | FULL |
| Sidebar visibility | FULL |
| Dashboard visibility | FULL |
| Property visibility | FULL |
| Property editing | FULL |
| Requirement viewing | FULL |
| Requirement editing | FULL |
| Document upload | FULL |
| Document viewing | FULL |
| Evidence viewing | FULL |
| Evidence download | FULL |
| Report viewing | FULL |
| Report generation | FULL |
| Report download | FULL |
| Timeline viewing | FULL |
| Audit history | FULL |
| Score visibility | FULL |
| Risk visibility | FULL |
| Compliance monitoring | Continue |
| Notifications | FULL |
| Reminder generation | Continue |
| Scheduled reports | Continue |
| Monthly digest | Continue |
| Automation | Continue |
| Background processing | Continue |
| Queue processing | Continue |
| Billing | FULL (upgrade path) |
| Invoices | READ if issued |
| Subscription management | FULL (convert trial) |
| Exports | FULL |
| Support actions | FULL |
| AI features | Per plan |
| API access | FULL |
| Admin visibility | ADMIN |
| Reactivation eligibility | N/A |
| Data retention | Standard |
| Recovery options | Convert to paid |

**Portal mode:** `FULL_ACCESS` (trial banner)

---

### TRIAL_EXPIRED

| Capability | Policy |
|------------|--------|
| Authentication | FULL |
| Portal access | BILLING |
| Navigation | BILLING + profile only |
| Sidebar visibility | LIMITED (billing, profile, support) |
| Dashboard visibility | DENY (lifecycle screen) |
| Property visibility | READ (export window 30 days policy) |
| Property editing | DENY |
| Requirement viewing | READ |
| Requirement editing | DENY |
| Document upload | DENY |
| Document viewing | READ |
| Evidence viewing | READ |
| Evidence download | READ |
| Report viewing | READ (existing reports) |
| Report generation | DENY |
| Report download | READ |
| Timeline viewing | READ |
| Audit history | READ |
| Score visibility | READ (last computed) |
| Risk visibility | READ |
| Compliance monitoring | Pause |
| Notifications | Billing conversion only |
| Reminder generation | Pause |
| Scheduled reports | Pause |
| Monthly digest | Pause |
| Automation | Pause |
| Background processing | Pause |
| Queue processing | Drain then pause |
| Billing | FULL |
| Invoices | READ |
| Subscription management | FULL (start subscription) |
| Exports | READ (data export) |
| Support actions | FULL |
| AI features | DENY |
| API access | BILLING endpoints only |
| Admin visibility | ADMIN |
| Reactivation eligibility | Trial conversion or new subscription |
| Data retention | 90 days then READ_ONLY policy |
| Recovery options | Subscribe |

**Portal mode:** `PAYMENT_REQUIRED`

---

### PAYMENT_PENDING

| Capability | Policy |
|------------|--------|
| Authentication | FULL |
| Portal access | BILLING |
| Navigation | Onboarding + billing |
| Sidebar visibility | LIMITED |
| Dashboard visibility | DENY until payment complete |
| Property visibility | LIMITED (onboarding scope) |
| Property editing | LIMITED |
| Requirement viewing | LIMITED |
| Requirement editing | LIMITED |
| Document upload | LIMITED |
| Document viewing | LIMITED |
| Evidence viewing | LIMITED |
| Evidence download | DENY |
| Report viewing | DENY |
| Report generation | DENY |
| Report download | DENY |
| Timeline viewing | READ |
| Audit history | READ |
| Score visibility | DENY |
| Risk visibility | DENY |
| Compliance monitoring | Pause |
| Notifications | Onboarding + payment only |
| Reminder generation | Pause |
| Scheduled reports | Pause |
| Monthly digest | Pause |
| Automation | Pause |
| Background processing | Pause |
| Queue processing | Pause |
| Billing | FULL |
| Invoices | DENY |
| Subscription management | FULL (complete checkout) |
| Exports | DENY |
| Support actions | FULL |
| AI features | DENY |
| API access | Onboarding endpoints only |
| Admin visibility | ADMIN |
| Reactivation eligibility | Complete payment |
| Data retention | Standard |
| Recovery options | Complete checkout |

**Portal mode:** `PAYMENT_REQUIRED`

---

### PAYMENT_FAILED

| Capability | Policy |
|------------|--------|
| Authentication | FULL |
| Portal access | FULL with banner |
| Navigation | FULL |
| Sidebar visibility | FULL |
| Dashboard visibility | FULL |
| Property visibility | FULL |
| Property editing | FULL |
| Requirement viewing | FULL |
| Requirement editing | FULL |
| Document upload | FULL |
| Document viewing | FULL |
| Evidence viewing | FULL |
| Evidence download | FULL |
| Report viewing | FULL |
| Report generation | FULL |
| Report download | FULL |
| Timeline viewing | FULL |
| Audit history | FULL |
| Score visibility | FULL |
| Risk visibility | FULL |
| Compliance monitoring | Continue |
| Notifications | Payment failure + retry |
| Reminder generation | Continue |
| Scheduled reports | Continue |
| Monthly digest | Continue |
| Automation | Continue |
| Background processing | Continue |
| Queue processing | Continue |
| Billing | FULL |
| Invoices | FULL |
| Subscription management | FULL (update payment method) |
| Exports | FULL |
| Support actions | FULL |
| AI features | Per plan |
| API access | FULL |
| Admin visibility | ADMIN |
| Reactivation eligibility | Payment method update |
| Data retention | Standard |
| Recovery options | Retry payment |

**Portal mode:** `FULL_ACCESS` (payment warning banner)

---

### GRACE_PERIOD

| Capability | Policy |
|------------|--------|
| Authentication | FULL |
| Portal access | FULL with grace banner |
| Navigation | FULL |
| Sidebar visibility | FULL |
| Dashboard visibility | FULL |
| Property visibility | FULL |
| Property editing | LIMITED (no new side-effect automations) |
| Requirement viewing | FULL |
| Requirement editing | LIMITED |
| Document upload | FULL |
| Document viewing | FULL |
| Evidence viewing | FULL |
| Evidence download | FULL |
| Report viewing | FULL |
| Report generation | FULL |
| Report download | FULL |
| Timeline viewing | FULL |
| Audit history | FULL |
| Score visibility | FULL |
| Risk visibility | FULL |
| Compliance monitoring | Continue (read) |
| Notifications | Grace + payment recovery |
| Reminder generation | Continue |
| Scheduled reports | Continue |
| Monthly digest | Continue |
| Automation | LIMITED (no new destructive) |
| Background processing | Continue |
| Queue processing | Continue |
| Billing | FULL |
| Invoices | FULL |
| Subscription management | FULL |
| Exports | FULL |
| Support actions | FULL |
| AI features | Per plan |
| API access | FULL |
| Admin visibility | ADMIN |
| Reactivation eligibility | Payment recovery |
| Data retention | Standard |
| Recovery options | Update payment method |

**Portal mode:** `GRACE`

---

### CANCELLATION_SCHEDULED

| Capability | Policy |
|------------|--------|
| Authentication | FULL |
| Portal access | FULL |
| Navigation | FULL |
| Sidebar visibility | FULL |
| Dashboard visibility | FULL |
| Property visibility | FULL |
| Property editing | FULL |
| Requirement viewing | FULL |
| Requirement editing | FULL |
| Document upload | FULL |
| Document viewing | FULL |
| Evidence viewing | FULL |
| Evidence download | FULL |
| Report viewing | FULL |
| Report generation | FULL |
| Report download | FULL |
| Timeline viewing | FULL |
| Audit history | FULL |
| Score visibility | FULL |
| Risk visibility | FULL |
| Compliance monitoring | Continue |
| Notifications | Renewal/cancellation info only |
| Reminder generation | Continue until expiry |
| Scheduled reports | Continue until expiry |
| Monthly digest | Continue until expiry |
| Automation | Continue until expiry |
| Background processing | Continue until expiry |
| Queue processing | Continue until expiry |
| Billing | FULL (resume subscription) |
| Invoices | FULL |
| Subscription management | FULL (undo cancellation) |
| Exports | FULL |
| Support actions | FULL |
| AI features | Per plan |
| API access | FULL |
| Admin visibility | ADMIN |
| Reactivation eligibility | Resume before period end |
| Data retention | Standard |
| Recovery options | Resume subscription |

**Portal mode:** `FULL_ACCESS` (cancellation scheduled banner)

---

### CANCELLED_IMMEDIATE

| Capability | Policy |
|------------|--------|
| Authentication | FULL |
| Portal access | BILLING |
| Navigation | BILLING + profile + support |
| Sidebar visibility | LIMITED |
| Dashboard visibility | DENY |
| Property visibility | READ (export window) |
| Property editing | DENY |
| Requirement viewing | READ |
| Requirement editing | DENY |
| Document upload | DENY |
| Document viewing | READ |
| Evidence viewing | READ |
| Evidence download | READ |
| Report viewing | READ |
| Report generation | DENY |
| Report download | READ |
| Timeline viewing | READ |
| Audit history | READ |
| Score visibility | READ |
| Risk visibility | READ |
| Compliance monitoring | Pause |
| Notifications | Reactivation/billing only |
| Reminder generation | Pause |
| Scheduled reports | Revoke |
| Monthly digest | Pause |
| Automation | Pause |
| Background processing | Pause |
| Queue processing | Drain then pause |
| Billing | FULL |
| Invoices | READ |
| Subscription management | FULL (resubscribe) |
| Exports | READ |
| Support actions | FULL |
| AI features | DENY |
| API access | BILLING only |
| Admin visibility | ADMIN |
| Reactivation eligibility | Resubscribe |
| Data retention | 12 months standard |
| Recovery options | New subscription |

**Portal mode:** `BILLING_RECOVERY`

---

### SUBSCRIPTION_EXPIRED

| Capability | Policy |
|------------|--------|
| Authentication | FULL |
| Portal access | BILLING or READ_ONLY (policy tier) |
| Navigation | Per portal mode |
| Sidebar visibility | LIMITED |
| Dashboard visibility | DENY or READ lifecycle screen |
| Property visibility | READ |
| Property editing | DENY |
| Requirement viewing | READ |
| Requirement editing | DENY |
| Document upload | DENY |
| Document viewing | READ |
| Evidence viewing | READ |
| Evidence download | READ |
| Report viewing | READ |
| Report generation | DENY |
| Report download | READ |
| Timeline viewing | READ |
| Audit history | READ |
| Score visibility | READ |
| Risk visibility | READ |
| Compliance monitoring | Pause |
| Notifications | Renewal only |
| Reminder generation | Pause |
| Scheduled reports | Pause |
| Monthly digest | Pause |
| Automation | Pause |
| Background processing | Pause |
| Queue processing | Pause |
| Billing | FULL |
| Invoices | READ |
| Subscription management | FULL (renew) |
| Exports | READ |
| Support actions | FULL |
| AI features | DENY |
| API access | BILLING + read APIs |
| Admin visibility | ADMIN |
| Reactivation eligibility | Renew subscription |
| Data retention | 12 months |
| Recovery options | Renew |

**Portal mode:** `BILLING_RECOVERY` or `READ_ONLY` (configurable tier)

---

### READ_ONLY

| Capability | Policy |
|------------|--------|
| Authentication | FULL |
| Portal access | READ |
| Navigation | Read routes only |
| Sidebar visibility | READ sections |
| Dashboard visibility | READ |
| Property visibility | READ |
| Property editing | DENY |
| Requirement viewing | READ |
| Requirement editing | DENY |
| Document upload | DENY |
| Document viewing | READ |
| Evidence viewing | READ |
| Evidence download | READ |
| Report viewing | READ |
| Report generation | DENY |
| Report download | READ |
| Timeline viewing | READ |
| Audit history | READ |
| Score visibility | READ |
| Risk visibility | READ |
| Compliance monitoring | Pause |
| Notifications | Renewal/reactivation only |
| Reminder generation | Pause |
| Scheduled reports | Pause |
| Monthly digest | Pause |
| Automation | Pause |
| Background processing | Pause |
| Queue processing | Pause |
| Billing | FULL |
| Invoices | READ |
| Subscription management | FULL (upgrade) |
| Exports | READ |
| Support actions | FULL |
| AI features | DENY |
| API access | Read + billing |
| Admin visibility | ADMIN |
| Reactivation eligibility | Subscribe |
| Data retention | Extended (24 months) |
| Recovery options | Subscribe |

**Portal mode:** `READ_ONLY`

**Policy gap (current):** No first-class `READ_ONLY` band exists today; maps to `SUSPENDED`/`CANCELLED` with API deny — **POLICY_GAP**.

---

### SUSPENDED

| Capability | Policy |
|------------|--------|
| Authentication | FULL or DENY (suspension class) |
| Portal access | DENY operational |
| Navigation | Support + billing if payment-related |
| Sidebar visibility | MINIMAL |
| Dashboard visibility | DENY |
| Property visibility | DENY or READ (admin reinstatement path) |
| Property editing | DENY |
| Requirement viewing | DENY or READ |
| Requirement editing | DENY |
| Document upload | DENY |
| Document viewing | DENY or READ |
| Evidence viewing | DENY or READ |
| Evidence download | DENY |
| Report viewing | DENY |
| Report generation | DENY |
| Report download | DENY |
| Timeline viewing | READ |
| Audit history | ADMIN |
| Score visibility | DENY |
| Risk visibility | DENY |
| Compliance monitoring | Pause |
| Notifications | Suspension notice + recovery |
| Reminder generation | Pause |
| Scheduled reports | Pause |
| Monthly digest | Pause |
| Automation | Pause |
| Background processing | Pause |
| Queue processing | Pause |
| Billing | FULL if payment suspension |
| Invoices | READ |
| Subscription management | Per suspension reason |
| Exports | ADMIN or policy window |
| Support actions | FULL |
| AI features | DENY |
| API access | DENY (billing exempt) |
| Admin visibility | ADMIN |
| Reactivation eligibility | Per suspension class |
| Data retention | Standard |
| Recovery options | Payment or admin reinstatement |

**Portal mode:** `SUSPENDED`

---

### ARCHIVED

| Capability | Policy |
|------------|--------|
| Authentication | DENY |
| Portal access | DENY |
| Navigation | N/A |
| Sidebar visibility | N/A |
| Dashboard visibility | DENY |
| Property visibility | ADMIN |
| Property editing | DENY |
| Requirement viewing | ADMIN |
| Requirement editing | DENY |
| Document upload | DENY |
| Document viewing | ADMIN |
| Evidence viewing | ADMIN |
| Evidence download | ADMIN |
| Report viewing | ADMIN |
| Report generation | DENY |
| Report download | ADMIN |
| Timeline viewing | ADMIN |
| Audit history | ADMIN |
| Score visibility | ADMIN |
| Risk visibility | ADMIN |
| Compliance monitoring | Terminate |
| Notifications | Archive notice only |
| Reminder generation | Terminate |
| Scheduled reports | Terminate |
| Monthly digest | Terminate |
| Automation | Terminate |
| Background processing | Terminate |
| Queue processing | Terminate |
| Billing | DENY |
| Invoices | ADMIN |
| Subscription management | DENY |
| Exports | ADMIN |
| Support actions | Contact support |
| AI features | DENY |
| API access | DENY |
| Admin visibility | ADMIN |
| Reactivation eligibility | Admin reactivation |
| Data retention | Until purge eligible |
| Recovery options | Admin reinstatement |

**Portal mode:** `ARCHIVED`

---

### ACCOUNT_DELETED

| Capability | Policy |
|------------|--------|
| Authentication | DENY |
| Portal access | DENY |
| All customer capabilities | DENY |
| Admin visibility | Purge audit only |
| Data retention | Purged per policy |
| Recovery options | None (irreversible) |

**Portal mode:** `ACCOUNT_DELETED`

---

### UNKNOWN

| Capability | Policy |
|------------|--------|
| Authentication | FULL (if JWT valid) |
| Portal access | DENY operational |
| All mutations | DENY |
| Billing | BILLING (safe recovery) |
| Support actions | FULL |
| Admin visibility | ADMIN |

**Portal mode:** `BILLING_RECOVERY` (safe default)

---

### LEGACY

| Capability | Policy |
|------------|--------|
| Authentication | FULL |
| Portal access | READ + BILLING |
| Operational features | READ until migrated |
| Billing | FULL (migration path) |
| Background processing | Pause until resolved |
| Admin visibility | ADMIN |

**Portal mode:** `READ_ONLY` until migration completes

---

## Cross-reference: canonical band mapping (implementation bridge)

| Policy state | Current `canonical_entitlement_state` | Notes |
|--------------|--------------------------------------|-------|
| ACTIVE, TRIAL, CANCELLATION_SCHEDULED, PAYMENT_FAILED (pre-grace) | ENABLED | |
| GRACE_PERIOD, PAYMENT_FAILED (in grace) | GRACE | |
| SUBSCRIPTION_EXPIRED, TRIAL_EXPIRED, SUSPENDED (billing) | SUSPENDED | |
| CANCELLED_IMMEDIATE | CANCELLED | |
| READ_ONLY | **None** | POLICY_GAP |
| ARCHIVED, ACCOUNT_DELETED | org lifecycle | Orthogonal to billing band |

---

**Outcome:** `ACCOUNT_LIFECYCLE_POLICY_MATRIX_COMPLETE`
