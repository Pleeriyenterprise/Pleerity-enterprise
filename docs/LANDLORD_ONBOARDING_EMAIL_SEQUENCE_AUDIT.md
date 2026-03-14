# Landlord 7-Day Onboarding Email Sequence – Task vs Codebase Audit

## Goal

Audit the codebase against the task requirements for a **behaviour-aware 7-day onboarding email sequence** for new landlords. Identify what is implemented, what is missing, and any conflicts. Propose the safest, most professional implementation path. **Do not implement blindly.**

---

## 1. Current Architecture Summary

| Component | Current implementation |
|-----------|------------------------|
| **Email event registry** | `backend/services/email_event_registry.py`: flat dict `EMAIL_EVENTS` (event_id → category, template_key, trigger). No formal "event groups"; category `reporting_notifications` exists and is used for SCHEDULED_REPORT, MONTHLY_DIGEST, RENEWAL_REMINDER. |
| **Notification preferences** | `notification_preferences` collection keyed by `client_id`. Fields: `reporting_notifications_enabled`, `compliance_notifications_enabled`, `marketing_notifications_enabled`. Orchestrator gates by `email_category`; for `reporting_notifications` it checks `reporting_notifications_enabled` (default True). |
| **Email send logging** | **`message_logs`** collection (not "email_send_log"). Fields include: message_id, client_id, recipient, template_key, channel, status, idempotency_key, metadata, created_at. All sends go through `notification_orchestrator.send()` and are logged here. |
| **Scheduler** | APScheduler (AsyncIOScheduler) with **MongoDB job store** (`scheduled_jobs`). Jobs are **recurring** (cron/interval) and referenced as `job_runner:run_scheduled_job` with args=`[job_id]`. No per-user one-off jobs in current design. |
| **Delayed / sequence emails** | **Lead nurture**: `lead_nurture_service.process_checklist_nurture_queue()` – recurring job finds **leads** (not clients) due by `created_at` + NURTURE_DAYS; sends one email per lead per run; updates lead `nurture_stage`. No queue collection; query is over `leads` with stage + created_at. **Pattern**: single recurring job + query "due" items. |
| **Templates** | **Python-built HTML** in `email_service._build_html_body()` (and `email_templates/email_layout.py` for customer layout). **No .html files** in backend; no Jinja/file-based email templates. New templates = new `EmailTemplateAlias` + branch in email_service. |
| **User / landlord identity** | "User" in task = **client** (organisation). First **portal user** is created at provisioning. Trigger for "new landlord" = when **client** is provisioned (onboarding_status = PROVISIONED) and welcome/password-setup email sent (provisioning_jobs.status = WELCOME_EMAIL_SENT). |
| **Onboarding checklist** | `onboarding_checklist_service`: server-driven checklist (add properties, set jurisdictions, upload certificates, etc.). State on `client.onboarding_checklist`. Used for UI; not currently used for email sequence. |
| **Duplicate protection** | Orchestrator: `idempotency_key` → insert one log; duplicate key → return `duplicate_ignored`. So "same onboarding email twice" = use stable idempotency_key per (client_id, event_id). |

---

## 2. Task Requirements vs Current State

### 2.1 Define New Onboarding Event Group (LANDLORD_ONBOARDING_SEQUENCE)

| Requirement | Status | Notes |
|-------------|--------|-------|
| Event group LANDLORD_ONBOARDING_SEQUENCE | **Missing** | Registry has no "groups"; only flat event list. |
| 8 events (ONBOARDING_DAY0_WELCOME … ONBOARDING_DAY7_ACTIVATION_PUSH) | **Missing** | Not in EMAIL_EVENTS. |
| Category reporting_notifications | **Exists** | Category and preference check already in orchestrator. |
| Template names (welcome_onboarding_email, …) | **Missing** | No such template_key or alias yet. |

**Recommendation:** Add the 8 events to `email_event_registry.py` with category `reporting_notifications` and template_keys that match new aliases (e.g. ONBOARDING_DAY0_WELCOME → template_key ONBOARDING_DAY0_WELCOME). Optionally add a constant list `LANDLORD_ONBOARDING_EVENT_IDS` for the sequence order and use it in the scheduler/queue.

---

### 2.2 Trigger Conditions (user_onboarding_started)

| Requirement | Status | Notes |
|-------------|--------|-------|
| Start sequence when "User registers" | **Clarification** | In this codebase, "landlord" = client; "register" = client provisioned and portal ready. |
| Trigger event: user_onboarding_started | **Missing** | No such event or hook. |
| When triggered: schedule onboarding sequence jobs | **Missing** | No scheduling call. |

**Recommendation:** Define **user_onboarding_started** as: client_id just reached **WELCOME_EMAIL_SENT** in provisioning (portal ready, password-setup email sent). **Trigger point**: in `provisioning_runner.run_provisioning_job()` after setting status to WELCOME_EMAIL_SENT (and after optional analytics `provisioning_completed`), call a new function e.g. `schedule_onboarding_sequence(client_id)`. That function does **not** add 8 one-off scheduler jobs (APScheduler + MongoDB store is better suited to recurring jobs). Instead it should **enqueue** 8 items in a new queue collection (see 2.3).

---

### 2.3 Scheduling System

| Requirement | Status | Notes |
|-------------|--------|-------|
| schedule_onboarding_sequence(user_id) | **Missing** | Task says user_id; codebase uses client_id for notifications. Use **client_id**. |
| Day 0 immediately … Day 7 +168 hours | **Missing** | No queue or jobs. |
| Same scheduler as other lifecycle jobs | **Partial** | Scheduler is shared; current lifecycle jobs are **recurring** (cron/interval). Per-user **one-off** at run_date would require `scheduler.add_job(..., DateTrigger(run_date=...))` with unique job id per (client_id, day). Possible but: (1) MongoDB job store + many users = many jobs; (2) cancelling "remaining" jobs requires removing jobs from scheduler by id. |

**Conflict:** Task says "schedule the onboarding sequence jobs" with specific run times. Two approaches:

- **A) One-off scheduler jobs per user:** Add 8 jobs per client with DateTrigger(run_date=...). Job id e.g. `onboarding_{client_id}_day{N}`. To cancel: remove jobs by id. Works but increases scheduler load and requires careful cleanup on "stop sequence".
- **B) Queue + recurring processor (recommended):** New collection e.g. `onboarding_email_queue`: documents `{ client_id, event_id, send_at, status }`. `schedule_onboarding_sequence(client_id)` inserts 8 rows with send_at = now, now+24h, … now+168h. A **recurring** job (e.g. every 15–60 min) runs `process_onboarding_email_queue()`: finds rows with `send_at <= now` and `status = PENDING`, runs behaviour checks, sends email, marks SENT. Cancel by updating queue: `status = CANCELLED` for client_id. Aligns with `notification_retry_queue` and lead nurture patterns; no dynamic scheduler add/remove.

**Recommendation:** Use **B) Queue + recurring processor**. Same "scheduler" in the sense that a scheduled job runs periodically; the "when" for each email is stored in the queue. Document "schedule_onboarding_sequence(client_id)" as "enqueue 8 onboarding email items with send_at offsets".

---

### 2.4 Behaviour-Aware Conditions (check_onboarding_state)

| Requirement | Status | Notes |
|-------------|--------|-------|
| check_onboarding_state(user_id) → has_added_property, has_uploaded_certificate, monitoring_enabled | **Missing** | No such helper. |
| If monitoring_enabled → stop sequence | **N/A** | Need to define "monitoring_enabled". |
| If has_added_property and no certificate → modify content to encourage upload | **N/A** | Content variant; can be done in template or context. |
| If user already activated monitoring → do not send remaining emails | **N/A** | Same as stop condition. |

**Recommendation:** Add `onboarding_state_checker.py` (or equivalent) with async `check_onboarding_state(client_id) -> dict`:

- **has_added_property:** `properties.count_documents({"client_id": client_id}) >= 1`.
- **has_uploaded_certificate:** At least one document/certificate linked to a property (exact collection/field to use: follow existing document storage, e.g. `documents` or property-level docs).
- **monitoring_enabled:** Use **notification_preferences.compliance_notifications_enabled === True** as the "opted into compliance monitoring" flag. Optionally also require at least one property so "activation" = property + compliance alerts on. For "stop sequence" the minimal safe definition is: **compliance_notifications_enabled === True**.

Before each send in the queue processor: call `check_onboarding_state`; if `monitoring_enabled` → mark all remaining PENDING items for this client as CANCELLED and skip send. If `has_added_property` and not `has_uploaded_certificate` → pass a flag in context so template/body can show "encourage certificate upload" variant (optional; can be Phase 2).

---

### 2.5 Template Content Requirements (structure)

| Requirement | Status | Notes |
|-------------|--------|-------|
| All templates: Header, Greeting, Main content, CTA, Why-you-received, Notification preferences link, Footer | **Exists** | Customer layout in `email_templates/email_layout.py` and `_build_html_body` already provides this for customer-facing templates (header, greeting, body, cta_label/cta_url, why_received, show_preferences_link, footer). |

**Recommendation:** Use the **existing customer layout** (build_customer_email_layout) for all 8 onboarding emails so they automatically get the required structure. No new structure needed.

---

### 2.6 Template Purposes and CTAs (8 templates)

| Template | Purpose / CTA | Status |
|----------|----------------|--------|
| welcome_onboarding_email | Introduce Pleerity; CTA "Add your first property" | Missing |
| setup_reminder_email | Remind setup; list monitored items; CTA "Continue setup" | Missing |
| compliance_education_email | Educate on requirements; CTA "Track these automatically in Pleerity" | Missing |
| product_value_email | Automation engine; CTA "View your compliance dashboard" | Missing |
| document_pack_intro_email | Landlord document packs; CTA "View landlord document packs" | Missing |
| risk_awareness_email | Consequences of missing certs; CTA "Enable compliance alerts" | Missing |
| case_example_email | Scenario (e.g. Gas Safety); CTA "Start monitoring your property" | Missing |
| activation_push_email | Final push; CTA "Activate monitoring" | Missing |

All 8 are missing. Content and CTAs can be implemented as per task once templates exist.

---

### 2.7 Template Implementation: File-Based vs Python-Built

| Requirement | Status | Notes |
|-------------|--------|-------|
| Task: "email templates folder: welcome_onboarding_email.html …" | **Conflict** | Codebase has **no .html email templates**; all customer email HTML is built in Python in `email_service._build_html_body()` and `email_templates/email_layout.py`. |

**Conflict:** Task asks for literal `.html` files in an "email templates folder". The codebase standard is **Python-built** templates (see also INTERNAL_ALERT_EMAIL_SYSTEM_AUDIT.md).

**Recommendation:** Implement the 8 onboarding emails as **Python-built** templates: add 8 `EmailTemplateAlias` values and 8 branches in `_build_html_body` / `_build_text_body` (or one parameterised branch keyed by template_key). Use the existing customer layout and pass per-template content (title, body copy, cta_label, cta_url, why_received). **Do not** introduce a new template engine or .html files for this feature only. Document in deliverables: "Templates implemented as Python-built templates (no .html files), consistent with existing codebase."

---

### 2.8 Sequence Stop Conditions

| Requirement | Status | Notes |
|-------------|--------|-------|
| Stop if user enables monitoring | **N/A** | Handled by check_onboarding_state + cancel remaining queue items. |
| Stop if user disables onboarding emails | **Clarification** | Task could mean: (1) disable **reporting_notifications** (then orchestrator already blocks send), or (2) a separate "onboarding sequence" opt-out. Recommendation: (1) only – if reporting_notifications_enabled is False, orchestrator blocks; no need to cancel queue. Optionally (2) later: add e.g. onboarding_sequence_opted_out on notification_preferences and check before send. |
| Stop if account deleted | **N/A** | Processor can check client exists before send; if not, mark queue item failed/cancelled. |
| Cancel remaining scheduled jobs | **N/A** | With queue approach: update queue status to CANCELLED for client_id where status = PENDING. |

---

### 2.9 Preference Enforcement

| Requirement | Status | Notes |
|-------------|--------|-------|
| Before each send: check user_notification_preferences; if reporting_notifications_enabled == False, do not send | **Done** | Orchestrator already loads notification_preferences by client_id and blocks when email_category is reporting_notifications and reporting_notifications_enabled is False. Onboarding templates will use category reporting_notifications. |

No extra logic needed; ensure template_key → notification_templates row with email_category = reporting_notifications.

---

### 2.10 Email Send Logging

| Requirement | Status | Notes |
|-------------|--------|-------|
| Log in "email_send_log" with user_id, email_event, template_used, timestamp, delivery_status | **Conflict** | Codebase uses **message_logs** (no "email_send_log"). Fields: client_id (not user_id), template_key, status, created_at; metadata can hold email_event. |

**Recommendation:** Use **message_logs** as the send log. When sending onboarding email, pass `event_type` (or equivalent) in context so it is stored in metadata. Optionally store `email_event` in metadata for easy querying. Map task "user_id" → **client_id**; "delivery_status" → **status** (PENDING, SENT, FAILED, etc.). Document the mapping in deliverables.

---

### 2.11 Duplicate Protection

| Requirement | Status | Notes |
|-------------|--------|-------|
| Prevent sending same onboarding email twice; check if email_event already logged before sending | **Partial** | Orchestrator idempotency_key prevents duplicate **send** for the same key. Queue processor can use idempotency_key = e.g. `ONBOARDING_{event_id}_{client_id}` so each (client, event) is sent at most once. Alternatively, before send, query message_logs for client_id + metadata.email_event = event_id; if found, skip and mark queue item SENT. |

**Recommendation:** Use **idempotency_key** = `ONBOARDING_{event_id}_{client_id}` so orchestrator handles duplicate prevention. Optionally also check queue item status (only process PENDING) and after send set status = SENT so the same row is never processed again.

---

### 2.12 Files to Create or Modify (task list)

| Task file | Action | Notes |
|-----------|--------|-------|
| backend/services/email_event_registry.py | **Modify** | Add LANDLORD_ONBOARDING_EVENT_IDS and 8 entries in EMAIL_EVENTS. |
| backend/services/onboarding_scheduler.py | **Create** | Implement schedule_onboarding_sequence(client_id) (enqueue 8 items) and process_onboarding_email_queue() (recurring job logic). Optionally split: onboarding_sequence_service.py for queue + processor, and call from job_runner. |
| backend/services/email_service.py | **Modify** | Add 8 template branches (or one parameterised) and 8 EmailTemplateAlias if not already added elsewhere. |
| backend/services/onboarding_state_checker.py | **Create** | check_onboarding_state(client_id) → has_added_property, has_uploaded_certificate, monitoring_enabled. |
| email templates folder: *.html | **Conflict** | Use Python-built templates; no .html files. |

Additional files:

- **database.py:** Seed 8 notification_templates rows (template_key, email_template_alias, email_category=reporting_notifications).
- **models/core.py:** Add 8 EmailTemplateAlias values for onboarding emails.
- **job_runner.py:** Add run_onboarding_sequence_processing and register in JOB_RUNNERS.
- **server.py:** Add recurring job (e.g. hourly) for onboarding_sequence_processing.
- **provisioning_runner.py:** After WELCOME_EMAIL_SENT, call schedule_onboarding_sequence(client_id).

---

## 3. Conflicts and Recommended Resolution

| # | Conflict | Recommended resolution |
|---|----------|------------------------|
| 1 | Task: ".html" email templates in folder | Use **Python-built** templates in email_service + existing customer layout; no new .html files. |
| 2 | Task: "email_send_log" | Use existing **message_logs**; map user_id → client_id, delivery_status → status; store email_event in metadata. |
| 3 | Task: "schedule jobs" (one-off per user) | Use **queue + recurring processor** instead of 8 one-off scheduler jobs per user; same scheduler system, simpler and consistent with codebase. |
| 4 | "User" vs client | Use **client_id** everywhere (recipient from client contact_email or portal user email as per orchestrator). |

---

## 4. Implementation Order (Safest)

1. **Registry and templates (no send yet)**  
   Add 8 events to email_event_registry; add 8 EmailTemplateAlias and notification_templates seeds; add 8 branches in email_service (or one parameterised) using customer layout. No scheduler or trigger yet.

2. **Onboarding state checker**  
   Implement onboarding_state_checker.check_onboarding_state(client_id). Define monitoring_enabled (e.g. compliance_notifications_enabled), has_added_property, has_uploaded_certificate.

3. **Queue and processor**  
   Add collection onboarding_email_queue (client_id, event_id, send_at, status). Implement schedule_onboarding_sequence(client_id) to insert 8 PENDING rows. Implement process_onboarding_email_queue(): find due PENDING; for each, load client, check_onboarding_state (cancel rest if monitoring_enabled), check reporting pref, send via orchestrator with idempotency_key ONBOARDING_{event_id}_{client_id}, mark SENT, handle stop conditions.

4. **Trigger**  
   In provisioning_runner after WELCOME_EMAIL_SENT, call schedule_onboarding_sequence(client_id).

5. **Recurring job**  
   Register run_onboarding_sequence_processing in job_runner and add hourly (or similar) job in server.py.

6. **Cancel on monitoring enabled**  
   When compliance_notifications_enabled is set to True (e.g. in profile update_notification_preferences), call a small helper to cancel remaining PENDING onboarding queue items for that client_id. Optional: cancel on account delete (e.g. client deleted).

---

## 5. Deliverables Checklist (to return)

- **Files created:** onboarding_state_checker.py, onboarding_scheduler.py (or onboarding_sequence_service.py with queue + processor).
- **Files modified:** email_event_registry.py, email_service.py, models/core.py, database.py, job_runner.py, server.py, provisioning_runner.py.
- **Scheduler integration:** Recurring job for process_onboarding_email_queue; schedule_onboarding_sequence called from provisioning_runner.
- **Onboarding state logic:** check_onboarding_state(client_id) with has_added_property, has_uploaded_certificate, monitoring_enabled.
- **Email templates:** 8 Python-built templates (no .html); registry updates; 8 notification_templates seeded.
- **Example scheduled job output:** Log or document shape of queue after schedule_onboarding_sequence(client_id) (e.g. 8 documents with send_at and event_id).

---

## 6. Summary

- **Implemented:** Notification preferences (reporting_notifications), message_logs, orchestrator gating, customer email layout, provisioning flow and WELCOME_EMAIL_SENT, recurring scheduler pattern.
- **Missing:** Onboarding event group and 8 events, 8 templates, queue collection and processor, schedule_onboarding_sequence trigger, behaviour check (check_onboarding_state), cancel-remaining logic.
- **Conflicts resolved:** Use Python-built templates (no .html); use message_logs (not email_send_log); use client_id; use queue + recurring job (not 8 one-off scheduler jobs per user).

Implement in the order above and avoid duplicating existing preference or logging behaviour.
