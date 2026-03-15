# Lead follow-up / email sequence: logging and flow

## Summary

- **Lead tab (per-lead):** Follow-up and nurture sends **are** logged on the lead’s audit log so admins can see progress and which message was sent.
- **Notification health & email delivery:** Those same sends **are** recorded in `message_logs` and appear in the admin Notification Health and Email Delivery views; they are not currently filterable by `lead_id`.

---

## 1. Flow when a follow-up or nurture email is sent

### Day-based / type-based follow-up (LeadFollowUpService)

1. **Scheduler** (e.g. every 15 minutes) runs `LeadFollowUpService.process_followup_queue()`.
2. Queue finds leads with `followup_status IN_PROGRESS`, `next_followup_at <= now`, and consent/eligibility checks pass.
3. For each lead, `send_next_followup(lead)`:
   - Picks the next step from the sequence (e.g. `nurture_day0_welcome`, `nurture_day2_compliance_education`, or type-specific steps).
   - Calls `send_followup_email(lead, template_id, subject)` which uses **notification_orchestrator.send** with `template_key="LEAD_FOLLOWUP"`, `event_type=f"lead_followup_{template_id}"`, `client_id=None`.
4. **After send:**
   - **Lead document:** `followup_step`, `last_followup_at`, `next_followup_at` (and `followup_status=COMPLETED` when sequence ends) are updated.
   - **Lead audit log:** `LeadService.log_audit(FOLLOWUP_EMAIL_SENT, lead_id, details={ step, template_id, email })` or on failure `LeadService.log_audit(FOLLOWUP_EMAIL_FAILED, lead_id, details={ step, template_id, error })`.
5. **Orchestrator** writes a row to **message_logs** (status PENDING then SENT/FAILED) with `client_id=None`, `template_key=LEAD_FOLLOWUP`, `metadata.event_type=lead_followup_{template_id}`. Recipient comes from context; **lead_id is not stored in message_logs**.

### Checklist nurture (LeadNurtureService)

1. **Initial send:** When a checklist lead is created with consent, `send_checklist_delivery_email_and_update_lead` sends email 1 and sets `nurture_stage=1`, `last_nurture_sent_at`.
2. **Daily job** `process_checklist_nurture_queue()` finds COMPLIANCE_CHECKLIST leads due for the next nurture (stages 2–5), sends one email per lead per run.
3. **After each send:** Lead is updated (`nurture_stage`, `last_nurture_sent_at`) and **LeadService.log_audit(FOLLOWUP_EMAIL_SENT, lead_id, details={ type: "checklist_nurture", nurture_stage, email })** is called.
4. Orchestrator again writes to **message_logs** with `client_id=None`; event_type is like `checklist_nurture_1`, etc.

### Other lead-related emails

- **Risk-check completed** transactional: sent via orchestrator with `event_type="lead_transactional_risk_check_completed"`; lead_followup_service logs **FOLLOWUP_EMAIL_SENT** with details.
- **SLA breach / hot lead / high intent** admin alerts: sent via orchestrator; not logged to lead audit (they are internal admin notifications).

---

## 2. Where things are logged

| What | Where | Visible to admin |
|------|--------|-------------------|
| Each follow-up/nurture **send** (and failure) | **lead_audit_logs** (via `LeadService.log_audit`) | Yes – Lead detail → **Audit** tab |
| Same sends (delivery attempt) | **message_logs** (by notification_orchestrator) | Yes – **Notification Health** (recent/summary/timeseries) and **Email delivery** |
| Lead progress (step/stage) | **leads** document: `followup_step`, `last_followup_at`, `next_followup_at`, `followup_status`; for checklist also `nurture_stage`, `last_nurture_sent_at` | Yes – Lead detail (overview / Checklist Nurture card) |

---

## 3. Lead tab – what the admin sees

- **Overview:** Score, stage, tags, `followup_status`, and for checklist leads **Checklist Nurture Sequence** (nurture_stage 0–5, last nurture sent at).
- **Audit tab:** List of audit events (e.g. `LEAD_CREATED`, `FOLLOWUP_EMAIL_SENT`, `FOLLOWUP_EMAIL_FAILED`, `LEAD_CONTACTED`, …) with `created_at`, `actor_id`, `actor_type`. Each `FOLLOWUP_EMAIL_SENT` / `FOLLOWUP_EMAIL_FAILED` has **details** (e.g. `step`, `template_id`, or `type: "checklist_nurture"`, `nurture_stage`) in the API; the UI currently shows event + actor and could be extended to show these details so the admin can see “which message / which stage” was sent.

---

## 4. Notification health and email delivery

- **message_logs** is the source for:
  - **GET /api/admin/notification-health/summary** (aggregates, status)
  - **GET /api/admin/notification-health/timeseries** (buckets)
  - **GET /api/admin/notification-health/recent** (recent message_logs with template_key, status, recipient, error, etc.)
  - **GET /api/admin/email-delivery** (message_logs + EMAIL_SKIPPED_NO_RECIPIENT audit, filterable by template, status, client_id, since)
- Lead follow-up/nurture emails are written with **client_id=null** and **template_key=LEAD_FOLLOWUP** (or similar); **metadata.event_type** identifies the specific flow (e.g. `lead_followup_nurture_day2_compliance_education`, `checklist_nurture_2`). So they **do** appear in notification health and email delivery, but **cannot be filtered by lead_id** because lead_id is not stored in message_logs. Adding `lead_id` to the context passed to the orchestrator (and then to message_logs metadata) would allow filtering “all emails for this lead” in the email delivery view if desired.

---

## 5. End-to-end flow (concise)

1. Lead is created → optional **start_followup_sequence** or checklist delivery sets `followup_status`, `next_followup_at` or `nurture_stage`.
2. **Scheduler / daily job** runs → for each due lead, service sends one email via **notification_orchestrator.send**.
3. **Orchestrator** sends via Postmark and writes **message_logs** (PENDING → SENT/FAILED); lead emails use `client_id=None`, `event_type` in metadata.
4. **Lead service** updates the **leads** document (step/stage, last sent, next due) and **LeadService.log_audit(FOLLOWUP_EMAIL_SENT or FOLLOWUP_EMAIL_FAILED)** → **lead_audit_logs**.
5. Admin sees: **per lead** – Audit tab (event + details in API; UI can show template_id/step/nurture_stage) and overview fields; **globally** – Notification Health and Email Delivery for all sends, including lead emails, without lead_id filter unless message_logs are extended.
