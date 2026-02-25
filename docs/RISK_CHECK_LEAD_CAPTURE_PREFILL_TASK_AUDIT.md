# Marketing Risk Check → Lead Capture → Activate Monitoring → Pre-filled Intake — Task Audit

**Task:** Implement/verify Risk Check as lead-only until payment; “Activate Monitoring” links with pre-filled intake via lead_token; no change to provisioning triggers. **Do not implement blindly.** This audit maps task requirements to current code, identifies implemented vs missing, and notes conflicts or safest options.

**Non-negotiable (task):** Risk demo creates Lead only (no Client/PortalUser); Intake is the only place Client+Properties are created; Payment via existing Stripe checkout; Provisioning via Stripe webhooks only; Auto-fill editable, no auto-set consent or billing_plan.

---

## 1. A) DATA MODEL: RiskLead (backend)

| Requirement | Current state | Status |
|-------------|---------------|--------|
| Collection/table for risk leads | `risk_leads` collection in MongoDB; used in `backend/routes/risk_check.py` (COLLECTION = "risk_leads"), `database.py` indexes | **Done** |
| Formal model in backend/models | No Pydantic/model class in `backend/models`; docs built as dict in `risk_check_report()` | **Missing** — task asks for model “in backend/models where your other models live”. Optional for behaviour; improves validation and docs. |
| _id, created_at, updated_at | Doc has `created_at` (iso); no `updated_at` in insert; `_id` from MongoDB | **Partial** — add `updated_at` on updates if desired. |
| first_name, full_name, email, phone | first_name, email present; full_name, phone not in doc | **Partial** — add full_name, phone if intake needs them. |
| property_count, has_hmo | Stored as property_count, any_hmo | **Done** (any_hmo = has_hmo) |
| gas/eicr/epc status fields | gas_status, eicr_status stored; no epc_rating_or_status | **Partial** — add epc_rating_or_status if needed for prefill. |
| tracking_method (enum) | Stored as string (e.g. "Manual reminders", "Automated system") | **Done** |
| calculated_score, risk_band | computed_score, risk_band | **Done** (naming differs) |
| estimated_exposure_low/high | Not stored; only exposure_range_label (text) | **Missing** — task wants bounded ints; scoring currently has no numeric exposure. Add optional if needed. |
| converted, converted_at, converted_client_id | status = "converted", converted_at, client_id (not converted_client_id) | **Partial** — behaviour same; task field name is converted_client_id. Webhook sets status, converted_at, client_id. |
| last_activation_link_sent_at, activation_link_token | last_email_sent_at (for nurture); no activation_link_token, no last_activation_link_sent_at | **Missing** — required for task’s tokenised “Activate Monitoring” link. |
| source | Not stored | **Missing** — add e.g. "homepage_risk_check". |
| Indexes: email, created_at, activation_link_token | database.py: lead_id, created_at, email, risk_band, status | **Partial** — add index on activation_link_token when token exists. |

**File refs:** `backend/routes/risk_check.py` 132–157 (doc shape); `backend/database.py` 151–155 (indexes). No `backend/models/risk_lead.py` (or similar).

---

## 2. B) ENDPOINTS (backend/routes)

### B.1) POST /api/risk-check (questionnaire)

| Requirement | Current | Status |
|-------------|---------|--------|
| Single POST /api/risk-check accepting questionnaire | Two endpoints: POST /api/risk-check/preview (no email) and POST /api/risk-check/report (with email, persist) | **Different shape** — task suggests one endpoint; current split is valid (preview vs report). Keep as-is or add thin POST /api/risk-check that delegates. |
| Compute calculated_score, risk_band, estimated_exposure_* | compute_risk_check_result() returns score, risk_band, exposure_range_label; no estimated_exposure_low/high | **Partial** — scoring done; add optional exposure_low/high if required. |
| If email => upsert lead by email (or create) | Report always creates new lead (lead_id = RISK-xxx); no upsert by email | **Gap** — task “upsert lead by email”. Current can create duplicates if same email twice. Recommend: find by email (case-insensitive), update if found else insert. |
| Return partial preview if no email, full report if email | preview returns band/teaser/flags; report persists and returns full report | **Done** |
| Never create Client | No client creation in risk_check routes | **Done** |

**File refs:** `backend/routes/risk_check.py` 84–108 (preview), 110–188 (report).

### B.2) POST /api/risk-check/send-report

| Requirement | Current | Status |
|-------------|---------|--------|
| Input: lead_id or email | N/A | **Missing** — no such endpoint. |
| Send “Your Risk Report” email with “Activate Monitoring” CTA | Email sent inside POST /report via _send_risk_report_email(lead) (risk_lead_email_service step 1) | **Done** but link has no token (see B.3). |
| CTA link = FRONTEND_APP_ORIGIN + "/intake/start?lead_token=XXXX" | _activate_url(lead) returns base + "/intake/start" (no lead_token) | **Missing** — task requires lead_token (signed, expiry e.g. 7 days). |
| Generate signed token (HMAC/JWT), encode lead_id, expiry | Not implemented | **Missing** |
| Store last_activation_link_sent_at | last_email_sent_at, email_sequence_step stored; no last_activation_link_sent_at | **Missing** |
| If email not configured, return activation URL in response | N/A | **Missing** (endpoint doesn’t exist). |

**File refs:** `backend/services/risk_lead_email_service.py` 22–31 (_activate_url); `backend/routes/risk_check.py` 163–168 (send email after insert).

### B.3) GET /api/risk-check/lead-from-token

| Requirement | Current | Status |
|-------------|---------|--------|
| Query: lead_token=... | N/A | **Missing** — endpoint does not exist. |
| Verify signature + expiry | N/A | **Missing** |
| Return sanitized lead payload for prefill (intake-relevant only) | N/A | **Missing** |
| Do NOT return risk exposure numbers (recommended) | N/A | **Missing** |

**Recommendation:** Add GET /api/risk-check/lead-from-token?lead_token=... that: verifies token (HMAC or JWT with secret + expiry), loads lead by lead_id from token, returns e.g. { email, first_name, full_name?, phone?, property_count, any_hmo, gas_status, eicr_status, tracking_method } (no score/exposure if desired).

---

## 3. C) FRONTEND: Risk Check page + Activate Monitoring link

| Requirement | Current | Status |
|-------------|---------|--------|
| /risk-check route/page | App.js: Route /risk-check → RiskCheckPage | **Done** |
| Two-stage: questions then gate full report behind email (or blur+email) | RiskCheckPage: Step 1 questions → Step 2 partial → Step 3 email gate → Step 4 full report | **Done** |
| On email submit: call POST risk-check then send-report (or combine) | Frontend calls postReport (POST /api/risk-check/report) only; report handler sends email internally | **Done** (single call). Task’s separate send-report is for “resend” or optional second call; not required for first-time flow. |
| Show “Report sent. Check your email.” | Step 4 shows full report; no explicit “Report sent. Check your email.” (email is sent by backend) | **Partial** — could add short confirmation line. |
| Fix “Activate Monitoring” link in emails: use FRONTEND_PUBLIC_ORIGIN (or similar), link = .../intake/start?lead_token=... | _activate_url uses PUBLIC_MARKETING_BASE_URL then get_public_app_url; link is base + /intake/start (no lead_token) | **Missing** — must add token generation and append ?lead_token= to link; use single env for app origin (task: Option SAFE = direct to APP origin). |

**File refs:** `frontend/src/App.js` (route); `frontend/src/pages/public/RiskCheckPage.js` (flow); `frontend/src/api/riskCheckAPI.js` (postReport); `backend/services/risk_lead_email_service.py` (_activate_url).

---

## 4. D) FRONTEND: IntakePage auto-fill from RiskLead (A = Auto-fill)

| Requirement | Current | Status |
|-------------|---------|--------|
| Route /intake/start uses IntakePage.js | Confirmed | **Done** |
| On mount: read lead_token from query | IntakePage reads lead_id and from (source); does NOT read lead_token | **Missing** |
| If lead_token present: GET /api/risk-check/lead-from-token?lead_token=... | Not implemented | **Missing** |
| Pre-fill formData: full_name, email, phone, property count hint, is_hmo on first property, optional document_submission_method from tracking_method | Not implemented; only marketing.lead_id/source set for submit | **Missing** |
| Safer property handling: 1 property card + banner “You indicated X properties; add them here” if property_count > 1 | Not implemented | **Missing** |
| Banner: “We preloaded your setup from your risk check. You can change anything.” | Not implemented | **Missing** |
| Do NOT auto-set: billing_plan, consent checkboxes, payment | N/A | **OK** — nothing auto-sets these today. |

**File refs:** `frontend/src/pages/IntakePage.js` 146–207 (marketing state from lead_id/from only; no lead_token, no prefill).

---

## 5. E) MARK LEAD AS CONVERTED (backend) — no change to provisioning

| Requirement | Current | Status |
|-------------|---------|--------|
| In Stripe webhook (checkout.session.completed or subscription created): when customer email + metadata client_id/plan_code | checkout.session.completed handler uses metadata client_id, plan_code; lead_id from metadata | **Done** |
| Find RiskLead by email (case-insensitive) if not already converted | Current finds by lead_id in metadata only; does not fall back to email lookup | **Partial** — task: “Try to find RiskLead by email”. Current requires lead_id in session metadata (set at checkout when user had lead_id in URL). Adding email fallback would catch users who lost lead_id. |
| Set converted = true, converted_at = now, converted_client_id = client_id | Sets status = "converted", converted_at, client_id (same semantics; field name converted_client_id in task) | **Done** |
| Does NOT provision; only attribution | No provisioning in this block; only risk_leads.update_one and optional client.initial_risk_snapshot | **Done** |

**File refs:** `backend/services/stripe_webhook_service.py` 641–676 (mark risk lead converted by lead_id from metadata).

**Conflict/option:** Task says “find RiskLead by email”. Current design: lead_id is passed from intake to checkout and into Stripe metadata, so webhook has lead_id. Safest addition: if metadata has lead_id, keep current behaviour; if metadata lacks lead_id but has customer email, try find-one by email (case-insensitive) and mark converted. That way both “link through lead_id” and “same email later” are covered.

---

## 6. F) DOMAIN + URL SAFETY

| Requirement | Current | Status |
|-------------|---------|--------|
| Single source of truth for public URLs | get_public_app_url() in utils/public_app_url.py (FRONTEND_PUBLIC_URL, PUBLIC_APP_URL, FRONTEND_URL, VERCEL_URL, RENDER_EXTERNAL_URL) | **Done** |
| BACKEND: PUBLIC_APP_ORIGIN, PUBLIC_MARKETING_ORIGIN | Backend uses PUBLIC_MARKETING_BASE_URL in risk_lead_email_service; get_public_app_url for app | **Partial** — task names PUBLIC_APP_ORIGIN / PUBLIC_MARKETING_ORIGIN; current uses PUBLIC_MARKETING_BASE_URL and get_public_app_url. Align naming in config/docs or add aliases. |
| FRONTEND: REACT_APP_PUBLIC_APP_ORIGIN, REACT_APP_API_BASE_URL | REACT_APP_API_BASE_URL exists; no REACT_APP_PUBLIC_APP_ORIGIN in audit | **Partial** — frontend may use same env as API base; document app origin for intake/start links. |
| Activation links: Option SAFE = always direct to APP origin (portal app), not marketing domain | _activate_url uses PUBLIC_MARKETING_BASE_URL; task recommends directing to APP origin so /intake/start is on same app | **Conflict** — task “Option SAFE: Always direct activation links to the APP origin”. So email link should be APP origin + /intake/start?lead_token=... (not marketing). Use get_public_app_url (or PUBLIC_APP_ORIGIN) for activation links, not PUBLIC_MARKETING_BASE_URL. |

**Recommendation:** Use one backend env for “app origin” (e.g. FRONTEND_PUBLIC_URL or PUBLIC_APP_ORIGIN) for all activation and intake links. Do not use marketing domain for “Activate Monitoring” so /intake/start is always on the app that hosts the intake.

---

## 7. G) TESTS

| Task requirement | Current | Status |
|------------------|---------|--------|
| Backend: risk-check creates lead, does NOT create client | test_risk_check.py: report mocks DB, asserts no client creation; test_marketing_funnel_conversion covers intake+lead_id | **Done** |
| Backend: lead-from-token returns 200 with sanitized payload | No endpoint yet | **Missing** |
| Backend: token expiry returns 401/400 | No endpoint yet | **Missing** |
| Backend: webhook conversion sets converted=true, does not touch provisioning (assert no onboarding_status change in that path) | test_marketing_funnel_conversion has activate; no explicit “provisioning unchanged” test for webhook conversion block | **Partial** — add test that conversion update only touches risk_leads and does not change onboarding_status/provisioning. |
| Frontend: /intake/start?lead_token=... calls lead-from-token and pre-fills email/name | No test; no prefill implemented | **Missing** |
| Frontend: consents remain unchecked; plan not auto-set | No test | **Missing** |

**File refs:** `backend/tests/test_risk_check.py`; `backend/tests/test_marketing_funnel_conversion.py`; `backend/tests/test_risk_lead_email_service.py`.

---

## 8. H) IMPLEMENTATION NOTES (no breaking changes)

| Rule | Current | Status |
|------|---------|--------|
| Do NOT modify /api/intake/submit and /api/intake/checkout except optionally prefill (frontend-only) | Intake submit accepts lead_id/source; checkout passes lead_id to Stripe metadata. No backend change needed for prefill if prefill is frontend-only (GET lead-from-token, then set local state) | **OK** |
| Keep existing Stripe checkout and provisioning | No change in task to checkout or webhook provisioning flow | **OK** |
| Keep RBAC and admin dashboards unchanged | Task does not require changes | **OK** |

---

## 9. SUMMARY: IMPLEMENTED VS MISSING

**Implemented (keep as-is or minor tweaks):**

- risk_leads collection and indexes (email, created_at, lead_id, status, risk_band).
- POST /api/risk-check/preview and POST /api/risk-check/report; scoring; no Client creation.
- Report flow persists lead and sends email (step 1) via risk_lead_email_service.
- Intake reads lead_id (and from) from URL and passes lead_id to submit and checkout.
- Stripe webhook marks risk_leads converted (by lead_id in metadata), sets status, converted_at, client_id; optional initial_risk_snapshot on client; no provisioning in this block.
- Single source of truth for app URL (get_public_app_url); PUBLIC_MARKETING_BASE_URL used for email link base.
- Risk Check page: two-stage flow, email gate, report sent on submit.
- Tests: risk_check (preview/report), risk_lead_email (_activate_url, step1 body), marketing_funnel (intake+lead_id, activate).

**Missing or to add:**

1. **Lead document shape:** Add (optional) full_name, phone, source; add last_activation_link_sent_at and activation_link_token when token is implemented; optionally converted_client_id as alias for client_id; optionally estimated_exposure_low/high and epc_rating_or_status if needed for product.
2. **Upsert by email:** In report handler, find existing lead by email (case-insensitive); if found, update and return same lead_id (or new) per product rule; else insert new. Reduces duplicate leads.
3. **Signed lead_token and “Activate Monitoring” link:** Generate token (HMAC or JWT) with lead_id + expiry (e.g. 7 days); store in lead (activation_link_token) and set last_activation_link_sent_at when sending; build link as APP_ORIGIN + "/intake/start?lead_token=" + token. Use app origin (not marketing) for link.
4. **POST /api/risk-check/send-report:** Optional separate endpoint (lead_id or email) to resend report email with new token; or keep “send on report” and add token to that email only. If resend is required, add endpoint; else just add token to existing report email.
5. **GET /api/risk-check/lead-from-token:** Verify token, return sanitized prefill payload (email, first_name, full_name?, phone?, property_count, any_hmo, gas_status, eicr_status, tracking_method; no score/exposure if desired). Index activation_link_token for fast lookup.
6. **IntakePage prefill:** On mount, if lead_token in query: GET lead-from-token, prefill form (full_name, email, phone, property_count hint, is_hmo on first property); show one property + banner “You indicated X properties; add them here” when property_count > 1; show banner “We preloaded your setup from your risk check. You can change anything.” Do not set billing_plan or consent.
7. **Email link:** Switch activation link to use app origin (get_public_app_url or PUBLIC_APP_ORIGIN) and append ?lead_token=... so prefill works on the app that serves /intake/start.
8. **Webhook conversion fallback:** Optionally, when metadata has no lead_id, find risk_lead by customer email (case-insensitive) and mark converted (same fields). Keeps current lead_id path and adds email fallback.
9. **Tests:** Backend: lead-from-token 200 + sanitized payload; token expiry 401/400; webhook conversion does not change onboarding_status. Frontend: intake with lead_token prefills and leaves consents/plan unset.
10. **Formal RiskLead model (optional):** Add Pydantic model in backend/models for validation and docs; persist same shape in risk_leads.

---

## 10. CONFLICTS AND SAFEST OPTIONS

| Topic | Conflict | Safest option |
|-------|----------|---------------|
| Activation link base URL | Task: Option SAFE = APP origin. Current: PUBLIC_MARKETING_BASE_URL (marketing). | Use **app origin** (get_public_app_url or PUBLIC_APP_ORIGIN) for “Activate Monitoring” so /intake/start and lead_token are on the same app. Do not use marketing domain for this link. |
| Single POST /api/risk-check vs /preview and /report | Task says “POST /api/risk-check”. Current has /preview and /report. | **Keep** /preview and /report; they match frontend and are clear. Optionally add POST /api/risk-check that delegates to preview or report by presence of email. |
| Conversion: by lead_id vs by email | Task: “find RiskLead by email”. Current: convert by lead_id from metadata. | **Keep** lead_id in metadata (intake → checkout → webhook). **Add** fallback: if metadata has no lead_id, look up by customer email (case-insensitive) and mark converted. Same fields; no extra provisioning. |
| Upsert by email on report | Task: “if payload includes email => upsert lead by email (or create new)”. Current: always create. | **Add** upsert: find_one by email (case-insensitive); if found, update (and optionally reuse lead_id); else insert. Reduces duplicates and supports “same user does risk check again”. |

---

## 11. DELIVERABLES (task) — STATUS

| Deliverable | Status |
|-------------|--------|
| New backend routes + model + tests | Routes: preview/report exist; add lead-from-token and optionally send-report. Model: optional Pydantic. Tests: add for token and conversion. |
| New frontend /risk-check page + CTA wiring | Page and CTAs exist; fix email CTA to include lead_token and use app origin. |
| Fixed email templates: “Risk Report” email includes working Activate Monitoring link | Current link works but has no token; add token and use app origin so prefill works. |
| IntakePage lead_token prefill + banner | Not implemented; add per D. |
| Webhook conversion marking (lead attribution only) | Implemented; optionally add email fallback. |
| “How to test end-to-end” checklist | Not produced; add after implementation. |
| File:line references and PR-ready diff summary | This audit provides file refs; diff after implementation. |

---

## 12. RECOMMENDED IMPLEMENTATION ORDER (no code written here)

1. **Token and link:** Add signed lead_token (e.g. HMAC or JWT with secret + 7-day expiry), store activation_link_token and last_activation_link_sent_at on lead; change _activate_url to app origin + "/intake/start?lead_token=" + token; ensure report email (and any resend) uses it.
2. **GET /api/risk-check/lead-from-token:** Verify token, return sanitized prefill payload; add index on activation_link_token.
3. **IntakePage:** Read lead_token from query; call lead-from-token; prefill form and show banner; single property + “You indicated X properties” when property_count > 1.
4. **Upsert by email:** In report handler, find by email (case-insensitive) and update or insert.
5. **Webhook:** Add fallback: if no lead_id in metadata, find risk_lead by customer email and mark converted.
6. **Tests:** Backend token + expiry; webhook conversion without provisioning change; frontend prefill and consents/plan not set.
7. **Docs/config:** Document PUBLIC_APP_ORIGIN (or FRONTEND_PUBLIC_URL) for activation links; add “How to test end-to-end” checklist.

This audit is the single reference for what is implemented vs missing and how to implement without duplicating or breaking existing flows.
