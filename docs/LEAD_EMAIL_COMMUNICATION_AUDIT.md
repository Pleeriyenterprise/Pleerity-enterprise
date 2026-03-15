# Lead Email Communication – Task vs Codebase Audit

**Purpose:** Check the codebase against the task requirements for lead email communication (transactional + nurture). Identify what is implemented, what is missing, and any conflicts. Propose the safest implementation path. **Do not implement blindly.**

---

## 1. Executive Summary

| Requirement | Current state | Task alignment |
|-------------|----------------|----------------|
| **Transactional emails** | One generic acknowledgement for most captures; risk check has separate first email for **risk_leads** only | **Partial** – No distinct per-action transactionals (e.g. “consultation request received”, “document pack enquiry received”). Risk check transactional exists but targets `risk_leads`, not central `leads`. |
| **Nurture sequence** | Two systems: (1) Checklist nurture: 5 emails at days 0,2,4,6,9 for COMPLIANCE_CHECKLIST only; (2) Follow-up: 3 steps at 1h, 24h, 72h by type (document_pack, automation, market_research) | **Partial** – Task example: 7 emails at day0, 2, 4, 6, 8, 12, 15 with specific themes (welcome, compliance education, compliance mistakes, automation benefits, document pack intro, case example, conversion CTA). Current schedules and themes differ. |
| **Schedule nurture** | Yes – `next_followup_at` (follow-up job); checklist uses `nurture_next_index` + NURTURE_DAYS | **Done** – Mechanism exists; task wants different day-based schedule. |
| **Stop on convert** | Yes – `should_stop_followup` / `should_skip_nurture` check CONVERTED, LOST, MERGED, OPTED_OUT; conversion sets `followup_status=STOPPED` | **Done** |
| **Respect preferences** | Lead-level: `marketing_consent`, cookie consent; template-level: LEAD_FOLLOWUP uses `email_category: internal` (no client preference gating) | **Partial** – Task: “respect email notification preferences”. Lead consent is respected; template category for lead emails is “internal” so enterprise preference gating does not apply. Task asks for category **lead_nurture**. |
| **Log all lead emails** | Yes – `LeadService.log_audit(FOLLOWUP_EMAIL_SENT, …)`; orchestrator writes to `message_logs` | **Done** |
| **Prevent duplicate sends** | Yes – idempotency_key in orchestrator and in lead flows (`lead_id_LEAD_FOLLOWUP_{template_id}_{date_key}`, `lead_id_CHECKLIST_NURTURE_{index}_{date_key}`) | **Done** |
| **Use enterprise template system** | Yes – notification orchestrator, template_key LEAD_FOLLOWUP | **Partial** – Task: “categorized as lead_nurture”. Current: LEAD_FOLLOWUP has `email_category: "internal"`. No `lead_nurture` category in DB or orchestrator. |

---

## 2. Conflicting or Divergent Instructions

### 2.1 Transactional: one acknowledgement vs per-action transactionals

- **Current:** A single **acknowledgement** email is sent from `LeadFollowUpService.send_acknowledgement(lead)` for: chatbot, contact-form, pricing, document-service, automation-enquiry, market-research-enquiry, support-form. Same template `lead_acknowledgement`, subject “We've received your enquiry — Reference: {lead_id}”. Sent regardless of marketing consent (treated as transactional).
- **Task:** “Transactional emails should send **immediately** after lead actions” and lists five: (1) compliance risk check completed, (2) consultation request, (3) document pack enquiry, (4) automation enquiry, (5) market research enquiry.
- **Conflict:** Task implies **five distinct** transactional types. Codebase has **one** generic acknowledgement for most, and a **separate** risk-check report email for `risk_leads` only (no central-lead transactional for risk check).

**Recommendation (safest):** Keep the existing acknowledgement as the default “we received your enquiry” for all captures. Optionally add **per-action template keys** (e.g. `LEAD_TRANSACTIONAL_CONSULTATION`, `LEAD_TRANSACTIONAL_DOCUMENT_PACK`, …) that can be configured with different copy; if not configured, fall back to current acknowledgement. For **compliance risk check completed**, ensure central `leads` get a transactional (either by creating/updating lead in central system and sending the same or a similar “risk snapshot” transactional from the lead engine, or by documenting that risk_check remains a separate flow for `risk_leads` and only that flow sends the risk report). Prefer **no duplication**: if risk check creates a central lead, send one transactional (e.g. “Compliance risk check completed” or reuse acknowledgement) from the lead engine rather than two separate systems sending two emails.

### 2.2 Nurture: current sequences vs task example sequence

- **Current:**
  - **Checklist nurture** (`lead_nurture_service.py`): 5 emails at days **0, 2, 4, 6, 9** for leads with `source_platform=COMPLIANCE_CHECKLIST` only. Inline templates in code; sent via orchestrator with `template_key=LEAD_FOLLOWUP`.
  - **Default follow-up** (`lead_followup_service.py`): 3 steps at **1h, 24h, 72h** with type-specific first step for document_pack, automation, market_research; started only if `marketing_consent`; driven by `next_followup_at` and job `lead_followup_processing`.
- **Task example:** day0 welcome, day2 compliance education, day4 compliance mistakes, day6 automation benefits, day8 document pack introduction, day12 case example, day15 conversion CTA (**7 emails**, different themes).

**Conflict:** The task’s **day-based 7-email sequence** does not exist as-is. Current nurture is either checklist (5 emails, day-based) or follow-up (3 emails, hour-based).

**Recommendation (safest):** Do **not** remove or replace existing checklist or follow-up behaviour in one go. Add a **configurable day-based nurture sequence** (e.g. in config or DB) that matches the task example (0, 2, 4, 6, 8, 12, 15) and themes, and run it for leads that are not in the checklist flow (or unify under one “default day-based” sequence with a clear rule: e.g. COMPLIANCE_CHECKLIST keeps 5-email checklist; all others get the 7-email day-based sequence). Alternatively, make the existing follow-up sequence **configurable** (e.g. steps defined by days instead of hours) so the same job can drive the task’s schedule without a second competing scheduler.

### 2.3 Template category: internal vs lead_nurture

- **Current:** `LEAD_FOLLOWUP` in `database.py` has `email_category: "internal"`. Orchestrator only applies preference gating for `compliance_notifications`, `reporting_notifications`, `marketing_notifications`; `internal` and `system_critical` are always sent.
- **Task:** “Lead emails should use the same enterprise email template system but be **categorized as lead_nurture**.”

**Conflict:** Task requires a **lead_nurture** category; codebase has no such category. If we add it, we must decide whether lead_nurture is gated by a **client** notification preference (leads often have no client_id; sending uses system/default client). Today, lead-level “preferences” are handled by `marketing_consent` and unsubscribe, not by template category.

**Recommendation (safest):** (1) Add **email_category `lead_nurture`** to the notification template seed and use it for **new** lead-specific template keys (e.g. nurture sequence templates). (2) In the orchestrator, treat `lead_nurture` like `marketing_notifications` for **client** preference gating when `client_id` is present; when sending to leads (no client or system client), **do not** block on client preference—lead consent is already enforced at sequence level (marketing_consent, unsubscribe). (3) Optionally keep `LEAD_FOLLOWUP` as `internal` for backward compatibility, or migrate it to `lead_nurture` and add the orchestrator branch for `lead_nurture` so that any future client-level “lead nurture” preference can be honoured without code change.

---

## 3. Requirement-by-Requirement

### 3.1 Transactional lead emails (immediate)

| Task trigger | Implemented? | Notes |
|--------------|--------------|--------|
| Compliance risk check completed | Partial | `risk_check.py` → `_send_risk_report_email()` → `risk_lead_email_service.send_risk_lead_email(lead, 1)` for **risk_leads** only. No central-lead transactional for risk check unless lead is also created in `leads`. |
| Consultation request | Partial | Same generic acknowledgement as other captures (`send_acknowledgement`). No distinct “consultation request received” template. |
| Document pack enquiry | Partial | Same generic acknowledgement; `start_followup_sequence` with sequence `document_pack` (1h, 24h, 72h). |
| Automation enquiry | Partial | Same generic acknowledgement; sequence `automation`. |
| Market research enquiry | Partial | Same generic acknowledgement; sequence `market_research`. |

**Gaps:** (1) No distinct per-action transactional templates. (2) Risk check transactional is tied to `risk_leads`; if central lead is created for risk check, need a single transactional from lead engine or clear ownership to avoid duplicate emails.

### 3.2 Nurture sequence emails (timed)

| Task item | Implemented? | Notes |
|-----------|--------------|--------|
| Schedule nurture emails | Yes | `next_followup_at` + job; checklist uses `nurture_next_index` and NURTURE_DAYS. |
| Day-based example (0,2,4,6,8,12,15) | No | Checklist: 0,2,4,6,9. Follow-up: 1h, 24h, 72h. No 7-step day-based sequence matching task. |
| Stop when lead converts | Yes | `should_stop_followup` / `should_skip_nurture`; conversion sets `followup_status=STOPPED`. |
| Respect email preferences | Partial | Lead-level consent (marketing_consent, cookie, unsubscribe) respected. Template category is `internal`; task wants `lead_nurture`. |
| Log all lead emails sent | Yes | `LeadService.log_audit(FOLLOWUP_EMAIL_SENT, …)`; `message_logs` in orchestrator. |
| Prevent duplicate sends | Yes | idempotency_key in orchestrator and in lead follow-up / checklist nurture. |

### 3.3 Template system

| Task item | Implemented? | Notes |
|-----------|--------------|--------|
| Use enterprise email template system | Yes | Orchestrator; template_key LEAD_FOLLOWUP. |
| Categorize as lead_nurture | No | Current: LEAD_FOLLOWUP `email_category: "internal"`. No `lead_nurture` in DB or orchestrator. |

---

## 4. Safest Implementation Approach (Proposal)

1. **Audit / docs (this file)**  
   - Done. Use this doc as the single reference for gaps and conflicts.

2. **Template category `lead_nurture`**  
   - Add `lead_nurture` to the list of categories in the orchestrator’s preference check (same gating logic as `marketing_notifications` when client_id is set).  
   - Seed or update templates used for **lead nurture** (and optionally lead transactionals) with `email_category: "lead_nurture"`.  
   - Keep existing `LEAD_FOLLOWUP` behaviour; either leave as `internal` or migrate to `lead_nurture` and ensure lead sends without client_id are not blocked by client preference.

3. **Transactional emails**  
   - **Option A (minimal):** Keep single acknowledgement for all; add a single “compliance risk check completed” transactional for **central** leads when risk check creates/updates a lead (so one email per channel, no duplicate with risk_lead_email_service for same recipient).  
   - **Option B (task-aligned):** Introduce optional per-action template keys (e.g. LEAD_TRANSACTIONAL_CONSULTATION, LEAD_TRANSACTIONAL_DOCUMENT_PACK, …); if present and active, send that template instead of generic acknowledgement; else fall back to current acknowledgement.  
   - Prefer **Option A** unless product explicitly wants different copy per action type.

4. **Nurture sequence**  
   - **Option A (additive):** Add a **default day-based nurture sequence** (0, 2, 4, 6, 8, 12, 15) with 7 steps, configurable in code or config. Run it for leads that are not in the checklist flow (e.g. not COMPLIANCE_CHECKLIST). Use same scheduling pattern as checklist (e.g. `nurture_next_index` + list of days).  
   - **Option B (configurable):** Make follow-up sequence definition configurable (e.g. from DB or env): support both “delay_hours” and “delay_days” so the existing job can run either the current 3-step hour-based sequence or the 7-step day-based sequence.  
   - Ensure only one nurture path runs per lead (checklist **or** default day-based, not both), and that conversion/consent/unsubscribe stop all.

5. **No duplication / no conflict**  
   - Risk check: if central lead is created, send exactly one “risk check completed” (or acknowledgement) from the lead engine; do not also send the same content from risk_lead_email_service to the same email.  
   - Nurture: single scheduler per lead type (checklist vs default); clear rules so the same lead does not get two sequences.

6. **Implementation order**  
   - (1) Add `lead_nurture` category and orchestrator branch; (2) Add or adjust transactional for risk-check central lead if applicable; (3) Add default day-based nurture sequence or make sequence configurable; (4) Wire new templates to `lead_nurture` and test preference + conversion + dedupe.

---

## 5. References

- **Lead follow-up / acknowledgement:** `backend/services/lead_followup_service.py` (`send_acknowledgement`, `send_followup_email`, `start_followup_sequence`, sequences by `followup_sequence`).
- **Checklist nurture:** `backend/services/lead_nurture_service.py` (NURTURE_DAYS 0,2,4,6,9; 5-email sequence; `process_checklist_nurture_queue`).
- **Risk-check emails:** `backend/routes/risk_check.py` (`_send_risk_report_email`), `backend/services/risk_lead_email_service.py` (report + nurture for risk_leads).
- **Capture endpoints:** `backend/routes/leads.py` (all capture routes call `send_acknowledgement` and often `start_followup_sequence`).
- **Orchestrator / templates:** `backend/services/notification_orchestrator.py` (preference check at ~L279–304); template seed in `backend/database.py` (LEAD_FOLLOWUP, `email_category`).
- **Jobs:** `backend/job_runner.py` (`run_lead_followup_processing`, `process_checklist_nurture_queue`, `run_risk_lead_nurture_processing`).
