# Email trigger map (Phase 6 — governed customer rendering)

This document complements `backend/docs/NOTIFICATION_TEMPLATE_MATRIX.md` (DB template keys and gating). It records **who triggers**, **which code path renders HTML/text**, and **primary CTA** for major customer-facing emails.

## Canonical flow

1. Caller builds **context** (recipient, branding merge fields, structured payloads).
2. `notification_orchestrator.send(template_key=..., context=..., client_id=...)`.
3. `_render_email` may force **code-built** layout (bypass stale DB HTML) for specific aliases.
4. `EmailService._build_html_body` / `_build_text_body` apply `email_templates.email_layout.build_customer_email_layout` (or internal layout for staff).
5. Postmark send + `message_logs` / audit as implemented in the orchestrator.

## Scheduled compliance report (`SCHEDULED_REPORT` / alias `scheduled-report`)

| Item | Detail |
|------|--------|
| **Trigger** | `services.jobs.ScheduledReportJob.process_scheduled_reports` (cron); manual with attachment: `routes.reporting` → orchestrator with pre-built `message` HTML. |
| **Renderer** | Job path: orchestrator branch requires `report_rows` and/or `report_summary`; `EmailTemplateAlias.SCHEDULED_REPORT` → `email_templates.unified.scheduled_report_digest.build_scheduled_report_digest_html` / `build_scheduled_report_digest_text` inside `EmailService`. |
| **Payload** | `report_summary`, `properties_snapshot`, `report_rows`, `portal_link`, `generated_date`, `frequency`, `report_type`, `customer_reference`, `client_name`. No `report_content` in job path. |
| **Primary CTA** | “Open your portal” → `portal_link` (default `{app_base}/today`). |
| **Logging** | Standard orchestrator `message_logs` with `template_key` SCHEDULED_REPORT. |

## Payment & subscription (examples)

| template_key | Trigger (typical) | Renderer | Primary CTA |
|--------------|-------------------|----------|-------------|
| `SUBSCRIPTION_CONFIRMED` | Stripe webhook (`stripe_webhook_service`) | Code path → `EmailService` | Context-dependent |
| `PAYMENT_FAILED` | Stripe webhook | Code path → `EmailService` | Pay / update payment |
| `PAYMENT_RECEIPT` / payment flows | Webhook + `payment_receipt_layout=structured` branch in orchestrator | `EmailService` PAYMENT_RECEIPT | Portal / account |

## Password & activation

| template_key | Trigger | Renderer | Primary CTA |
|--------------|---------|----------|-------------|
| `PASSWORD_RESET` | `routes.auth` | DB template or fallback `EmailService` | Reset link |
| `WELCOME_EMAIL` | Provisioning / admin billing | Orchestrator → `EmailService` PASSWORD_SETUP | Set password |
| `ACTIVATION_REMINDER` | `provisioning` | Forced code path in orchestrator | Set password |
| `PORTAL_READY` | Admin routes (`DASHBOARD_READY`) when `dashboard_milestone_email` set | Forced code path | Open portal |

## Compliance alerts & reminders

| template_key | Trigger | Renderer | Primary CTA |
|--------------|---------|----------|-------------|
| `COMPLIANCE_ALERT` | `jobs` (status transitions) | `EmailService` COMPLIANCE_ALERT | Portal / requirement |
| `COMPLIANCE_EXPIRY_REMINDER` | `jobs` expiry runner | `EmailService` reminder template | View in portal (see product backlog for action-specific labels) |
| `MONTHLY_DIGEST` | `jobs` | Forced code path → `EmailService` MONTHLY_DIGEST | Context CTA |
| `PENDING_VERIFICATION_DIGEST` | `jobs` | `EmailService` | Review pending |

## Engagement / onboarding

| template_key | Trigger | Notes |
|--------------|---------|--------|
| `ONBOARDING_DAY*` | Onboarding scheduler / governance | `EmailService` ONBOARDING_ALIASES, shared customer layout |

## Internal / admin (not customer layout)

| template_key | Notes |
|--------------|--------|
| `INTERNAL_ALERT` | `internal_alert_layout` |
| `ADMIN_MANUAL`, `LEAD_HIGH_INTENT_ADMIN`, etc. | Separate templates; not unified customer digest. |

## Legacy / migration

- **Removed**: full requirement **table** and **monospace `report_content` dump** from job-driven `SCHEDULED_REPORT` body (replaced by unified digest).
- **Manual report email** (attachment): still passes pre-rendered `message` HTML from `reporting.py`; does not use the digest builder.
