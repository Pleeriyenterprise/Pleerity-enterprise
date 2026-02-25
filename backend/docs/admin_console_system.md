# Admin Console System – Implementation Audit vs Task Requirements

This document maps the current codebase to the task requirements for a **functional, permissioned, auditable Admin Console** synced with Marketing Site + App via a publish/version model. It identifies what is implemented, what is missing, and where requirements conflict with existing design—with recommended resolutions.

---

## 1. Data Models (Backend)

| Requirement | Current State | Gap / Conflict |
|-------------|---------------|-----------------|
| **leads** | **Implemented.** Collection `leads` with: source_platform, service_interest, name, email, phone, company_name, message_summary, utm_*, referrer_url, marketing_consent, status, stage, assigned_to, nurture_stage, tags[], admin_notes, created_at, updated_at, lead_id. | Task asks for `type` (lead/newsletter/checklist/demo). Current model uses **source_platform** (CONTACT_FORM, COMPLIANCE_CHECKLIST, WEB_CHAT, etc.) which is equivalent; no `page_path` field. **Recommendation:** Keep source_platform; add optional `page_path` if needed for attribution. Do **not** rename to `type` (would conflict with existing enums). |
| **enquiries_contact** | **Implemented as separate collection.** `contact_submissions` with submission_id, full_name, email, phone, subject, contact_reason, message, privacy_accepted, created_at, status, notes[], audit[]. | Task suggests optionally "unify with leads.type='contact'". **Recommendation:** Keep separate collections (contact_submissions, partnership_enquiries, talent_pool, leads). Unification would be a large, risky refactor; current unified **Admin Submissions** API already gives one list/export/notes surface. |
| **enquiries_partner** | **Implemented.** Collection `partnership_enquiries` with enquiry_id, status, notes, etc. | None. |
| **talent_pool** | **Implemented.** Collection `talent_pool` with submission_id, status, CV metadata, notes[], etc. | None. |
| **lead_notes** | **Partially implemented.** Task wants `lead_notes: {lead_id, author_user_id, note, created_at}`. Current: (1) **leads** have single field `admin_notes` (free text); (2) **Unified submissions** use `POST /api/admin/submissions/{composite_id}/notes` which **$push**es to a `notes` array on the document (`{ at, by, note }`). For type=lead, composite_id = `lead-{lead_id}`, so notes are stored on the **lead document** as `notes[]`, not in a separate `lead_notes` collection. | **Conflict:** Task asks for separate `lead_notes` table/collection. **Recommendation:** Keep current design (notes array on lead doc + same pattern for contact/talent/partnership). Adding a separate `lead_notes` collection would duplicate data and require migration; audit trail is satisfied by `notes[]` + `by`/`at`. If you need query-by-note later, add an index on `notes.by` or a separate collection then. |
| **site_pages** | **Implemented as `cms_pages`.** Has slug, title, blocks/sections, seo, status (draft/published), published_at, updated_at, page_id. No explicit `version:int` field; versioning is implicit via published_at/updated_at. | Task asks for `version:int`. **Recommendation:** Optional enhancement: add a `version` counter incremented on publish. Not required for cache busting if you use `published_at` or a separate `published_version` in the response. |
| **intake_schema_versions** | **Implemented.** `intake_schema_customizations` + `intake_schema_versions` (or equivalent versioning in admin_intake_schema). Draft vs live (field_overrides vs draft_overrides), publish flow exists. | Task asks for `schema_key`, `version`, `json_schema`, `ui_schema`, `status`, `published_at`. Current model is per-**service_code** (e.g. DOC_PACK_ESSENTIAL, CVP) with schema_version. **Recommendation:** Align naming (schema_key = service_code) in docs; ensure published_at is set on publish. |
| **analytics_events** | **Implemented.** Collection `analytics_events` with ts, event, lead_id, client_id, metadata, idempotency_key. Indexes on event+ts, client_id+ts, lead_id+ts. | Task asks for `event_name, user_id, lead_id, session_id, page, props, created_at`. Current uses `event` (not event_name), `ts` (not created_at), no top-level `page` (can be in metadata). **Recommendation:** No change required; add `page` to payload from public track if you add it. |
| **stripe_event_snapshots** | **Implemented as `stripe_events`.** Fields: event_id, type, created, processed_at, status, error, related_client_id, related_subscription_id, raw_minimal (safe extract). | Task asks for `payload` (full snapshot). Current stores **raw_minimal** only (id, type, created, object_id) to avoid storing PII/secrets. **Recommendation:** Do **not** store full payload by default (compliance/security). Keep raw_minimal; if reconciliation needs more, add optional payload store behind a feature flag and retention policy. |
| **audit_logs** | **Implemented.** Collection `audit_logs` with action, actor_role, actor_id, resource_type, resource_id, before_state, after_state, metadata (incl. diff), timestamp, ip_address. | Task asks for "module, action, actor, target_id, before, after". **Mapping:** resource_type ≈ module, action ≈ action, actor_id ≈ actor, resource_id ≈ target_id, before_state/after_state ≈ before/after. **Recommendation:** No structural change; document the mapping. Ensure all admin mutations call create_audit_log with before/after where applicable. |

---

## 2. Public Endpoints (Marketing Site)

| Requirement | Current State | Gap / Conflict |
|-------------|---------------|-----------------|
| **POST /api/public/leads** (type=lead/newsletter/checklist/demo) | **Partially implemented.** `POST /api/public/lead` (singular) exists; creates lead with source_platform=CONTACT_FORM only. Checklist leads use a different flow (e.g. `/api/leads/capture/checklist`). No single endpoint with `type` enum. | **Gap:** Single public lead endpoint with explicit `type` (lead | newsletter | checklist | demo) and dedupe by email+type within 24h. **Recommendation:** Add optional `type` (or `source`) to existing `POST /api/public/lead` body; map to source_platform. Implement 24h dedupe by email + source_platform (already have dedupe by email in LeadService.create_lead; tighten to 24h window if required). |
| **POST /api/public/contact** | **Implemented.** Rate-limited, dedupe by (type+email) 24h, consent/privacy, stores in contact_submissions. | None. |
| **POST /api/public/partnership** | **Implemented.** Wrapper in public.py delegates to partnerships route; stores in partnership_enquiries. | None. |
| **POST /api/public/talent** | **Implemented.** Wrapper delegates to talent_pool; stores in talent_pool. | None. |

**Dedupe:** Contact, talent, partnership already use 24h dedupe with "duplicate_ping" update. Leads use LeadService.find_duplicate (email/phone/source_metadata) without a 24h window; add time-bound dedupe if product requires it.

---

## 3. Admin Endpoints (Leads & Submissions)

| Requirement | Current State | Gap / Conflict |
|-------------|---------------|-----------------|
| **GET /api/admin/leads?type=&status=&q=&date_from=&date_to=&assigned_to=** | **Implemented.** GET /api/admin/leads with source_platform, service_interest, stage, intent_score, status, assigned_to, search, sla_breach_only, page, limit. | Task asks for type (map to source_platform) and date_from/date_to. **Gap:** date_from/date_to may need to be added if not already (leads list uses created_at; confirm filter exists). |
| **GET /api/admin/leads/{id}** | **Implemented.** Returns lead + audit log + contacts. | None. |
| **PATCH /api/admin/leads/{id}** (status/tags/assigned_to) | **Implemented as PUT** /api/admin/leads/{id} with stage, admin_notes, etc. Assign is separate POST .../assign. Tags supported on lead. | Minor: task says PATCH; PUT is acceptable. Ensure status (e.g. CONVERTED, LOST) is updatable via stage/status field. |
| **POST /api/admin/leads/{id}/notes** | **Implemented via unified submissions.** POST /api/admin/submissions/lead-{id}/notes (body: note). Pushes to lead's `notes[]`. Leads route does not have a dedicated POST .../notes. | **Recommendation:** Keep using unified submissions for notes, or add POST /api/admin/leads/{id}/notes that pushes to the same `notes` array for consistency with leads UX. |
| **GET /api/admin/leads/export.csv** | **Implemented elsewhere.** GET /api/admin/submissions/export/csv?type=lead&... returns CSV for leads (and contact/talent/partnership). | Task path is /api/admin/leads/export.csv. **Recommendation:** Either add a redirect/alias from /api/admin/leads/export (or export.csv) to submissions export with type=lead, or document that export is under /api/admin/submissions/export/csv?type=lead. |

---

## 4. Site Builder Publish Model

| Requirement | Current State | Gap / Conflict |
|-------------|---------------|-----------------|
| **GET /api/public/pages/{slug}** (latest PUBLISHED) | **Implemented** at **GET /public/cms/pages/{slug}** (prefix is /public/cms). Returns only published page via cms_service.get_published_page(slug). | **Path mismatch:** Task says /api/public/pages/{slug}; current is /public/cms/pages/{slug}. **Recommendation:** If marketing site expects /api/public/pages/{slug}, add a thin route that delegates to get_published_page, or configure frontend to use /public/cms/pages/{slug}. Prefer one canonical URL and document it. |
| **GET /api/admin/pages** (draft + published list) | **Implemented.** Admin CMS routes list pages (draft and published). | Naming: task says "pages"; current is CMS/site-builder. No conflict. |
| **PUT /api/admin/pages/{slug}/draft** | **Implemented.** CMS service has draft updates; publish flow exists. | Confirm route path (admin is under /api/admin/cms). |
| **POST /api/admin/pages/{slug}/publish** | **Implemented.** cms_service.publish_page; sets published_at, status. | Optional: increment a `version` integer on publish for cache busting. |

---

## 5. Intake Schema Publish Model

| Requirement | Current State | Gap / Conflict |
|-------------|---------------|-----------------|
| **GET /api/public/intake-schema/{schema_key}** (latest PUBLISHED) | **Gap.** No public read-only endpoint that returns the **published** intake schema for a given service/schema_key. Intake wizard likely gets schema from another path (e.g. embedded in app or admin-only schema endpoint). | **Recommendation:** Add GET /api/public/intake-schema/{schema_key} (or /api/intake/schema/{schema_key}) that returns only published/live schema for use by marketing intake form. Admin continues to use draft + preview. |
| **PUT/POST draft and publish** | **Implemented.** Admin intake schema: save draft, publish; versioning and draft_overrides exist. | None. |
| **schema_version on each intake submission** | **Gap.** Intake submit (POST /api/intake/submit) does not explicitly accept or store a `schema_version` (or intake_schema_version) on the submitted payload. Draft service uses intake_schema_version internally. | **Recommendation:** Add optional `schema_version` (or intake_schema_version) to intake submit request; persist it on the client/intake_submission/order record so you know which schema version the user saw. |

---

## 6. Analytics & CFO Dashboard

| Requirement | Current State | Gap / Conflict |
|-------------|---------------|-----------------|
| **POST /api/public/track** (records analytics_events) | **Gap.** No public track endpoint. Analytics events are written server-side only (log_event from intake, auth, Stripe, etc.). | **Recommendation:** Add POST /api/public/track (rate-limited, sanitized) accepting event_name, page, session_id, props; write to analytics_events. Use for client-side page views / CTA clicks. |
| **GET /api/admin/analytics/overview** | **Implemented.** Conversion overview: KPIs (leads, intake_submitted, payment_succeeded, first_doc_uploaded), conversion_rates, median times, leads_by_source, failures. | None. |
| **GET /api/admin/analytics/revenue** | **Implemented.** Revenue KPIs, subscriber breakdown, time series, payment health (failed, refunds). Uses payments + client_billing. | None. |
| **Stripe as source of truth; store snapshots; compute KPIs** | **Implemented.** stripe_events stored (id, type, status, processed_at, raw_minimal); payments collection normalized from Stripe; revenue/executive-overview use payments + client_billing. | See stripe_event_snapshots above (no full payload by default). |

---

## 7. RBAC & Safety

| Requirement | Current State | Gap / Conflict |
|-------------|---------------|-----------------|
| **Roles: OWNER, ADMIN, SUPPORT, CONTENT** | **Partially implemented.** Current roles: ROLE_OWNER, ROLE_ADMIN, ROLE_CLIENT_ADMIN, ROLE_CLIENT, ROLE_TENANT. **No ROLE_SUPPORT or ROLE_CONTENT.** | **Conflict:** Task requires four staff roles (OWNER, ADMIN, SUPPORT, CONTENT) with different module access. **Recommendation:** Introduce ROLE_SUPPORT and ROLE_CONTENT (or map CONTENT to a permission set). Gate routes and nav by role: e.g. Support can access Support Dashboard + Notification Health; Content can access Site Builder, Blog, FAQ, Legal; Admin/Owner see all. Implement in middleware or route dependencies and hide nav items in frontend by role. |
| **Gate routes + nav by role** | **Partially implemented.** admin_route_guard and require_owner_or_admin used; no role-specific visibility. | Add role checks so Support cannot access Billing, Content cannot access Audit Logs, etc. |
| **All admin mutations → audit_log with before/after** | **Partially implemented.** create_audit_log supports before_state/after_state; not every admin mutation may pass them. | Audit lead/submission updates, CMS publish, intake schema publish, and other critical mutations with before/after. |
| **Rate limiting public forms** | **Implemented.** Contact, lead, talent, partnership use check_rate_limit. | None. |
| **Sanitize user content (XSS)** | **Partially implemented.** Lead message sanitized (sanitize_html) in some flows. | Ensure all user-provided content (notes, messages, CMS blocks if rendered from DB) is sanitized before render in admin UI. |

---

## 8. Real-Time Updates / Cache Busting

| Requirement | Current State | Gap / Conflict |
|-------------|---------------|-----------------|
| **Marketing site fetches published pages + schema on load** | **Implemented** for pages (get_published_page). Schema: no public published endpoint yet. | Add public intake schema endpoint (see above). |
| **Short TTL or published_version for cache busting** | **Partial.** CMS can add Cache-Control or a version query param. | **Recommendation:** When admin publishes, either invalidate cache (if using Vercel/Render invalidation API) or add a `published_version` (or published_at) in the API response and have the frontend use it in the fetch URL (e.g. ?v=123) so cache busts. |

---

## 9. Frontend (Admin) – Summary

- **Lead Management:** Table with filters, detail panel, notes, status, assignment, export exists (Leads page + unified submissions). Consent, source, UTM shown where stored.
- **Content Management:** Site Builder, Blog, FAQ, Legal, Canned Responses, etc. exist in nav and routes. Draft/preview/publish exists for CMS.
- **Pricing & Billing:** Billing and Pending Payments exist. Task says "Pending payments as sub-tab under Billing"; currently separate nav item. **Recommendation:** Optionally move Pending Payments under Billing as a tab for cleaner nav.
- **Support Dashboard:** CRN lookup, client, onboarding status, notifications; Notification Health available. Align with Support role access.

---

## 10. Checklist Nurture (5 Emails)

**Implemented.** lead_nurture_service: 5-email sequence for COMPLIANCE_CHECKLIST (days 0, 2, 4, 6, 9); consent required; tags (checklist_download, checklist_nurture_v1) set. No change required for core requirement.

---

## 11. Deliverables Checklist (High Level)

| Item | Status |
|------|--------|
| Backend models (leads, contact, partner, talent, notes, site_pages/cms_pages, intake_schema versions, analytics_events, stripe_events, audit_logs) | Done (with notes above) |
| Public endpoints (leads, contact, partnership, talent) | Done; leads endpoint needs type/source and optional 24h dedupe |
| Admin endpoints (list/get/patch/notes/export for leads) | Done (export via submissions; notes via submissions or add under leads) |
| Site Builder draft → publish | Done |
| Intake Schema draft → publish | Done |
| Public published page GET | Done (path /public/cms/pages/{slug}) |
| Public published intake schema GET | **Missing** |
| schema_version on intake submission | **Missing** |
| POST /api/public/track | **Missing** |
| Analytics overview + revenue | Done |
| RBAC (OWNER, ADMIN, SUPPORT, CONTENT) | **Partial** (SUPPORT, CONTENT not defined; gating by role not done) |
| Audit before/after on all admin mutations | Partial (ensure coverage) |
| Rate limiting + sanitization | Done / partial |
| README admin_console_system.md | This document |

---

## 12. Conflicting Instructions – Recommended Resolutions

1. **Unified vs separate collections (contact/partner/talent/leads):** Keep separate collections; keep unified Admin Submissions API. Do not merge into a single leads table with type.
2. **lead_notes table vs notes array:** Keep notes array on each submission type (including leads); do not add a separate lead_notes collection unless you need cross-lead note search later.
3. **Stripe full payload:** Do not store full Stripe payload by default; keep raw_minimal. Add optional payload only with retention and access control.
4. **Public pages URL:** Prefer one canonical URL; either document /public/cms/pages/{slug} or add alias /api/public/pages/{slug}.
5. **RBAC:** Add SUPPORT and CONTENT roles and gate routes/nav by role rather than broadening access.

---

## 13. Data Flows (Summary)

- **Marketing → Admin:** Contact form → POST /api/public/contact → contact_submissions. Lead form → POST /api/public/lead → leads. Partnership → POST /api/public/partnership → partnership_enquiries. Talent → POST /api/public/talent → talent_pool. All are rate-limited and deduped; consent captured where required.
- **Admin → Marketing (content):** Admin edits in CMS (draft) → Publish → cms_pages.status = published, published_at set. Marketing site GET /public/cms/pages/{slug} returns only published. Intake schema: admin edits draft → Publish → live customizations; marketing intake should read via a dedicated public published-schema endpoint (to be added).
- **Analytics:** Server-side events (intake_submitted, payment_succeeded, etc.) → analytics_events. Optional: POST /api/public/track for client-side events. CFO dashboard reads analytics_events, payments, client_billing.

---

## 14. Publish Model (Summary)

- **Site Builder:** Edits are draft until "Publish". Publish sets status=published, published_at, and optionally version++. Public endpoint returns only published. Portal/App uses same published endpoint.
- **Intake Schema:** Edits stored as draft_overrides; Publish copies to live field_overrides and sets published_at/version. Marketing intake form must call a **published-only** schema endpoint so schema changes do not affect in-flight users until published.

---

*Document generated from codebase audit. Implement changes in small, reviewable steps; prefer extending existing patterns over introducing new ones.*
