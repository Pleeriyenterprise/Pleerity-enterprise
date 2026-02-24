# 7-Day Email Nurture Sequence for Checklist Leads — Audit

## Purpose

Check the codebase against the task requirements for the **7-day email nurture sequence** for compliance checklist leads. Identify what is implemented, what is missing, and any conflicts. Do not implement in this step.

---

## 1. Task Requirements (Summary)

| Area | Requirement |
|------|-------------|
| **Trigger** | `lead.source_platform == "COMPLIANCE_CHECKLIST"` |
| **New fields** | `nurture_stage` (int, default 0), `last_nurture_sent_at` (datetime) |
| **Sequence** | 5 emails: Day 0 (immediate), Day 2, Day 4, Day 6, Day 9 |
| **Logic** | Daily cron finds leads due for next email; send → increment `nurture_stage`; stop if lead converts to registered user |
| **Email** | Postmark transactional; unsubscribe link (must be respected); informational disclaimer; professional tone |
| **Constraints** | Do not modify provisioning flow |
| **Deliverables** | Email templates, automation logic, lead tracking updates, admin visibility of nurture stage |

---

## 2. What Is Already Implemented

| Item | Status | Location / Notes |
|------|--------|-------------------|
| **Lead capture for checklist** | ✅ | `routes/leads.py`: `POST /api/leads/capture/compliance-checklist` creates lead with `source_platform=COMPLIANCE_CHECKLIST`, `service_interest=CVP`. Does **not** start any follow-up (comment: "Does not start follow-up sequence"). |
| **Lead document shape** | ✅ | `lead_service.py`: `create_lead` builds lead with `followup_status`, `followup_step`, `last_followup_at`, `next_followup_at`, `followup_sequence`. No `nurture_stage` or `last_nurture_sent_at`. |
| **Unsubscribe endpoint** | ✅ | `POST /api/leads/unsubscribe/{lead_id}` sets `marketing_consent=False`, `followup_status=OPTED_OUT`; audit `MARKETING_CONSENT_UPDATED`. Nurture must **not** send when `followup_status == OPTED_OUT` or `marketing_consent == False`. |
| **Conversion = stop** | ✅ | `convert_lead` sets `status=CONVERTED`, `client_id`, `followup_status=STOPPED`. Existing follow-up logic already stops on `status` CONVERTED/LOST/MERGED/UNSUBSCRIBED and on `!marketing_consent`. Same checks apply to nurture. |
| **Postmark / templates** | ✅ | `notification_orchestrator.send()` with `template_key="LEAD_FOLLOWUP"`; `lead_followup_service` uses orchestrator, builds subject/body, passes `recipient`, `subject`, `message` (HTML). Template registered in DB as `LEAD_FOLLOWUP` (alias `admin-manual`). |
| **Follow-up queue job** | ✅ | `job_runner.run_lead_followup_processing()` → `LeadFollowUpService.process_followup_queue()`. Runs on scheduler (e.g. every 15 min). Finds leads with `followup_status=IN_PROGRESS`, `next_followup_at <= now`; uses `followup_sequence` (default vs abandoned_intake) and `followup_step` (1h, 24h, 72h). |
| **Unsubscribe in templates** | ✅ | `lead_followup_service.TEMPLATES`: each body includes `{unsubscribe_link}`; `UNSUBSCRIBE_URL` env (default `http://localhost:3000/unsubscribe`); link format `...?lead={lead_id}`. Nurture emails must include same pattern. |
| **Admin lead detail** | ✅ | `GET /api/admin/leads/{lead_id}` returns full lead; AdminLeadsPage shows Contact Info, Status & Qualification, audit log. No `nurture_stage` / `last_nurture_sent_at` displayed yet. |

---

## 3. What Is Missing

| Item | Status | Notes |
|------|--------|--------|
| **`nurture_stage` and `last_nurture_sent_at`** | ❌ | Not in `lead_models` or `create_lead` payload. Must be added to lead document (default 0 and None). |
| **Checklist-specific sequence** | ❌ | Current follow-up is 1h/24h/72h for default and abandoned_intake. Task requires **day-based** sequence: Day 0, 2, 4, 6, 9 (5 emails). Easiest: separate “nurture” flow for `source_platform == COMPLIANCE_CHECKLIST` (do not reuse `followup_step`/`next_followup_at` for this). |
| **Email 1 (Day 0) – immediate delivery** | ❌ | Task: thank, PDF link, expectations, light CVP positioning. Today capture redirects to thank-you page; **no immediate email** is sent. Either send from capture endpoint (right after create_lead) or from a job that runs frequently and treats “nurture_stage 0, created just now” as due. |
| **Emails 2–5 (Day 2, 4, 6, 9)** | ❌ | No templates or logic. Need: Gas Safety (Day 2), Portfolio compliance (Day 4), Deadline awareness (Day 6), Soft trial (Day 9). |
| **Daily cron for nurture** | ❌ | No job that selects `source_platform == COMPLIANCE_CHECKLIST`, `marketing_consent == True`, status not CONVERTED/LOST/MERGED, and “lead age >= X days and nurture_stage == N” to send next email and increment `nurture_stage`. |
| **Admin visibility of nurture stage** | ❌ | Lead API returns full doc; once fields exist they are available. Admin UI does not show `nurture_stage` or `last_nurture_sent_at`; add to Details (e.g. for COMPLIANCE_CHECKLIST only). |
| **Company address footer** | ⚠️ | Task: “Company address footer” in each email. Existing follow-up templates have “Reference: {lead_id}” and unsubscribe; no company address. Add to nurture (and optionally to existing follow-up) for compliance. |

---

## 4. Conflicts and Design Choices

### 4.1 Trigger: “If lead.source == compliance_checklist”

- Backend uses `source_platform` (value `COMPLIANCE_CHECKLIST`). Task sometimes says “source = compliance_checklist”. **No conflict**: treat as `source_platform == LeadSourcePlatform.COMPLIANCE_CHECKLIST`.

### 4.2 Reuse existing follow-up vs separate nurture

- **Existing:** `followup_sequence` (default / abandoned_intake), `followup_step` (0,1,2,3), `next_followup_at` (time-based). Used by `process_followup_queue()` every ~15 min.
- **Task:** Day 0, 2, 4, 6, 9 (day-based from `created_at`), 5 emails, “daily cron”.
- **Conflict:** Day-based scheduling does not fit the current “next_followup_at + followup_step” model (which is hour-based).
- **Recommendation:** Implement a **separate nurture flow** for checklist leads:
  - Add `nurture_stage` (0–5, 0 = none sent, 1–5 = email 1–5 sent) and `last_nurture_sent_at`.
  - Do **not** set `followup_status=IN_PROGRESS` or `next_followup_at` for checklist leads for this sequence (avoid mixing with 1h/24h/72h queue).
  - New daily job (or extend an existing daily run): find checklist leads where (created_at + required days ≤ now) and (nurture_stage = next expected stage); send email; set `nurture_stage += 1`, `last_nurture_sent_at = now`.  
  - **Email 1 (Day 0):** Send immediately on capture (after create_lead) **or** from the same daily job with “lead age >= 0 and nurture_stage == 0”. Immediate at capture is simpler and matches “Immediate – send checklist delivery email”.

### 4.3 Consent and unsubscribe

- Task: “Include unsubscribe link (it must be respected when user unsubscribes)”.
- **Already respected:** Unsubscribe sets `marketing_consent=False` and `followup_status=OPTED_OUT`. Nurture logic must **skip** sending when `marketing_consent != True` or `followup_status == OPTED_OUT` (same as existing follow-up). Use same unsubscribe URL pattern as in `lead_followup_service` (e.g. `UNSUBSCRIBE_URL` + `?lead={lead_id}`).

### 4.4 Optional “trial link click but no signup” follow-up

- Task mentions optional: if user clicks trial link but does not sign up, send one more email (“Need help setting up your compliance dashboard?”). This requires click tracking (e.g. link with lead_id) and a separate trigger. **Recommendation:** Omit in first delivery; add as a later enhancement if needed.

---

## 5. Implementation Plan (No Code Yet)

1. **Lead model / create_lead**
   - Add `nurture_stage: int = 0` and `last_nurture_sent_at: Optional[datetime]` to the lead document in `create_lead` (and ensure existing leads can be queried with these missing → treat as 0 / None).

2. **Compliance checklist capture**
   - After `create_lead` for `COMPLIANCE_CHECKLIST`:
     - If **marketing_consent** and not duplicate: send Email 1 (checklist delivery) via existing orchestrator + new template (or inline context); set `nurture_stage = 1`, `last_nurture_sent_at = now`.
     - If no consent: do not send; keep `nurture_stage = 0` (no further nurture emails).

3. **Nurture email templates**
   - Add 5 templates (bodies + subjects) in a dedicated structure (e.g. in `lead_followup_service` or a small `lead_nurture_service`). Each must include: informational disclaimer, unsubscribe link, company address footer. Use same Postmark path as follow-up (`LEAD_FOLLOWUP` or a dedicated template key if you add one).

4. **Daily nurture job**
   - New function `process_checklist_nurture_queue()` (or similar):
     - Query: `source_platform == COMPLIANCE_CHECKLIST`, `status` not in (CONVERTED, LOST, MERGED), `marketing_consent == True`, `followup_status != OPTED_OUT`.
     - For each lead, compute “next due” from `created_at` and `nurture_stage` (stage 1 → Day 2, 2 → Day 4, 3 → Day 6, 4 → Day 9; stage 5 = sequence complete).
     - If lead age ≥ required days and `nurture_stage` matches: send corresponding email; increment `nurture_stage`; set `last_nurture_sent_at`; audit log.
   - Register this in `job_runner` and run it **daily** (e.g. one run per day; exact hour configurable).

5. **Admin visibility**
   - Lead API already returns full document. In AdminLeadsPage, in the lead Details tab, when `source_platform === 'COMPLIANCE_CHECKLIST'`, show `nurture_stage` and `last_nurture_sent_at` (e.g. “Nurture stage: 2 / 5”, “Last nurture email: …”).

6. **Provisioning**
   - No changes to provisioning flow; conversion is already reflected in lead status/client_id and stops follow-up; same stop conditions apply to nurture.

---

## 6. Summary Table

| Requirement | Implemented | Action |
|-------------|-------------|--------|
| Trigger: source == compliance_checklist | ✅ (field exists) | Use in nurture query |
| Fields: nurture_stage, last_nurture_sent_at | ❌ | Add to lead doc and create_lead |
| Sequence: 5 emails Day 0,2,4,6,9 | ❌ | New templates + day-based logic |
| Daily cron for nurture | ❌ | New job + scheduler |
| Stop if lead converts | ✅ | Use same status/client_id checks |
| Postmark + unsubscribe + disclaimer | ✅ (pattern exists) | Reuse in nurture templates |
| Admin visibility of nurture stage | ❌ | Show in lead detail for checklist |
| Do not modify provisioning | N/A | No change to provisioning |

---

## 7. File Touch List (When Implementing)

- **Backend:** `services/lead_models.py` (optional: document fields), `services/lead_service.py` (add nurture fields to `create_lead`), `services/lead_followup_service.py` or new `services/lead_nurture_service.py` (templates + send + queue logic), `routes/leads.py` (send Email 1 on capture when consent), `job_runner.py` (new daily job), `server.py` (schedule the job).
- **Frontend:** `AdminLeadsPage.js` (show nurture_stage and last_nurture_sent_at for COMPLIANCE_CHECKLIST in Details).
- **Config / env:** Unsubscribe URL and company address can come from env (e.g. `COMPANY_ADDRESS_FOOTER`) for reuse.

No conflicting instructions identified that block implementation; the safest approach is a **separate nurture flow** keyed by `source_platform == COMPLIANCE_CHECKLIST` and day-based scheduling, without reusing the existing hour-based followup_step queue for these 5 emails.
