# Certificate Expiry Tracking + Compliance Calendar Accuracy – Codebase Audit

## Scope

Task: Deterministic certificate expiry tracking; calendar, reminders, and scoring from a single source of truth per property/requirement; no legal-advice wording.

---

## 1) Data model

| Task requirement | Current state | Location / notes |
|-----------------|---------------|------------------|
| **property_requirements records** | Collection is named **`requirements`** (not `property_requirements`); one doc per property+requirement_type. | `backend/models/core.py` (Requirement), `backend/services/provisioning.py` (_generate_requirements), `db.requirements` everywhere. |
| **applicability enum (REQUIRED \| NOT_REQUIRED \| UNKNOWN)** | **Not present** on requirement docs. Property-level applicability exists: `requirement_catalog.get_applicable_requirements(property_doc)` returns which requirement *keys* apply (e.g. gas only if cert_gas_safety==YES). No per-requirement applicability. | `backend/services/requirement_catalog.py`. |
| **confirmed_expiry_date (nullable)** | **Not present.** Requirement has single **`due_date`** (datetime). | `backend/models/core.py` Requirement. |
| **extracted_expiry_date (nullable)** | **Not present.** Extraction/apply flow writes to **`due_date`** only. | `backend/routes/documents.py` (apply extraction, regenerate_requirement_due_date). |
| **expiry_source enum (CONFIRMED \| EXTRACTED \| NONE)** | **Not present.** | — |
| **extraction_confidence (0–1, nullable)** | **Not present** on requirement. Appears in intake/extraction payloads only. | `backend/routes/intake.py` (extraction_confidence in payload). |
| **status computed: VALID \| EXPIRING_SOON \| OVERDUE \| UNKNOWN_DATE \| NOT_REQUIRED** | **Partially present.** `RequirementStatus`: PENDING, COMPLIANT, OVERDUE, EXPIRING_SOON. No VALID (COMPLIANT used), no UNKNOWN_DATE, no NOT_REQUIRED. Status is stored and updated by jobs/documents, not purely computed from dates. | `backend/models/core.py` (RequirementStatus). |

**Conclusion (1):** Add to **existing `requirements` collection** (no rename): `applicability`, `confirmed_expiry_date`, `extracted_expiry_date`, `expiry_source`, `extraction_confidence`. Compute/store status with task semantics (VALID/EXPIRING_SOON/OVERDUE/UNKNOWN_DATE/NOT_REQUIRED). Alias COMPLIANT↔VALID where needed for backward compatibility.

---

## 2) Expiry source rules

| Task rule | Current state |
|-----------|----------------|
| Use **confirmed_expiry_date** if present, else **extracted_expiry_date**, else none. | Single **due_date** only; no two-source logic. |
| Calendar and reminders must use the **same** rule. | Calendar and reminders both use **requirement.due_date** (e.g. `backend/routes/calendar.py`, `backend/services/jobs.py` send_daily_reminders). |

**Conclusion (2):** Introduce a single helper (e.g. `get_effective_expiry_date(requirement)`) that returns confirmed_expiry_date or extracted_expiry_date or None; calendar and reminder code paths must call this (and persist/compute due_date from it where appropriate) so one rule drives both.

---

## 3) Applicability rules

| Task rule | Current state |
|-----------|----------------|
| **NOT_REQUIRED** → exclude from scoring penalties and calendar events. | No per-requirement applicability; scoring uses **property-level** applicable keys only (`get_applicable_requirements`). Calendar/reminders do **not** filter by applicability. |
| **UNKNOWN** → low-weight “uncertainty” penalty; show banner to confirm property attributes. | No UNKNOWN applicability; no uncertainty penalty or banner. |

**Conclusion (3):** Add per-requirement **applicability**; filter calendar and reminder queries to exclude NOT_REQUIRED; in scoring, exclude NOT_REQUIRED and apply a low-weight penalty for UNKNOWN; add a UI banner when any requirement has UNKNOWN (and prompt to confirm property attributes).

---

## 4) UI entry points

| Task | Current state |
|------|----------------|
| **After upload:** “Confirm document details” (property + requirement type + expiry date). | Apply-extraction flow can set **due_date**; no dedicated “Confirm document details” step with editable expiry. |
| **Property requirement page:** update expiry date; mark NOT_REQUIRED with controlled reason list. | No dedicated page. PATCH/update requirement exists in places (e.g. documents apply, regenerate_requirement_due_date). No NOT_REQUIRED or reason list in API/UI. |

**Conclusion (4):** Add post-upload “Confirm document details” (property, requirement type, expiry) and a property-requirement view/API to set expiry and NOT_REQUIRED with a fixed reason list.

---

## 5) Calendar endpoint

| Task | Current state |
|------|----------------|
| **GET /api/calendar/events** – events grouped by date. | **Not present.** Existing: **GET /api/calendar/expiries** (year, month), **GET /api/calendar/upcoming** (days). |
| Include: property_id, property_name, requirement_type, due_date, status, **document_id** (if any). | Expiries/upcoming include property_id, requirement_type, due_date, status, (property) address; **no document_id**. |
| Only items with **due_date present** and **applicability != NOT_REQUIRED**. | No applicability filter; due_date is required by query. |

**Conclusion (5):** Add **GET /api/calendar/events** (or alias) that returns events grouped by date, with property_id, property_name, requirement_type, due_date, status, document_id (from linked document lookup), and filter by effective due_date + applicability != NOT_REQUIRED. Keep existing /expiries and /upcoming for backward compatibility; optionally have them use the same expiry rule and applicability filter.

---

## 6) Reminder engine

| Task | Current state |
|------|----------------|
| **Daily scheduled job** for due-item reminders. | **Exists:** `JobScheduler.send_daily_reminders()` in `backend/services/jobs.py`. Uses requirements (due_date, status PENDING/EXPIRING_SOON), reminder_days_before from preferences. |
| Find due items at **30/14/7/1 days** from user settings. | **Single window:** `reminder_days_before` (default 30). No separate 30/14/7/1 intervals. |
| Send email/SMS per preferences. | **Done:** email and SMS via notification_orchestrator; recipient resolution and preferences (e.g. sms_urgent_alerts_only) applied. |
| Write to **message_logs** with **type=REMINDER** and references (client_id, property_id, requirement_type, due_date). | **Partial:** Orchestrator writes to **message_logs** (template_key, metadata.event_type e.g. "daily_reminder"). **No** explicit type=REMINDER; metadata does **not** include per-requirement property_id, requirement_type, due_date. |

**Conclusion (6):** Keep daily job. Optionally support 30/14/7/1 intervals from preferences. Ensure reminder writes to message_logs use **event_type** (or equivalent) **"REMINDER"** and include in metadata **client_id**, and for each reminded item **property_id**, **requirement_type**, **due_date** (e.g. as list in metadata for the single aggregate email, or one log per requirement if we move to per-requirement sends).

---

## 7) Scoring consistency

| Task rule | Current state |
|-----------|----------------|
| **NOT_REQUIRED** excluded from score. | No NOT_REQUIRED; property-level applicability only (`get_applicable_requirements`). |
| **UNKNOWN** → low penalty. | No UNKNOWN. |
| **Missing evidence** penalty only when **REQUIRED**. | Scoring uses applicable keys only; “missing” is implied by no doc / status. |
| **Portfolio score** = average of property scores (or weighted by bedrooms). | Portfolio logic in `compliance_scoring.py` / `catalog_compliance.py`; portfolio score exists; weighting by bedrooms is optional. |

**Conclusion (7):** When adding applicability, exclude NOT_REQUIRED from score denominator and from “missing” penalty; add UNKNOWN with a low weight; keep portfolio as average (or bedroom-weighted) of property scores.

---

## 8) No legal advice

| Task | Current state |
|------|----------------|
| Replace “required” with **“tracked”** + **“may apply depending on your situation”** in UI (compliance/certs). | UI uses “required” in many places (e.g. licence_required, form labels, “Upgrade required”). **No** systematic “tracked” / “may apply” wording for compliance/certificate context. |

**Conclusion (8):** Identify compliance/certificate-specific copy and replace with “tracked” and “may apply depending on your situation” where appropriate; leave generic “required” for form validation / feature gating.

---

## Conflicts and recommended approach

- **Collection name:** Task says “property_requirements”; codebase uses **requirements**. **Recommendation:** Keep **requirements**; add new fields and computed status. Avoid renaming collection unless a full migration is planned.
- **Status values:** Task: VALID | EXPIRING_SOON | OVERDUE | UNKNOWN_DATE | NOT_REQUIRED. Current: PENDING | COMPLIANT | OVERDUE | EXPIRING_SOON. **Recommendation:** Add UNKNOWN_DATE and NOT_REQUIRED; treat VALID as alias for COMPLIANT in API/responses; compute status from effective expiry + applicability.
- **GET /api/calendar/events:** Task asks for this path explicitly. **Recommendation:** Implement **GET /api/calendar/events** with task shape (grouped by date, with document_id, applicability filter). Keep **/expiries** and **/upcoming** for backward compatibility; optionally refactor them to use the same expiry rule and filter.
- **Reminder message_logs “type” and references:** **Recommendation:** Use **event_type="REMINDER"** (or equivalent) for reminder sends and add to metadata **client_id** and, for each item, **property_id**, **requirement_type**, **due_date** (e.g. list of refs for the aggregate reminder email).

---

## Deliverables checklist (from task)

| Deliverable | Status |
|-------------|--------|
| Code + tests: **expiry source selection** (confirmed vs extracted) | Not implemented; single due_date only. |
| Code + tests: **NOT_REQUIRED exclusion** (calendar + scoring) | Not implemented; no applicability on requirements. |
| Code + tests: **calendar event generation** (GET /api/calendar/events, shape, filters) | Partial; need /events and document_id + applicability. |
| Code + tests: **reminder job writes to message_logs** with type=REMINDER and references | Partial; job exists and writes logs; need REMINDER type and refs in metadata. |

---

## File reference summary

| Area | Files |
|------|--------|
| Requirement model | `backend/models/core.py` (Requirement, RequirementStatus) |
| Requirement creation | `backend/services/provisioning.py` (_generate_requirements) |
| Applicability (property-level) | `backend/services/requirement_catalog.py` (get_applicable_requirements) |
| Due date / extraction | `backend/routes/documents.py` (apply extraction, regenerate_requirement_due_date) |
| Calendar | `backend/routes/calendar.py` (get_expiry_calendar, get_upcoming_expiries) |
| Reminders | `backend/services/jobs.py` (send_daily_reminders, _send_reminder_email, _maybe_send_reminder_sms) |
| Notification logs | `backend/services/notification_orchestrator.py` (message_logs insert, metadata.event_type) |
| Scoring | `backend/services/compliance_scoring.py`, `backend/services/catalog_compliance.py` |
| Document–requirement link | Documents have requirement_id; requirements do not store document_id (lookup by requirement_id). |

Implementing the task will require: (1) schema and rule changes for expiry source and applicability, (2) one shared expiry-resolution rule for calendar and reminders, (3) GET /api/calendar/events and optional alignment of /expiries and /upcoming, (4) reminder metadata for REMINDER and refs, (5) UI for confirm-details and NOT_REQUIRED, (6) scoring updates for NOT_REQUIRED/UNKNOWN, (7) copy changes for “tracked”/“may apply,” and (8) tests for expiry source, NOT_REQUIRED exclusion, calendar events, and reminder message_logs.
