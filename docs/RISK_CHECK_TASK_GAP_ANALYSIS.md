# Compliance Risk Check – Task Gap Analysis (Marketing Diagnostic Funnel)

**Purpose:** Compare the current implementation against the new “Marketing Diagnostic Funnel” task requirements. Identify what exists, what’s missing, and where the spec conflicts with the current design. Propose the safest, non-breaking path. **No implementation in this document.**

---

## 1. Current Implementation Summary

| Area | What Exists |
|------|-------------|
| **Route** | `/risk-check` → `frontend/src/pages/public/RiskCheckPage.js` (not `pages/RiskCheckPage.js`) |
| **API** | `POST /api/risk-check/preview`, `POST /api/risk-check/report` in `backend/routes/risk_check.py` |
| **Scoring** | `backend/services/risk_check_scoring.py`: start 100, subtract gas/eicr/hmo/tracking; bands **75–100 LOW, 50–74 MODERATE, 0–49 HIGH** |
| **Inputs (Step 1)** | `property_count`, `any_hmo`, `gas_status` (Valid/Expired/Not sure), `eicr_status`, `tracking_method` (Manual reminders / Spreadsheet / No structured tracking / Automated system) |
| **Storage** | Collection `risk_leads`: lead_id, first_name, email, property_count, any_hmo, gas_status, eicr_status, tracking_method, computed_score, risk_band, exposure_range_label, flags, disclaimer_text, utm_*, created_at. **No `status` or `recommended_plan_code`.** |
| **Email** | One email only: “Your Compliance Risk Snapshot” sent on report (via `_send_risk_report_email` + LEAD_FOLLOWUP). **No `email_sequence_step` or `last_email_sent_at`; no steps 2–5.** |
| **Admin** | Dedicated `GET /api/admin/risk-leads`, export CSV, `POST .../resend-report`. Admin page “Risk Check Leads” at `/admin/risk-leads` (table: date, name, email, properties, risk_band, score, utm_source, “Email report again”). **Not under “Leads Management” as GET /api/admin/leads/risk.** |
| **CTA** | “Activate Monitoring” → `/intake/start` (no `?plan=`). “View Full Plan Comparison” → `/pricing`. |
| **Frontend API** | Page uses `client.post('/risk-check/preview')` and `client.post('/risk-check/report')` from `api/client.js`. **No dedicated `riskCheckAPI.js`.** |
| **Jobs** | No job for risk-lead nurture steps 2–5. `job_runner.py` has no risk_lead_nurture entry. |
| **Tests** | `backend/tests/test_risk_check_scoring.py` (scoring unit tests). `frontend/.../RiskCheckPage.test.js` (step flow, email gate). **No backend test_risk_check.py for preview/report 200/422/insert/email mock.** |

---

## 2. New Task Requirements vs Current State

### 2.1 Frontend

| Requirement | Current | Gap / Conflict |
|-------------|---------|----------------|
| Route `/risk-check` → RiskCheckPage | ✅ In `App.js`; page in `pages/public/RiskCheckPage.js` | Spec says `pages/RiskCheckPage.js`; **keep current path** (public) to avoid breaking imports. |
| Step 1: property_count, **has_hmo**, **gas_last_date** (date or "unknown"), **eicr_last_date** (date or "unknown"), **tracking_method** ("manual" \| "automated") | Step 1: property_count, **any_hmo**, **gas_status** (Valid/Expired/Not sure), **eicr_status**, tracking_method (4 options) | **Conflict:** Different field names and shapes. New spec uses dates and binary manual/automated. |
| Step 2: “Preliminary result: Risk Level {{band}}”, blurred score, CTA “Get Full Risk Report” | ✅ Partial reveal + email gate; “Generate My Risk Report” | Wording slightly different; **compatible.** |
| Step 3: first_name, email, “Generate My Risk Report”, full breakdown with **compliance_score capped at 97**, **key_flags** (max 5), **recommended_plan** | Full report with score 0–100, flags list, **no cap at 97**, **no recommended_plan** | **Missing:** recommended_plan; display cap 97 (optional); key_flags max 5 (we have variable flags). |
| CTA: “Activate Monitoring” → **/intake/start?plan=PLAN_X** | → `/intake/start` (no plan param) | **Missing:** `recommended_plan_code` from backend and `?plan=` on link. |
| Progress: “Step 1 of 3” etc. | ✅ “Step X of 3” | ✅ |
| Create `frontend/src/api/riskCheckAPI.js` (preview + report, same style as intakeAPI) | Uses `client` from `api/client.js` directly in page | **Optional:** Add riskCheckAPI.js for consistency; not required for behaviour. |
| Disclaimer: “Informational indicator only. Not legal advice.” | ✅ In disclaimer_text and email | ✅ |

### 2.2 Backend – Endpoints and Models

| Requirement | Current | Gap / Conflict |
|-------------|---------|----------------|
| `RiskCheckPreviewRequest`: property_count, has_hmo, gas_last_date, eicr_last_date, tracking_method | `RiskCheckStep1`: property_count, any_hmo, gas_status, eicr_status, tracking_method | **Conflict:** Request shape differs (dates vs status strings; has_hmo vs any_hmo). |
| `RiskCheckReportRequest` = Preview + first_name, email | ✅ Report = Step1 + first_name, email + utm | ✅ |
| `RiskCheckPreviewResponse`: risk_band, blurred_score_hint, **flags_preview** (2–3), **recommended_plan_code** | Preview returns risk_band, teaser_text, blurred_score_hint, flags_count | **Missing:** flags_preview list; recommended_plan_code. |
| `RiskCheckReportResponse`: compliance_score, risk_band, key_flags (max 5), estimated_exposure_range, **recommended_plan_code**, lead_id | Report returns score, risk_band, exposure_range_label, flags, disclaimer_text, property_breakdown | **Missing:** recommended_plan_code in response and in stored doc. |
| Mongo: **status** ("new" \| "nurture_started" \| "converted"), **recommended_plan_code**, **inputs** (answers), **utm** (optional) | Doc has flat fields, no status, no recommended_plan_code | **Missing:** status; recommended_plan_code; optional “inputs” object (we have flat fields; can add status + recommended_plan_code only). |

### 2.3 Backend – Scoring

| Requirement | Current | Gap / Conflict |
|-------------|---------|----------------|
| New file: `risk_scoring_service.py`; `calculate_marketing_risk(inputs)` | Existing: `risk_check_scoring.py`; `compute_risk_check_result(...)` | **Conflict:** Different file name and function name. New spec: **start 97**, deduct by property count tiers, has_hmo, tracking (manual -12, automated 0), **gas_last_date** (unknown -12, >12mo -15, 9–12mo -8), **eicr_last_date** (unknown -10, >5y -12, 4–5y -6). **Bands: ≥85 Low, 70–84 Moderate, <70 High.** Current: start 100, status-based penalties, bands 75+ Low, 50–74 Moderate, 0–49 High. |
| Score cap 97, min 0 | Score 0–100 (no 97 cap) | **Conflict:** Spec requires 97 cap. |
| Key flags (max 5), specific strings | We have variable-length flags with title/description/recommended_next_step | **Compatible:** Can cap at 5 and align copy. |
| Recommended plan: ≤2 → PLAN_1_SOLO, 3–10 → PLAN_2_PORTFOLIO, 11+ → PLAN_3_PRO | Not implemented | **Missing:** Add to scoring/response. |

### 2.4 Email Nurture

| Requirement | Current | Gap / Conflict |
|-------------|---------|----------------|
| On report: insert lead, send Email 1, set last_email_sent_at, email_sequence_step = 1 | Insert lead + send 1 email (no sequence fields) | **Missing:** last_email_sent_at, email_sequence_step on doc. |
| 5 emails: 1 immediate, 2 at +2d, 3 at +4d, 4 at +6d, 5 at +10d | Only email 1 | **Missing:** `risk_lead_email_service.py` with 5 templates; daily job to send steps 2–5. |
| `risk_lead_nurture_job.py`: find leads status != converted, send by days since created_at | No job | **Missing:** Job + register in job_runner (and optionally scheduler). |

### 2.5 Admin

| Requirement | Current | Gap / Conflict |
|-------------|---------|----------------|
| **Under “Leads Management”**: GET **/api/admin/leads/risk** | GET **/api/admin/risk-leads** (separate router) | **Conflict:** Spec wants risk under leads API path; we have dedicated risk-leads. |
| Display: first_name, email, property_count, band, score, recommended_plan, created_at, status. Actions: “Open Risk Report”, “Start Intake” (link with ?plan=), “Mark Converted” | Table: date, name, email, properties, risk_band, score, utm_source; “Email report again” | **Missing:** recommended_plan, status, “Open Risk Report” modal, “Start Intake” with ?plan=, “Mark Converted”. |

### 2.6 Non-Regression

| Requirement | Current | Status |
|-------------|---------|--------|
| Do not change intake submit, checkout, provisioning, Stripe webhooks | Risk-check is standalone; no touch to those flows | ✅ |

---

## 3. Conflicts and Recommended Resolution

### 3.1 Scoring Model (Major)

- **Spec:** New file `risk_scoring_service.py`, start 97, date-based gas/eicr, bands 85/70, plan recommendation.
- **Current:** `risk_check_scoring.py`, start 100, status-based gas/eicr, bands 75/50.

**Recommendation (safest):**

- **Option A (minimal change):** Keep current scoring and bands. Add **only**: (1) `recommended_plan_code` from property_count (≤2 → PLAN_1_SOLO, 3–10 → PLAN_2_PORTFOLIO, 11+ → PLAN_3_PRO) in existing `risk_check_scoring.py` and in API response/storage; (2) optionally cap **display** at 97 in frontend (e.g. `Math.min(97, score)`). No change to backend score range. No new scoring file; no breaking change to existing risk_leads or behaviour.
- **Option B (full spec):** Introduce `risk_scoring_service.py` (or extend current module) with the spec’s 97-cap and date-based logic; accept **new request shape** (gas_last_date, eicr_last_date, has_hmo, manual/automated) either in new v2 endpoints or by backward-compatible parsing (e.g. map “Valid” → recent date, “Expired” → old date). Risk: existing frontend and any saved payloads assume status strings; migration path needed.

**Proposed:** **Option A** for this phase: add plan recommendation and optional display cap; defer date-based scoring and 97-backend-cap to a later “Real Scoring Engine Upgrade” so the conversion engine stays stable and non-breaking.

### 3.2 Request/Response Shape (Field Names and Types)

- **Spec:** has_hmo, gas_last_date (date | "unknown"), eicr_last_date (date | "unknown"), tracking "manual" | "automated".
- **Current:** any_hmo, gas_status, eicr_status, tracking_method (four options).

**Recommendation:** Keep current request shape so existing frontend and docs keep working. If product later wants date-based UX, add optional fields (e.g. gas_last_date) and map them into the same scoring inputs internally, or add a separate v2 endpoint. **Do not rename or replace existing fields in this phase.**

### 3.3 Admin API Location

- **Spec:** GET `/api/admin/leads/risk` under Leads Management.
- **Current:** GET `/api/admin/risk-leads` and dedicated “Risk Check Leads” page.

**Recommendation:** Add **GET /api/admin/leads/risk** (in leads router or as alias) that returns the same risk_leads data with RBAC (owner/admin). Keep **GET /api/admin/risk-leads** so the existing Admin “Risk Check Leads” page continues to work. Admin UI can later show a “Risk” sub-tab under Leads that calls `/api/admin/leads/risk` and reuses or mirrors the current table; no breaking change.

### 3.4 Nurture: 5 Emails and Daily Job

- **Spec:** 5-email sequence; steps 2–5 at +2, +4, +6, +10 days via daily job.
- **Current:** 1 email on report.

**Recommendation:** Add in a **non-breaking** way:

1. **Schema:** Add to risk_leads doc: `status` (default `"new"`), `email_sequence_step` (default 1 after first email), `last_email_sent_at` (optional). Do not backfill; new leads get them.
2. **Service:** Create `backend/services/risk_lead_email_service.py` with `send_risk_lead_email(lead, step: int)` and the 5 subjects/bodies from the spec. Step 1 = current “Your Compliance Risk Snapshot”; steps 2–5 as specified. Use existing notification orchestrator (e.g. LEAD_FOLLOWUP with context). On report, after insert, set `email_sequence_step = 1`, `last_email_sent_at = now`, optionally `status = "nurture_started"`.
3. **Job:** Create `backend/jobs/risk_lead_nurture_job.py` (or add to `job_runner.py`): find risk_leads where status != "converted" and (days since created_at) and current step allow sending next email; send step 2 at day ≥ 2, step 3 at day ≥ 4, step 4 at day ≥ 6, step 5 at day ≥ 10; update `email_sequence_step` and `last_email_sent_at`; idempotent, no deletes. Register in `JOB_RUNNERS` and add a daily scheduler job (same pattern as checklist_nurture). Do not wire to Render cron until ready.

This keeps existing “send 1 email on report” behaviour and adds the sequence without touching intake/checkout/provisioning.

### 3.5 Plan Recommendation and CTA

- **Spec:** recommended_plan_code in response and DB; CTA to `/intake/start?plan=PLAN_X`.

**Recommendation:** Add in current codebase without changing scoring logic:

- In `risk_check_scoring.py` (or in `risk_check.py` from property_count): compute `recommended_plan_code`: property_count ≤ 2 → PLAN_1_SOLO, 3–10 → PLAN_2_PORTFOLIO, 11+ → PLAN_3_PRO.
- Add to report response and to risk_leads doc.
- In RiskCheckPage, primary CTA: `Link to={\`/intake/start${report.recommended_plan_code ? `?plan=${report.recommended_plan_code}` : ''}\`}`.

No conflict with existing flows; intake can accept `?plan=` if it already does, or ignore until supported.

### 3.6 Tests

- **Spec:** `backend/tests/test_risk_check.py`: preview 200 + band + recommended_plan; report 200 + insert; score cap 97; missing required → 422; email send for step 1 mocked.
- **Current:** `test_risk_check_scoring.py` (scoring only); RiskCheckPage.test.js (flow).

**Recommendation:** Add `backend/tests/test_risk_check.py` for API: preview returns 200 and band (and recommended_plan when added); report returns 200 and lead exists in DB; missing required fields → 422; mock `_send_risk_report_email` and assert it’s called on report. Keep existing scoring and frontend tests. If we keep score 0–100 (Option A), test “score in 0–100” instead of “cap 97”; if we add 97 cap later, add a dedicated test.

---

## 4. Summary: What to Add vs What to Change

**Add (no breaking changes):**

- `recommended_plan_code` in scoring (from property_count), in report response, and in risk_leads doc.
- Primary CTA with `?plan=` when recommended_plan_code is present.
- risk_leads: optional `status`, `email_sequence_step`, `last_email_sent_at`; set on report.
- `risk_lead_email_service.py`: 5 email templates; send step 1 on report (current behaviour); steps 2–5 from service.
- `risk_lead_nurture_job`: daily job to send steps 2–5 by days since created_at; register in job_runner (+ scheduler).
- GET `/api/admin/leads/risk` (alias or under leads router) returning risk_leads, RBAC.
- Backend tests: `test_risk_check.py` (preview/report/422/insert/email mock).
- Optional: `riskCheckAPI.js`; optional: display cap 97 in frontend; optional: “Open Risk Report” modal, “Start Intake” link with plan, “Mark Converted” in admin.

**Do not change (stability):**

- Existing request/response field names (any_hmo, gas_status, eicr_status, tracking_method options).
- Existing scoring formula and bands (unless we explicitly choose Option B and migrate).
- Existing GET /api/admin/risk-leads and Admin “Risk Check Leads” page.
- Intake, checkout, provisioning, Stripe webhooks.

**Fix (cleanup):**

- Remove duplicate `app.include_router(admin_risk_leads.router)` in `server.py` if present.

---

## 5. File / Location Reference (for implementation)

| Item | Action | File(s) |
|------|--------|--------|
| Plan recommendation | Add | `risk_check_scoring.py` or `risk_check.py`; response + risk_leads doc |
| CTA with ?plan= | Add | `RiskCheckPage.js` |
| status, email_sequence_step, last_email_sent_at | Add to doc | `risk_check.py` (report handler) |
| 5-email service | New | `backend/services/risk_lead_email_service.py` |
| Nurture job | New | `backend/jobs/risk_lead_nurture_job.py` (or logic in job_runner); register in job_runner + server scheduler |
| GET /api/admin/leads/risk | Add | e.g. in `routes/leads.py` (admin_router) or thin alias to same data |
| test_risk_check.py | New | `backend/tests/test_risk_check.py` |
| Duplicate router | Fix | `server.py` (single include for admin_risk_leads) |

Implementing in the order above keeps the conversion engine stable and avoids duplication or conflict with the existing risk-check flow and with intake/checkout/provisioning.
