# Certificate Expiry Tracking + Compliance Calendar — Task Compliance Audit

**Goal:** Calendar, reminders, and scoring from a clear source of truth per property_requirement; avoid legal-advice wording.

**Audit date:** Current codebase state vs. task requirements. No blind implementation; gaps and safe recommendations only.

---

## 1) Data model

| Requirement | Status | Location / notes |
|-------------|--------|------------------|
| property_requirements records (Gas Safety, EICR, EPC, Licence, etc.) | **Done** | `requirements` collection; provisioning generates per-property requirements (`backend/services/provisioning.py`). |
| applicability enum: REQUIRED \| NOT_REQUIRED \| UNKNOWN (default UNKNOWN) | **Done** | `Applicability` in `backend/models/core.py`; `Requirement.applicability` default `Applicability.UNKNOWN`. |
| confirmed_expiry_date (nullable) | **Done** | `Requirement.confirmed_expiry_date`, optional. |
| extracted_expiry_date (nullable) | **Done** | `Requirement.extracted_expiry_date`, optional. |
| expiry_source enum: CONFIRMED \| EXTRACTED \| NONE | **Done** | `ExpirySource` in `core.py`; `Requirement.expiry_source` optional. |
| extraction_confidence (0–1, nullable) | **Done** | `Requirement.extraction_confidence` optional. |
| status computed: VALID \| EXPIRING_SOON \| OVERDUE \| UNKNOWN_DATE \| NOT_REQUIRED | **Done** | `RequirementStatus` includes all; **VALID** is represented as **COMPLIANT** in code/API (docstring in `expiry_utils.get_computed_status`). No conflict; task allows “VALID equivalent”. |

**Conclusion (1):** Data model matches the task. No duplication; no conflict.

---

## 2) Expiry source rules

| Requirement | Status | Location / notes |
|-------------|--------|------------------|
| Use confirmed_expiry_date if present, else extracted_expiry_date, else none | **Done** | `get_effective_expiry_date()` in `backend/utils/expiry_utils.py`; fallback to legacy `due_date` when both null. |
| Calendar and reminders use the same rule | **Done** | Calendar routes and `send_daily_reminders` in `jobs.py` use `get_effective_expiry_date` and `is_included_for_calendar`. |

**Conclusion (2):** Single rule implemented; no conflict.

---

## 3) Applicability rules

| Requirement | Status | Location / notes |
|-------------|--------|------------------|
| applicability == NOT_REQUIRED → exclude from scoring and calendar | **Done** | Scoring: `compliance_scoring.py` (NOT_REQUIRED → full score for that key). Calendar/reminders: `is_included_for_calendar()` excludes NOT_REQUIRED. |
| UNKNOWN → low-weight “uncertainty” penalty; show banner to confirm property attributes | **Partial** | **Backend:** UNKNOWN with no evidence gets `status_factor` 0.5 in `compliance_scoring.py`. **Frontend:** No banner yet that says “confirm property attributes” when any requirement has applicability UNKNOWN. |

**Recommendation (3):** Add a small UI banner on the dashboard or requirements/compliance views when the client has any requirement with `applicability === "UNKNOWN"`: e.g. “Some tracked items depend on your property details. Confirm your property settings so we can show the right items.” Link to property settings or requirements. No backend change required.

---

## 4) UI entry points

| Requirement | Status | Location / notes |
|-------------|--------|------------------|
| After upload: “Confirm document details” (property + requirement type + expiry date) | **Done** | `DocumentsPage.js`: modal after single-file upload with property, requirement type, expiry date; saves via PATCH requirement `confirmed_expiry_date`. |
| Property requirement page: update expiry + mark NOT_REQUIRED with controlled reason list | **API only** | **Backend:** `PATCH /api/properties/{property_id}/requirements/{requirement_id}` with `confirmed_expiry_date`, `applicability`, `not_required_reason` (controlled list: no_gas_supply, exempt, not_applicable, other). **Frontend:** No dedicated “property requirement” page or inline edit that calls this PATCH. RequirementsPage lists requirements and links to documents but does not allow editing expiry or setting NOT_REQUIRED. |

**Recommendation (4):** Add a small “Edit” or “Set expiry / Not applicable” action on the requirements list (e.g. in `RequirementsPage.js`) or on a property detail view that calls the existing PATCH with a modal: expiry date picker and applicability dropdown (REQUIRED / NOT_REQUIRED / UNKNOWN) plus, when NOT_REQUIRED, reason dropdown from the same controlled list. Reuse existing API; no new backend.

---

## 5) Calendar endpoint

| Requirement | Status | Location / notes |
|-------------|--------|------------------|
| GET /api/calendar/events, events grouped by date | **Done** | `backend/routes/calendar.py` `get_calendar_events()`. |
| Include property_id, property_name, requirement_type, due_date, status, document_id | **Done** | Response includes these fields. |
| Only include items with due_date present and applicability != NOT_REQUIRED | **Done** | Uses `is_included_for_calendar()` and `get_effective_expiry_date()`; NOT_REQUIRED and no effective date excluded. |

**Conclusion (5):** Calendar endpoint matches task. No conflict.

---

## 6) Reminder engine

| Requirement | Status | Location / notes |
|-------------|--------|------------------|
| Daily scheduled job exists | **Done** | `JobScheduler.send_daily_reminders()` in `backend/services/jobs.py`. |
| Find due items at intervals (30/14/7/1 days) based on user settings | **Partial** | Single window: `reminder_days_before` (default 30); profile allows 7, 14, 30, 60, 90. Task asks for “30/14/7/1 days” — current behaviour is one configurable window (e.g. “remind if due within 30 days”), not separate reminders at 30, 14, 7, 1 days. |
| Send email/SMS per preferences | **Done** | Email and SMS per preferences; recipient resolution and plan gating in place. |
| Write to message_logs with type=REMINDER and references (client_id, property_id, requirement_type, due_date) | **Done** | `event_type="REMINDER"` and `context["reminder_refs"] = json.dumps([{property_id, requirement_type, due_date}, ...])` in `_send_reminder_email` and `_maybe_send_reminder_sms`; message_logs store metadata.event_type and metadata.reminder_refs; client_id is on the log document. |

**Recommendation (6):** Keep current single-window behaviour unless product explicitly wants multiple reminders (e.g. at 30, 14, 7, 1 days). If multiple intervals are required, extend notification preferences (e.g. list of days) and the job loop to send at each interval; no change to expiry source or REMINDER refs.

---

## 7) Scoring consistency

| Requirement | Status | Location / notes |
|-------------|--------|------------------|
| NOT_REQUIRED excluded from score | **Done** | `compliance_scoring.py`: key with NOT_REQUIRED gets status_factor 1.0 (no penalty). |
| UNKNOWN low penalty | **Done** | UNKNOWN with no evidence: `status_factor` 0.5. |
| Missing evidence penalty only when REQUIRED | **Done** | Handled via applicability; NOT_REQUIRED and UNKNOWN handled as above. |
| Portfolio score = average of property scores (or weighted by bedrooms) | **Done** | `portfolio_score_and_risk()` uses weighted average by E(p) = 1 + 0.5*HMO + 0.2*(bedrooms>=4) + 0.2*(occupancy!=single_family). |

**Conclusion (7):** Scoring matches task. No conflict.

---

## 8) No legal advice

| Requirement | Status | Location / notes |
|-------------|--------|------------------|
| Replace “required” with “tracked” + “may apply depending on your situation” in compliance/certificate UI | **Not done** | No systematic replacement. Many UI strings use “required” (form validation, “Action Required”, “Upgrade required”, etc.). Task targets **compliance/certificate** wording only (e.g. “Gas Safety required” → “Gas Safety tracked; may apply depending on your situation”). |

**Recommendation (8):** Limit changes to **compliance and certificate** contexts (e.g. requirements list, calendar, document/requirement labels). Do not change generic “required” (form fields, upgrade prompts, etc.). Search for compliance-specific copy (e.g. “requirement”, “certificate required”, requirement type labels) and replace with “tracked” and “may apply depending on your situation” where it refers to legal/regulatory obligation. Avoid touching legal or terms pages unless explicitly in scope.

---

## Deliverables (tests)

| Deliverable | Status | Location / notes |
|-------------|--------|------------------|
| Expiry source selection | **Done** | `test_certificate_expiry_tracking.py`: `TestGetEffectiveExpiryDate` (confirmed > extracted > due_date). |
| NOT_REQUIRED exclusion | **Done** | Same file: `TestIsIncludedForCalendar`, `TestGetComputedStatus`; scoring NOT_REQUIRED in `compliance_scoring.py` (covered by existing scoring tests). |
| Calendar event generation | **Done** | GET /calendar/events used by frontend; backend filters by effective date and NOT_REQUIRED. No explicit test for full events response; unit tests cover helpers. |
| Reminder job writes to message_logs | **Done** | Test verifies `_send_reminder_email` is called with `reminder_refs`; doc test states event_type REMINDER and message_log contract. |

**Conclusion (deliverables):** Tests satisfy the requested deliverables. Optional: add one API test for GET /calendar/events (shape and NOT_REQUIRED exclusion) if you want explicit coverage.

---

## Summary: what’s implemented vs missing

- **Fully implemented:** Data model, expiry source rule, applicability (NOT_REQUIRED/UNKNOWN) in backend, calendar events API, reminder job with REMINDER + refs, scoring (NOT_REQUIRED, UNKNOWN, portfolio), confirm-details modal after upload, PATCH requirement API for expiry and NOT_REQUIRED.
- **Gaps (no conflict):**
  1. **UNKNOWN banner:** Show a banner when any requirement has applicability UNKNOWN, prompting user to confirm property attributes.
  2. **Property requirement page / edit in UI:** No frontend that calls PATCH to update expiry or set NOT_REQUIRED with reason; API is ready.
  3. **Reminder intervals:** Single window (e.g. 30 days) only; task text “30/14/7/1 days” could mean one window or multiple; optional to add multiple intervals.
  4. **No legal advice (copy):** Compliance/certificate wording not yet switched to “tracked” and “may apply depending on your situation”.

**Conflicts:** None. Existing implementation aligns with the task; remaining work is additive (UI banner, requirement edit UI, optional reminder intervals, copy pass).

**Safest next steps (in order):**
1. Add UNKNOWN banner in one place (e.g. dashboard or requirements page) with link to property/requirements.
2. Add PATCH requirement from the requirements list (or property detail): “Edit” → modal for expiry date and applicability + not_required_reason.
3. Do a targeted copy pass for compliance/certificate screens only: “tracked” and “may apply depending on your situation.”
4. Only if product asks for it: extend reminder engine to support 30/14/7/1 day intervals via preferences and job logic.
