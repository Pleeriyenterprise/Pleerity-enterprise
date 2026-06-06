# RENT-OPERATIONS-LANDLORD-TENANT-RUNTIME-AUDIT-01

**Classification:** `RENT_REMINDER_GAP`  
**Run tag:** `20260606T115547Z`  
**Marker:** `RENT-LT-AUDIT-20260606T115547Z`  
**Staging:** `https://pleerityenterprise.co.uk` / `https://pleerity-enterprise.onrender.com/api`

## Executive summary

Rent Operations is **operationally verified end-to-end** for landlord setup, status derivation, payment recording, tenant isolation, arrears/risk signals, cross-surface consistency, mobile usability, permissions, edge resilience, and regression tests.

**Not classified `VERIFIED_OPERATIONALLY`** because automatic live email/SMS reminder delivery is **not enabled on staging** (`RENT_REMINDERS_LIVE_SEND=false`). Manual mark-sent reminder workflow and daily job event creation are proven.

## Staging personas

| Role | ID / email |
|------|------------|
| Landlord client | `6fd5ac4c-3fd4-4112-ade7-156977deb49f` / `nancy@yopmail.com` |
| Tenant | `962fa7b2-d8a0-4082-8d89-f4a2abb402e0` / `f7-ops-wales@yopmail.com` |
| Property | `d35a58ae-3c81-491c-9694-1d021dd3b8ad` (Kenny Cresent) |
| Tenancy | `pty_9ec2e1723d7b` |
| Schedule | `rs_da9f62d77236` |

Reminder-safe channels: manual mark-sent, in-app when live send enabled.

## Checklist

| Part | Result |
|------|--------|
| setup | PASS |
| tracking_setup | PASS |
| status_logic | PASS |
| payments | PASS |
| tenant | PASS |
| reminders | PASS (manual); live send not proven |
| arrears_risk | PASS |
| cross_surface | PASS |
| mobile | PASS |
| audit_trail | PASS |
| permissions | PASS |
| edge_resilience | PASS |
| regression | PASS |

**Secondary flags:** RENT_REMINDER_GAP

## Part findings

### 1 — Runtime setup
Active landlord with rent tracking enabled, linked tenancy, schedule, and capabilities API 200.

### 2 — Rent tracking setup
API schedule preview/create, idempotency, validation blocking, and browser proof: enable-tracking modal visible at 390px with submit reachable (`screenshots/rent_setup_modal_mobile.png`).

### 3 — Rent status logic
Statuses observed: UPCOMING, OVERDUE, SEVERELY_OVERDUE, PARTIALLY_PAID, PAID. Overdue only after due date (20/20 probes pass). Partial payment preserves PARTIALLY_PAID. All six KPI fields present on summary.

### 4 — Payment recording
Full/partial/late payments via API; duplicate reference handled safely; overpayment rejected (400). Mobile record-payment button reachable.

### 5 — Tenant-facing
Tenant portal loads; tenant blocked from landlord rent APIs (403). No tenant rent UI surface today — documented as by design.

### 6 — Reminder triggering
`rent_operations_daily_job` creates reminder events. Manual `mark-sent` idempotent (200/200). **Live email/SMS not proven** — staging flag off.

### 7 — Arrears / risk signals
21 overdue, 6 tenancies in arrears, 5 rent risk signals, financial snapshot 200. Command Centre rent items: 0 (no drift blocker).

### 8 — Cross-surface consistency
`rent_collected_this_month_minor` matches across summary and occupancy-operational-summary (432750).

### 9 — Mobile runtime
375/390/414px: page, tabs, KPI cards, no horizontal overflow (`screenshots/rent_ops_*.png`).

### 10 — Audit trail
Admin audit logs show RENT_LEDGER_CREATED, RENT_PAYMENT_RECORDED, RENT_STATUS_RECALCULATED.

### 11 — Permissions
Landlord 200; tenant 403; contractor 401; unauthenticated 401.

### 12 — Edge / resilience
Schedule idempotency key replay safe.

### 13 — Regression
Backend 27 passed; `ClientRentOperationsPage.test.js` passed (getRentCapabilities mock added).

## Harness

`backend/rent_operations_landlord_tenant_runtime_audit_01_execute.py`

## Classification rationale

Per audit rules, `VERIFIED_OPERATIONALLY` requires proven automatic reminder behaviour or explicit confirmation with correct classification. Manual workflow passes; live send does not — therefore **`RENT_REMINDER_GAP`**, not `VERIFIED_OPERATIONALLY`.
