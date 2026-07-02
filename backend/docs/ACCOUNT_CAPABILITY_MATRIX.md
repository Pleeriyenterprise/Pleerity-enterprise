# Account Capability Matrix

**Programme:** ACCOUNT-LIFECYCLE-CAPABILITY-AUTHORITY-01  
**Authority version:** `account_capability_v1`  
**Parent:** `ACCOUNT_CAPABILITY_AUTHORITY.md`

Maps every **capability** against every **lifecycle state**. Portal mode overlays in `ACCOUNT_PORTAL_MODE_CAPABILITY_MATRIX.md`.

## Grant legend

| Code | Meaning |
|------|---------|
| **A** | ALLOW (full) |
| **R** | READ only |
| **D** | DENY |
| **H** | HIDDEN |
| **P** | PLAN_GATED (lifecycle allows; plan may block) |
| **L** | LIMITED (grace side-effects) |
| **N** | N/A |

---

## Matrix: core customer capabilities

| Capability | ACTIVE | TRIAL | TRIAL_EXP | PAY_PEND | PAY_FAIL | GRACE | CANCEL_SCHED | CANCEL_IMM | SUB_EXP | READ_ONLY | SUSP | ARCH | DELETED | UNKNOWN | LEGACY |
|------------|--------|-------|-----------|----------|----------|-------|--------------|------------|---------|-----------|------|------|---------|---------|--------|
| CAP_AUTH_LOGIN | A | A | A | A | A | A | A | A | A | A | A* | D | D | A | A |
| CAP_PROP_VIEW | A | A | R | L | A | A | A | R | R | R | D | D | D | D | R |
| CAP_PROP_CREATE | A | A | D | L | A | L | A | D | D | D | D | D | D | D | D |
| CAP_PROP_EDIT | A | A | D | L | A | L | A | D | D | D | D | D | D | D | D |
| CAP_REQ_VIEW | A | A | R | L | A | A | A | R | R | R | D | D | D | D | R |
| CAP_REQ_RESOLVE | A | A | D | L | A | L | A | D | D | D | D | D | D | D | D |
| CAP_DOC_UPLOAD | P | P | D | L | P | L | P | D | D | D | D | D | D | D | D |
| CAP_DOC_VIEW | A | A | R | L | A | A | A | R | R | R | D | D | D | D | R |
| CAP_EVIDENCE_DOWNLOAD | A | A | R | D | A | A | A | R | R | R | D | D | D | D | R |
| CAP_REPORT_VIEW | A | A | R | D | A | A | A | R | R | R | D | D | D | D | R |
| CAP_REPORT_GENERATE_PDF | P | P | D | D | P | L | P | D | D | D | D | D | D | D | D |
| CAP_REPORT_DOWNLOAD | A | A | R | D | A | A | A | R | R | R | D | D | D | D | R |
| CAP_DASHBOARD_VIEW | A | A | D | D | A | A | A | D | D | R | D | D | D | D | R |
| CAP_TODAY_VIEW | A | A | D | D | A | A | A | D | D | D | D | D | D | D | D |
| CAP_TODAY_ACT | A | A | D | D | A | L | A | D | D | D | D | D | D | D | D |
| CAP_CMD_CTR_VIEW | A | A | D | D | A | A | A | D | D | R | D | D | D | D | R |
| CAP_SCORE_VIEW | A | A | R | D | A | A | A | R | R | R | D | D | D | D | R |
| CAP_BILLING_VIEW | A | A | A | A | A | A | A | A | A | A | A* | D | D | A | A |
| CAP_SUB_MANAGE | A | A | A | A | A | A | A | A | A | A | A* | D | D | A | A |
| CAP_SUB_RENEW | N | N | A | A | N | N | A | A | A | A | A* | D | D | A | A |
| CAP_DATA_EXPORT | A | A | R | D | A | A | A | R | R | R | D | D | D | D | R |
| CAP_SUPPORT_ACCESS | A | A | A | A | A | A | A | A | A | A | A | A | D | A | A |
| CAP_NOTIF_EMAIL | A | A | D | D | A | A | A | D | D | D | D | D | D | D | D |
| CAP_NOTIF_SMS | P | P | D | D | P | P | P | D | D | D | D | D | D | D | D |
| CAP_AI_ASSISTANT | P | P | D | D | P | L | P | D | D | D | D | D | D | D | D |
| CAP_OPS_MAINTENANCE | P | P | D | D | P | L | P | D | D | D | D | D | D | D | D |
| CAP_TENANT_PORTAL | P | P | D | D | P | L | P | D | D | D | D | D | D | D | D |

\* SUSPENDED: payment-related suspension may allow login + billing only.

---

## Matrix: background capabilities

| Capability | ACTIVE | TRIAL | GRACE | CANCEL_SCHED | CANCEL_IMM | SUB_EXP | READ_ONLY | SUSP | ARCH | DELETED |
|------------|--------|-------|-------|--------------|------------|---------|-----------|------|------|---------|
| CAP_BG_REMINDERS | A | A | A | A | D | D | D | D | D | D |
| CAP_BG_DIGEST | A | A | A | A | D | D | D | D | D | D |
| CAP_BG_SCHEDULED_REPORTS | P | P | P | P | D | D | D | D | D | D |
| CAP_BG_COMPLIANCE_CHECK | A | A | A | A | D | D | D | D | D | D |
| CAP_BG_SCORE_RECALC | A | A | A | A | D | D | D | D | D | D |
| CAP_BG_RISK_RECALC | P | P | P | P | D | D | D | D | D | D |
| CAP_BG_LIFECYCLE_SYNC | A | A | A | A | A | A | A | A | D | D |

---

## Alignment with ALPA policy matrix

This matrix **operationalises** `ACCOUNT_LIFECYCLE_POLICY_MATRIX.md`:

| ALPA code | ACA grant |
|-----------|-----------|
| FULL | A or P |
| READ | R |
| DENY | D |
| LIMITED | L |
| BILLING | Billing CAP_* only A; others D or R |
| ADMIN | Customer D; admin console separate |

---

## Policy gaps (current platform)

| Gap | State | Issue |
|-----|-------|-------|
| CM-001 | READ_ONLY | No platform band; SUSPENDED/CANCELLED maps to full DENY |
| CM-002 | BILLING_RECOVERY | Read tier (R) not implemented; APIs return D |
| CM-003 | GRACE | L grants not distinguished in frontend |

---

**Outcome:** `ACCOUNT_CAPABILITY_MATRIX_COMPLETE`
