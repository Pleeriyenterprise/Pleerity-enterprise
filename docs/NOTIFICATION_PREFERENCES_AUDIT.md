# Notification Preferences & Intake Contact Preferences – Audit Report

**Goal:** Determine if UI toggles and intake selections are (1) saved, (2) read during notification sending, and (3) actually change who gets contacted and via which channel.

**Date:** 2025-02 (codebase snapshot).

---

## 1) Notifications Settings Page – API & Storage

### Frontend
- **Page:** `frontend/src/pages/NotificationPreferencesPage.js`
- **GET:** `api.get('/profile/notifications')` → `GET /api/profile/notifications` (line 252)
- **PUT:** `api.put('/profile/notifications', preferences)` → `PUT /api/profile/notifications` (line 289)

### Backend
- **Routes:** `backend/routes/profile.py`
  - `GET /api/profile/notifications` → `get_notification_preferences` (lines 118–170)
  - `PUT /api/profile/notifications` → `update_notification_preferences` (lines 173–274)
- **Request body (PUT):** `NotificationPreferencesRequest` – all fields optional; see `profile.py` lines 21–49.
- **DB:** Collection `notification_preferences`; keyed by `client_id`; upsert on update (`profile.py` lines 244–247).
- **Return (GET):** Merged stored + defaults; includes `client_id`, all toggle and timing fields, SMS fields, digest section toggles, `daily_reminder_enabled`.

**Stored fields (and defaults):**
- `status_change_alerts`, `expiry_reminders`, `monthly_digest`, `document_updates`, `system_announcements` (all default True)
- `reminder_days_before` (7, 14, 30, 60, 90)
- `quiet_hours_enabled`, `quiet_hours_start`, `quiet_hours_end`
- `sms_enabled`, `sms_phone_number`, `sms_phone_verified`, `sms_urgent_alerts_only`
- `digest_compliance_summary`, `digest_action_items`, `digest_upcoming_expiries`, `digest_property_breakdown`, `digest_recent_documents`, `digest_recommendations`, `digest_audit_summary`
- `daily_reminder_enabled`

---

## 2) Intake Fields – Where Stored

| Field | Stored on | Model / collection | File:line |
|-------|-----------|--------------------|-----------|
| **preferred_contact** | Client | `Client.preferred_contact` (EMAIL / SMS / BOTH) | `backend/models/core.py` 347; `backend/routes/intake.py` 757 |
| **managed_by** | Property | `Property.managed_by` (LANDLORD / AGENT) | `backend/models/core.py` 528, 757; intake `routes/intake.py` 804 |
| **send_reminders_to** | Property | `Property.send_reminders_to` (LANDLORD / AGENT / BOTH) | `backend/models/core.py` 529, 758; `routes/intake.py` 805 |
| **agent_name, agent_email, agent_phone** | Property | `Property` | `backend/models/core.py` 530–532, 759–761; `routes/intake.py` 806–808 |

**Note:** There is no field named `reminder_recipient`; the equivalent is **`send_reminders_to`** on the property.

---

## 3) Notification Sending Pipeline

### Scheduler / jobs
- **Entrypoints:** `backend/job_runner.py` – `run_daily_reminders()`, `run_monthly_digests()`, `run_compliance_status_check()` (lines 13–64).
- **Implementation:** `backend/services/jobs.py` – `JobScheduler.send_daily_reminders`, `send_monthly_digests`, `check_compliance_status_changes`.

### What each job does and what it reads

| Job | Method | Prefs read | Used to suppress? | Recipient resolution |
|-----|--------|------------|-------------------|------------------------|
| Daily reminders | `send_daily_reminders` | `expiry_reminders`, `reminder_days_before` | Yes: skip if `expiry_reminders` false | Client only; `_send_reminder_email(client, …)`; SMS via `_maybe_send_reminder_sms(client, prefs, …)` |
| Monthly digest | `send_monthly_digests` | `monthly_digest` | Yes: skip if `monthly_digest` false | Client only; `client.email` or `client.contact_email` |
| Compliance status | `check_compliance_status_changes` | `status_change_alerts` | Yes: skip alert if false | Client only |

**Recipient and channel resolution:**
- **`backend/services/notification_orchestrator.py`**
  - `send()` loads client (lines 206–219) and `notification_preferences` (lines 227–231; only `sms_enabled`, `sms_phone_number` projected).
  - Channel comes from **template** (`template.channel`: EMAIL or SMS), not from client.preferred_contact.
  - **`_resolve_recipient(client, channel)`** (lines 422–432):
    - EMAIL: `client.contact_email` or `client.email`
    - SMS: if `prefs.sms_enabled` then `prefs.sms_phone_number` or `client.sms_phone_number`; else None

**Providers:**
- **Email:** Postmark via `_postmark_client` (`notification_orchestrator.py` 67–73, 480–572). Requires `POSTMARK_SERVER_TOKEN`.
- **SMS:** Twilio via `_twilio_client` (76–84, 601+). Requires `SMS_ENABLED=true`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, and `TWILIO_PHONE_NUMBER` or `TWILIO_MESSAGING_SERVICE_SID`.

**Message logging:**
- All sends (and blocks) go to **`message_logs`** (e.g. `notification_orchestrator.py` 276–284, 539–546). Audit events: `AuditAction.EMAIL_SENT`, `EMAIL_SKIPPED_NO_RECIPIENT`, `NOTIFICATION_PROVIDER_NOT_CONFIGURED`, etc.

---

## 4) Truth Table – Inputs vs Behaviour

**Inputs (from UI + intake):**

- **Notification preferences (per client):**  
  `expiry_reminders`, `monthly_digest`, `status_change_alerts`, `document_updates`, `system_announcements`, `daily_reminder_enabled`, `quiet_hours_*`, `sms_enabled`, `sms_phone_number`, `sms_urgent_alerts_only`, `reminder_days_before`, digest_* toggles.
- **Intake (client):** `preferred_contact` (EMAIL / SMS / BOTH).
- **Intake (property):** `send_reminders_to` (LANDLORD / AGENT / BOTH), `managed_by`, `agent_email`, `agent_phone`.

**Outputs (who receives, which channel, what is suppressed):**

| Preference / intake | Stored? | Read when sending? | Effect today |
|---------------------|--------|---------------------|--------------|
| **expiry_reminders** | Yes | Yes (`jobs.py` 75–79) | If False → daily reminder job skips client (no email, no SMS). |
| **reminder_days_before** | Yes | Yes (`jobs.py` 76, 95) | Used to filter requirements “expiring in next N days”. |
| **monthly_digest** | Yes | Yes (`jobs.py` 211–214) | If False → monthly digest job skips client. |
| **status_change_alerts** | Yes | Yes (`jobs.py` 499, 574) | If False → no compliance status change email (webhooks still fire). |
| **daily_reminder_enabled** | Yes | **No** | **UI-only.** Daily reminder job does not check it; user can turn “daily reminder” off in UI but still receives it. |
| **quiet_hours_*** | Yes | **No** | **UI-only.** No job checks time window; sends can occur during “quiet hours”. |
| **document_updates** | Yes | **No** | **UI-only.** No code path that sends “document upload/verification” notifications checks this. (AI extraction applied email in `documents.py` ~1810 does not check it.) |
| **system_announcements** | Yes | **No** | **UI-only.** No “system announcement” send path that checks this. |
| **digest_*** (sections) | Yes | **No** | **UI-only.** Digest content is built in jobs without filtering by digest_compliance_summary, digest_action_items, etc. |
| **sms_enabled** | Yes | Yes (orchestrator `_resolve_recipient` 427–430) | If False → SMS recipient is None → SMS blocked (no_recipient). |
| **sms_phone_number** | Yes | Yes (orchestrator 430) | Used as SMS destination when sms_enabled. |
| **sms_urgent_alerts_only** | Yes | **No** | **UI-only.** SMS reminder is sent regardless of severity when plan allows and sms_enabled. |
| **preferred_contact** (client) | Yes (intake → client) | **No** | **Not used.** Channel is determined by template + plan + prefs.sms_enabled; client.preferred_contact is never read. |
| **send_reminders_to** (property) | Yes | **No** | **Not used.** All reminder/digest/alert sends go to client (client.email / contact_email); no logic to send to agent or BOTH. |
| **managed_by** | Yes | **No** | **Not used** for notifications. |
| **agent_email / agent_phone** | Yes | **No** | **Not used** when sending reminders or digests. |

**Who receives today:**
- **(a)** All reminder/digest/alert emails go to **client** (`client.email` or `client.contact_email`). No routing to agent or alternate recipient based on property.
- **(b)** **Channels:** Email always used when template is EMAIL. SMS used only when (1) template is SMS, (2) plan has `sms_reminders`, (3) `prefs.sms_enabled`, (4) `prefs.sms_phone_number` (or client.sms_phone_number) set. `preferred_contact` does not influence this.
- **(c)** **Suppressed events:** Only when `expiry_reminders` false (daily reminder), `monthly_digest` false (monthly digest), or `status_change_alerts` false (compliance alert). All other toggles are stored but not enforced.

---

## 5) SMS Implementation Status

- **SMS is implemented** (Twilio in `notification_orchestrator.py:601`; `_send_sms`; `COMPLIANCE_EXPIRY_REMINDER_SMS` template; plan feature `sms_reminders`; 24h throttle).
- **Behaviour:** SMS is sent only when template is SMS, plan allows `sms_reminders`, and client has `sms_enabled` and a phone number. So the “SMS option” in the UI is enforced for the reminder SMS path.
- **Gaps:**  
  - `sms_urgent_alerts_only` is not enforced (no “only send SMS for RED” logic).  
  - No need to “disable SMS option” or “SMS coming soon” unless product decision is to hide SMS until fully ready; currently it is functional for plan-gated reminder SMS.

---

## 6) Root-Cause Summary

| Area | Implemented | UI-only / not enforced |
|------|-------------|--------------------------|
| **Settings API** | GET/PUT save and load all toggles; DB and return schema correct | — |
| **Daily reminder** | expiry_reminders, reminder_days_before respected | daily_reminder_enabled not checked |
| **Monthly digest** | monthly_digest respected | digest_* section toggles not used; digest content not filtered |
| **Status alerts** | status_change_alerts respected | — |
| **Document / system** | — | document_updates, system_announcements never read |
| **Quiet hours** | — | quiet_hours_* never read |
| **SMS** | sms_enabled + phone used for SMS recipient; plan gate + throttle | sms_urgent_alerts_only not used |
| **Intake** | preferred_contact, send_reminders_to, managed_by, agent_* stored | Never read for who receives or which channel; all sends go to client only |

---

## 7) File Paths + Line References (Quick Index)

| Component | File | Lines (approx) |
|-----------|------|-----------------|
| Client notification prefs model | `backend/models/core.py` | 401–439 |
| Profile GET/PUT notifications | `backend/routes/profile.py` | 118–274, 21–49 (request model) |
| Frontend Notifications page | `frontend/src/pages/NotificationPreferencesPage.js` | 252 (GET), 289 (PUT), 300–341 (toggle list) |
| Daily reminders job | `backend/services/jobs.py` | 46–179, 277–329 |
| Monthly digest job | `backend/services/jobs.py` | 181–274, 331–400 |
| Compliance status job | `backend/services/jobs.py` | 464–615 |
| Job runner entrypoints | `backend/job_runner.py` | 13–64 |
| Orchestrator send + recipient | `backend/services/notification_orchestrator.py` | 135–323, 422–432 |
| Orchestrator email/SMS | `backend/services/notification_orchestrator.py` | 480–572 (email), 601+ (SMS) |
| Intake client/preferred_contact | `backend/routes/intake.py` | 757, 665 (validation) |
| Intake property send_reminders_to, managed_by, agent_* | `backend/routes/intake.py` | 740–741, 804–808 |
| Property model | `backend/models/core.py` | 528–532, 757–761 |
| AI extraction applied email (no document_updates check) | `backend/routes/documents.py` | 1808–1829 |

---

## 8) Minimal Patch Plan to Fully Enforce Preferences

1. **Daily reminder**
   - In `jobs.py` in `send_daily_reminders`, after loading `prefs`, skip if `prefs.get("daily_reminder_enabled", True) is False` (same pattern as `expiry_reminders`).  
   - **File:** `backend/services/jobs.py` (e.g. after line 79).

2. **Quiet hours**
   - In the same job loop (and in `send_monthly_digests`, `check_compliance_status_changes` if they should respect quiet hours), after resolving “send to this client,” compute current time in client’s preferred TZ (or UTC if no TZ stored); if within `quiet_hours_start`–`quiet_hours_end` and `quiet_hours_enabled` is True, skip send (and optionally log or audit).  
   - Requires a small helper and optional `client.timezone` or use UTC.  
   - **Files:** `backend/services/jobs.py` (each job that sends).

3. **Document-updates preference**
   - Before calling `notification_orchestrator.send` for `AI_EXTRACTION_APPLIED` (and any other “document update” template), load `notification_preferences` for the document’s client_id; if `document_updates` is False, skip the send (and optionally log).  
   - **File:** `backend/routes/documents.py` (around 1807–1810).

4. **System announcements**
   - If/when a “system announcement” send path exists (e.g. admin-triggered or scheduled), load prefs and skip when `system_announcements` is False.  
   - No current send path to change in codebase.

5. **Digest sections**
   - When building digest content in `jobs.py` (e.g. `digest_content` dict and any HTML/text), omit sections when the corresponding digest_* pref is False (e.g. `digest_action_items`, `digest_upcoming_expiries`, …).  
   - **File:** `backend/services/jobs.py` (digest content building and any template that consumes it).

6. **sms_urgent_alerts_only**
   - In the daily reminder path, before calling `_maybe_send_reminder_sms`, check `prefs.get("sms_urgent_alerts_only", True)`; if True, only send SMS when there is at least one overdue (or “RED”) item in the expiring/overdue list; otherwise allow SMS for any reminder.  
   - **File:** `backend/services/jobs.py` (around 161–167).

7. **Intake: send_reminders_to / preferred_contact**
   - **Recipient routing:** In `jobs.py`, when building the reminder/digest run per client, consider properties’ `send_reminders_to` and, when AGENT or BOTH, resolve agent_email/agent_phone from properties; for each send, either (a) send to client only and keep current behaviour, or (b) send to client and/or agent based on `send_reminders_to` (e.g. separate orchestrator calls with `context.recipient` override for agent).  
   - **Channel:** If product wants “preferred_contact” to drive channel (e.g. BOTH → email and SMS when available), then in orchestrator or jobs, when template is reminder/digest, derive channel(s) from `client.preferred_contact` (and plan + prefs) and call send for each channel (email and/or SMS) instead of relying only on template channel.  
   - **Files:** `backend/services/jobs.py` (recipient and channel logic); `backend/services/notification_orchestrator.py` (if recipient override or multi-channel per event).

---

## 9) Tests to Add

1. **Unit: recipient/channel selection**
   - Given a client with `preferred_contact=BOTH`, `notification_preferences.sms_enabled=True`, `sms_phone_number` set; when a reminder is sent, assert that (after implementation) both email and SMS are attempted (or that the resolver returns both).  
   - Given `send_reminders_to=AGENT` and property with `agent_email` set, assert (after implementation) that the reminder email is sent to agent_email (e.g. via context.recipient or equivalent).

2. **Unit: toggles suppress sends**
   - With `expiry_reminders=False`, assert daily reminder job does not call `_send_reminder_email` for that client.  
   - With `daily_reminder_enabled=False` (after patch), assert daily reminder job does not send for that client.  
   - With `document_updates=False` (after patch), assert that applying AI extraction does not call `notification_orchestrator.send` for `AI_EXTRACTION_APPLIED`.  
   - With `monthly_digest=False`, assert monthly digest job skips client.  
   - With `status_change_alerts=False`, assert compliance status job does not send COMPLIANCE_ALERT for that client.

3. **Integration (optional)**
   - Run reminder job with a test client that has various prefs; assert message_logs (and optionally audit) contain expected sent vs blocked for that client.

---

## 10) Conflicting Instructions / Safest Option

- **Conflict:** Task asks to “add safe stubs: disable SMS option in UI OR show ‘SMS coming soon’” if SMS is not implemented. In this codebase, **SMS is implemented** (Twilio, plan-gated, preference-gated). Disabling the SMS option or showing “coming soon” would be misleading.  
- **Recommendation:** Do **not** disable or stub SMS in UI. Keep current behaviour; document that `sms_urgent_alerts_only` is not yet enforced and add that as a small follow-up (see patch plan item 6).

- **Intake vs settings:** Intake collects `preferred_contact` and property-level `send_reminders_to` / agent details; notification settings use a separate `notification_preferences` document. There is no conflict between them for storage; the gap is that **neither pipeline uses intake preferences for routing**. Safest option: implement routing in jobs/orchestrator in a backward-compatible way (default “client only” when `send_reminders_to` is missing or LANDLORD), and use `preferred_contact` only when product decides it should override or complement template channel (e.g. “BOTH” = send email and SMS for reminders).

---

## Summary

- **Saved and enforced:** `expiry_reminders`, `reminder_days_before`, `monthly_digest`, `status_change_alerts`, `sms_enabled`, `sms_phone_number` (for SMS path).
- **Saved but not enforced (UI-only):** `daily_reminder_enabled`, `quiet_hours_*`, `document_updates`, `system_announcements`, all `digest_*` section toggles, `sms_urgent_alerts_only`.
- **Intake stored but never used for notifications:** `preferred_contact`, `send_reminders_to`, `managed_by`, `agent_email`, `agent_phone`.
- **SMS:** Implemented (Twilio); no “disable SMS” or “coming soon” stub needed; add enforcement of `sms_urgent_alerts_only` if desired.
- **Minimal patch plan** (section 8) and **tests** (section 9) above complete the deliverables.
