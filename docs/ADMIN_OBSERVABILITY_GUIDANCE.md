# Admin observability guidance

**Purpose:** Quick reference for staff interpreting automation health, delivery states, and when to act.

---

## 1. Delivery states (outcome_metrics)

| State | Meaning | When to act |
|-------|--------|-------------|
| **provider_accepted** | Provider (e.g. Postmark) accepted the message for delivery. Final delivery/bounce may not be confirmed yet. | None. Normal. |
| **delivered** | Provider confirmed delivery; message reached the recipient. | None. Best outcome. |
| **bounced** | Provider reported a bounce (bad address, mailbox full, etc.). | Consider updating/removing the address; no urgent automation fix unless bounces are widespread. |
| **unknown** | Accepted by the provider but no delivery or bounce webhook received yet. | **Normal for a short time** (minutes to a few hours) after a run. **Act if** unknown stays high for **more than 6 hours** after the run: check provider webhook configuration and message_logs; may indicate webhook or provider delays. |
| **failed** | Send failed before provider acceptance (validation, rate limit, API error). | Check error_message and message_logs; fix configuration or templates. Repeated failures need investigation. |

**Summary:** Use outcome_metrics.delivery_* to see how many messages were accepted, delivered, bounced, or still unknown. Failed means the send never reached the provider.

**Unknown stale threshold:** If `delivery_unknown` remains > 0 for **6 hours** after a run finished, the system flags it and you should review (see Automation Centre / System Health).

---

## 2. Job observability tiers

### Fully observable

Run status, outcome counts (attempted/success/failed), and delivery breakdown (provider_accepted, delivered, bounced, unknown, failed). Message logs drill-down and CSV export available.

| Job | Notes |
|-----|--------|
| daily_reminders | Reminder emails/SMS; delivery_* after reconciliation. |
| monthly_digest | Digest emails. |
| pending_verification_digest | Admin digest for docs awaiting verification. |
| compliance_check_morning / compliance_check_evening | Compliance status change alerts. |
| scheduled_reports | Scheduled compliance reports by email. |

### Partially observable

Run status and counts; failures recorded. No delivery reconciliation (no delivery_* breakdown).

| Job | Notes |
|-----|--------|
| renewal_reminders | Run and counts; no delivery_* (could be added later). |
| notification_retry_worker | Retries; no per-run delivery breakdown. |
| notification_failure_spike_monitor | Alerting only. |

### Execution-level only

Run success/failure (and optional count). No business-outcome or delivery breakdown.

| Job | Notes |
|-----|--------|
| compliance_score_snapshots | Completion only. |
| expiry_rollover_recalc | No delivery. |
| compliance_recalc_worker | No delivery. |
| sla_watchdog | Creates incidents. |
| scheduler_heartbeat | Liveness; last_heartbeat_at in health. |
| delivery_reconciliation | Count of runs updated. |

---

## 3. When a degraded state needs action

- **Degraded** = the job ran but some sends failed or were skipped (e.g. partial failure).
- **Action:** Review outcome_metrics and use **Message logs** (for notification jobs) to see which recipients failed. Act if:
  - Failures repeat on the next run, or
  - Critical notifications (e.g. compliance alerts) are affected, or
  - You see a **delivery unknown stale** warning (unknown still high >6h after run).
- **Failed** = the job run itself failed (exception or total failure). Check error_message and incidents; fix the cause.

---

## 4. API reference

- **GET /api/admin/observability/delivery-state-definitions** — Definitions and staff guidance for each delivery state; includes `delivery_unknown_stale_hours`.
- **GET /api/admin/observability/health-summary** — Includes `delivery_unknown_stale_runs` (runs with unknown > 0 older than threshold) and `delivery_unknown_stale_hours`.
