# Internal Alert Email System – Task vs Codebase Audit

## Goal

Audit the codebase against the task requirements for a **structured internal alert email system** for operational alerts to administrators. Identify what is implemented, what is missing, and any conflicts. Propose the safest, most professional options. **Do not implement blindly.**

**Task constraint:** Internal emails must NOT use customer-facing email templates. They must be clear, structured, and diagnostic-focused.

---

## 1. Current Architecture Summary

| Component | Current implementation |
|-----------|-------------------------|
| **Internal send path** | Same as customer: `notification_orchestrator.send(template_key, client_id=None, context={"recipient": addr, "subject": ..., "body": ...})`. Uses **ADMIN_MANUAL** template (email_template_alias admin-manual). |
| **Internal template** | **ADMIN_MANUAL** in `email_service._build_html_body`: simple HTML with header "Compliance Vault Pro", greeting, and `model.get('message', ...)`. No dedicated file `internal_alert_email.html`. No severity-based layout or structured diagnostic blocks. |
| **Recipients** | **ADMIN_ALERT_EMAILS** (comma-separated) or **OPS_ALERT_EMAIL**; parsed in sla_watchdog, notification_failure_spike_monitor, provisioning_runner, webhooks. Multiple recipients supported (e.g. cap at 3 in sla_watchdog). |
| **Incidents** | **`incidents`** collection (not `system_incidents`). Fields: severity, title, description, source, status (open/acknowledged/resolved), created_at, updated_at, acknowledged_by, acknowledged_at, resolved_by, resolved_at, related_job_run_id, related_job_name, metadata. Resolution note in `metadata.note_resolve`. Indexes on status, severity, created_at. |
| **Incident creation** | `incident_service.create_incident()`; used by **sla_watchdog** (heartbeat stale P1, delivery_unknown P2, job missed SLA P0/P1/P2, job degraded P2). |
| **Alert email trigger** | **sla_watchdog**: after creating an incident, calls `_send_incident_alert_email(incident_id, title, description, severity)` → orchestrator.send(ADMIN_MANUAL, client_id=None, context={recipient, subject, body}). Subject = `[severity] title`. **notification_failure_spike_monitor**: sends OPS_ALERT_NOTIFICATION_SPIKE (admin-manual) with cooldown. **provisioning_runner**, **webhooks**: send to admin list. |
| **Rate limiting** | **Notification spike**: NOTIFICATION_SPIKE_COOLDOWN_SECONDS (default 3600), `notification_spike_cooldown` collection with last_sent_at. **SLA incident**: one email per incident per recipient (idempotency_key = SLA_INCIDENT_{incident_id}_{addr}); no time-based "same alert type" suppression window. |
| **Alert registry** | No **internal_alert_registry.py**. Alert types are implicit in sla_watchdog (heartbeat, delivery_unknown, job_monitor) and in notification_failure_spike_monitor. |
| **Aggregation** | No grouping of multiple alerts into a single "Multiple monitoring alerts" email. |

---

## 2. Task Requirements vs Current State

### 2.1 Create Internal Alert Email Layout (backend/email/templates/internal_alert_email.html)

| Requirement | Status | Notes |
|-------------|--------|-------|
| Dedicated template for internal system alerts | **Missing** | No file `internal_alert_email.html`. Internal alerts use **ADMIN_MANUAL**, which renders a generic "Compliance Vault Pro" header + `model.get('message')` in a simple div. |
| Layout: Alert header with severity, summary, affected job/component, diagnostic info, timestamp, suggested action, system context, footer | **Missing** | Current body is plain text passed as "body" in context; ADMIN_MANUAL template expects **"message"** for HTML body, so incident body may not appear (see conflict below). No severity indicator, no structured sections. |

**Conflict:** Task asks for **backend/email/templates/internal_alert_email.html** (file-based). The codebase uses **Python-built** HTML in `email_service._build_html_body` for admin-manual; there is no Jinja or file-based email templates for internal mail. Customer layout uses `email_templates/email_layout.py` (Python), not `.html` files.

**Recommendation:** Add a **Python-built** internal alert layout (e.g. in `email_templates/internal_alert_layout.py` or a dedicated function in `email_service`) that accepts severity, title, component, last_successful_run, expected_interval, status, impact, suggested_action, dashboard_link, timestamp. Render to HTML with clear sections. Do **not** use the customer layout. Optionally add a **new** template_key (e.g. INTERNAL_ALERT) with a dedicated alias that uses this layout, so orchestrator continues to resolve by template_key and internal alerts bypass customer branding. Avoid introducing a new template engine (Jinja) only for this; keep consistency with existing Python-rendered internal content.

---

### 2.2 Alert Severity Levels

| Requirement | Status | Notes |
|-------------|--------|-------|
| P0 – Critical, P1 – Major, P2 – Warning | **Done** | `incident_service`: SEVERITY_P0, SEVERITY_P1, SEVERITY_P2. sla_watchdog assigns P0/P1/P2 by job max_delay and source. |
| Severity in subject and body | **Partial** | Subject uses `[severity] title` (e.g. [P1] Scheduler heartbeat stale). Body is plain text; no structured "Severity: P1" block in a dedicated layout. |

---

### 2.3 Alert Email Subject Format

| Requirement | Status | Notes |
|-------------|--------|-------|
| Format: [Severity] Component or Job – Brief Description | **Partial** | Current subject = `[{severity}] {title}` (e.g. [P1] Scheduler heartbeat stale). Task example adds "– Pleerity monitoring"; optional. Title already acts as description. |

---

### 2.4 Alert Content Structure

| Requirement | Status | Notes |
|-------------|--------|-------|
| Alert title, severity, component/job name, last successful run, expected interval, current status, possible impact, suggested action, link to dashboard | **Partial** | Incident has title, description, severity, source, related_job_name, metadata (last_finished_at, etc.). Email body is a short string (title + description + severity); not structured into sections. Dashboard link not included in email. |

---

### 2.5 Alert Event Registry (backend/services/internal_alert_registry.py)

| Requirement | Status | Notes |
|-------------|--------|-------|
| File INTERNAL_ALERTS = { "SCHEDULER_HEARTBEAT_STALE": { severity, component, description }, ... } | **Missing** | No internal_alert_registry.py. Alert types exist only in code (sla_watchdog, notification_failure_spike_monitor). |
| All internal alerts reference this registry | **N/A** | No registry to reference. |

**Recommendation:** Add **internal_alert_registry.py** with a dict of alert_type_id → severity, component, description (and optionally default title/suggested_action). Callers (sla_watchdog, spike monitor, etc.) use the registry to get severity and description; incident creation and email subject/body can be built from it. Keeps a single place to add new alert types.

---

### 2.6 Alert Trigger Sources

| Requirement | Status | Notes |
|-------------|--------|-------|
| Scheduler watchdog, job monitor, delivery reconciliation, notification retry, compliance recalculation, email delivery monitor | **Partial** | **sla_watchdog** (runs every 10 min): heartbeat stale, delivery_unknown stale, per-job SLA (job_schedule_registry). **notification_failure_spike_monitor**: email delivery failure spike. **provisioning_runner**: provisioning failed. **webhooks**: Stripe webhook failure. **compliance_sla_monitor**: compliance recalc SLA. No dedicated "delivery reconciliation worker" or "notification retry worker" alert type in registry; delivery_unknown is covered by sla_watchdog. |

---

### 2.7 Alert Delivery Targets

| Requirement | Status | Notes |
|-------------|--------|-------|
| ADMIN_ALERT_EMAILS, OPS_ALERT_EMAIL; multiple recipients comma-separated | **Done** | Both env vars used; comma-split for ADMIN_ALERT_EMAILS; fallback to OPS_ALERT_EMAIL. |

---

### 2.8 Alert Rate Limiting

| Requirement | Status | Notes |
|-------------|--------|-------|
| Only send identical alert once per configurable window (e.g. 30 min) | **Partial** | **Spike monitor**: NOTIFICATION_SPIKE_COOLDOWN_SECONDS (default 3600), stored in notification_spike_cooldown collection. **SLA incidents**: one email per **incident** (idempotency_key = incident_id + addr). If the same "type" (e.g. heartbeat stale) creates a new incident after resolve, a new email is sent. No "same alert type once per 30 min" suppression across incidents. |

**Recommendation:** For SLA-driven alerts, current behaviour is "one email per incident". To add "identical alert type once per N minutes", either: (a) before creating an incident, check whether an open or recently closed incident of the same source/related_job exists within the window and skip create (and skip email), or (b) before sending the email, check a dedicated "last_alert_sent" store (e.g. by alert_type + component) and skip if within window. (a) aligns with "one incident per issue"; (b) allows multiple incidents but throttles email. Task example suggests 30-minute suppression; configurable via env (e.g. INTERNAL_ALERT_SUPPRESSION_MINUTES).

---

### 2.9 Alert Aggregation

| Requirement | Status | Notes |
|-------------|--------|-------|
| If multiple alerts in short period, group into one email (e.g. "3 alerts in last 5 minutes") | **Missing** | Each incident triggers its own email. No aggregation step. |

**Recommendation:** Optional enhancement: a separate job or step that, before sending individual alerts, checks for multiple open/recent incidents in a short window and sends one "[P1] Multiple monitoring alerts" email with a list. More complex; can be a later phase.

---

### 2.10 Incident Logging (system_incidents)

| Requirement | Status | Notes |
|-------------|--------|-------|
| Database collection **system_incidents** with alert_type, severity, component, message, timestamp, resolved, metadata | **Partial** | Collection is named **incidents** (not system_incidents). Fields: severity, title, description, source, status, created_at, updated_at, resolved_by, resolved_at, related_job_name, metadata. Task "alert_type" ≈ source (or could add alert_type). "message" ≈ description. "resolved" ≈ status == "resolved". |

**Conflict:** Task asks for **system_incidents**; codebase has **incidents**.

**Recommendation:** **Do not** add a second collection. Treat **incidents** as the incident log. If reporting or external systems require the name "system_incidents", add an alias or view; or document that "incidents" is the system incidents collection. Add a top-level **resolution_notes** field if needed (currently note is in metadata.note_resolve).

---

### 2.11 Resolution Tracking

| Requirement | Status | Notes |
|-------------|--------|-------|
| resolved, resolved_at, resolution_notes | **Done** | status (open/acknowledged/resolved), resolved_at, resolved_by; resolution note in metadata.note_resolve. resolve_incident(incident_id, resolved_by, note). |

---

### 2.12 Email Service Integration

| Requirement | Status | Notes |
|-------------|--------|-------|
| Internal alerts use centralized email service | **Done** | All go through notification_orchestrator.send(). |
| Bypass notification preferences and customer templates | **Done** | client_id=None; template_key ADMIN_MANUAL (or OPS_ALERT_NOTIFICATION_SPIKE) with email_category "internal"; orchestrator does not apply customer preference check for internal. Customer layout is not used for ADMIN_MANUAL. |
| Always deliver to administrators | **Done** | Recipients from ADMIN_ALERT_EMAILS / OPS_ALERT_EMAIL. |

**Bug / inconsistency:** ADMIN_MANUAL HTML body uses `model.get('message', ...)`. SLA watchdog passes **"body"** in context, not "message". So the rendered email may show the default "You have a new notification from Compliance Vault Pro" instead of the incident description. **Recommendation:** In email_service for ADMIN_MANUAL, use `model.get('message') or model.get('body', '')` so both keys work, or standardize callers to pass "message".

---

## 3. Conflicts and Recommended Approach

| Conflict | Task | Codebase | Recommendation |
|----------|------|----------|----------------|
| Internal template file | backend/email/templates/internal_alert_email.html | Python-built ADMIN_MANUAL in email_service | Add a **Python** internal alert layout (e.g. build_internal_alert_html(severity, title, component, ...)) and use it from a dedicated template_key (e.g. INTERNAL_ALERT) or from a dedicated alias used only for incident alerts. Do not add Jinja/file template unless the project standardizes on it. |
| Collection name | system_incidents | incidents | Keep **incidents**; do not create system_incidents. Document or alias if needed. |
| Registry | internal_alert_registry.py with INTERNAL_ALERTS | No registry | Add **internal_alert_registry.py**; have sla_watchdog and other monitors reference it for severity/component/description. |
| Rate limiting | Identical alert once per 30 min | One email per incident; spike has 1h cooldown | Keep current per-incident behaviour; optionally add configurable suppression per (alert_type, component) in a small store or by "recent incident of same type" check. |
| Body key | - | context "body" vs template "message" | Use **message** or **body** in ADMIN_MANUAL (e.g. model.get('message') or model.get('body', '')). Fix callers or template so incident body is shown. |

---

## 4. What to Implement (Prioritized, Safest)

1. **Fix ADMIN_MANUAL body key**  
   In `email_service._build_html_body` for ADMIN_MANUAL, use `model.get('message') or model.get('body', '...')` so existing callers that pass "body" (e.g. sla_watchdog) show the incident text. Optionally have sla_watchdog pass "message" for consistency.

2. **Add internal_alert_registry.py**  
   Define INTERNAL_ALERTS dict (e.g. SCHEDULER_HEARTBEAT_STALE, JOB_MISSED_SLA, DELIVERY_UNKNOWN_STALE, EMAIL_DELIVERY_FAILURE_SPIKE, PROVISIONING_FAILED, STRIPE_WEBHOOK_FAILURE) with severity, component, description. No change to incident creation yet; use registry when building email content or when adding new alert types.

3. **Add internal alert layout (Python)**  
   New function that builds HTML for internal alerts: severity badge, title, component, last successful run, expected interval, status, impact, suggested action, dashboard link, timestamp. Call it from a dedicated path (e.g. new template_key INTERNAL_ALERT with alias internal-alert, or extend ADMIN_MANUAL to accept structured context and use this layout when present). Ensure internal alerts do not use the customer layout.

4. **Wire registry into sla_watchdog**  
   When sending incident email, get severity/component/description from registry by alert type (e.g. SCHEDULER_HEARTBEAT_STALE); build subject and body (or structured context) from it. Include dashboard link (e.g. to /admin/incidents or observability) in body if possible.

5. **Optional: alert suppression window**  
   Configurable INTERNAL_ALERT_SUPPRESSION_MINUTES; before sending, check if the same alert_type (or source+related_job) already sent within the window; skip send if so. Store last_sent in a small collection or in incidents metadata.

6. **Do not** add system_incidents; keep using incidents. Add resolution_notes as top-level field if desired (currently metadata.note_resolve).

7. **Do not** add aggregation in the first phase unless required; it can be a follow-up.

---

## 5. Deliverables Checklist (Task vs Proposed)

| Deliverable | Task | Proposed |
|-------------|------|----------|
| Internal alert template created | internal_alert_email.html | Python internal alert layout function; optional new template_key INTERNAL_ALERT. |
| Alert registry implemented | internal_alert_registry.py | Same; INTERNAL_ALERTS dict + helper. |
| Alert throttling logic | 30-min suppression | Keep per-incident idempotency; add optional per-alert-type suppression via configurable window. |
| Incident logging system | system_incidents | Use existing **incidents** collection and incident_service. |
| Integration with scheduler and job monitoring | Triggers from watchdog, etc. | Already integrated; extend to use registry and new layout. |
| Example alert email output | Structured body | After layout and registry: subject [P1] Scheduler heartbeat stale; body with severity, component, last heartbeat, suggested action, link. |

---

## 6. Summary

- **Already in place:** Centralized send via orchestrator; ADMIN_ALERT_EMAILS / OPS_ALERT_EMAIL; incidents collection with P0/P1/P2, resolution tracking; sla_watchdog creating incidents and sending admin email; notification spike monitor with cooldown; subject format [Severity] title.
- **Missing or partial:** Dedicated internal alert **layout** (structured, diagnostic); **internal_alert_registry.py**; use of "message" vs "body" for ADMIN_MANUAL body; dashboard link in email; optional 30-min suppression per alert type; optional aggregation.
- **Conflicts resolved by:** Using a Python-built internal layout instead of .html; keeping **incidents** as the incident log; adding a registry and fixing body key so internal alerts are readable and consistent.

Implement in the order above; do not break existing incident creation or orchestrator flow.
