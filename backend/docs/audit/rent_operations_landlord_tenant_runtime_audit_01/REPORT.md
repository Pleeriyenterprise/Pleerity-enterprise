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

---

## RENT-REMINDER-LIVE-DELIVERY-CLOSEOUT-01 closeout (20260606T123538Z)

**Classification:** `PARTIAL`

### Closeout checklist
- setup: PASS
- due_delivery: FAIL
- overdue_delivery: FAIL
- suppression: PASS
- partial_payment: PASS
- audit_delivery: PASS
- tenant_visibility: PASS
- retry: FAIL
- regression: PASS

**Blockers:** due_delivery, overdue_delivery, retry

Local mongo probe: `skipped`

### Closeout implementation delivered
- Safe live send guards: client allowlist, yopmail recipient domain guard, tenant email resolution
- `RENT_REMINDER` notification template seeded
- `render.yaml` staging env: `RENT_REMINDERS_LIVE_SEND`, client allowlist, safe domains
- Harness: `backend/rent_reminder_live_delivery_closeout_01_execute.py` (step-up + confirmation for job runs)

### Runtime blockers observed
- Admin scoped job runs returned **403** (missing step-up; fixed in harness) then **429 rate limit** after repeated closeout probes
- Staging not yet redeployed with live-send env + template seed at time of run
- Existing reminder events on pilot ledgers show `delivery_status: manual` from pre-live era

### Re-run after deploy
1. Confirm Render deploy includes env vars and commit
2. Wait for admin job rate limit window to clear
3. `python rent_reminder_live_delivery_closeout_01_execute.py`
4. Expect `RENT_REMINDER` rows in `/admin/message-logs` to `f7-ops-wales@yopmail.com` with `status: sent`

---

## RENT-REMINDER-LIVE-DELIVERY-CLOSEOUT-01 closeout (20260606T131535Z)

**Classification:** `PARTIAL`

### Closeout checklist
- setup: PASS
- due_delivery: FAIL
- overdue_delivery: FAIL
- suppression: PASS
- partial_payment: PASS
- audit_delivery: PASS
- tenant_visibility: PASS
- retry: FAIL
- regression: PASS

**Blockers:** due_delivery, overdue_delivery, retry

Local mongo probe: `skipped`

---

## RENT-REMINDER-LIVE-DELIVERY-POST-DEPLOY-PROOF-01 (20260606T135207Z)

**Classification:** `FAIL_OPERATIONAL`

### Post-deploy checklist
- env_proof: FAIL
- due_delivery: FAIL
- overdue_delivery: FAIL
- idempotency: FAIL
- tenant_delivery: PASS
- regression: PASS

**Blockers:** env_proof, due_delivery, overdue_delivery, idempotency

Commit probe: `1dfcc85ad93d`
Missing reminder candidates: 0

---

## RENT-REMINDER-LIVE-DELIVERY-POST-DEPLOY-PROOF-01 (20260606T143514Z)

**Classification:** `PARTIAL` (not `VERIFIED_OPERATIONALLY` — no live `sent` delivery evidence)

### Post-deploy checklist
- env_proof: PASS — commit `1dfcc85a` deployed; admin job 200; rate limit cleared
- due_delivery: FAIL
- overdue_delivery: FAIL
- idempotency: PASS — duplicate job 200; no duplicate sends
- tenant_delivery: PASS
- regression: PASS — 28 pytest passed

**Blockers:** due_delivery, overdue_delivery

### Findings
- Staging backend at commit `1dfcc85ad93dcd4918d648be630064b655549b1b`
- `rent_operations_daily_job` executed successfully (processed=1) after rate limit cleared
- **Zero missing reminder types** on pilot payable ledgers — all applicable due/overdue events already exist with `delivery_status: manual` from pre-live era
- Live send path only attempts delivery when **new** reminder events are created; existing manual events are skipped by design
- No `RENT_REMINDER` message_logs with `status=sent` to `f7-ops-wales@yopmail.com`
- Harness: `backend/rent_reminder_live_delivery_post_deploy_proof_01_execute.py`

### Next proof window
Re-run when a pilot ledger crosses due_soon/due_today/overdue threshold **without** an existing reminder event (e.g. new period or calendar boundary on un-evented ledger).
