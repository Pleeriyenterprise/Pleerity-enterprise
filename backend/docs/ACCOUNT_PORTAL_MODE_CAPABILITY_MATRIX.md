# Account Portal Mode Capability Matrix

**Programme:** ACCOUNT-LIFECYCLE-CAPABILITY-AUTHORITY-01  
**Authority version:** `account_capability_v1`  
**Parent:** `ACCOUNT_PORTAL_MODE_AUTHORITY.md`, `ACCOUNT_CAPABILITY_AUTHORITY.md`

**Policy:** Portal mode **consumes** capability grants. It never decides permissions independently.

---

## Resolution flow

```
account_lifecycle_state → base grants (ACCOUNT_CAPABILITY_MATRIX)
portal_mode → UI overlay (visibility, polling, CTAs) — NOT permission source
effective_grant = base_grant (portal mode may only restrict further, never expand)
```

---

## FULL_ACCESS

| Capability domain | Grant | UI overlay |
|-------------------|-------|------------|
| Operational (prop, req, doc, today) | A / P | Full navigation |
| Billing | A | Standard |
| Reports | A / P | Full catalog |
| Background | A / P | Jobs continue |
| Polling | A | Enabled |

**Banner overlays:** TRIAL conversion, CANCELLATION_SCHEDULED date, PAYMENT_FAILED warning.

---

## GRACE

| Capability domain | Grant | UI overlay |
|-------------------|-------|------------|
| Operational | A / L | Grace banner |
| CAP_REQ_RESOLVE, CAP_TODAY_ACT | L | Limited side-effects |
| Billing | A | Payment CTA prominent |
| Background | A | Continue |
| Polling | A | Enabled |

---

## BILLING_RECOVERY

| Capability domain | Grant | UI overlay |
|-------------------|-------|------------|
| CAP_BILLING_* | A | Primary surface |
| CAP_SUB_RENEW, CAP_ACCOUNT_RECOVERY | A | Resubscribe CTA |
| CAP_PROP_VIEW, CAP_REQ_VIEW, CAP_REPORT_VIEW | R | Read-only routes |
| CAP_PROP_EDIT, CAP_DOC_UPLOAD, CAP_TODAY_* | D / H | Locked; lifecycle screen |
| CAP_DATA_EXPORT | R | Secondary CTA |
| CAP_SUPPORT_* | A | Support guidance |
| Background | D | Paused |
| Polling | D | **Disabled** (circuit breaker) |

---

## PAYMENT_REQUIRED

| Capability domain | Grant | UI overlay |
|-------------------|-------|------------|
| CAP_BILLING_CHECKOUT | A | Checkout funnel |
| Onboarding CAP_* | L | Onboarding scope only |
| Operational | D / H | Hidden until payment |
| Background | D | Paused |
| Polling | D | Disabled |

---

## READ_ONLY

| Capability domain | Grant | UI overlay |
|-------------------|-------|------------|
| View capabilities | R | Read routes visible |
| Write capabilities | D | Edit actions hidden |
| CAP_SUB_RENEW | A | Upgrade CTA |
| CAP_DATA_EXPORT | R | Export CTA |
| Background | D | Paused |
| Polling | R | Minimal (read surfaces only) |

---

## SUSPENDED

| Capability domain | Grant | UI overlay |
|-------------------|-------|------------|
| Operational | D / H | Suspension screen |
| CAP_BILLING_* | A* | *If payment suspension |
| CAP_SUPPORT_* | A | Contact support |
| Background | D | Paused |
| Polling | D | Disabled |

---

## ARCHIVED

| Capability domain | Grant | UI overlay |
|-------------------|-------|------------|
| All customer CAP_* | D | Pre-auth deny screen |
| CAP_SUPPORT_REQUEST | A | Contact support only |
| Background | D | Terminated |
| Polling | D | Disabled |

---

## ACCOUNT_DELETED

| Capability domain | Grant | UI overlay |
|-------------------|-------|------------|
| All CAP_* | D | Deleted account screen |
| CAP_AUTH_LOGIN | D | Sign-in denied |
| Background | D | Terminated |

---

## Portal mode × navigation visibility

| Route | FULL | GRACE | BILLING_REC | PAY_REQ | READ_ONLY | SUSP | ARCH |
|-------|------|-------|-------------|---------|-----------|------|------|
| /today | Show | Show | Hide→recovery | Hide | Hide | Hide | Hide |
| /properties | Show | Show | Read | Hide | Read | Hide | Hide |
| /requirements | Show | Show | Read | Hide | Read | Hide | Hide |
| /reports | Show | Show | Read | Hide | Read | Hide | Hide |
| /settings/billing | Show | Show | Show | Show | Show | Show* | Hide |
| /dashboard | Show | Show | Recovery | Onboarding | Read | Hide | Hide |

Navigation Authority receives **effective grants** — not portal_mode string alone.

---

## Current gap (audit)

Frontend uses `hasFeature` without portal mode overlay → **PORTAL_MODE_GAP** (ACA-005). Implementation: ILP-3 consumes this matrix via lifecycle-contract.

---

**Outcome:** `ACCOUNT_PORTAL_MODE_CAPABILITY_MATRIX_COMPLETE`
