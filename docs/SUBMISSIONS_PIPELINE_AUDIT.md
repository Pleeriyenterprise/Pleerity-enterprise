# Inbound Submission Management — Audit vs Task Requirements

## Purpose

Check the codebase against the task requirements for **professional, secure inbound submission management** (Lead Management, Talent Pool, Partnership Enquiries, Contact Enquiries). Identify what exists, what is missing, and any conflicts. **Do not implement** until approved.

---

## 1. Task Requirements (Summary)

| Area | Requirement |
|------|-------------|
| **Scope** | Lead Management (marketing + checklist), Talent Pool, Partnership Enquiries, Contact Enquiries. |
| **Data** | Prefer ONE collection `submissions` with `type`: "lead" \| "talent" \| "partnership" \| "contact"; or 4 collections. Schema: status, priority, source, person, message, metadata, consent, assignment, tags, notes, dedupe_key, spam_score, audit. |
| **Public API** | POST /api/public/lead, /contact, /partnership, /talent → validate, sanitize, dedupe, store; return `{ ok, submission_id, message }`. No internal leak. |
| **Validation** | Pydantic per type; email/phone/max lengths; strip HTML (stored XSS); message ≤2000; reject script/dangerous. |
| **Dedupe** | dedupe_key = sha256(type + normalized_email + phone + message_snippet_80 + day_bucket); if exists in 24h → duplicate note or update existing. |
| **Spam** | Rate limit (e.g. 5/min per IP), honeypot support. |
| **Safety** | No auto-email to leads unless explicitly enabled; consent flags + source + timestamp; submissions not exposed to non-admin. |
| **Admin API** | GET/PATCH /api/admin/submissions, notes, mark-spam, export CSV; RBAC owner/admin; audit on every PATCH. |
| **Optional** | ADMIN_NOTIFY_EMAIL for internal “New submission” email. |
| **Frontend** | Real pages: table, search, filters, detail drawer (message, metadata, audit, notes), actions (status, assign, tags, mark spam, copy), bulk export. Unified /admin/submissions with tabs preferred. |
| **Tests** | Validation rejects invalid payloads; dedupe 24h; RBAC; PATCH audit; export CSV. |
| **Docs** | docs/SUBMISSIONS_PIPELINE.md (events, statuses, fields, security). |

---

## 2. What Exists Today

### 2.1 Leads

| Item | Location | Notes |
|------|----------|--------|
| **Collection** | `leads` | Rich schema: lead_id, source_platform, service_interest, intent_score, stage, status, nurture, follow-up, source_metadata, etc. |
| **Public capture** | `backend/routes/leads.py` | POST /api/leads/capture/chatbot, /capture/contact-form, /capture/compliance-checklist, /capture/document-service, /capture/whatsapp. Uses LeadService.create_lead. |
| **Dedupe** | `backend/services/lead_service.py` | find_duplicate by email, phone, source_metadata; returns existing lead (is_duplicate). No 24h bucket or dedupe_key. |
| **Admin** | `backend/routes/leads.py` admin_router | Many endpoints under /api/admin/leads (list, get, update, notes, status, etc.). Uses admin_route_guard. |
| **Frontend** | /admin/leads → AdminLeadsPage | Full lead management UI (separate from “submissions”). |
| **Gaps** | — | No POST /api/public/lead. No unified “submissions” type. Lead schema differs from task’s person/message/consent/source shape. No HTML sanitization in lead_service. No rate limit on lead capture. |

### 2.2 Talent Pool

| Item | Location | Notes |
|------|----------|--------|
| **Collection** | `talent_pool` | Schema: submission_id, full_name, email, country, linkedin_url, phone, interest_areas, professional_summary, years_experience, skills_tools, availability, work_style, cv_*, consent_accepted, status (NEW/REVIEWED/SHORTLISTED/ARCHIVED), admin_notes, tags. |
| **Public** | `backend/routes/talent_pool.py` | POST /api/talent-pool/submit (not /api/public/talent). |
| **Dedupe** | Same file ~50–56 | By email only: if existing email → 400. No 24h key, no message snippet. |
| **Validation** | `backend/models/talent_pool.py` | Pydantic TalentPoolSubmission; no max lengths, no HTML strip. |
| **Admin** | talent_pool.py | GET /api/talent-pool/admin/list, /admin/{id}, PUT /admin/{id}, GET /admin/stats. admin_route_guard only (no require_owner_or_admin). |
| **Frontend** | /admin/talent-pool → AdminTalentPoolPage.jsx | Table, stats, search, status filter, “View” → navigates to /admin/talent-pool/{id}. **No route for /admin/talent-pool/:id** → 404. |
| **Gaps** | — | No rate limit; no honeypot; no sanitization; no notes array; no mark-spam; no export; no assignment; no audit array on doc; no dedupe_key; no source (page, utm). |

### 2.3 Partnership Enquiries

| Item | Location | Notes |
|------|----------|--------|
| **Collection** | `partnership_enquiries` | Model in `backend/models/partnership.py`: enquiry_id, first_name, last_name, role_title, work_email, phone, partnership_type, company_name, country_region, website_url, org_*, collaboration_*, problem_solved, timeline, additional_notes, declaration_accepted, status (NEW/REVIEWED/APPROVED/REJECTED/ARCHIVED), admin_notes, tags, ack_email_sent. |
| **Public** | `backend/routes/partnerships.py` | POST /api/partnerships/submit (not /api/public/partnership). **Sends acknowledgement email automatically** (send_partnership_ack_email) — conflicts with “do not send emails to leads automatically unless explicitly enabled”. |
| **Dedupe** | Same file ~55–64 | By work_email only; 400 if exists. No 24h key. |
| **Admin** | partnerships.py | GET /admin/list, /admin/{id}, PUT /admin/{id}, GET /admin/stats. admin_route_guard. |
| **Frontend** | /admin/partnership-enquiries → AdminPartnershipEnquiriesPage.jsx | Table, stats, search, status filter, “View” → /admin/partnership-enquiries/{id}. **No route for detail** → 404. |
| **Gaps** | — | Same as talent: no rate limit, honeypot, sanitization, notes[], mark-spam, export, assignment, audit[], dedupe_key, source. **Conflict:** auto ack email. |

### 2.4 Contact Enquiries

| Item | Location | Notes |
|------|----------|--------|
| **Two implementations** | **A** `backend/routes/public.py` | POST /api/public/contact → writes to **contact_submissions** (submission_id, full_name, email, phone, company_name, contact_reason, subject, message, status "new", source_ip). **Rate limit 5/min per IP.** No dedupe key, no consent, no HTML strip. |
| | **B** `backend/routes/admin_modules.py` | POST /api/public/contact (duplicate path) → writes to **contact_enquiries** (enquiry_id, ContactEnquiry model). No rate limit. |
| **Admin** | admin_modules.py | GET /api/admin/contact/enquiries, /contact/enquiries/{id}, POST /contact/enquiries/{id}/reply. Reads **contact_enquiries**. |
| **Frontend** | /admin/inbox/enquiries → AdminContactEnquiriesPage.jsx | Fetches /api/admin/contact/enquiries → **shows contact_enquiries**. Submissions from public.router go to **contact_submissions**, so **admin page does not show submissions from public.py**. Data split across two collections. |
| **Gaps** | — | Contact flow broken: two collections, two public endpoints (same path). No notes array, mark-spam, export, assignment, audit, dedupe_key, consent, source. Detail route /admin/inbox/enquiries/:id not defined in App.js (link points to it). |

### 2.5 Database indexes

| Collection | Indexes in database.py |
|------------|-------------------------|
| leads | Not created in database._create_indexes (relies on application or manual). |
| talent_pool | Not present in database.py. |
| partnership_enquiries | Not present in database.py. |
| contact_submissions | Not present. |
| contact_enquiries | Not present. |

### 2.6 RBAC

- Talent, partnership, contact admin use **admin_route_guard** (admin role). Task asks **owner/admin**; same as other admin areas unless project uses require_owner_or_admin for sensitive data — then submissions should use it.

---

## 3. Conflicts and Recommendations

### 3.1 One “submissions” collection vs four

- **Task:** Prefer one collection `submissions` with type field.
- **Current:** Four collections with different schemas; leads deeply integrated (nurture, follow-up, conversion).
- **Recommendation:** **Do not merge leads into a new submissions collection.** Option A: Introduce a new `submissions` collection only for **talent, partnership, contact** (and optionally a thin “lead” submission that also creates/links to a lead). Option B: Keep four collections and add a **unified admin API** (GET /api/admin/submissions?type=…) that queries all four and normalizes response. Option B is safer and avoids migration; Option A gives one store for new flows. **Safest:** Keep existing collections; add unified admin list/detail/export that reads from all four; add validation/sanitization/dedupe/rate-limit to existing public endpoints; align contact to one collection (see below).

### 3.2 Contact: two collections and two public endpoints

- **Conflict:** public.py writes to `contact_submissions`; admin_modules writes to `contact_enquiries`; admin UI reads `contact_enquiries`. So either (1) marketing site uses admin_modules’ contact and enquiries are in contact_enquiries, or (2) marketing uses public.router and data is in contact_submissions and never shown in admin.
- **Recommendation:** **Consolidate to one collection.** Prefer **contact_submissions** (already has rate limiting and /api/public prefix). Deprecate admin_modules POST /api/public/contact; make admin list/get/reply read and write **contact_submissions** (and extend schema with status, replied_at, etc. if needed). Remove or migrate contact_enquiries so admin “Contact Enquiries” shows a single source of truth.

### 3.3 Partnership acknowledgement email

- **Task:** “No sending emails to leads automatically unless explicitly enabled.”
- **Current:** Partnership submit sends ack email unconditionally.
- **Recommendation:** Make it **configurable**: e.g. env `PARTNERSHIP_SEND_ACK_EMAIL=true` or per-deployment; default **false** for new installs. Or keep current behaviour and document as “explicitly enabled for partnership ack only.” Prefer env default off so task rule is satisfied.

### 3.4 Public endpoint paths

- **Task:** POST /api/public/lead, /contact, /partnership, /talent.
- **Current:** /api/public/contact exists (two implementations); leads under /api/leads/capture/*; partnership /api/partnerships/submit; talent /api/talent-pool/submit.
- **Recommendation:** Add **thin wrappers** at /api/public/lead, /api/public/partnership, /api/public/talent that accept task-shaped payload, map to existing services, and return `{ ok: true, submission_id, message }`. Lead wrapper can call LeadService or write to a new submission type. Avoid breaking existing form POST URLs; either keep existing paths as-is and add /api/public/* as additional options, or migrate forms to new paths and keep old paths as redirects.

### 3.5 Leads vs “submission type lead”

- **Task:** “Lead Management (marketing leads + checklist downloads)”.
- **Current:** Leads are a full CRM-style entity (stages, nurture, follow-up). Task’s “lead” might mean “any lead-form submission” to be stored and shown in a pipeline.
- **Recommendation:** **Do not replace leads collection.** Either (1) add a submission type “lead” that stores a copy in `submissions` and optionally links to or creates a lead in `leads`, or (2) keep leads as-is and expose a unified admin view that includes “leads” as one tab/source. Prefer (2) for minimal change: unified admin UI that shows leads (from leads collection) plus talent, partnership, contact from their collections.

---

## 4. What Is Missing (Checklist)

| # | Item | Status |
|---|------|--------|
| 1 | Single `submissions` collection with type + full schema (or keep 4 collections + unified API) | ❌ Not as specified |
| 2 | Indexes: type+status+created_at, person.email, dedupe_key (unique/partial) | ❌ None for submissions/talent_pool/partnership_enquiries/contact_* |
| 3 | Pydantic validation per type + max lengths + message ≤2000 | ⚠️ Partial (models exist; no max lengths, no sanitization) |
| 4 | HTML sanitization (strip tags) on message/textarea fields | ❌ |
| 5 | dedupe_key = sha256(type+email+phone+message_80+day); 24h dedupe behaviour | ❌ (only email-based dedupe for talent/partnership; contact none) |
| 6 | Rate limiting per IP (e.g. 5/min) on all public submission endpoints | ⚠️ Only on public.router contact/service-inquiry |
| 7 | Honeypot field support → mark spam / discard | ❌ |
| 8 | POST /api/public/lead, /contact, /partnership, /talent returning { ok, submission_id, message } | ⚠️ Only /api/public/contact (and duplicate); others different paths |
| 9 | Consent + source + timestamp stored (consent object, source.page/url/campaign/utm) | ⚠️ Partial (partnership/talent have consent; contact/lead vary) |
| 10 | GET /api/admin/submissions?type=&status=&q=&from=&to=&page=&page_size= | ❌ |
| 11 | GET /api/admin/submissions/{id} | ❌ (per-type admin get exist; no unified id) |
| 12 | PATCH /api/admin/submissions/{id} (status, priority, assignment, tags) + audit on every PATCH | ❌ (PUT updates exist without audit array on doc) |
| 13 | POST /api/admin/submissions/{id}/notes | ❌ (admin_notes single field only where present) |
| 14 | POST /api/admin/submissions/{id}/mark-spam | ❌ |
| 15 | GET /api/admin/submissions/export?type=&status=&from=&to= → CSV | ❌ |
| 16 | require_owner_or_admin on admin submission endpoints | ⚠️ admin_route_guard only |
| 17 | Optional ADMIN_NOTIFY_EMAIL on new submission | ❌ |
| 18 | Frontend: unified /admin/submissions with tabs OR four pages with table, filters, search, detail drawer | ⚠️ Four pages exist; no detail routes; no drawer; no export, no mark-spam, no assignment |
| 19 | Detail view: full message, metadata, audit log, notes thread, actions (status, assign, tags, mark spam, copy) | ❌ (links go to missing routes) |
| 20 | Bulk actions: mark spam, assign, export CSV | ❌ |
| 21 | Confirmation modals for mark spam / delete; empty/loading/error states | ❌ |
| 22 | No XSS: message never rendered as HTML | ⚠️ Not documented; ensure frontend escapes |
| 23 | Retention policy placeholder (flag for auto-delete after X days) | ❌ |
| 24 | Backend tests: validation, dedupe 24h, RBAC, PATCH audit, export CSV | ❌ |
| 25 | docs/SUBMISSIONS_PIPELINE.md | ❌ |

---

## 5. File:Line References (Existing Code)

| Area | File | Lines / Notes |
|------|------|----------------|
| Lead capture (public) | backend/routes/leads.py | capture_chatbot_lead ~90–155, capture_contact_form_lead ~158–198, capture_compliance_checklist_lead ~201–248, capture_document_service_lead ~251–284, capture_whatsapp_lead ~287–326 |
| Lead service create_lead | backend/services/lead_service.py | create_lead ~54+, find_duplicate used before insert |
| Talent public submit | backend/routes/talent_pool.py | POST /submit ~46–87 |
| Talent admin | backend/routes/talent_pool.py | list ~94–119, get ~122–138, put ~141–196, stats ~199–215 |
| Partnership public submit | backend/routes/partnerships.py | POST /submit ~50–109; send_partnership_ack_email ~112–155 |
| Partnership admin | backend/routes/partnerships.py | list ~163–186, get ~189–205, put ~208–259, stats ~262–277 |
| Contact public (contact_submissions) | backend/routes/public.py | POST /contact ~86–135; rate_limit ~63–80 |
| Contact public (contact_enquiries) | backend/routes/admin_modules.py | POST /api/public/contact ~29–50 |
| Contact admin | backend/routes/admin_modules.py | GET /contact/enquiries ~55–59, GET /contact/enquiries/{id} ~61–65, POST reply ~72–79 |
| Admin UI leads | frontend: /admin/leads | AdminLeadsPage (separate from submissions) |
| Admin UI talent | frontend/src/pages/AdminTalentPoolPage.jsx | Table, stats, filter; View → /admin/talent-pool/{id} (no route) |
| Admin UI partnership | frontend/src/pages/AdminPartnershipEnquiriesPage.jsx | Table, stats, filter; View → /admin/partnership-enquiries/{id} (no route) |
| Admin UI contact | frontend/src/pages/AdminContactEnquiriesPage.jsx | Fetches /api/admin/contact/enquiries; View → /admin/inbox/enquiries/{id} (no route) |
| Sidebar | frontend/src/components/admin/UnifiedAdminLayout.js | Leads ~61, Talent Pool ~62, Partnership Enquiries ~63, Contact Enquiries /admin/inbox/enquiries ~64 |

---

## 6. Recommended Implementation Order (After Approval)

1. **Fix contact**  
   - Single collection (e.g. contact_submissions); single public endpoint; admin reads/writes same collection; add status, reply fields if needed.
2. **Validation and safety**  
   - Add Pydantic max lengths, HTML strip (e.g. strip tags) on message/textarea for all four flows; reject script/dangerous payloads.
3. **Dedupe and spam**  
   - Define dedupe_key (sha256 type+normalized email+phone+message_80+day); 24h dedupe behaviour; rate limit on talent_pool and partnerships; optional honeypot.
4. **Public API shape**  
   - Add /api/public/lead, /api/public/partnership, /api/public/talent (wrappers or new) returning { ok, submission_id, message }; store source (page, url, utm), consent, ip, user_agent.
5. **Admin API**  
   - Either unified GET/PATCH /api/admin/submissions (querying four collections or a new submissions store) or keep per-type endpoints and add: notes array, mark-spam, export CSV, audit log on PATCH; use require_owner_or_admin if project standard.
6. **Partnership email**  
   - Env PARTNERSHIP_SEND_ACK_EMAIL default false; send ack only if enabled.
7. **Frontend**  
   - Add detail routes for talent, partnership, contact (or one unified submission detail); detail drawer/page with message, metadata, audit, notes, actions; bulk export and mark-spam; confirm modals; empty/loading/error states.
8. **Indexes and docs**  
   - Create indexes for submissions (or per collection); add docs/SUBMISSIONS_PIPELINE.md.
9. **Tests**  
   - Validation, dedupe, RBAC, PATCH audit, export CSV.

---

## 7. Summary

| Topic | Status | Action |
|-------|--------|--------|
| Collections | 4 existing (leads, talent_pool, partnership_enquiries, contact_submissions + contact_enquiries) | Unify contact to one collection; optional unified submissions store for talent/partnership/contact; leave leads as-is. |
| Public endpoints | contact (duplicate), leads/talent/partnership on different paths | Add /api/public/* wrappers; consolidate contact to one. |
| Validation/sanitization | Partial | Add max lengths, HTML strip, reject dangerous. |
| Dedupe | Email-only or none | Implement 24h dedupe_key. |
| Rate limit | Contact only | Extend to talent, partnership, lead. |
| Admin API | Per-type list/get/put; no notes array, mark-spam, export | Add notes, mark-spam, export; optional unified list. |
| Frontend | Four list pages; no detail routes, no drawer, no export | Add detail routes/drawer, bulk actions, export. |
| Partnership ack email | Always sent | Make configurable (env default off). |
| RBAC | admin_route_guard | Consider require_owner_or_admin for submissions. |

No blocking conflict; the safest approach is to keep existing collections and leads flow, unify contact to one collection and one admin source, harden validation/dedupe/rate-limit, add unified admin UX and export, and make partnership ack configurable.
