# Lifecycle-Based Email Notification System – Task vs Codebase Audit

## Goal

Audit the codebase against the task requirements for a **complete lifecycle-based email notification system**. Identify what is implemented, what is missing, and any conflicts. Propose the safest, most professional options. **Do not implement blindly.**

**Task constraint:** Do not break existing email sending functionality; extend it into a structured lifecycle-driven system.

---

## 1. Current Architecture (Post–Unified Template Implementation)

| Component | Current implementation |
|-----------|------------------------|
| **Single send path** | All email/SMS goes through `notification_orchestrator.send(template_key, client_id, context, idempotency_key=..., event_type=...)`. Direct `EmailService.send_email()` is deprecated. |
| **Event/template registry** | **DB:** `notification_templates` collection. Each document: `template_key`, `channel`, `email_template_alias`, `email_category`, gating flags. **No** Python file `email_event_registry.py`. Callers use `template_key` (e.g. `WELCOME_EMAIL`, `PASSWORD_RESET`) directly. |
| **Template resolution** | Orchestrator loads template by `template_key` → gets `email_template_alias` → renders via DB `email_templates` or `EmailService._build_html_body(alias, context)`. |
| **Customer layout** | `email_templates/email_layout.py`: `build_customer_email_layout()`. Customer-facing templates in `email_service.py` use this (header, body, CTA, “Why you received”, preferences link, footer with support/website/security line). No `base_email.html` file. |
| **Preferences** | `notification_preferences` (by `client_id`): `compliance_notifications_enabled`, `reporting_notifications_enabled`, `marketing_notifications_enabled` (and existing fields). |
| **Enforcement** | In orchestrator: if `email_category` is not `system_critical` or `internal`, check the corresponding preference; if disabled, block send and log `BLOCKED_PREFERENCE_DISABLED`. |
| **Logging** | **`message_logs`** collection: `message_id`, `client_id`, `recipient`, `template_key`, `channel`, `status`, `sent_at`, `error_message`, `idempotency_key`, `metadata` (includes `email_category`, `event_type`). No separate `email_send_log` collection. |
| **Deduplication** | Callers pass `idempotency_key`. Orchestrator rejects duplicate keys (returns `duplicate_ignored`). Per-event keys built by callers (e.g. `client_id + template_key + date_key`, or `order_id + ORDER_DELIVERED`). |

---

## 2. Task Requirements vs Current State

### 2.1 Create Email Event Registry (backend/services/email_event_registry.py)

| Requirement | Status | Notes |
|-------------|--------|-------|
| Centralized registry file `EMAIL_EVENTS = { "ACCOUNT_VERIFICATION": { "category", "template", "trigger" }, ... }` | **Missing** | No `email_event_registry.py`. Event→template→category is defined in **DB** `notification_templates` (template_key, email_template_alias, email_category). Triggers are implicit (which job/route calls `send(template_key=...)`). |
| Registry used by email sending service | **N/A** | Sending uses DB template lookup by `template_key`, not a Python dict. |

**Conflict:** Task asks for a **Python registry** (single source of truth) with keys like `ACCOUNT_VERIFICATION` and values like `template: "account_verification_email"`. The codebase uses **DB** `notification_templates` with `template_key` (e.g. `WELCOME_EMAIL`) and `email_template_alias` (e.g. `password-setup`). Naming also differs: task uses snake_case template names (`account_verification_email`, `certificate_expiry_email`); codebase uses `template_key` UPPER_SNAKE and alias kebab-case (`password-setup`, `reminder`).

**Recommendation:** Introduce **`email_event_registry.py`** as a **read-only map** that mirrors and extends the existing model: define lifecycle event IDs (e.g. `ACCOUNT_VERIFICATION`, `PASSWORD_RESET`, `CERTIFICATE_EXPIRY_REMINDER`) and map each to `template_key` (used by orchestrator) and `category`. The registry does **not** replace the orchestrator’s DB lookup; it is the single place to see “which events exist” and “which template_key + category they use.” New events can be added here and then seeded into `notification_templates` (and optional `EmailTemplateAlias` / `_build_html_body` branches) so sending remains via orchestrator. Avoid duplicating gating logic in the registry; keep that in DB/orchestrator.

---

### 2.2 Implement Lifecycle Email Events – Mapping to Current System

Task groups events by category. Below: **Implemented** = template_key exists and is triggered somewhere; **Partial** = same email type but different name or single threshold; **Missing** = no template or no trigger.

#### ACCOUNT EVENTS

| Task template / event | Task trigger | Current implementation | Status |
|-----------------------|-------------|-------------------------|--------|
| account_verification_email | user registration | **WELCOME_EMAIL** (password-setup) sent after provisioning / token creation | **Implemented** (as welcome/setup) |
| welcome_email | (implied) | Same as above; one “welcome” flow | **Implemented** |
| password_reset_email | password reset request | **PASSWORD_RESET** (password-reset); triggered from auth (forgot password) | **Implemented** |
| password_changed_confirmation_email | password successfully updated | No template_key or trigger found | **Missing** |

All above are **system_critical** in DB where present.

#### PORTAL ACCESS EVENTS

| Task template | Task trigger | Current implementation | Status |
|---------------|--------------|------------------------|--------|
| portal_invitation_email | user invites another to portal | **ADMIN_INVITE** (admin-invite), **TENANT_INVITE** (tenant-invite) | **Implemented** |
| access_granted_email | permissions change | No dedicated template; could use ADMIN_MANUAL or custom | **Missing** |
| access_revoked_email | access removed | No dedicated template | **Missing** |

#### COMPLIANCE MONITORING EVENTS

| Task template | Task trigger | Current implementation | Status |
|---------------|--------------|------------------------|--------|
| certificate_expiry_email | compliance engine, multiple thresholds (30/14/7 days, expired) | **COMPLIANCE_EXPIRY_REMINDER** (reminder); one email per client per day; single configurable window `reminder_days_before` (e.g. 30); no separate 30/14/7/expired templates | **Partial** |
| certificate_overdue_email | (expired) | Same reminder email includes overdue items; no separate “overdue” template | **Partial** |
| compliance_risk_alert_email | compliance engine | **COMPLIANCE_ALERT** (compliance-alert) on status change; **ORDER_NOTIFICATION** uses same alias | **Implemented** |

Category **compliance_notifications** in DB for these.

#### COMPLIANCE STATUS EVENTS

| Task template | Task trigger | Current implementation | Status |
|---------------|--------------|------------------------|--------|
| compliance_score_update_email | compliance score recalculates | No dedicated template | **Missing** |
| document_missing_alert_email | required documents missing | No dedicated template | **Missing** |

#### DOCUMENT VAULT EVENTS

| Task template | Task trigger | Current implementation | Status |
|---------------|--------------|------------------------|--------|
| document_uploaded_confirmation_email | certificate uploaded | **AI_EXTRACTION_APPLIED** (ai-extraction-applied) after AI extraction; no generic “uploaded” confirmation | **Partial** |
| document_replaced_email | certificate replaced | No dedicated template | **Missing** |

#### REPORTING EVENTS

| Task template | Task trigger | Current implementation | Status |
|---------------|--------------|------------------------|--------|
| daily_compliance_report_email | scheduler | **SCHEDULED_REPORT** (scheduled-report) supports daily/weekly/monthly; no key named “daily_compliance_report” | **Implemented** (same concept) |
| weekly_portfolio_report_email | scheduler | Same SCHEDULED_REPORT with frequency | **Implemented** |
| monthly_portfolio_summary_email | scheduler | **MONTHLY_DIGEST** (monthly-digest) | **Implemented** |

Category **reporting_notifications** in DB.

#### DOCUMENT PACK PURCHASE EVENTS

| Task template | Task trigger | Current implementation | Status |
|---------------|--------------|------------------------|--------|
| document_pack_order_confirmation_email | customer purchases pack | Order flows use **ORDER_NOTIFICATION** or similar; **ORDER_DELIVERED** for delivery | **Partial** (confirmation may be ORDER_NOTIFICATION or custom) |
| document_pack_delivery_email | (delivery) | **ORDER_DELIVERED** (order-delivered) | **Implemented** |

#### BILLING EVENTS

| Task template | Task trigger | Current implementation | Status |
|---------------|--------------|------------------------|--------|
| subscription_started_email | - | **SUBSCRIPTION_CONFIRMED** (payment-receipt) on checkout completed | **Implemented** |
| payment_success_email | - | Same or PAYMENT_RECEIVED | **Implemented** |
| payment_failed_email | - | **PAYMENT_FAILED** (payment-failed) | **Implemented** |
| invoice_available_email | - | No dedicated template_key | **Missing** |
| subscription_cancelled_email | - | **SUBSCRIPTION_CANCELED** (subscription-canceled) | **Implemented** |

Category **system_critical** where applicable.

#### SUPPORT EVENTS

| Task template | Task trigger | Current implementation | Status |
|---------------|--------------|------------------------|--------|
| support_ticket_created_email | - | **SUPPORT_TICKET_CONFIRMATION** (admin-manual) | **Implemented** |
| support_ticket_updated_email | - | No dedicated template | **Missing** |
| support_ticket_resolved_email | - | No dedicated template | **Missing** |

#### MARKETING EVENTS

| Task template | Task trigger | Current implementation | Status |
|---------------|--------------|------------------------|--------|
| feature_announcement_email | - | No dedicated template_key | **Missing** |
| product_update_email | - | No dedicated template_key | **Missing** |

Category **marketing_notifications** would apply (not yet in DB for these).

---

### 2.3 Connect Email Service / Centralized Service

| Requirement | Status | Notes |
|-------------|--------|-------|
| All lifecycle emails pass through centralized service | **Done** | All sends go through `notification_orchestrator.send()`. |
| Service must: resolve template, check preferences, send via Postmark, log result | **Done** | Orchestrator loads template from DB, checks category vs preferences, calls `_send_email` (Postmark), writes/updates `message_logs`. |
| Do not allow direct email sending outside this service | **Done** | Direct `EmailService.send_email()` is deprecated and raises. |

No conflict; extend by ensuring **new** lifecycle events are only sent via orchestrator with a `template_key` that exists in `notification_templates`.

---

### 2.4 Enforce Notification Preferences

| Requirement | Status | Notes |
|-------------|--------|-------|
| Before sending non–system_critical, check user_notification_preferences; if disabled, do not send | **Done** | Orchestrator checks `email_category` and `compliance_notifications_enabled` / `reporting_notifications_enabled` / `marketing_notifications_enabled` (keyed by client_id in `notification_preferences`). |

**Naming:** Task says “user_notification_preferences”; codebase uses **client_id**-scoped `notification_preferences`. No change needed if one “user” per client; document the mapping.

---

### 2.5 Template Structure (base_email.html)

| Requirement | Status | Notes |
|-------------|--------|-------|
| All customer-facing emails use shared base template (Header, Greeting, Message, CTA, Why-you-received, Notification preference link, Footer) | **Done** | Customer-facing templates in `email_service.py` use `build_customer_email_layout()` from `email_templates/email_layout.py`. No `base_email.html` file. |

**Conflict:** Task asks for **base_email.html**. The implemented solution uses a **Python** layout. Recommendation: keep using the Python layout; do not add a second system. If you later introduce Jinja and `base_email.html`, make it mirror the same structure and variables.

---

### 2.6 Email Send Logging (email_send_log)

| Requirement | Status | Notes |
|-------------|--------|-------|
| Create **email_send_log** collection with user_id, email_event, email_category, template_used, timestamp, delivery_status, provider_response | **Partial** | **message_logs** already has: client_id, template_key, channel, status, sent_at, error_message, postmark_message_id, metadata (email_category, event_type). Task fields map as: user_id → client_id (or recipient); email_event → template_key or event_type; email_category → metadata.email_category; template_used → template_key; timestamp → created_at/sent_at; delivery_status → status; provider_response → postmark_message_id / error_message. |

**Conflict:** Task asks for a **new** `email_send_log` model/collection. The codebase already has **message_logs** with equivalent (and richer) data.

**Recommendation:** **Do not** add a second log collection. Use **message_logs** as the email activity log. If the task’s field names are required for reporting, add a **view** or **reporting helper** that maps message_logs documents to the task’s schema (user_id, email_event, email_category, template_used, timestamp, delivery_status, provider_response). Optionally add an index or metadata fields so filtering by `email_category` or `event_type` is efficient.

---

### 2.7 Duplicate Send Protection

| Requirement | Status | Notes |
|-------------|--------|-------|
| Prevent duplicate sends for same event within a defined window (e.g. certificate reminder not twice same day) | **Done** | Callers pass **idempotency_key** (e.g. `client_id + COMPLIANCE_EXPIRY_REMINDER + date_key`). Orchestrator returns `duplicate_ignored` if key already exists. Jobs use per-day keys for reminders, digests, scheduled reports. |
| Implement deduplication logic in email_service | **N/A** | Deduplication is in **orchestrator** via idempotency_key; email_service is render-only. |

No new deduplication needed; ensure new lifecycle triggers pass a stable **idempotency_key** (e.g. include event + entity id + date or window).

---

## 3. Conflicts and Recommended Approach

| Conflict | Task | Codebase | Recommendation |
|----------|------|----------|----------------|
| Event registry | Python file `email_event_registry.py` with dict of event → category, template, trigger | DB `notification_templates` (template_key, email_template_alias, email_category); triggers scattered in jobs/routes | Add **email_event_registry.py** as the **canonical list of lifecycle events** and their mapping to `template_key` + `email_category`. Orchestrator continues to resolve send rules from DB. Seed new events from registry into `notification_templates` (and add aliases/templates where needed). |
| Template naming | snake_case (e.g. account_verification_email, certificate_expiry_email) | template_key UPPER_SNAKE (WELCOME_EMAIL, COMPLIANCE_EXPIRY_REMINDER), alias kebab-case (password-setup, reminder) | Keep existing template_key and alias naming. In the registry, map task-style **event names** (e.g. ACCOUNT_VERIFICATION) to existing **template_key** (e.g. WELCOME_EMAIL). Add new template_keys/aliases only for events that are truly missing (e.g. PASSWORD_CHANGED_CONFIRMATION, INVOICE_AVAILABLE). |
| Email activity log | New `email_send_log` with user_id, email_event, email_category, template_used, timestamp, delivery_status, provider_response | Existing **message_logs** with client_id, template_key, status, metadata.email_category, etc. | **Do not** create email_send_log. Use **message_logs** as the single email activity log. Add a small reporting layer or view that exposes task-style fields from message_logs if needed. |
| base_email.html | Shared base template file | Python `build_customer_email_layout()` in email_templates/email_layout.py | Keep using the Python layout. Do not introduce base_email.html unless you standardize on Jinja later; then align its structure with the current layout. |

---

## 4. What to Implement (Prioritized, Without Breaking Existing Sends)

1. **Email event registry (backend/services/email_event_registry.py)**  
   - Define a single dict or list of lifecycle events with: event_id, category, template_key (existing or new), optional trigger description.  
   - Use it as the source of truth for “which lifecycle events exist” and for documentation.  
   - Optionally: a small helper that returns template_key and category for an event_id so callers can use event_id instead of template_key if you want an abstraction layer.

2. **Map existing template_keys into the registry**  
   - Populate the registry with current template_keys (WELCOME_EMAIL, PASSWORD_RESET, COMPLIANCE_EXPIRY_REMINDER, etc.) and their category and trigger.  
   - Ensures “lifecycle events” and “current sends” are one list.

3. **Add only missing lifecycle events/templates**  
   - Add **template_key** (and alias + _build_html_body or DB template) only for events that are truly missing, e.g.:  
     - password_changed_confirmation_email → PASSWORD_CHANGED_CONFIRMATION (system_critical)  
     - access_granted_email / access_revoked_email (if product needs them)  
     - compliance_score_update_email, document_missing_alert_email (if product needs them)  
     - document_uploaded_confirmation_email (generic, not only AI extraction), document_replaced_email  
     - invoice_available_email  
     - support_ticket_updated_email, support_ticket_resolved_email  
     - feature_announcement_email, product_update_email (marketing_notifications)  
   - Add corresponding entries to **notification_templates** and, where needed, to **EmailTemplateAlias** and **email_service._build_html_body**.

4. **Compliance reminder thresholds (optional)**  
   - Task asks for 30/14/7 days and expired. Current design: one reminder per client per day with a single configurable window.  
   - To match task without breaking behavior: either (a) keep one email and mention “multiple thresholds” in the body, or (b) introduce separate template_keys per threshold (e.g. COMPLIANCE_EXPIRY_REMINDER_30D, _14D, _7D, OVERDUE) and have the job send the appropriate one; idempotency_key must include threshold so one email per threshold per day.

5. **Do not add email_send_log**  
   - Rely on message_logs; add a view or reporting API that maps to the task’s log schema if required.

6. **Ensure all new triggers use orchestrator + idempotency_key**  
   - Any new trigger (e.g. “password changed”, “invoice available”) must call `notification_orchestrator.send(template_key=..., idempotency_key=...)` and not send email directly.

---

## 5. Deliverables Checklist (Task vs Proposed)

| Deliverable | Task | Proposed |
|-------------|------|----------|
| List of lifecycle events implemented | Full list per task section | Registry file + DB notification_templates; document “implemented” vs “added in this phase” in a short list. |
| Email templates created or updated | New templates for each event | Reuse existing templates where event already exists; add only new template_keys/aliases and layout usage for missing events. |
| Files modified | - | email_event_registry.py (new), database.py (seed new template_keys if any), email_service.py (new branches if new aliases), jobs/routes (new triggers if any). |
| Email event registry file | backend/services/email_event_registry.py | Same path; content = lifecycle event_id → template_key, category, trigger description; optionally used by a thin helper. |
| Email service updates | Resolve template, check prefs, send, log | No change to send path; orchestrator already does this. New events use existing path with new template_key. |
| Preference enforcement | if not system_critical and pref disabled, skip | Already in orchestrator; no change. |
| Logging implementation | email_send_log | Use message_logs; add reporting view or API if task schema is required. |
| Duplicate send protection | Dedup in email_service | Already in orchestrator via idempotency_key; ensure new callers pass key. |

---

## 6. Summary

- **Already in place:** Single send path via orchestrator, category-based preference enforcement, message_logs with template_key and category, idempotency-based deduplication, unified customer layout (Python), and most of the requested lifecycle events (account, portal invite, compliance alert, reminder, reporting, document pack delivery, billing, support ticket created).
- **Missing or partial:** Centralized **event registry** file, several **specific templates** (password_changed_confirmation, access_granted/revoked, compliance_score_update, document_missing_alert, document_replaced, invoice_available, support_ticket_updated/resolved, feature_announcement, product_update), and optional **per-threshold** compliance reminders (30/14/7/expired).
- **Conflicts resolved by:** Adding a registry that **maps** to existing template_keys and categories without replacing DB/orchestrator; **not** adding email_send_log; **not** introducing base_email.html; adding only the missing events/templates and triggers where needed.

Implement the registry and missing events/templates in small steps; keep all sends going through the orchestrator and message_logs.
