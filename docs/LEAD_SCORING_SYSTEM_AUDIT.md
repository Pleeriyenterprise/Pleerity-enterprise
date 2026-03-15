# Lead Scoring System – Task vs Codebase Audit

**Purpose:** Check the codebase against the task requirements for a lead scoring system (engagement, urgency, portfolio value, stage thresholds, hot lead alerts, recalculation triggers, logging). Identify what is implemented, what is missing, and any conflicts. Propose the safest implementation path. **Do not implement blindly.**

---

## 1. Executive Summary

| Requirement | Current state | Task alignment |
|-------------|----------------|----------------|
| **Lead scoring service** | `backend/services/lead_scoring.py` exists with `calculate_lead_score_from_signals()`, `stage_from_lead_score()`, `recalculate_lead_score(lead)` | **Partial** – Function takes lead-like kwargs, not `(lead, activity)`. Task suggests `calculate_lead_score(lead, activity)`; current is signal-based from lead doc only. |
| **Engagement signals** | Intent base (HIGH 40, MEDIUM 25, LOW 10); COMPLIANCE_RISK_CHECK +20; PRICING +15; consultation_request tag +25; document_pack +10; automation +20; nurture_cta_clicked +10; nurture_email_opened +5; pricing_requested tag +15 | **Partial** – Many signals present but point values and coverage differ from task. Missing: website form +10, chatbot +8, email opened +3 (have +5), email link +8 (have +10), returned 7 days +10, signup started +20. |
| **Urgency signals** | risk_level HIGH +15, MODERATE +10 | **Partial** – Task: high +30, medium +20. No certificate expiry soon (+25) or compliance gap (+20) for leads. |
| **Portfolio value** | portfolio_size >= 2 → +15 | **Partial** – Task: 1 +5, 2–5 +15, 6–20 +30, 20+ +50; user_type agent/property manager +40. No user_type on lead; portfolio bands not granular. |
| **Negative signals** | None | **Missing** – Task: no activity 30 days −15, marketing unsubscribe −10. |
| **Stage thresholds** | NEW 0–19, QUALIFIED 20–39, NURTURING 40–59, SALES_READY 60–100 | **Partial** – Task: 80+ = "hot" (fifth band). Current has no "hot" stage; SALES_READY covers 60–100. |
| **Never downgrade converted** | Stage update only when `suggested_stage != NEW` (create) or when `stage == NEW` (upsert). No explicit check for WON/CONVERTED. | **Gap** – Converted leads have stage=WON; recalc could suggest a lower stage. Callers do not always skip stage update for WON/CONVERTED. |
| **Hot lead alert** | `notify_high_intent_lead(lead)` triggered when **intent_score == HIGH** at create time only | **Partial** – Task: trigger when **score >= 80**; alert to include lead name, email, lead type, portfolio size, risk level, lead score, link to CRM. Current: intent-based, different content. |
| **Recalculation triggers** | create_lead; upsert_by_email path; POST /activity (track-activity); GET track-open | **Partial** – Missing: explicit trigger on consultation requested, document pack enquiry submitted (tags may be set but recalc not always in same flow), portfolio size updated (PATCH doesn’t recalc), “key activity logged” (activity is logged but recalc is triggered for known activities only). |
| **Logging** | `lead_audit_logs` with event, lead_id, actor, details, created_at. No dedicated score-update log. | **Partial** – Task: "lead_activity_log" with lead_id, previous_score, new_score, reason, timestamp. Current: no score-specific log; can use lead_audit_logs with new event LEAD_SCORE_UPDATED and details. |

---

## 2. Conflicting or Divergent Instructions

### 2.1 Function signature: `calculate_lead_score(lead, activity)` vs current

- **Task:** `calculate_lead_score(lead, activity)` — implies activity may carry one-off signals (e.g. “email opened”) for incremental scoring.
- **Codebase:** `calculate_lead_score_from_signals(...)` takes lead-derived kwargs (source_platform, tags, portfolio_size, etc.); `recalculate_lead_score(lead)` pulls all signals from the lead document. No separate `activity` argument; activity is persisted to the lead (e.g. tags, last_activity_at) and then recalc runs.

**Recommendation:** Keep recalc from the lead document only (single source of truth). When an activity occurs, the caller updates the lead (tags, last_activity_at, etc.) and then calls `recalculate_lead_score(lead)`. Do not add a second path that scores from a raw “activity” object without persisting first; that would risk double-counting or inconsistency. Optionally add a helper that builds an updated lead dict from `lead + activity` and then calls the existing calculator, for clarity at call sites.

### 2.2 Stage band: “80+ hot” vs single SALES_READY 60–100

- **Task:** 0–19 new, 20–39 qualified, 40–59 nurturing, 60–79 sales_ready, **80+ hot**.
- **Codebase:** 0–19 NEW, 20–39 QUALIFIED, 40–59 NURTURING, 60–100 SALES_READY. No HOT stage in `LeadStage` enum.

**Recommendation:** Either: (a) add stage `HOT` and map 80–100 to HOT in `stage_from_lead_score`, or (b) keep four stages and treat “hot” as **alert trigger only** (score >= 80 triggers internal alert; stage remains SALES_READY). Option (b) avoids schema/enum change and matches “trigger internal alert when score reaches 80” without introducing a new stage. If product wants a distinct “hot” stage in the CRM, choose (a).

### 2.3 Hot lead alert: intent vs score

- **Task:** When score reaches **80 or higher** → trigger internal alert (lead name, email, lead type, portfolio size, risk level, lead score, link to CRM).
- **Codebase:** When **intent_score == HIGH** at create time → `notify_high_intent_lead(lead)` (name, email, phone, service interest, source, message, link). No lead_score or risk_level in body; no portfolio_size.

**Recommendation:** Add a **score-based** hot-lead alert: after any recalc that sets lead_score >= 80, call a dedicated `notify_hot_lead_alert(lead)` (or extend the existing notifier with a score threshold and richer payload). Use the same channel (e.g. LEAD_HIGH_INTENT_ADMIN template or a dedicated template) and same admin list. Keep intent-based notification at create if desired, or unify to “only when score >= 80” to avoid duplicate alerts. Document that “hot” = score >= 80.

### 2.4 Logging: lead_activity_log vs lead_audit_logs

- **Task:** “Log score updates in lead_activity_log with lead_id, previous_score, new_score, reason, timestamp.”
- **Codebase:** Only `lead_audit_logs`; no `lead_activity_log` collection.

**Recommendation:** Do **not** introduce a new collection for a single event type. Log score updates in **lead_audit_logs** with a new event (e.g. `LEAD_SCORE_UPDATED`) and `details = { "previous_score", "new_score", "reason" }`; `created_at` is the timestamp. If the product later standardizes on a separate activity log, events can be dual-written or migrated.

---

## 3. Requirement-by-Requirement

### 3.1 Create lead scoring service (lead_scoring.py)

| Task | Implemented? | Notes |
|------|--------------|--------|
| File `backend/services/lead_scoring.py` | Yes | Exists. |
| Function `calculate_lead_score(lead, activity)` | Partial | Current: `calculate_lead_score_from_signals(...)` and `recalculate_lead_score(lead)`. No `activity` arg; signals from lead doc. |
| Three categories (engagement, urgency, portfolio) | Partial | All three represented but with different point values and missing sub-signals. |

### 3.2 Engagement signals (point deltas)

| Signal | Task | Current | Notes |
|--------|------|---------|--------|
| website form submission | +10 | — | Not explicit; intent_score may absorb. |
| compliance risk check completed | +20 | +20 | ✓ |
| chatbot conversation captured | +8 | — | Intent base only. |
| consultation request | +25 | +25 (tag) | ✓ |
| pricing page visit | +10 | +15 (source/tag) | Align to +10 or keep +15. |
| document pack enquiry | +15 | +10 | Increase to +15. |
| email opened | +3 | +5 (nurture_email_opened) | Align to +3 or keep +5. |
| email link clicked | +8 | +10 (nurture_cta_clicked) | Align to +8 or keep +10. |
| returned to site within 7 days | +10 | — | Would need last_activity_at vs previous visit; not implemented. |
| signup started | +20 | — | No “signup started” signal on lead. |

### 3.3 Urgency signals

| Signal | Task | Current | Notes |
|--------|------|---------|--------|
| high risk | +30 | +15 | Increase to +30. |
| medium risk | +20 | +10 | Increase to +20. |
| certificate expiry soon | +25 | — | No lead-level certificate data; property-level only. Omit or document as future. |
| compliance gap detected | +20 | — | No lead-level gap; property-level only. Omit or document as future. |

### 3.4 Portfolio value signals

| Signal | Task | Current | Notes |
|--------|------|---------|--------|
| 1 property | +5 | — | Add. |
| 2–5 properties | +15 | +15 for >= 2 | Refine to 2–5. |
| 6–20 properties | +30 | — | Add. |
| 20+ properties | +50 | — | Add. |
| user_type = agent or property manager | +40 | — | user_type not on lead; add field or derive; then +40. |

### 3.5 Negative signals

| Signal | Task | Current | Notes |
|--------|------|---------|--------|
| no activity for 30 days | −15 | — | Compare last_activity_at to now; apply if > 30 days. |
| marketing unsubscribe | −10 | — | Apply when followup_status = OPTED_OUT or similar. |

### 3.6 Lead stage thresholds

| Band | Task | Current | Notes |
|------|------|---------|--------|
| 0–19 | new | NEW | ✓ |
| 20–39 | qualified | QUALIFIED | ✓ |
| 40–59 | nurturing | NURTURING | ✓ |
| 60–79 | sales_ready | SALES_READY | Current 60–100; task 60–79. |
| 80+ | hot | — | Add as stage HOT or alert-only. |
| Never downgrade converted | Yes | Not enforced | Add guard: do not set stage if current stage is WON (or status CONVERTED). |

### 3.7 Internal hot lead alerts

| Task | Implemented? | Notes |
|------|--------------|--------|
| Trigger when score >= 80 | No | Currently intent_score == HIGH at create. |
| Alert content: name, email, lead type, portfolio size, risk level, lead score, link to CRM | Partial | notify_high_intent_lead has name, email, phone, service, source, message, link; missing portfolio_size, risk_level, lead_score. |
| Send to internal admin alert email | Yes | ADMIN_NOTIFICATION_EMAILS, LEAD_HIGH_INTENT_ADMIN template. |

### 3.8 Score recalculation triggers

| Trigger | Implemented? | Notes |
|---------|--------------|--------|
| New lead created | Yes | lead_service create_lead. |
| Risk check completed | Yes | Via create_lead sync (central lead). |
| Consultation requested | Partial | Tag set via activity; recalc in track-activity. If consultation comes from another endpoint, ensure tag + recalc. |
| Document pack enquiry submitted | Partial | source_platform/service_interest set at create; recalc at create. No separate “document pack enquiry” event after create unless via activity. |
| Nurture email link clicked | Yes | track-activity → recalc. |
| Key activity logged | Partial | Any activity in ALLOWED_ACTIVITY_TAGS triggers recalc. |
| Portfolio size updated | No | update_lead (PATCH) does not call recalc. Add recalc when portfolio_size (or other scoring fields) change. |

### 3.9 Logging

| Task | Implemented? | Notes |
|------|--------------|--------|
| Log score updates | No | No dedicated score log. |
| lead_id, previous_score, new_score, reason, timestamp | — | Use lead_audit_logs + LEAD_SCORE_UPDATED + details. |

### 3.10 Deliverables (reference)

- **Files created:** lead_scoring.py exists; extend it, no new service file needed.
- **Where scoring is triggered:** lead_service (create, upsert), routes/leads (track-activity, track-open). Add: after update_lead when scoring-relevant fields change; optionally after risk_check sync.
- **Stage transition logic:** lead_scoring.stage_from_lead_score; lead_service and routes persist stage. Add: do not overwrite stage when lead is already WON/CONVERTED.
- **Internal alert integration:** notify_high_intent_lead; add notify_hot_lead_by_score(lead) or equivalent, called when recalc yields score >= 80.
- **Example lead scoring output:** document in README or this audit: sample lead doc → calculate_lead_score_from_signals / recalculate_lead_score → score and suggested_stage.

---

## 6. Implementation Summary (after implementation)

### 6.1 Where scoring is triggered

| Trigger | Location | Reason passed |
|--------|----------|----------------|
| New lead created | `lead_service.py` `create_lead()` | `lead_created` |
| Upsert by email | `lead_service.py` `create_lead()` (duplicate path) | `upsert_by_email` |
| Lead activity (CTA click, etc.) | `routes/leads.py` `record_lead_activity()` | `activity_{activity_type}` |
| Email open (track-open) | `routes/leads.py` `track_lead_email_open()` | `nurture_email_opened` |
| Admin update (scoring fields) | `lead_service.py` `update_lead()` | `admin_update` |

All triggers call `LeadService.recalculate_and_persist_lead_score(lead_id, reason)`, which recalculates, persists score (and stage when allowed), logs `LEAD_SCORE_UPDATED`, and sends hot lead alert if score >= 80.

### 6.2 Stage rules

- **Bands:** 0–19 → NEW, 20–39 → QUALIFIED, 40–59 → NURTURING, 60–100 → SALES_READY.
- **Never downgrade converted:** `should_update_stage(lead, suggested_stage)` returns False when `lead.stage == WON` or `lead.status == CONVERTED` (or LOST). Stage is only written when this returns True.
- **Hot:** Score >= 80 triggers internal alert; stage remains SALES_READY (no separate HOT stage).

### 6.3 Internal hot lead alert

- **When:** After any recalc that yields `lead_score >= 80`.
- **Function:** `LeadService.notify_hot_lead_alert(lead)`.
- **Content:** Lead name, email, lead type (service_interest), portfolio size, risk level, lead score, link to CRM. Uses template `LEAD_HIGH_INTENT_ADMIN`; idempotency key `{lead_id}_LEAD_HOT_ALERT_{date}_{admin_email}` (one per lead per day per admin).
- **High intent at create:** If score < 80 and intent_score == HIGH, `notify_high_intent_lead(lead)` is still called (legacy behaviour).

### 6.4 Score update logging

- **Event:** `LeadAuditEvent.LEAD_SCORE_UPDATED`.
- **Collection:** `lead_audit_logs`.
- **Details:** `previous_score`, `new_score`, `reason`. Timestamp is `created_at`.

### 6.5 Example lead scoring output

**Input (lead dict):**
- `source_platform`: `COMPLIANCE_RISK_CHECK`, `intent_score`: `MEDIUM`, `risk_level`: `HIGH`, `portfolio_size`: 5, `tags`: `["consultation_request"]`

**Signals applied:** intent MEDIUM 25 + compliance risk check 20 + high risk 30 + portfolio 2–5 → 15 + consultation 25 = 115 → capped 100.

**Output:** `recalculate_lead_score(lead)` → `{"lead_score": 100, "suggested_stage": "SALES_READY"}`. Hot lead alert sent (score >= 80).

---

## 4. Safest Implementation Approach (Proposal)

1. **Keep existing API**  
   Keep `calculate_lead_score_from_signals(...)` and `recalculate_lead_score(lead)`. Do not add a separate `(lead, activity)` scoring path that bypasses persisting activity to the lead.

2. **Align point values and add missing signals (in lead_scoring.py)**  
   - Engagement: Set compliance risk check +20 (done); consultation +25 (done); document pack +15 (currently 10); pricing +10 (currently 15); email opened +3, email link +8 (or keep 5/10); add chatbot +8, website form +10 if source/tags allow. Omit “returned 7 days” and “signup started” unless product adds the underlying data.  
   - Urgency: high risk +30, medium +20. Leave certificate expiry and compliance gap for leads as future (no data).  
   - Portfolio: 1 → +5, 2–5 → +15, 6–20 → +30, 20+ → +50; user_type agent/property manager +40 (add user_type to lead or source_metadata if needed).  
   - Negative: no activity 30 days −15 (use last_activity_at); unsubscribe −10 (use followup_status or marketing_consent).

3. **Stage thresholds**  
   - Option A: Add LeadStage.HOT and map 80–100 → HOT; 60–79 → SALES_READY.  
   - Option B: Keep 60–100 as SALES_READY; trigger “hot lead” alert when score >= 80 without a new stage.  
   Recommend B unless CRM needs a HOT stage.

4. **Never downgrade converted**  
   In every place that writes `stage` from recalc (lead_service create_lead, upsert path, and any new trigger), only set stage if current stage is not WON and status is not CONVERTED. Optionally centralize in a small helper: `should_update_stage(lead, suggested_stage)`.

5. **Hot lead alert on score >= 80**  
   After recalc, if new score >= 80 and (optionally) score increased into the 80+ band, call `notify_hot_lead_alert(lead)` with lead name, email, lead type (service_interest/source), portfolio size, risk level, lead score, and CRM link. Reuse admin channel/template or add a dedicated one; idempotency per lead per day to avoid spam.

6. **Recalc triggers**  
   - Ensure recalc runs after risk check sync (already via create_lead).  
   - Add recalc in update_lead when portfolio_size, risk_level, user_type, or other scoring fields change.  
   - Keep recalc on track-activity and track-open.

7. **Logging**  
   Add event `LEAD_SCORE_UPDATED` to lead_audit_logs with details `{ "previous_score", "new_score", "reason" }`. Call it from a single place (e.g. after recalc when score or stage is persisted).

8. **Documentation**  
   Update this audit or a short “Lead scoring” section in docs with: where recalc is triggered, stage rules, hot-lead rule, and an example input/output for recalculate_lead_score.

---

## 5. References

- **Scoring:** `backend/services/lead_scoring.py` (calculate_lead_score_from_signals, stage_from_lead_score, recalculate_lead_score).
- **Triggers:** `backend/services/lead_service.py` (create_lead, upsert path); `backend/routes/leads.py` (record_lead_activity, track_lead_email_open).
- **Alerts:** `backend/services/lead_service.py` (notify_high_intent_lead).
- **Audit:** `backend/services/lead_service.py` (log_audit, LEAD_AUDIT_COLLECTION = "lead_audit_logs").
- **Models:** `backend/services/lead_models.py` (LeadStage, LeadIntentScore, LeadSourcePlatform, LeadServiceInterest).
