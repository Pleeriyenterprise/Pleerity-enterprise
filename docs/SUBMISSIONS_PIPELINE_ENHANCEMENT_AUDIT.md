# Submissions Pipeline — Enhancement Audit (Enterprise Rules)

This document checks the codebase against the **enhancement** task (marketing forms, backend enforcement, admin UI, internal notifications, docs/tests) and identifies what is implemented, what is missing, and **conflicts** with the current implementation. No code is changed here; recommendations are given for the safest, non-duplicative approach.

---

## A) Marketing-site forms

| Requirement | Current state | Gap / conflict |
|-------------|----------------|----------------|
| **4 forms: Lead, Contact, Partnership, Talent** | **Contact**: `ContactPage.js` → `POST /api/public/contact`. **Partnership**: `PartnershipEnquiryForm.js` → `POST /api/partnerships/submit` (not `/api/public/partnership`). **Talent**: `TalentPoolWizard.js` → `POST /api/talent-pool/submit` (not `/api/public/talent`). **Lead**: No dedicated marketing “Lead” form; leads are captured via `/api/leads/capture/*` (chatbot, contact-form, compliance-checklist, etc.) and `POST /api/public/lead` exists but no public page posts to it. | **Gap**: Contact form only sends core fields; Partnership/Talent use legacy endpoints. No standalone “Lead” form on marketing site (optional: add a simple “Request demo” / “Get in touch” form that posts to `/api/public/lead`). **Optional alignment**: Point Partnership and Talent forms to `/api/public/partnership` and `/api/public/talent` so all public submissions go through `/api/public/{type}`. |
| **privacy_accepted checkbox (required)** | Contact backend accepts `privacy_accepted: bool = False`; no rejection. Contact frontend does **not** send or show `privacy_accepted`. Partnership has `declaration_accepted`; Talent has `consent_accepted`. Neither has a dedicated “privacy policy accepted” checkbox. | **Gap**: All four forms lack a required “I accept the privacy policy” checkbox. Backend does not reject when `privacy_accepted` is false. |
| **marketing_opt_in (optional, default false)** | Contact backend has `marketing_opt_in`; frontend does not send it. Partnership/Talent have no marketing_opt_in field. Lead has `marketing_consent`. | **Gap**: Contact form needs checkbox + payload; Partnership/Talent need optional marketing_opt_in and backend support. |
| **Hidden UTM: utm_source, utm_medium, utm_campaign, utm_content, utm_term** | Contact backend has utm_source, utm_medium, utm_campaign only. Frontend sends none. Lead backend has utm_source, utm_medium, utm_campaign, referrer_url; no utm_content, utm_term. | **Gap**: Add utm_content, utm_term to contact (and lead if desired). All forms must send hidden UTM inputs (e.g. from URL params). |
| **Hidden referrer: document.referrer** | Contact backend has `referrer`; frontend does not send it. Lead has `referrer_url`. | **Gap**: All forms should set a hidden field from `document.referrer` and send it. |
| **Honeypot: field name `website` (hidden); if filled → mark spam** | Contact/lead use a field named `honeypot`; task specifies **`website`**. Backend uses `is_honeypot_filled(submission.honeypot)`; no `website` field. | **Conflict**: Task says honeypot field name **website**. **Recommendation**: Accept both `website` and legacy `honeypot` for backward compatibility: if either is filled, treat as bot (or add spam score). Use `website` in new forms. |

**Summary A**: Implement on all four forms: required privacy_accepted checkbox, optional marketing_opt_in, hidden UTM (all 5) + referrer, honeypot field `website` (backend accept `website` or `honeypot`). Optionally add a single “Lead” form that POSTs to `/api/public/lead` and point Partnership/Talent to `/api/public/partnership` and `/api/public/talent`.

---

## B) Backend enforcement

| Requirement | Current state | Gap / conflict |
|-------------|----------------|----------------|
| **Reject if privacy_accepted != true** | Contact and lead do **not** reject; they accept and store. Talent has `consent_accepted`; Partnership has `declaration_accepted` (different semantics). | **Gap**: Contact and lead must return 400 (or 422) with a clear message when `privacy_accepted` is not true. For Talent/Partnership, either add an explicit `privacy_accepted` field and enforce it, or map declaration_accepted/consent_accepted to “privacy accepted” and reject when false. **Safest**: Add explicit `privacy_accepted` to all four public payloads and reject when false. |
| **Sanitize text fields; never store raw HTML** | `submission_utils.sanitize_html()` strips tags and script-like content. Used for contact message/subject, talent free text, partnership additional_notes, lead message_summary. | **Done**. Ensure all user-editable text fields pass through sanitize_html before storage. |
| **Hard limits: name≤120, org≤160, email≤254, phone≤30, subject≤180, message≤2000** | Current: `MAX_NAME_LENGTH=200`, `MAX_SUBJECT_LENGTH=500`, `MAX_PHONE_LENGTH=50`, `MAX_MESSAGE_LENGTH=2000`. | **Conflict**: Tighter limits requested. **Recommendation**: Introduce enterprise constants (e.g. in `submission_utils`): name=120, org=160, phone=30, subject=180, message=2000, email=254. Apply in Pydantic and sanitize; existing docs may have longer content—truncate on write, do not reject. |
| **Dedupe: same (type + normalized email) within 24h → do not create; update existing: last_activity_at=now, audit "duplicate_ping"** | Current dedupe: `dedupe_key = sha256(type + email + phone + message_80 + day)`; if exists in 24h, return existing id **without** updating the record. | **Conflict**: Task wants dedupe by **(type + email)** only, and **update** existing doc (last_activity_at, audit "duplicate_ping") instead of only returning. **Recommendation**: Add a 24h lookup by (type, normalized_email). If found: update that doc with `last_activity_at=now` and push audit `{ action: "duplicate_ping", at, by: "system" }`, return existing id. If not found: create as today. Keeps one record per (type, email) per 24h and surfaces repeat pings in audit. |
| **Spam scoring: +50 honeypot, +20 urls>3, +20 script; if spam_score≥50 → status=spam** | Current: honeypot filled → generic success, no record (or no store). No spam_score field; no URL count or script-in-message scoring. | **Gap**: Implement spam scoring: (1) Compute spam_score (0 + 50 if honeypot, +20 if URL count in message > 3, +20 if message contains `<script` etc.). (2) Store spam_score on document. (3) If spam_score >= 50 set status to SPAM (or "spam" per task). Still store the submission (for audit) unless policy is to drop entirely—**safest**: store with status=SPAM so admins can review. |

**Summary B**: Enforce privacy_accepted on all four; apply new field limits (120/160/30/180/2000/254); change dedupe to (type + email) within 24h with update + duplicate_ping; add spam_score and set status=spam when ≥50.

---

## C) Admin UI completion

| Requirement | Current state | Gap / conflict |
|-------------|----------------|----------------|
| **Sidebar links → working pages: Leads, Talent Pool, Partnership Enquiries, Contact Enquiries** | All four exist and work: `/admin/leads`, `/admin/talent-pool`, `/admin/partnership-enquiries`, `/admin/inbox/enquiries`. | **Done**. |
| **Table list + filters + search** | Contact: list only, no filters/search in UI. Talent/Partnership: search + status filter. Leads: full filters. | **Gap**: Contact list page has no search/filter UI; add status filter and search (backend already supports via admin_submissions or contact endpoint). |
| **Detail: status dropdown (type-specific)** | Detail page uses one flat list of statuses for all types. | **Gap**: Restrict status options by type (e.g. contact: NEW, IN_PROGRESS, RESPONDED, CLOSED, SPAM; talent: NEW, REVIEWED, SHORTLISTED, ARCHIVED, SPAM). |
| **Detail: assignment dropdown (admin users)** | PATCH supports `assigned_to` only for type=lead. Detail page has no assignment UI. | **Gap**: Expose assignment on detail for types that support it (lead already in backend; optionally add assigned_to to contact/talent/partnership in backend). Need GET /api/admin/team/users or equivalent to populate assignee dropdown. |
| **Detail: notes thread, audit timeline, tags, copy email/phone, mark spam (confirm modal)** | Notes, audit, copy, mark spam with confirm exist. Tags: PATCH supports tags but detail page does not show or edit tags. | **Gap**: Add tags display and edit on detail (load from doc, PATCH on change). Confirm modal for mark spam is inline “Confirm? Yes/No”; can be replaced with a proper modal. |
| **CSV export for current filter selection** | Export exists at `GET /api/admin/submissions/export/csv?type=&status=&from_date=&to_date=`. List pages use type-specific endpoints (e.g. talent-pool/admin/list) with search + status; export does not take `q`. | **Gap**: Export should accept the same filters as the list (e.g. `q`, status, from_date, to_date) so “Export CSV” uses current filter selection. Add `q` to export endpoint and pass current list params from each list page to the export URL. |

**Summary C**: Add contact list search/filter; type-specific status dropdown and tags UI on detail; assignment dropdown (and backend for contact/talent/partnership if desired); export with same params as list (including `q`).

---

## D) Internal notifications (safe)

| Requirement | Current state | Gap / conflict |
|-------------|----------------|----------------|
| **If ADMIN_NOTIFY_EMAIL set: send internal notification on new submission (status=new) only** | Not implemented. Docs note “ADMIN_NOTIFY_EMAIL: Not implemented”. | **Gap**: After creating a submission with status=new (or NEW), if `ADMIN_NOTIFY_EMAIL` is set, send one internal email (e.g. “New [type] submission: id”). |
| **Do not send emails to submitter in this phase** | Partnership ack is gated by `PARTNERSHIP_SEND_ACK_EMAIL` (default off). No other auto-email to submitter. | **Done**. |
| **Log mail failures; do not block submission creation** | N/A yet. | **Requirement**: Send notification asynchronously or in a try/except; on failure log and continue; do not roll back or fail the request. |

**Summary D**: Add optional internal notification on new submission when ADMIN_NOTIFY_EMAIL is set; log failures and do not block creation.

---

## E) Documentation + tests

| Requirement | Current state | Gap / conflict |
|-------------|----------------|----------------|
| **docs/SUBMISSIONS_PIPELINE.md: field definitions, status pipelines per type, dedupe/spam rules, security** | `docs/SUBMISSIONS_PIPELINE.md` exists with overview, statuses, fields, security, indexes. | **Gap**: Update doc to reflect: (1) New field limits (120/160/30/180/2000/254). (2) Dedupe rule: (type + email) within 24h, update with last_activity_at and duplicate_ping. (3) Spam scoring (honeypot + URLs + script) and status=spam when ≥50. (4) privacy_accepted required; honeypot field `website`. |
| **Tests: privacy_accepted required** | Not tested. | **Gap**: Add test that POST without privacy_accepted=true returns 400/422. |
| **Tests: dedupe update behavior** | Tests cover dedupe_key and rate limit; no test for “second request updates existing with duplicate_ping”. | **Gap**: Add test: two identical (type+email) submissions within 24h; second returns 200 with same id and existing doc has last_activity_at updated and audit entry duplicate_ping. |
| **Tests: spam honeypot behavior** | `test_submissions_pipeline.py` has `is_honeypot_filled`. No test that submission with honeypot gets status=spam or is rejected/stored as spam. | **Gap**: Add test: submit with honeypot filled → either no record or record with status=SPAM and spam_score≥50. |
| **Tests: RBAC** | List/get/export without auth return 401. | **Done**. |

**Summary E**: Update SUBMISSIONS_PIPELINE.md with new rules and fields; add tests for privacy_accepted, dedupe-update, and spam/honeypot.

---

## Conflicts and recommended resolution

| Conflict | Recommendation |
|----------|-----------------|
| **Honeypot field name: task says `website`, code uses `honeypot`** | Support both: backend checks `website` first, then `honeypot`; if either non-empty, apply spam or reject. New forms use `website`; existing integrations keep working. |
| **Dedupe: current (type+email+phone+message+day) vs task (type+email) with update** | **Adopt task**: 24h window by (type, normalized_email) only; on duplicate do not create, update existing with last_activity_at and audit "duplicate_ping", return existing id. Optionally keep dedupe_key for analytics but dedupe logic by email. |
| **Field limits: current 200/500/50 vs task 120/180/30** | **Adopt task limits** in submission_utils and Pydantic; truncate or validate so existing data is not invalidated. |
| **Spam: current “honeypot → no store” vs task “spam_score and store with status=spam”** | **Adopt task**: Compute spam_score; store all submissions; set status=spam when spam_score≥50. Allows audit and review. |
| **privacy_accepted: current optional vs task required** | **Adopt task**: Reject (400/422) when privacy_accepted is not true for contact and lead; add and enforce for talent and partnership. |

---

## Implementation order (recommended, no duplication)

1. **Backend constants and validation**  
   In `submission_utils`: add ENTERPRISE_MAX_NAME=120, ENTERPRISE_MAX_ORG=160, ENTERPRISE_MAX_PHONE=30, ENTERPRISE_MAX_SUBJECT=180; keep message=2000, email=254. Use in Pydantic and sanitize.

2. **Backend: privacy_accepted**  
   For contact and lead: require `privacy_accepted is True`; return 422 with clear message otherwise. For talent and partnership: add `privacy_accepted` to request models and require True (keep declaration_accepted/consent_accepted for their own meaning).

3. **Backend: honeypot field**  
   Accept `website` (and keep `honeypot`). If either filled → apply +50 spam or treat as bot; prefer storing with status=SPAM and spam_score=50.

4. **Backend: spam scoring**  
   Add `compute_spam_score(message, honeypot_filled)` (+50 honeypot, +20 URLs>3, +20 script); set status to SPAM when score≥50; store spam_score on doc.

5. **Backend: dedupe by (type + email)**  
   For contact, talent, partnership: 24h lookup by normalized email (and type). If found: update last_activity_at, push audit "duplicate_ping", return existing id. If not: create as now. Lead remains with LeadService.find_duplicate unless product wants same behavior.

6. **Frontend: all four forms**  
   Add to Contact, Partnership, Talent: required privacy_accepted checkbox, optional marketing_opt_in, hidden UTM (all 5) + referrer, hidden honeypot `website`. Optionally add one Lead form (e.g. “Request demo”) posting to `/api/public/lead` with same fields.

7. **Frontend: Partnership/Talent POST to /api/public/***  
   Optional: change PartnershipEnquiryForm and TalentPoolWizard to POST to `/api/public/partnership` and `/api/public/talent` so all submissions go through public API (backend already supports these routes).

8. **Admin: contact list filters + export with q**  
   Add status filter and search to Contact Enquiries page; ensure export URL includes current filters (status, q, from_date, to_date). Backend export: add query param `q` and apply same search as list.

9. **Admin: detail page**  
   Type-specific status dropdown; tags display and edit; assignment dropdown (with GET admin users) for lead and optionally others; confirm modal for mark spam.

10. **ADMIN_NOTIFY_EMAIL**  
    After insert (status=new), if env set, send internal email; catch and log errors, do not fail request.

11. **Docs and tests**  
    Update SUBMISSIONS_PIPELINE.md; add tests for privacy_accepted required, dedupe update, spam/honeypot, RBAC (already present).

---

## File reference (current implementation)

| Area | File |
|------|------|
| Contact form | `frontend/src/pages/public/ContactPage.js` |
| Partnership form | `frontend/src/pages/public/PartnershipEnquiryForm.js` |
| Talent form | `frontend/src/pages/public/TalentPoolWizard.js` |
| Public contact API | `backend/routes/public.py` (contact, lead, talent, partnership) |
| Submission utils | `backend/utils/submission_utils.py` |
| Talent submit | `backend/routes/talent_pool.py` |
| Partnership submit | `backend/routes/partnerships.py` |
| Admin submissions API | `backend/routes/admin_submissions.py` |
| Admin detail page | `frontend/src/pages/AdminSubmissionDetailPage.jsx` |
| Admin list pages | `AdminContactEnquiriesPage.jsx`, `AdminTalentPoolPage.jsx`, `AdminPartnershipEnquiriesPage.jsx`, `AdminLeadsPage.js` |
| Pipeline doc | `docs/SUBMISSIONS_PIPELINE.md` |
| Tests | `backend/tests/test_submissions_pipeline.py` |

---

## Summary table

| Category | Implemented | Missing / to change |
|----------|-------------|----------------------|
| **A Forms** | Contact uses /api/public/contact; backend has consent/utm/honeypot | All forms: privacy_accepted (required), marketing_opt_in, UTM×5, referrer, honeypot `website`; optional Lead form; optional switch Partnership/Talent to /api/public/* |
| **B Backend** | Sanitize, rate limit, dedupe (current key), honeypot reject | privacy_accepted required; new limits 120/160/30/180; dedupe by (type+email) + update; spam_score + status=spam |
| **C Admin** | Four pages, detail with notes/audit/copy/mark spam, export CSV | Contact filters/search; type-specific status; tags UI; assignment dropdown; export with `q` |
| **D Notify** | Partnership ack gated | ADMIN_NOTIFY_EMAIL on new submission; log failures, no block |
| **E Docs/tests** | SUBMISSIONS_PIPELINE.md, RBAC tests, sanitize/dedupe key tests | Doc update; tests: privacy_accepted, dedupe-update, spam/honeypot |

Implement in the order above to avoid duplication and keep behavior consistent with existing production code.
