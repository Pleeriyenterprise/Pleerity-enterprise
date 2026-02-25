# Compliance Risk Check – Gap Analysis & Implementation Plan

**Purpose:** Check the codebase against the two task specs (standalone “Compliance Risk Check” conversion demo + “Marketing Diagnostic Funnel”) to identify what exists, what’s missing, and how to resolve conflicts safely without duplicating or breaking existing flows.

---

## 1. What Exists Today

### 1.1 Frontend
- **Routes:** Public routes live in `App.js` (e.g. `/`, `/pricing`, `/contact`, `/demo`, `/intake/start`). **No `/risk-check` route.**
- **Navbar:** `PublicHeader.js` – Platforms, Services, Pricing, Insights, About, Portal Login. **No “Check Your Compliance Risk” CTA.**
- **Layout:** Public pages use `PublicLayout` (header + footer). `DemoPage.js` at `/demo` is a static “platform demo” (images + CTA to `/intake/start`). **No conflict with a new risk-check page; risk-check is a separate flow.**
- **Intake:** `IntakePage.js` at `/intake/start`, `UnifiedIntakeWizard` at `/order/intake`. Task says **do not modify** these or use `/api/intake/submit` for the demo.

### 1.2 Backend
- **Collections:** `database.py` creates indexes for `contact_submissions`, `talent_pool`, `partnership_enquiries`, `leads`, `analytics_events`, `payments`, etc. **No `risk_leads` collection or indexes.**
- **Leads:** `leads` collection and `LeadService` / `routes/leads.py` – list, export, capture (contact, checklist, chatbot). Admin list at `GET /api/admin/leads`. **Risk-check leads are separate; store in `risk_leads`, not `leads`.**
- **Admin submissions:** `admin_submissions.py` – unified list/export by type: `contact`, `talent`, `partnership`, `lead`. **`risk_leads` not in `COLLECTION_MAP`; adding it is a small, safe extension.**
- **Email:** `lead_nurture_service` and `notification_orchestrator` send via Postmark (template_key e.g. `LEAD_FOLLOWUP`). Partnership ack email exists. **No “Risk Report” template yet; add one or use existing admin-manual pattern with custom subject/body.**
- **Compliance scoring:** `compliance_scoring`, `compliance_score`, `requirement_catalog` – property/client-based, document-driven. **Task explicitly says “We are not touching the full compliance scoring backend.” Risk-check uses its own simple deterministic formula.**

### 1.3 Safe Boundaries (Do Not Touch)
- Intake routes and components: `/intake/start`, `UnifiedIntakeWizard`, `/order/intake`, `/api/intake/*`.
- Stripe / checkout / provisioning: webhooks, `stripe_webhook_service`, `provisioning`, client creation.
- Real compliance score engine: `compliance_scoring`, `compliance_score`, property/client documents.

---

## 2. What’s Missing (Implementation Checklist)

### 2.1 Backend
| Item | Status | Notes |
|------|--------|------|
| `risk_leads` collection | Missing | Add in code only; MongoDB creates on first insert. Optionally add indexes in `database._create_indexes()` (e.g. `lead_id`, `created_at`, `email`) for admin list/export. |
| `POST /api/risk-check/preview` | Missing | Input: Step 1 answers (no email). Output: `risk_band`, `teaser_text`, `blurred_score_hint`, `flags_count`. No persistence. |
| `POST /api/risk-check/report` | Missing | Input: Step 1 + first_name + email. Output: full report (score, risk_band, exposure_range_label, flags, disclaimer_text). Persist to `risk_leads`; return `lead_id`. |
| Scoring logic (deterministic) | Missing | New module e.g. `backend/services/risk_check_scoring.py`: 100 − gas (0/12/25) − eicr (0/10/20) − hmo (0/10) − tracking (0/6/10/15). Clamp 0–100. Bands: 0–49 HIGH, 50–74 MODERATE, 75–100 LOW. **Do not reuse** `utils/risk_bands.py` (different thresholds and purpose). |
| Risk report email (optional) | Missing | If Postmark configured: send “Your Compliance Risk Snapshot” after report. Use orchestrator with a dedicated template_key (e.g. `RISK_CHECK_REPORT`) or reuse `LEAD_FOLLOWUP` with custom context. |
| Admin: risk_leads list + export | Missing | Either extend `admin_submissions` with type `risk` → collection `risk_leads` and id field `lead_id`, or add a small `GET /api/admin/risk-leads` + export. Latter keeps risk-check fully isolated. |
| Admin: “Email report again” | Missing | Action that re-sends the same report email to the lead (using stored snapshot). |

### 2.2 Frontend
| Item | Status | Notes |
|------|--------|------|
| Route `/risk-check` | Missing | Add in `App.js` (public section). |
| Page component `RiskCheckPage` | Missing | New file e.g. `frontend/src/pages/public/RiskCheckPage.js` (or `.jsx`). Use `PublicLayout`. |
| Navbar CTA “Check Your Compliance Risk” → `/risk-check` | Missing | Add in `PublicHeader.js` (desktop + mobile). |
| Step 1 – Questions | Missing | Fields: property_count, any_hmo, gas_status, eicr_status, tracking_method. Button “Calculate Risk” → call `POST /api/risk-check/preview`. |
| Step 2 – Partial reveal + email gate | Missing | Show preliminary risk + blurred content; form: first_name, email; “Generate My Risk Report” → call `POST /api/risk-check/report`. |
| Step 3 – Full report + CTAs | Missing | Show score, risk band, exposure label, flags, “How Pleerity fixes this”, disclaimer. CTA “Activate Compliance Monitoring” → `/intake/start`. Secondary “View platform demo” → `/demo` or anchor. |
| Progress indicator | Missing | “Step 1 of 3” → “Step 2 of 3” → “Step 3 of 3”. |
| Copy and disclaimers | Missing | Use exact wording from spec (meta title/description, headings, disclaimer text, email subject/body). |

### 2.3 Admin
| Item | Status | Notes |
|------|--------|------|
| Risk leads table under Lead Management | Missing | New tab/section or sub-route under Leads: columns date, name, email, property_count, risk_band, score, utm_source. |
| “Email report again” action | Missing | Calls backend to re-send report email for that lead. |

---

## 3. Conflicting Instructions and Recommended Resolution

### 3.1 Two specs compared
- **Spec A (Standalone Demo):** No client creation, no provisioning, no Stripe from demo. Two endpoints: `preview` (no email) and `report` (with email, persist to `risk_leads`). Exposure wording: avoid fines; use “potential vulnerability to missed renewals and documentation gaps.”
- **Spec B (Marketing Funnel):** Single `POST /api/risk-check` with optional email; “Estimated Risk Exposure: £X–£Y”; “Push to Stripe” at end of flow (CTA to checkout).

### 3.2 Conflicts and recommended approach

| Conflict | Spec A | Spec B | Recommended (safest) |
|----------|--------|--------|------------------------|
| API shape | `preview` + `report` (two endpoints) | One `POST /api/risk-check` | **Keep two endpoints.** Clear separation: preview = no PII; report = with PII + persistence. |
| Exposure wording | No specific fines; “potential vulnerability to missed renewals…” | “Estimated Risk Exposure: £X–£Y” | **Use Spec A wording.** Avoid monetary figures unless legally verified. Safer and consistent with “not legal advice.” |
| Stripe | CTA only → `/intake/start` (no Stripe call from demo) | “Push to Stripe” (CTA to checkout) | **No change.** “Activate Monitoring” / “Activate Compliance Monitoring” → link to existing `/intake/start`. No new Stripe session from risk-check. |
| Scoring | Simple subtractive (gas/eicr/hmo/tracking); bands 0–49 HIGH, 50–74 MODERATE, 75–100 LOW | Weighted % (Gas 25%, Electrical 20%, etc.); “Cap at 97%” | **Use Spec A for MVP.** Simpler, deterministic, no dependency on real compliance engine. Cap at 100; “cap at 97%” can be a display-only tweak later if needed. |
| Property breakdown | Simulated “Property 1 – 58%”, “Property 2 – 71%” for multi-property | Same idea | **Implement simulated breakdown** when property_count > 1 (e.g. distribute score across fake “properties” for display only). |

### 3.3 Risk bands vs existing code
- `backend/utils/risk_bands.py`: 80+ Low, 60+ Moderate, 40+ High, &lt;40 Critical (used for **real** compliance score in portal).
- Risk-check spec: **75–100 = LOW**, **50–74 = MODERATE**, **0–49 = HIGH** (same “high score = low risk” but different thresholds).
- **Recommendation:** Do **not** import `risk_bands` for the demo. Define demo-specific constants in the new risk-check module (e.g. `RISK_CHECK_BAND_LOW_MIN = 75`, `RISK_CHECK_BAND_MODERATE_MIN = 50`) so production compliance UX never changes.

---

## 4. Implementation Order (Professional and Safe)

1. **Backend – scoring and API (no persistence)**
   - Add `backend/services/risk_check_scoring.py`: pure function that takes Step 1 payload, returns score 0–100, risk_band, exposure_range_label, flags list. Unit test this.
   - Add `backend/routes/risk_check.py`: `POST /api/risk-check/preview` (calls scoring, returns teaser + blurred hint + flags_count).
   - Register router in `server.py` (no auth for preview).

2. **Backend – persistence and report**
   - Add `risk_leads` collection usage in `risk_check.py`: generate `lead_id` (e.g. `RISK-` + short id), store on `POST /api/risk-check/report` with first_name, email, Step 1 answers, computed score/risk_band/flags, utm_*, created_at.
   - Return full report + `lead_id` from report endpoint.
   - Optional: send “Your Compliance Risk Snapshot” email via notification orchestrator (new template_key or existing with context).

3. **Backend – admin**
   - Add `GET /api/admin/risk-leads` (and optional CSV export) with `admin_route_guard`. Or extend `admin_submissions` with type `risk` and `risk_leads` + `lead_id`. Prefer dedicated admin risk-leads routes to keep risk-check isolated.
   - Add “Email report again” endpoint: `POST /api/admin/risk-leads/{lead_id}/resend-report` (lookup lead, re-send same report email).

4. **Frontend – page and flow**
   - Add `RiskCheckPage.js` (or `.jsx`) with 3 steps, progress indicator, and exact copy from spec. Call `preview` then `report`; on report response show full report and CTAs to `/intake/start` and `/demo`.
   - Add route `/risk-check` in `App.js` and navbar CTA in `PublicHeader.js`.

5. **Admin UI**
   - Add Risk Leads table (new page or tab under Lead Management): list risk_leads, columns as above, “Email report again” button.

6. **Tests**
   - Backend: unit test scoring (e.g. expired gas + no tracking → expect score drop and HIGH band).
   - Frontend: shallow test that Step 2 does not show full report until email submitted (and report called).

---

## 5. File and Location Summary

| Layer | File(s) to add or touch |
|-------|--------------------------|
| Backend scoring | **New:** `backend/services/risk_check_scoring.py` |
| Backend API | **New:** `backend/routes/risk_check.py` |
| Backend server | **Touch:** `server.py` – include risk_check router |
| Backend DB | **Optional touch:** `database.py` – indexes for `risk_leads` |
| Backend admin | **New:** `backend/routes/admin_risk_leads.py` (or extend admin_submissions) |
| Frontend page | **New:** `frontend/src/pages/public/RiskCheckPage.js` |
| Frontend routes | **Touch:** `App.js` – route `/risk-check`; **Touch:** `PublicHeader.js` – CTA |
| Frontend export | **Touch:** `frontend/src/pages/public/index.js` – export RiskCheckPage if needed |
| Admin UI | **New:** `frontend/src/pages/AdminRiskLeadsPage.jsx` (or section in AdminLeadsPage) + route and nav link |
| Tests | **New:** `backend/tests/test_risk_check_scoring.py`; **New:** `frontend/src/pages/public/RiskCheckPage.test.js` (minimal) |
| Docs | **New:** `docs/RISK_CHECK_GAP_ANALYSIS.md` (this file) |

---

## 6. Summary

- **Nothing in the codebase currently implements the risk-check flow or `risk_leads`.** No duplication; no changes to intake, Stripe, or compliance scoring.
- **Conflicts between the two specs** are resolved by: two endpoints (preview + report), Spec A exposure wording (no £ figures), CTA only to `/intake/start`, and demo-specific scoring constants.
- **Safest approach:** Implement in the order above; keep risk-check isolated (dedicated routes and collection); add minimal admin surface (list + resend email); run scoring unit test and a simple frontend flow test.

Implementing in this order keeps existing flows untouched and makes the Compliance Risk Check a measurable, conversion-focused addition that can be tuned later (e.g. copy, bands, or optional plan recommendation by property count) without affecting production compliance or provisioning.
