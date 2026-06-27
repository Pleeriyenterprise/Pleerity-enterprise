# Delivery Reconciliation Assessment

**Programme:** OPERATIONAL-PRODUCTION-ACCEPTANCE-VALIDATION-01  
**Validated at:** 2026-06-27T21:56:13Z

---

## Summary

| Metric | Value |
|---|---|
| Stale `delivery_unknown` job runs | **20** |
| Stale threshold | 6 hours |
| Primary jobs | `daily_reminders` (12), `scheduled_reports` (8) |
| Health impact | Contributes to `overall_health=attention_required` / degraded automation score |

---

## Sample run investigation

Probed message_logs for two stale `daily_reminders` runs (`DELIVERY_RECONCILIATION_ASSESSMENT.json`):

| Run | DELIVERED | SENT | FAILED | SMS_24H_THROTTLE |
|---|---|---|---|---|
| `6a3f9112…` (2026-06-27) | 22 | **3** | 3 | 2 |
| `6a3e3f92…` (2026-06-26) | 19 | **3** | 3 | 2 |

The **3 SENT** messages per run are **`COMPLIANCE_EXPIRY_REMINDER_SMS`** — accepted by provider, no `delivered_at` webhook received.

---

## Classification

| Case | Verdict |
|---|---|
| Email reminders | **Reconciled** — majority DELIVERED with Postmark webhook timestamps |
| SMS reminders | **Provider limitation / missing delivery webhook** — remain SENT indefinitely |
| Failed sends | **Genuine failures** — 3 FAILED per run; separate from unknown |
| Throttled SMS | **Expected** — `sms_24h_throttle`; not counted as delivery_unknown |

**Root cause for stale unknown counts:** `delivery_reconciliation` correctly counts SENT-without-DELIVERED as `delivery_unknown`. SMS channel lacks delivery confirmation webhooks on staging, so 3 rows per daily_reminders run persist past the 6h stale window.

This is **not** message orphaning or reconciliation job failure. The `delivery_reconciliation` scheduled job runs; metrics reflect live `message_logs` state.

---

## Recommendations (non-blocking for operational authority)

1. Treat SMS SENT-without-DELIVERED as terminal after N hours for health scoring (product decision — not implemented in this validation).
2. Verify SMS provider webhook configuration if delivery proof is required.
3. Acknowledge or resolve the aggregate P2 "Delivery unknown unresolved" incident after operator review.

**Degraded health is genuine** — not a false positive from broken monitoring.
