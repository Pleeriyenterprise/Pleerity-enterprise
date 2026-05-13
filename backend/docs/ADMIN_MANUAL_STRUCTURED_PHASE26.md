# Phase 2.6 — Structured `admin-manual` email layout

`EmailTemplateAlias.ADMIN_MANUAL` (`admin-manual`) now supports an **optional structured layout** when the orchestrator context sets **`admin_manual_structured: true`** and a non-empty **`admin_manual_summary`**.

- **Template keys and routing are unchanged.**
- **Legacy behaviour** is preserved when those flags/fields are absent (simple `message` / `body` body).

## Callers upgraded (structured + Phase 2.5 adapters)

| Template key | Adapter / source |
|--------------|------------------|
| `OPS_ALERT_NOTIFICATION_SPIKE` | `enrich_ops_notification_spike_email_context`, `enrich_risk_regen_queue_ops_email_context` |
| `STRIPE_WEBHOOK_FAILURE_ADMIN` | `enrich_stripe_webhook_failure_admin_context` |
| `PROVISIONING_FAILED_ADMIN` | `enrich_provisioning_failed_admin_context` |
| `COMPLIANCE_SLA_ALERT` | `enrich_compliance_sla_alert_email_context` |
| `LEAD_SLA_BREACH_ADMIN` | `enrich_lead_sla_breach_admin_context` |
| `SUPPORT_INTERNAL_NOTIFICATION` | `enrich_submission_internal_notification_context` (submission admin notify) |
| `ORDER_NOTIFICATION` | `enrich_order_notification_staff_context` when SLA warning/breach (renders via `COMPLIANCE_ALERT` + structured branch) |

## Still legacy without adapter (examples)

| Template key | Reason |
|--------------|--------|
| `LEAD_HIGH_INTENT_ADMIN` | No structured adapter yet; variable sales copy. |
| Generic `ADMIN_MANUAL` from routes/jobs | Highly variable bodies; no safe default structure without per-flow adapters. |

## HTML sections (structured)

Summary, optional **Urgency and response**, **Customer impact**, operational impact, optional **Likely causes**, recommended actions, optional **If left unresolved**, primary resolution CTA, optional secondary links, collapsible technical/debug block.

Implementation: `email_templates/admin_manual_structured_layout.py` and `EmailService._build_html_body` / `_build_text_body` for `ADMIN_MANUAL`.
