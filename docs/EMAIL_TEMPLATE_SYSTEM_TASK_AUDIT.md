# Unified Email Template System – Task vs Codebase Audit

## Goal

Audit the codebase against the task requirements for a unified, enterprise-grade email template system. Identify what is implemented, what is missing, and any conflicts. Propose the safest, most professional options without implementing blindly.

**Task scope:** Customer-facing emails only. Internal system alerts and staff notifications must NOT use the new template.

---

## 1. Current Architecture Summary

| Component | Current implementation |
|-----------|-------------------------|
| **Entry point** | All outbound email goes through `services/notification_orchestrator.py` (single entry point). Direct `EmailService.send_email()` is deprecated. |
| **Templates** | (1) **DB:** `email_templates` collection (alias, subject, html_body, text_body, is_active). (2) **Fallback:** `EmailService._build_html_body(template_alias, model)` – Python f-strings building full HTML per alias. |
| **Template registry** | `notification_templates` collection: template_key, channel, email_template_alias, requires_provisioned, requires_active_subscription, requires_entitlement_enabled, plan_required_feature_key. No `email_category` (system_critical / compliance / reporting / marketing). |
| **Rendering** | Orchestrator loads template from DB; if not found, calls `EmailService()._build_html_body(alias, context)`. No Jinja2 or shared HTML base file. |
| **Preferences** | `notification_preferences` collection keyed by **client_id** (not user_id). Fields: expiry_reminders, daily_reminder_enabled, quiet_hours_enabled, sms_enabled, reminder_days_before, etc. Used by jobs (e.g. `send_daily_reminders`) to skip sends. **Admin** notification prefs live in `portal_users.notification_preferences`. No `compliance_notifications_enabled` / `reporting_notifications_enabled` / `marketing_notifications_enabled` as in the task. |
| **Enforcement** | **Orchestrator:** Checks gating (requires_provisioned, requires_active_subscription, plan gates). Does **not** check “email category” or “user opted out of compliance/reporting/marketing”. **Jobs:** Before sending reminders, jobs read `notification_preferences` and respect `daily_reminder_enabled`, `expiry_reminders`, etc. |
| **Logging** | `message_logs` collection: message_id, client_id, recipient, template_key, channel, status (PENDING/SENT/FAILED/…), sent_at, error_message, created_at, etc. Audit log: `AuditAction.EMAIL_SENT` / `EMAIL_FAILED` with template_key, message_id, postmark_id. No explicit `email_type` or `category` on the log. |
| **Footer** | `EmailService._build_email_footer(model)` – company name, tagline, optional customer reference. **Does not include:** “Why you received this email”, “Manage notification preferences”, or security line. |

---

## 2. Task Requirements vs Current State

### 2.1 Shared Email Layout System

| Requirement | Status | Notes |
|-------------|--------|-------|
| Create `backend/email/templates/base_email.html` | **Missing** | No `backend/email/` directory. No shared base HTML file. |
| All customer-facing emails extend this layout | **N/A** | No base to extend. Each template is built inline in `_build_html_body()` or stored as full HTML in `email_templates`. |
| Structure: Header → Body → Primary action → “Why you received” → Notification preference link → Footer | **Partial** | Current: header (per-template) + body + CTA + footer. Missing: “Why you received”, “Manage notification preferences”. Footer is minimal (company + tagline + ref). |

**Conflict:** Task suggests an HTML file (e.g. Jinja) that templates “extend”. The codebase uses Python-built HTML and optional DB-stored full bodies. Introducing a `.html` base that templates “extend” would require a template engine (Jinja2) and a new rendering path alongside the orchestrator.

**Recommendation:** Prefer a **Python-based shared layout** that stays within the current flow: a single function (e.g. `build_customer_email_layout(greeting, body_html, cta_label, cta_url, why_received_text, show_preferences_link, **kwargs)`) that returns full HTML. All customer-facing templates (in `EmailService` or in DB) would be refactored to supply these slots. No new engine, no new directory of HTML files unless you later standardize on Jinja. If you later adopt Jinja, `backend/email/templates/base_email.html` can wrap this structure and templates can extend it.

---

### 2.2 Branding Requirements

| Requirement | Status | Notes |
|-------------|--------|-------|
| Pleerity logo in header | **Partial** | No logo image in current templates; header uses text and color only. |
| Brand name: Pleerity Enterprise Ltd | **Done** | In footer (company_name). |
| Tagline: AI-Driven Solutions & Compliance | **Done** | In footer (tagline). |
| Primary color teal/green, neutral background, clean enterprise look | **Done** | #00B8A9, #0B1D3A, max-width 600px, Arial. |
| Professional, minimal, mobile-readable, major client compatible | **Done** | Inline styles, 600px, readable font. |
| Avoid heavy graphics | **Done** | No large images. |

**Gap:** Logo in header. Optional: add a single logo URL (env or constant) and inject in the shared header.

---

### 2.3 Email Layout Structure (per email)

| Requirement | Status | Notes |
|-------------|--------|-------|
| Header: logo, brand name, divider | **Partial** | Brand/divider implied; no logo. |
| Greeting: Hello {{user_name}} | **Done** | e.g. Hello {client_name}, or “there”. |
| Message content: short paragraphs, bullets | **Done** | Varies by template; generally short. |
| Action section (CTA button) | **Done** | Buttons styled consistently (teal, padding). |
| Transparency block (“Why you received this email”) | **Missing** | Not present in any template. |
| Notification preferences link | **Missing** | No “Manage notification preferences” in emails. |
| Footer: company, tagline, support email, website, security note | **Partial** | Footer has company + tagline (+ ref). **Missing:** support email, website URL, “For security, Pleerity will never ask for your password by email.” Task says do NOT include physical address. |

**Recommendation:** Add to the shared footer (or base layout): support email (e.g. info@pleerityenterprise.co.uk), website (e.g. https://pleerityenterprise.co.uk), and the security sentence. Add one “Why you received” slot and one “Manage notification preferences” link (only for non–system_critical; see categories below).

---

### 2.4 Email Categories

| Requirement | Status | Notes |
|-------------|--------|-------|
| Categories: system_critical, compliance_notifications, reporting_notifications, marketing_notifications | **Missing** | No `email_category` (or equivalent) on templates. `notification_templates` has only requires_provisioned, requires_active_subscription, plan_required_feature_key. |
| system_critical: cannot unsubscribe (password reset, account verification, security, billing receipts) | **Missing** | No concept of “system_critical” or “cannot unsubscribe”. |
| compliance_notifications / reporting_notifications / marketing_notifications: users may disable | **Missing** | No category-based opt-out in orchestrator. |

**Recommendation:** Add an optional `email_category` (or `notification_category`) to `notification_templates`: `system_critical` | `compliance_notifications` | `reporting_notifications` | `marketing_notifications`. Map existing template_keys to these (e.g. WELCOME_EMAIL, PASSWORD_RESET → system_critical; COMPLIANCE_EXPIRY_REMINDER, COMPLIANCE_ALERT → compliance_notifications; SCHEDULED_REPORT, MONTHLY_DIGEST → reporting_notifications; marketing if any). Default existing rows to a sensible category where missing.

---

### 2.5 Notification Preference Model

| Requirement | Status | Notes |
|-------------|--------|-------|
| Model: user_notification_preferences | **Different** | Current: `notification_preferences` keyed by **client_id**, used for reminder/digest/SMS toggles (expiry_reminders, daily_reminder_enabled, sms_enabled, etc.). Task: **user_id**, compliance_notifications_enabled, reporting_notifications_enabled, marketing_notifications_enabled. |
| Defaults: all enabled except marketing (opt-out) | **N/A** | Current prefs are different shape. |

**Conflict:** Task says “user_id”; system is client-centric (client_id, portal_user_id). For CVP, the “user” receiving email is usually the client (or a portal user under that client). So “user” could map to client_id or to portal_user_id depending on whether you want preferences per client or per portal user.

**Recommendation:** Keep existing `notification_preferences` (client_id) and **extend** it (or add a parallel structure) with: `compliance_notifications_enabled`, `reporting_notifications_enabled`, `marketing_notifications_enabled` (default True for compliance/reporting, False or True for marketing per your policy). Use client_id as the scope for “user” unless you need per-portal-user preferences. Document the mapping (user_id → client_id or portal_user_id) so the task’s “user_id” is clear in your domain.

---

### 2.6 Enforcement Logic

| Requirement | Status | Notes |
|-------------|--------|-------|
| Before sending non–system_critical email, check preferences; if disabled, do not send | **Missing** | Orchestrator does not check “category” or “compliance/reporting/marketing enabled”. Jobs do check expiry_reminders / daily_reminder_enabled for their own flows. |

**Recommendation:** In the orchestrator, **after** existing gating (provisioning, subscription, plan), **before** inserting the message_log and sending:

- Resolve `email_category` for the template (from notification_templates or a map).
- If category is `system_critical`, skip preference check and proceed.
- Else load notification_preferences for the client (or user); if the corresponding flag is False (e.g. compliance_notifications_enabled), return a “blocked” result (e.g. outcome=blocked, block_reason=preference_disabled) and optionally write a message_log with status BLOCKED_PREFERENCE so it’s visible in notification health. Do not send the email.

---

### 2.7 Unsubscribe / Manage Preferences

| Requirement | Status | Notes |
|-------------|--------|-------|
| Link “Manage notification preferences” in emails | **Missing** | No such link in any template. |
| Link target: /account/notification-preferences | **Mismatch** | App has client portal routes such as `/notifications` or `/settings/notifications` (and redirects like `/app/notifications` → `/settings/notifications`). No `/account/notification-preferences` in App.js. |

**Recommendation:** Add “Manage notification preferences” to the shared footer/layout for non–system_critical emails. Use the **existing** client portal path (e.g. `/settings/notifications` or whatever is canonical) so the link works. If you want a task-compliant URL, add a route (e.g. `/account/notification-preferences`) that redirects to the existing settings page. Do not break existing deep links.

---

### 2.8 Hyperlink Formatting

| Requirement | Status | Notes |
|-------------|--------|-------|
| No raw URLs; use buttons or clean links | **Done** | Templates use `<a href="...">Label</a>` or styled buttons. |

---

### 2.9 Mobile Optimization

| Requirement | Status | Notes |
|-------------|--------|-------|
| Max width ~600px, readable font, tappable buttons, minimal images | **Done** | max-width 600px (or 700 in one report), inline styles, no heavy images. |

---

### 2.10 Security Messaging

| Requirement | Status | Notes |
|-------------|--------|-------|
| Footer line: “For security, Pleerity will never ask for your password by email.” | **Missing** | Not in _build_email_footer. |

**Recommendation:** Add this line to the shared customer email footer.

---

### 2.11 Logging and Audit

| Requirement | Status | Notes |
|-------------|--------|-------|
| Log every send: user_id, email_type, category, timestamp, delivery_status | **Partial** | message_logs: client_id, template_key, channel, status, created_at, sent_at, etc. No explicit “email_type” (template_key is the type) or “category”. |
| Log unsubscribe actions | **N/A** | No category-based unsubscribe yet; when added, log preference updates in audit_log. |

**Recommendation:** When adding `email_category` to templates, store it on the message_log (e.g. in metadata or a top-level field) so “category” is available for reporting. Optionally add a small “email_type” alias in metadata if you want a task-style name. Keep using existing status for delivery_status.

---

### 2.12 Templates to Update

| Task list | Current coverage |
|-----------|------------------|
| Password reset | **Done** (PASSWORD_RESET, WELCOME_EMAIL for setup). |
| Account verification | **Done** (WELCOME_EMAIL, admin invite, etc.). |
| Compliance reminders | **Done** (COMPLIANCE_EXPIRY_REMINDER, reminder alias). |
| Compliance reports | **Done** (SCHEDULED_REPORT, monthly digest). |
| Risk alerts | **Done** (COMPLIANCE_ALERT, risk-related). |
| Billing notifications | **Done** (PAYMENT_FAILED, SUBSCRIPTION_CONFIRMED, etc.). |
| Document pack purchases | **Done** (ORDER_DELIVERED, order notifications). |
| Subscription confirmations | **Done** (SUBSCRIPTION_CONFIRMED, PAYMENT_RECEIVED). |
| Portal invitations | **Done** (WELCOME_EMAIL, ADMIN_INVITE, TENANT_INVITE). |

All of these should be **migrated to** the new shared layout (header, body, CTA, “Why you received”, preferences link where applicable, footer with support + website + security line). They are not today using a single base layout.

---

### 2.13 Internal / Staff Emails (Must NOT Use Customer Template)

| Requirement | Status | Notes |
|-------------|--------|-------|
| Internal system alerts and staff notifications must NOT use the customer template | **Compatible** | Staff/admin emails (OPS_ALERT, PROVISIONING_FAILED_ADMIN, LEAD_*_ADMIN, etc.) use template_key that maps to admin-manual or similar. You can define “customer-facing” as “uses the new base layout”; staff templates continue to use current admin-manual content and do not include the customer footer/preferences link. |

**Recommendation:** When implementing the shared layout, call it only for templates that are explicitly customer-facing (e.g. list of template_keys or category != internal). Do not pass internal/staff template_keys through the customer base layout.

---

## 3. Conflicts and Recommended Approach

| Conflict | Task | Codebase | Recommendation |
|----------|------|----------|----------------|
| Base layout file | `backend/email/templates/base_email.html`, templates “extend” it | No HTML templates; Python-built HTML and DB html_body | Introduce a **Python-built** shared layout (single function or small module) that returns full HTML with header, body slot, CTA, “Why you received”, preferences link, footer. Refactor customer templates to use it. Optionally add Jinja later and a base_email.html that mirrors this structure. |
| Preference model | user_notification_preferences, user_id, compliance/reporting/marketing_enabled | notification_preferences by client_id, expiry_reminders, daily_reminder_enabled, sms_enabled, etc. | **Extend** existing notification_preferences (or add fields) with compliance_notifications_enabled, reporting_notifications_enabled, marketing_notifications_enabled. Keep client_id as scope (or map user_id → client_id). Do not remove existing fields; jobs and orchestrator continue to use them. |
| Preferences link URL | /account/notification-preferences | /settings/notifications (or similar) | Use **existing** client route in the email link. Add redirect from /account/notification-preferences to that route if you need the exact path. |
| Categories | Four categories, system_critical cannot be unsubscribed | No category on templates | Add **email_category** (or notification_category) to notification_templates; implement enforcement in the orchestrator before send; add “Manage notification preferences” and “Why you received” only for non–system_critical. |

---

## 4. Proposed Implementation Order (When Approved)

1. **Base layout (Python)**  
   - Add a module (e.g. `backend/services/email_layout.py` or under `backend/email/`) that builds the shared customer HTML: header (brand + optional logo), body slot, primary CTA, “Why you received” paragraph, “Manage notification preferences” link (optional), footer (company, tagline, support email, website, security line).  
   - No new engine; same entry point (orchestrator → render → send).

2. **Footer and transparency**  
   - Add support email, website, and security sentence to the shared footer.  
   - Add “Why you received” and “Manage notification preferences” (for non–system_critical) to the layout; pass per-template text from callers.

3. **Categories**  
   - Add `email_category` to notification_templates (or a map template_key → category).  
   - Map existing template_keys to system_critical | compliance_notifications | reporting_notifications | marketing_notifications.

4. **Preferences**  
   - Extend notification_preferences (or equivalent) with compliance_notifications_enabled, reporting_notifications_enabled, marketing_notifications_enabled.  
   - Defaults: e.g. True for compliance and reporting, False for marketing (or per your policy).

5. **Enforcement**  
   - In the orchestrator, before send: if template is not system_critical, load preferences and skip send (and optionally write a blocked log) when the corresponding flag is False.

6. **Templates**  
   - Refactor customer-facing `_build_html_body` branches (and any DB templates that are customer-facing) to use the new layout function; supply greeting, body, CTA, why_received, and whether to show preferences link.  
   - Leave internal/staff templates (admin-manual, OPS_ALERT, etc.) unchanged for the customer layout.

7. **Logging**  
   - Ensure message_log (or metadata) includes category when available; log preference updates (e.g. when user disables a category) in audit_log.

8. **Optional**  
   - Add `backend/email/templates/base_email.html` (Jinja) later if you want to move to file-based templates; keep the same structure and variables so content matches the Python-built layout.

---

## 5. Deliverables Checklist (Task vs Proposed)

| Deliverable | Task | Implemented |
|-------------|------|--------------|
| Base email layout template | backend/email/templates/base_email.html | Python shared layout in `backend/email_templates/email_layout.py` (avoids stdlib `email` shadowing). |
| Updated templates using the layout | All customer emails | Refactor customer-facing branches and DB templates to use the layout; keep internal templates separate. |
| Notification preference model | user_notification_preferences, user_id, 3 flags | Extend notification_preferences (client_id) with 3 category flags; document user_id → client_id if needed. |
| Enforcement before send | if not system_critical: check prefs; if disabled, do not send | In orchestrator, after gating, resolve category and preferences; block send and optionally log when disabled. |
| Hyperlink styling | No raw URLs | Already satisfied; keep using links/buttons. |
| Logging of email activity | user_id, email_type, category, timestamp, delivery_status | message_log already has client_id, template_key, status, created_at; add category to metadata or field; keep existing audit for sends and add audit for preference changes. |

---

## 6. Status

- **Audit:** Complete.  
- **Implementation:** Not started. Proceed with the proposed order and recommendations above when approved; do not add a new template engine or duplicate sending paths.
