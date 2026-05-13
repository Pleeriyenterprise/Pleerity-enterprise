# Phase 2.5 — Operational email presentation audit

Additive alignment of admin/operational emails with `operational_alert_presentation.py`
where safe **without** changing: incident creation, stored severities, scheduler/recovery logic,
notification routing (`template_key`), or idempotency key schemes.

## Paths audited

| Path | `template_key` | DB `email_template_alias` | Sender |
|------|----------------|---------------------------|--------|
| SLA watchdog incidents | `INTERNAL_ALERT` | `internal-alert` | `sla_watchdog._send_incident_alert_email` (Phase 2) |
| Notification failure spike | `OPS_ALERT_NOTIFICATION_SPIKE` | `admin-manual` | `notification_failure_spike_monitor` |
| Risk regen queue attention | `OPS_ALERT_NOTIFICATION_SPIKE` | `admin-manual` | `risk_signal_regen_alert_monitor` |
| Provide-info token → admin | `INTERNAL_ALERT` | `internal-alert` | `routes/public.py` |
| Stripe webhook failure | `STRIPE_WEBHOOK_FAILURE_ADMIN` | `admin-manual` | `routes/webhooks.py` |
| Provisioning failed | `PROVISIONING_FAILED_ADMIN` | `admin-manual` | `services/provisioning_runner.py` |
| Compliance SLA (tenant) | `COMPLIANCE_SLA_ALERT` | `admin-manual` | `services/compliance_sla_monitor.py` |
| Lead high-intent / SLA breach | `LEAD_HIGH_INTENT_ADMIN`, `LEAD_SLA_BREACH_ADMIN` | `admin-manual` | `lead_service`, `lead_followup_service` |
| Other `ADMIN_MANUAL` | various | `admin-manual` | admin routes, work orders, etc. |

## Migrated (Phase 2.5)

1. **`OPS_ALERT_NOTIFICATION_SPIKE` (failure spike)** — `enrich_ops_notification_spike_email_context()` merges operator-first sections + registry `EMAIL_DELIVERY_FAILURE_SPIKE` copy; raw spike lines appended under `--- Raw telemetry (debug) ---`. Same `template_key`, same idempotency pattern.

2. **`OPS_ALERT_NOTIFICATION_SPIKE` (risk regen)** — `enrich_risk_regen_queue_ops_email_context()` uses `RISK_REGEN_QUEUE_ATTENTION` registry copy + incident / Automation Centre links; raw queue dump in debug section. Same `template_key`.

3. **Minimal `INTERNAL_ALERT` (public provide-info)** — `enrich_minimal_internal_alert_context(..., use_structured_operator_layout=True)` may set `severity_label` + summary fields so the **Phase 2** internal layout renders; callers supply `dashboard_link`, `suggested_action`, `component`, and optional `customer_impact`.

4. **`COMPLIANCE_SLA_ALERT`** — `enrich_compliance_sla_alert_email_context()` sets `admin_manual_structured` with operator sections (urgency, customer impact, likely causes, ordered actions, technical/debug). Same `template_key` and idempotency keys.

5. **`ORDER_NOTIFICATION` (SLA warning/breach)** — `enrich_order_notification_staff_context()` when `event_type` is `sla_warning` / `sla_breach`; uses `COMPLIANCE_ALERT` alias branch with `admin_manual_structured` in `EmailService` (staff copy, deep link to order).

6. **`LEAD_SLA_BREACH_ADMIN`** — `enrich_lead_sla_breach_admin_context()`; structured admin-manual, calm subject (no emoji alarm).

7. **`SUPPORT_INTERNAL_NOTIFICATION`** — `enrich_submission_internal_notification_context()` for `notify_admin_new_submission` (human titles for known submission types).

8. **Job monitor human titles** — `human_job_monitor_email_title()` + expanded `INTERNAL_ALERTS` registry (customer impact, urgency, ordered actions) feed `INTERNAL_ALERT` / incident presentation from `sla_watchdog`.

9. **Legacy internal-alert HTML** — `internal_alert_layout` legacy branch uses `description or message` so minimal sends still render body text when structured flags are absent.

## Intentionally unchanged (documented)

| Path | Reason |
|------|--------|
| `STRIPE_WEBHOOK_FAILURE_ADMIN` | Distinct billing/security semantics; no incident id; adapter would need new registry subtype and billing-specific links — deferred to avoid scope creep. |
| `PROVISIONING_FAILED_ADMIN` | Same as above; tied to provisioning job + in-app fan-out; keep short admin-manual copy unless product asks for unified ops layout. |
| ~~`COMPLIANCE_SLA_ALERT`~~ | **Migrated (2026-05):** structured `admin-manual` adapter; still not incident-backed — keep tenant framing in copy. |
| ~~`LEAD_SLA_BREACH_ADMIN`~~ | **Migrated:** structured adapter; still sales workflow semantics. |
| `LEAD_HIGH_INTENT_ADMIN` | Remains legacy unless a dedicated adapter is added. |
| Generic `ADMIN_MANUAL` | Highly variable bodies; no single safe adapter without false structure. |

See also **`ADMIN_MANUAL_STRUCTURED_PHASE26.md`** for structured HTML rendering when `admin_manual_structured` is set.

## Risks remaining

- **OPS_ALERT** and **INTERNAL_ALERT** still use different **rendering aliases** (`admin-manual` vs `internal-alert`); Phase 2.6 adds structured **layout** for `admin-manual` when adapters set the structured flags.
- Spike subject line text changed (CRIT/WARN → CRITICAL / WARNING wording); idempotency keys unchanged.
- **INTERNAL_ALERT** uses Phase 2 HTML when `severity_label` is set (watchdog path, or `enrich_minimal_internal_alert_context(..., use_structured_operator_layout=True)`); other minimal sends remain on the legacy internal layout until opted in.
