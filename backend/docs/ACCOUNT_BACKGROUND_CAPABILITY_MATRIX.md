# Account Background Capability Matrix

**Programme:** ACCOUNT-LIFECYCLE-CAPABILITY-AUTHORITY-01  
**Authority version:** `account_capability_v1`  
**Parent:** `ACCOUNT_CAPABILITY_MATRIX.md`, `ACCOUNT_LIFECYCLE_POLICY_AUTHORITY.md`

Background services must consume **lifecycle capabilities** — not `clients.subscription_status` or `entitlement_status` alone.

---

## Job inventory

| Job / worker | Module | Current filter | Required capability | Lifecycle states (run) |
|--------------|--------|----------------|---------------------|------------------------|
| Daily compliance reminders | `jobs.send_daily_reminders` | `subscription_status ACTIVE`, `entitlement_status ENABLED` | `CAP_BG_REMINDERS` + `CAP_NOTIF_EMAIL` | ACTIVE, TRIAL, GRACE, CANCELLATION_SCHEDULED |
| SMS reminders (within daily) | `jobs._maybe_send_reminder_sms` | plan + prefs | `CAP_NOTIF_SMS` | Same + PLAN_GATED |
| Monthly digest | `jobs.send_monthly_digests` | Same as reminders | `CAP_BG_DIGEST` | ACTIVE, TRIAL, GRACE, CANCELLATION_SCHEDULED |
| Scheduled reports | `jobs.process_scheduled_reports` | ENABLED + `scheduled_reports` | `CAP_BG_SCHEDULED_REPORTS` | ACTIVE, TRIAL, CANCELLATION_SCHEDULED |
| Compliance status check | `jobs.check_compliance_status_changes` | Partial lifecycle gating | `CAP_BG_COMPLIANCE_CHECK` | ACTIVE, TRIAL, GRACE |
| Subscription lifecycle + renewal emails | `jobs.process_subscription_lifecycle_and_reminders` | billing lifecycle | `CAP_BG_LIFECYCLE_SYNC`, `CAP_BG_RENEWAL_REMINDERS` | All billing states |
| Renewal reminders | `jobs.send_renewal_reminders` | Stripe ACTIVE | `CAP_BG_RENEWAL_REMINDERS` | ACTIVE, CANCELLATION_SCHEDULED |
| Pending verification digest | `jobs.send_pending_verification_digest` | Admin/compliance | `CAP_BG_VERIFICATION_DIGEST` | ACTIVE |
| Stripe subscription reconcile | `run_stripe_subscription_reconcile` | System | `CAP_BG_LIFECYCLE_SYNC` | System (all) |
| Score recalculation | Score engine workers | Not uniformly gated | `CAP_BG_SCORE_RECALC` | ACTIVE, TRIAL, GRACE |
| Risk recalculation | Risk / predictive workers | Ops flag | `CAP_BG_RISK_RECALC` | ACTIVE + `predictive_maintenance` |
| AI extraction queue | Extraction workers | Per-job | `CAP_AI_EXTRACTION_BASIC` / `ADVANCED` | ACTIVE, TRIAL, GRACE (L) |
| Notification orchestrator | `notification_orchestrator` | `entitlement_status`, template feature | `CAP_NOTIF_*` | Per communication matrix |
| Automation centre jobs | Admin automation | Admin scope | System | Not customer CAP_* |

---

## Lifecycle → background behaviour

| Lifecycle state | CAP_BG_REMINDERS | CAP_BG_DIGEST | CAP_BG_SCHEDULED_REPORTS | CAP_BG_COMPLIANCE_CHECK | CAP_BG_SCORE_RECALC |
|---------------|------------------|---------------|--------------------------|-------------------------|---------------------|
| ACTIVE | Run | Run | Run (if plan) | Run | Run |
| TRIAL | Run | Run | Run (if plan) | Run | Run |
| GRACE_PERIOD | Run | Run | Run (if plan) | Run | Run |
| CANCELLATION_SCHEDULED | Run until expiry event | Run until expiry | Run until expiry | Run | Run |
| PAYMENT_FAILED | Run (pre-grace) | Run | Run | Run | Run |
| CANCELLED_IMMEDIATE | **Stop** | **Stop** | **Revoke** | **Stop** | **Stop** |
| SUBSCRIPTION_EXPIRED | **Stop** | **Stop** | **Stop** | **Stop** | **Stop** |
| READ_ONLY | **Stop** | **Stop** | **Stop** | **Stop** | **Stop** |
| SUSPENDED | **Stop** | **Stop** | **Stop** | **Stop** | **Stop** |
| ARCHIVED | **Terminate** | **Terminate** | **Terminate** | **Terminate** | **Terminate** |
| ACCOUNT_DELETED | **Terminate** | **Terminate** | **Terminate** | **Terminate** | **Terminate** |

---

## Reactivation → resume behaviour

| Event | Jobs to resume | Idempotency |
|-------|----------------|-------------|
| `PAYMENT_RECOVERED` | Reminders, digest, compliance, score | Per client per day |
| `ACCOUNT_REACTIVATED` | All paused jobs + re-register schedules | `client_id` + event id |
| `SUBSCRIPTION_STARTED` | Scheduled reports if plan allows | Subscription id |

**Policy:** Resume only after capability resolver confirms ACTIVE grants. No duplicate digest on replay.

---

## Notification template capability gates

| Template family | Capability | Blocked states |
|-----------------|------------|----------------|
| Compliance reminder email | `CAP_NOTIF_EMAIL` | CANCELLED, EXPIRED, SUSPENDED, ARCHIVED |
| SMS reminder | `CAP_NOTIF_SMS` | Same + PLAN_GATED |
| Grace notice | `CAP_NOTIF_EMAIL` | ARCHIVED, DELETED |
| Cancellation confirmation | `CAP_NOTIF_EMAIL` | — (send once on transition) |
| Monthly digest | `CAP_BG_DIGEST` | Terminal billing states |
| Renewal reminder | `CAP_BG_RENEWAL_REMINDERS` | CANCELLED_IMMEDIATE, EXPIRED |

---

## Data source (policy)

| Current (audit) | Target |
|-----------------|--------|
| `clients.subscription_status` | `account_lifecycle_state` from policy snapshot |
| `clients.entitlement_status` | Effective `CAP_BG_*` grant |
| Mirror lag risk | Read `client_billing` or lifecycle-contract snapshot |

**Gap:** **BACKGROUND_CAPABILITY_GAP** (ACA-006).

---

## Queue processing

| Queue type | Capability | Pause when |
|------------|------------|------------|
| Report generation | `CAP_REPORT_GENERATE_*` | Lifecycle DENY |
| Evidence pack jobs | `CAP_REPORT_AUDIT_PACK` | Lifecycle DENY |
| Extraction jobs | `CAP_AI_EXTRACTION_*` | Lifecycle DENY |
| Maintenance jobs | `CAP_OPS_MAINTENANCE` | Lifecycle DENY |

**Policy:** Drain in-flight jobs; do not start new jobs when capability grant is DENY.

---

## Analytics

| Activity | Capability | Notes |
|----------|------------|-------|
| Product analytics events | `CAP_COMPLIANCE_ACTIVITY` | No PII in terminal states |
| Billing analytics | System | Stripe sync only |

---

**Outcome:** `ACCOUNT_BACKGROUND_CAPABILITY_MATRIX_COMPLETE`
