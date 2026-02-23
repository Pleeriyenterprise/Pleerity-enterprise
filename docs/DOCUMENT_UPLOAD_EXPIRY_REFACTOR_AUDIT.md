# Document Upload Flow — Deterministic Expiry Refactor Audit

**Task:** Refactor document upload flow to enforce deterministic expiry tracking.

**Audit scope:** Map each task requirement to current implementation; identify gaps, conflicts, and safest options. No implementation in this document.

---

## 1) After file upload, DO NOT immediately mark requirement as satisfied

| Current behaviour | Location | Gap / conflict |
|-------------------|----------|----------------|
| **Single-file upload** (`POST /api/documents/upload`) calls `regenerate_requirement_due_date(requirement_id, client_id)` immediately after insert. That function sets `status: COMPLIANT` and `due_date: now + frequency_days` on the requirement. | `backend/routes/documents.py` ~718–719, 1304–1324 | **Conflict.** Requirement is marked satisfied on upload without user confirmation. |
| **Bulk upload** and **ZIP upload**: when AI matches a document to a requirement, they call `regenerate_requirement_due_date`, which again sets COMPLIANT and a synthetic due date. | `documents.py` ~266–267 (bulk), ~566–567 (zip) | Same as above. |
| **Admin upload** also calls `regenerate_requirement_due_date` after insert. | `documents.py` ~839–840 | Same. |

**Conclusion:** Task requirement is **not** met. Upload currently marks the requirement as satisfied (COMPLIANT) before any confirmation.

**Recommendation:**  
- **Option A (strict):** Remove the call to `regenerate_requirement_due_date` from upload paths (single, bulk, zip, admin). After upload, leave requirement status as-is (e.g. PENDING) and do not set `due_date` from document until the user confirms (see item 2). Calendar/reminders already use `get_effective_expiry_date` (confirmed > extracted > due_date); with no confirmed/extracted/due from upload, the requirement would not drive calendar/reminders until confirmation.  
- **Option B (softer):** Only stop setting COMPLIANT on upload; still allow setting `due_date` from extraction later when user applies extraction. Then the “confirm details” modal becomes the gate for both writing `confirmed_expiry_date` and setting status to COMPLIANT (e.g. only when user confirms in modal or via apply-extraction with confirmed_data).  
- **Safest:** Option A: do not call `regenerate_requirement_due_date` on upload. Add a separate, explicit “apply confirmation” path (modal submit or apply-extraction with confirmation) that writes `confirmed_expiry_date` (and optionally `extracted_expiry_date` if from AI) and sets status from `get_computed_status` (or COMPLIANT when confirmed and in range). This keeps one clear rule: “satisfied” only after confirmation.

---

## 2) Open confirmation modal: pre-fill extracted fields, require confirmation of expiry_date before applying

| Current behaviour | Location | Gap / conflict |
|-------------------|----------|----------------|
| After **single-file upload**, frontend opens “Confirm document details” modal with property and requirement type; user can enter expiry date and submit. Submit sends only `confirmed_expiry_date` via `PATCH /api/properties/{property_id}/requirements/{requirement_id}`. | `frontend/src/pages/DocumentsPage.js` ~89–117 (handleUpload sets confirmDetailsModal), ~236–257 (handleConfirmDetailsSubmit), ~933+ (modal UI) | Modal does **not** pre-fill from extraction: extraction is enqueued asynchronously after upload, so at modal open there is usually no extraction yet. “Require confirmation before applying” is partially met for the PATCH path (user can skip), but backend has already “applied” satisfaction on upload (item 1). |
| **Apply extraction** (`POST /documents/{id}/apply-extraction`) can be called with or without `confirmed_data`. When expiry_date is present and document is linked to a requirement, it updates requirement `due_date`, `extracted_expiry_date`, `expiry_source: EXTRACTED`, and sets status to COMPLIANT/OVERDUE/EXPIRING_SOON. No separate “confirm expiry” step. | `backend/routes/documents.py` ~1565–1808 | Applying extraction updates the requirement immediately; there is no requirement to confirm expiry in a modal before this. |
| **Admin confirm extraction** (`POST /documents/admin/extraction-queue/confirm`) applies extraction to the requirement (due_date, extracted_expiry_date, expiry_source, status) without end-user confirmation. | `documents.py` ~937–993 | By design for admin; task may still imply “user” confirmation for client flow. |

**Conclusion:**  
- Confirmation modal exists for single-file upload but does not pre-fill from extraction (timing: extraction runs after upload).  
- “Require user confirmation of expiry_date before applying” is not enforced: upload already applies satisfaction (item 1), and apply-extraction applies to requirement without going through the confirm modal.

**Recommendation:**  
- After fixing item 1 (no immediate COMPLIANT on upload), the post-upload modal could be shown when extraction completes (e.g. poll or push), or the flow could be: upload → later user opens document → “Review extraction” → pre-filled modal (expiry, issue_date, certificate_number) → user confirms expiry → then call apply-extraction with confirmed_data (or a dedicated “confirm and apply” endpoint) that writes `confirmed_expiry_date`, `expiry_source: CONFIRMED`, and sets status from `get_computed_status`.  
- For pre-fill: when opening the confirm modal, if the document has `ai_extraction.data` or `extraction_id`, fetch extraction and pre-fill expiry_date, issue_date, certificate_number so the user only confirms or corrects.

---

## 3) Save into property_requirement: confirmed_expiry_date, issue_date, certificate_number, expiry_source (CONFIRMED or EXTRACTED)

| Current behaviour | Location | Gap / conflict |
|-------------------|----------|----------------|
| **Requirement model** has `confirmed_expiry_date`, `extracted_expiry_date`, `expiry_source`. It does **not** have `issue_date` or `certificate_number`. | `backend/models/core.py` ~560–578 (Requirement class) | **Gap:** task asks to save `issue_date` and `certificate_number` into property_requirement; they are not on the Requirement model. |
| **PATCH requirement** accepts only `confirmed_expiry_date`, `applicability`, `not_required_reason`. It sets `expiry_source: "CONFIRMED"` when `confirmed_expiry_date` is provided. | `backend/routes/properties.py` ~254–310 | No issue_date or certificate_number. |
| **apply-extraction** and **admin_confirm_extraction** write to requirement: `due_date`, `extracted_expiry_date`, `expiry_source: EXTRACTED`, `extraction_confidence`, `status`. They do not write issue_date or certificate_number to the requirement. | `documents.py` ~966–983 (admin), ~1703–1728 (client apply-extraction) | issue_date and certificate_number are stored on the **document** (e.g. `ai_extraction.applied_data`, `certificate_number` on document) and in extraction records, not on the requirement. |

**Conclusion:**  
- `confirmed_expiry_date` and `expiry_source` are saved to the requirement (via PATCH and apply-extraction).  
- `issue_date` and `certificate_number` are **not** stored on the requirement; they exist on document/extraction only.

**Recommendation:**  
- **Option A:** Add optional `issue_date` and `certificate_number` to the Requirement model and to the PATCH requirement payload; when user confirms in the modal or via apply-extraction with confirmed_data, write these to the requirement as well. This matches the task verbatim (“Save fields into property_requirement”).  
- **Option B:** Keep issue_date and certificate_number on document/extraction only; document remains the source of truth for certificate metadata; requirement only holds expiry and applicability. Then the task wording “save into property_requirement” would be satisfied only for confirmed_expiry_date and expiry_source.  
- **Safest:** Option A if you need certificate-level data on the requirement (e.g. for reports or reminders). Otherwise Option B with a short note in the spec that certificate_number/issue_date are stored on the document.

---

## 4) Add applicability enum: REQUIRED | NOT_REQUIRED | UNKNOWN (default UNKNOWN)

| Current behaviour | Location | Gap / conflict |
|-------------------|----------|----------------|
| **Applicability** enum and **Requirement.applicability** with default UNKNOWN exist. PATCH requirement supports `applicability` and `not_required_reason`. | `backend/models/core.py` (Applicability, Requirement), `backend/routes/properties.py` ~254–301 | **Done.** No gap. |

**Conclusion:** Implemented. No change needed.

---

## 5) Calendar must pull ONLY from confirmed_expiry_date

| Current behaviour | Location | Gap / conflict |
|-------------------|----------|----------------|
| Calendar (and reminders) use **effective** expiry: `get_effective_expiry_date(req)` = confirmed_expiry_date **else** extracted_expiry_date **else** due_date (legacy). | `backend/utils/expiry_utils.py`, `backend/routes/calendar.py` (get_calendar_events, get_expiry_calendar, get_upcoming_expiries), `backend/services/jobs.py` (send_daily_reminders) | **Conflict.** Task says calendar must pull **only** from `confirmed_expiry_date`. Current design uses a hierarchy (confirmed > extracted > due_date). |

**Conclusion:** Strict interpretation of the task (“ONLY from confirmed_expiry_date”) would exclude items that have only `extracted_expiry_date` (or legacy `due_date`) from the calendar until the user confirms. That would change behaviour for existing data and for “apply extraction without confirm modal” flows.

**Recommendation:**  
- **Option A (strict):** Add a calendar-only rule: include an item in calendar events only if `confirmed_expiry_date` is present; ignore extracted_expiry_date and due_date for calendar. Reminders could follow the same rule (“only remind when confirmed_expiry_date is set”). This matches the task literally but reduces visibility of unconfirmed extractions.  
- **Option B (keep current):** Keep “effective” date (confirmed > extracted > due_date) for calendar and reminders so that unconfirmed but extracted data still shows. Document that “calendar uses effective expiry; for compliance reporting we prefer confirmed when available.”  
- **Safest:** Option B unless product explicitly requires that nothing appears on the calendar until the user has confirmed. If product requires strict “only confirmed,” implement Option A with a clear migration note: requirements with only extracted_expiry_date would no longer appear on the calendar until the user confirms.

---

## 6) If applicability == NOT_REQUIRED, exclude from scoring and reminders

| Current behaviour | Location | Gap / conflict |
|-------------------|----------|----------------|
| **Calendar:** `is_included_for_calendar(req)` returns False when applicability is NOT_REQUIRED; these events are excluded. | `backend/utils/expiry_utils.py`, `backend/routes/calendar.py` | **Done.** |
| **Reminders:** `send_daily_reminders` uses `is_included_for_calendar(req)`; NOT_REQUIRED requirements are skipped. | `backend/services/jobs.py` ~106–108 | **Done.** |
| **Scoring:** NOT_REQUIRED gives full score for that requirement key (no penalty). | `backend/services/compliance_scoring.py` ~198–203 | **Done.** |

**Conclusion:** Implemented. No gap.

---

## 7) Nightly job: recalc statuses and send reminders based on confirmed_expiry_date

| Current behaviour | Location | Gap / conflict |
|-------------------|----------|----------------|
| **send_daily_reminders** runs (daily); it uses `get_effective_expiry_date` (confirmed > extracted > due_date) and `is_included_for_calendar`; it updates requirement `status` to OVERDUE or EXPIRING_SOON and sends reminders with `event_type=REMINDER` and `reminder_refs`. | `backend/services/jobs.py` ~94–175 | Task says “based on confirmed_expiry_date.” Current behaviour is “based on effective expiry.” So same conflict as item 5: strict reading would require the job to consider only requirements that have `confirmed_expiry_date` set. |

**Conclusion:** Nightly job exists and uses effective expiry. If item 5 is resolved with “only confirmed,” this job should be aligned to use only confirmed_expiry_date for inclusion and due date.

**Recommendation:** Same as item 5: either restrict to confirmed_expiry_date only (Option A) or keep effective expiry (Option B). Keep job and calendar in sync with the same rule.

---

## 8) Tests

| Task requirement | Current tests | Gap |
|-----------------|---------------|-----|
| Upload without confirmation does not affect calendar | None found. | **Missing.** Need a test: upload a document (no confirm modal submit); assert requirement is not COMPLIANT or has no confirmed_expiry_date; assert calendar events for that requirement are absent or not driven by that upload. |
| NOT_REQUIRED excludes requirement from score | Coverage of NOT_REQUIRED in scoring is implicit in expiry_utils tests and in compliance_scoring logic. | **Partial.** No dedicated test that a requirement with applicability=NOT_REQUIRED is excluded from score (e.g. property score does not penalise that requirement). |
| Expiry transition from VALID to OVERDUE triggers reminder | None found. | **Missing.** Need a test that when a requirement’s effective expiry date moves from future to past (or status from COMPLIANT to OVERDUE), the reminder job includes it in reminder_refs / sends a reminder (or that the job’s logic would include it when run). |

**Recommendation:**  
- Add test: after upload, without calling confirm modal or apply-extraction, requirement status is not set to COMPLIANT (once item 1 is fixed) and calendar does not show the requirement (or shows only if effective date exists from elsewhere).  
- Add test: requirement with applicability=NOT_REQUIRED is excluded from score (e.g. score breakdown or property score).  
- Add test: requirement with effective expiry in the past is included in reminder_refs when the daily reminder job runs (mock DB with one such requirement and assert reminder_refs or send call).

---

## Summary table

| # | Requirement | Status | Action |
|---|-------------|--------|--------|
| 1 | Do not mark requirement as satisfied on upload | **Not met** | Remove or defer `regenerate_requirement_due_date` on upload; gate “satisfied” on confirmation. |
| 2 | Confirmation modal; pre-fill; require confirmation before applying | **Partial** | Modal exists; add pre-fill from extraction when available; require confirmation before writing to requirement (align with item 1). |
| 3 | Save confirmed_expiry_date, issue_date, certificate_number, expiry_source to requirement | **Partial** | confirmed_expiry_date and expiry_source done; add issue_date and certificate_number to model + PATCH/apply if needed. |
| 4 | Applicability enum REQUIRED / NOT_REQUIRED / UNKNOWN | **Done** | None. |
| 5 | Calendar ONLY from confirmed_expiry_date | **Conflict** | Choose: strict (only confirmed) vs current (effective = confirmed > extracted > due_date). |
| 6 | NOT_REQUIRED excluded from scoring and reminders | **Done** | None. |
| 7 | Nightly job recalc and reminders from confirmed_expiry_date | **Conflict** | Align with item 5 (only confirmed vs effective). |
| 8 | Tests: upload without confirm → calendar; NOT_REQUIRED → score; VALID→OVERDUE → reminder | **Gaps** | Add the three tests above. |

---

## Recommended order of changes (no blind implementation)

1. **Decide** calendar/reminder rule: only `confirmed_expiry_date` (strict) vs effective date (current). Document decision.
2. **Implement item 1:** Stop calling `regenerate_requirement_due_date` on document upload (single, bulk, zip, admin). Optionally: add an explicit “apply confirmation” path that sets status and confirmed_expiry_date.
3. **Implement item 2:** Ensure confirmation modal is the gate for applying to requirement; pre-fill modal from extraction when document has extraction data (e.g. when opening modal after extraction completes).
4. **Item 3:** If product needs issue_date/certificate_number on requirement, add fields to Requirement model and to PATCH/apply-extraction; otherwise document that they are on document only.
5. **Items 5 & 7:** If strict “only confirmed” is chosen, change calendar and reminder job to include only requirements with `confirmed_expiry_date` set; else leave as-is and document.
6. **Item 8:** Add the three tests described above.

No duplication with existing certificate-expiry work: this refactor reuses `get_effective_expiry_date`, `is_included_for_calendar`, PATCH requirement, and reminder job; it only changes when and what is written on upload vs on confirmation.
