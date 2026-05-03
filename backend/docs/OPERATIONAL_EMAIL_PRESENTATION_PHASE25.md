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

3. **Minimal `INTERNAL_ALERT` (public provide-info)** — `enrich_minimal_internal_alert_context()` sets `description`/`title`, plus `dashboard_link`, `suggested_action`, `component`. **Does not** set `severity_label` (stays on legacy internal-alert layout).

4. **Legacy internal-alert HTML** — `internal_alert_layout` legacy branch uses `description or message` so minimal sends still render body text even without calling the adapter.

## Intentionally unchanged (documented)

| Path | Reason |
|------|--------|
| `STRIPE_WEBHOOK_FAILURE_ADMIN` | Distinct billing/security semantics; no incident id; adapter would need new registry subtype and billing-specific links — deferred to avoid scope creep. |
| `PROVISIONING_FAILED_ADMIN` | Same as above; tied to provisioning job + in-app fan-out; keep short admin-manual copy unless product asks for unified ops layout. |
| `COMPLIANCE_SLA_ALERT` | Tenant/compliance product alert, not system `incidents`; different audience framing — do not fold into SLA watchdog presentation. |
| `LEAD_*` admin templates | Sales/CRM workflow; not operational incident semantics. |
| Generic `ADMIN_MANUAL` | Highly variable bodies; no single safe adapter without false structure. |

See also **`ADMIN_MANUAL_STRUCTURED_PHASE26.md`** for structured HTML rendering when `admin_manual_structured` is set.

## Risks remaining

- **OPS_ALERT** and **INTERNAL_ALERT** still use different **rendering aliases** (`admin-manual` vs `internal-alert`); Phase 2.6 adds structured **layout** for `admin-manual` when adapters set the structured flags.
- Spike subject line text changed (CRIT/WARN → CRITICAL / WARNING wording); idempotency keys unchanged.
- Minimal INTERNAL_ALERT still does not use structured (Phase 2) HTML unless `severity_label` is set deliberately later.
