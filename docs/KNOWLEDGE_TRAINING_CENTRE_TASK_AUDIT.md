# Knowledge & Training Centre – Task vs Codebase Audit

**Document:** Analysis only. No code or assets were modified.

**Purpose:** Identify what is implemented, what is missing, and any conflicts so implementation can proceed without duplication or conflict. Do not implement blindly.

**Source:** User task (Sections 1–16): two knowledge portals (Admin Knowledge Centre + User Help Centre), `knowledge_articles` model, categories, admin UI, article editor, versioning, PDF export, user help centre, visibility rules, search, release notes, product linking, permissions, status, future AI support.

---

## 1. Executive Summary

| Area | Implemented | Missing / Partial | Conflict / Decision |
|------|-------------|-------------------|----------------------|
| **Two portals** | Single public KB + admin management | Admin Knowledge Centre (internal-only) vs User Help Centre (user-facing) as distinct experiences | Naming: codebase uses "Knowledge Base"; task uses "Knowledge Centre". Recommend UI label "Knowledge Centre" / "Help Centre"; keep API/DB names for compatibility. |
| **Database model** | `kb_articles`, `kb_categories`, `kb_search_analytics` | Task field set (audience, version, summary, release notes type, etc.) | Collection name: task says `knowledge_articles`; codebase uses `kb_articles`. Recommend keep `kb_articles`, add new fields. |
| **Categories** | Single set of user-oriented defaults | Split ADMIN vs USER default categories per task | Add audience/scoped categories and seed task’s lists. |
| **Admin UI** | Article list, create/edit, publish/delete, Categories + Analytics tabs | Audience & Version columns, Archive action, Export PDF | Add columns and actions; add "Archive" (status) distinct from unpublish/deactivate. |
| **Article editor** | Markdown textarea | Rich editor (headings, lists, images, code, links, screenshots); tagging (modules, feature flags, roles) | Enhance editor and tagging; optional phase. |
| **Version control** | None | version field, "Last Updated" / "Version" display | Add version field and optional history. |
| **PDF export** | None for KB | "Download Training Guide" with branding, page numbers | New feature; reuse reportlab pattern from reporting/template_renderer. |
| **User Help Centre** | /help links to public /support/knowledge-base | In-app Help Centre filtered by USER audience, search, categories | New client-side Help Centre + authenticated API filtered by audience. |
| **Visibility** | All published articles visible on public KB | Audience ADMIN | STAFF | USER controlling where articles appear | Add audience field; filter admin list and user help by audience. |
| **Search** | Regex on title, excerpt, content, tags | "Most relevant first" | Add relevance (e.g. text score or simple ranking). |
| **Release notes** | None | Special type: version, release_date, changes, affected_modules | New article type or dedicated structure. |
| **Product linking** | None | "Need help? See: [Article]" on product pages | Add links from key product pages to help articles. |
| **Permissions** | Admin-only write; public read (unauthenticated) | Staff read internal; users read user-only; admins full CRUD | Add audience-based read + optional staff role. |
| **Status** | draft, published, archived (enum); soft delete (is_active) | Draft not shown to users; Archive action | Clarify archived vs deactivated; ensure draft never shown to end users. |
| **Future AI** | None | Schema ready for AI suggestions/drafts/outdated flagging | Add optional fields (e.g. last_reviewed_at, ai_suggestions) without breaking schema. |

---

## 2. Current Implementation (What Exists)

### 2.1 Backend

| Location | What exists |
|----------|-------------|
| **Routes** | `backend/routes/knowledge_base.py` |
| **Collections** | `kb_articles`, `kb_categories`, `kb_search_analytics` (no `knowledge_articles`) |
| **Article document** | `article_id`, `title`, `slug`, `category_id`, `excerpt`, `content`, `tags`, `status` (draft/published/archived), `meta_title`, `meta_description`, `view_count`, `is_active`, `created_at`, `created_by`, `updated_at`, `updated_by`, `published_at`; on unpublish: `unpublished_at`, `unpublished_by`; on delete: `deactivated_at`, `deactivated_by`. |
| **Categories** | `category_id`, `name`, `icon`, `description`, `order`, `is_active`, `article_count`, `created_at`, `created_by`. |
| **Default categories** | Single set: Getting Started, Billing & Subscriptions, Account & Login, Compliance Vault Pro, Documents & Uploads, Orders & Delivery, Reports & Calendar, Integrations, Troubleshooting. (All user-oriented; no admin-only sections.) |
| **Public API** | `GET /api/kb/articles` (category, tag, search), `GET /api/kb/articles/{slug}`, `GET /api/kb/categories`, `GET /api/kb/featured`, `GET /api/kb/tags/popular`. No authentication; returns all published articles. |
| **Admin API** | `GET/POST /api/admin/kb/articles`, `GET/PUT /api/admin/kb/articles/{id}`, `POST publish`, `POST unpublish`, `DELETE` (soft deactivate), `GET/POST/PUT/DELETE` categories, `GET /api/admin/kb/analytics`. Protected by `admin_route_guard`. |
| **Search** | Regex on `title`, `excerpt`, `content`, `tags`; sort by `order` and `published_at`. No relevance ranking. |
| **Audit** | `log_kb_action` writes to `audit_logs` (KB_ARTICLE_CREATED, UPDATED, PUBLISHED, UNPUBLISHED, DEACTIVATED). |

**Not present:** `audience`, `version`, `summary` (only `excerpt`), `related_feature_flags`, `downloadable_pdf_url`, `related_articles` (stored; API derives related from same category), `product_module`. No PDF export for articles. No release-notes-specific type or fields.

### 2.2 Frontend

| Location | What exists |
|----------|-------------|
| **Admin** | `AdminKnowledgeBasePage.js` at `/admin/knowledge-base`. Menu: "Knowledge Base" in sidebar (`UnifiedAdminLayout.js`). Article list with filters (search, status, category), Create/Edit (modal or form), Publish, Delete; Categories tab; Analytics tab. Editor: textarea (markdown). No Audience or Version columns; no Archive; no Export PDF. |
| **Public KB** | `PublicKnowledgeBasePage.js` at `/support/knowledge-base` (and `:slug`). Used for unauthenticated public; shows all published articles. Search, browse by category, article view, related articles. |
| **Client Help** | `HelpPage.js` at `/help` (client portal). Links: Email support, "Knowledge base" → `/support/knowledge-base` (same window or external). No in-app list of USER-only articles; no search within client app. |

**Routes (App.js):**  
- `/support/knowledge-base` and `/support/knowledge-base/:slug` → Public KB.  
- `/help` → Client portal Help page (links out to KB).  
- `/admin/knowledge-base` → Admin KB management (admin-only).

### 2.3 PDF and exports elsewhere

- **Reporting:** `reporting.py` uses reportlab for PDF/CSV/Excel.  
- **Compliance pack:** `client.py` / `tenant.py` + `compliance_pack_service` generate PDF.  
- **Documents:** `template_renderer.py`, `document_generator.py` generate DOCX/PDF.  
- **KB:** No PDF export for articles; no "Download Training Guide" button or endpoint.

### 2.4 Scripts

- `export_cms_to_kb.py`: Exports **CMS pages** to `docs/assistant_kb` as markdown for the Pleerity Assistant. Not related to KB article PDF export or knowledge_articles.

---

## 3. Gap Analysis (Task vs Codebase)

### 3.1 Section 1 – Knowledge Centre structure

| Requirement | Status | Notes |
|-------------|--------|--------|
| **Admin Knowledge Centre** (staff training, playbooks, admin guides, release notes, troubleshooting, system architecture) | **Missing** | Current admin KB has no audience separation; all articles are in one pool. Need audience `ADMIN` (and optionally `STAFF`) and categories/scoping so this is clearly "internal only". |
| **User Help Centre** (getting started, properties, certificates, compliance score, reminders, dashboard, billing, troubleshooting) | **Partial** | Public KB + /help link exist but (1) not scoped to USER audience, (2) not in-dashboard "Help Centre" with categories/search for logged-in users only. |

**Recommendation:** Implement two entry points: (1) Admin Knowledge Centre = current admin KB enhanced with audience/categories and internal-only visibility; (2) User Help Centre = new in-app experience under client menu "Help Centre" showing only USER-audience articles via authenticated API.

### 3.2 Section 2 – Database model

| Task field | In codebase | Action |
|------------|-------------|--------|
| id | article_id | Keep article_id (or add id as alias). |
| title | ✅ title | — |
| slug | ✅ slug | — |
| audience (ADMIN \| STAFF \| USER) | ❌ | Add. |
| category | ✅ category_id | — |
| tags | ✅ tags | — |
| content | ✅ content | — |
| summary | excerpt only | Add summary or treat excerpt as summary; align naming. |
| status (draft \| published \| archived) | ✅ status (draft, published, archived) | Ensure "archived" is used and distinct from soft delete. |
| version | ❌ | Add. |
| related_feature_flags | ❌ | Add (optional). |
| created_by, updated_by, created_at, updated_at | ✅ | — |
| downloadable_pdf_url | ❌ | Add (optional) or generate on demand. |
| related_articles | Derived at read time | Optional stored field for curation. |
| product_module | ❌ | Add (optional). |

**Collection name:** Task says `knowledge_articles`; codebase uses `kb_articles`. **Recommendation:** Keep `kb_articles` and add new fields to avoid breaking existing data and API consumers. Document mapping in this audit.

### 3.3 Section 3 – Categories

| Task – ADMIN categories | In codebase |
|------------------------|-------------|
| Staff Training, Operations Playbooks, Admin Console, Provisioning, Compliance Engine, Job Monitoring, Feature Flags, Support Procedures | ❌ Not as separate admin set |

| Task – USER categories | In codebase |
|-------------------------|-------------|
| Getting Started, Adding Properties, Uploading Evidence, Compliance Score, Dashboard Guide, Reminders, Compliance Packs, Billing | Partially (Getting Started, Billing, etc. exist but not exact list; no "Adding Properties", "Uploading Evidence", "Compliance Score", etc.) |

**Recommendation:** Add an `audience` or `scope` on categories (e.g. ADMIN vs USER) and seed two default sets per task; keep existing categories as USER where they match, add missing USER and all ADMIN categories.

### 3.4 Section 4 – Admin Knowledge Centre UI

| Requirement | Status |
|-------------|--------|
| Menu: Admin Dashboard → Knowledge Centre | ✅ Under "Knowledge Base" at `/admin/knowledge-base`. Recommend renaming to "Knowledge Centre" in UI. |
| Article list: Title, Category, Audience, Status, Last Updated, Version | Title, Category, Status present. **Missing:** Audience, Version, Last Updated (can use updated_at). |
| Actions: Create, Edit, Publish, Archive, Delete, Export PDF | Create, Edit, Publish, Delete present. **Missing:** Archive (set status to archived), Export PDF. Unpublish exists but is not Archive. |

### 3.5 Section 5 – Article editor

| Requirement | Status |
|-------------|--------|
| Rich editor: headings, lists, images, step-by-step, code blocks, internal links, screenshots | Current: single markdown textarea. **Missing:** rich editor (or enhanced markdown with uploads). |
| Tagging: product modules, feature flags, roles | Tags exist as list; no structured tagging for modules/flags/roles. **Missing:** structured tags or tag types. |

### 3.6 Section 6 – Version control

| Requirement | Status |
|-------------|--------|
| Track versions (e.g. 1.0, 1.1, 2.0) | **Missing:** no version field. |
| Display "Last Updated", "Version" | updated_at exists; **Missing:** version field and display in UI. |

### 3.7 Section 7 – Downloadable training manuals (PDF)

| Requirement | Status |
|-------------|--------|
| Export article as PDF | **Missing.** |
| Button "Download Training Guide" | **Missing.** |
| PDF: Title, Version, Last Updated, Content, page numbers, Pleerity branding | **Missing.** Reuse reportlab approach from reporting/compliance_pack/template_renderer. |

### 3.8 Section 8 – User Help Centre

| Requirement | Status |
|-------------|--------|
| User dashboard menu: "Help Centre" | **Partial:** "Help" exists and links to public KB; not "Help Centre" with in-app articles. |
| Article categories, search | Public KB has categories and search; not scoped to logged-in user or USER audience. |
| Example titles (e.g. "How to Add a Property", "How to Upload a Gas Safety Certificate") | **Missing:** no seeded USER articles with these titles; can be content-only. |

**Recommendation:** Add client route e.g. `/app/help` or keep `/help` and replace current Help page with a full Help Centre: categories, search, list/detail of USER-audience articles via authenticated API. Optionally keep "Email support" and "Knowledge base" link for backward compatibility.

### 3.9 Section 9 – Article visibility rules

| Rule | Status |
|------|--------|
| ADMIN → only in admin knowledge centre | **Missing:** no audience field; admin list shows all. |
| STAFF → visible to staff roles | **Missing.** |
| USER → visible in help centre | **Missing:** public KB shows all published. |

**Recommendation:** Add `audience` (ADMIN | STAFF | USER). Admin list: show all, filterable by audience. Public/list-for-users: only USER (and optionally STAFF for logged-in staff). Admin-only API for internal articles (ADMIN/STAFF).

### 3.10 Section 10 – Search

| Requirement | Status |
|-------------|--------|
| Search across title, summary, tags, content | **Partial:** title, excerpt, content, tags. |
| Most relevant first | **Missing:** current sort is order + published_at; no relevance scoring. |

**Recommendation:** Add simple relevance (e.g. MongoDB text index + text score, or match count in application layer) and sort by relevance when a query is present.

### 3.11 Section 11 – Release notes

| Requirement | Status |
|-------------|--------|
| Special article type: Release Notes | **Missing.** |
| Fields: version, release_date, changes, affected_modules | **Missing.** |

**Recommendation:** Either (a) add article type `article_type: "release_notes"` and fields `release_version`, `release_date`, `changes` (list), `affected_modules` (list), or (b) separate collection for release notes. (a) keeps one content model and allows listing "release notes" in admin and user views.

### 3.12 Section 12 – Linking documentation to product

| Requirement | Status |
|-------------|--------|
| Product pages link to help articles (e.g. Evidence Upload → "Need help? See: Uploading Certificates Guide") | **Missing.** |

**Recommendation:** Add optional `help_article_slug` or `help_article_id` (or a small "product_help_links" config) and render a "Need help? See: …" link on key pages (Evidence Upload, Dashboard, Compliance Score, etc.).

### 3.13 Section 13 – Admin permissions

| Requirement | Status |
|-------------|--------|
| Only admins create/edit/publish/archive | **Partial:** admin_route_guard protects admin KB; no distinction between "admin" and "staff" for write. |
| Staff may read internal articles but not edit unless permitted | **Missing:** no staff role or read-only internal access. |
| Users can only read user articles | **Missing:** public KB is unauthenticated and shows all published. |

**Recommendation:** Keep admin-only write. For read: (1) Admin API returns all articles (for admin Knowledge Centre). (2) New client endpoint e.g. `GET /api/client/help/articles` (or reuse `/api/kb/articles` with auth + audience filter) returns only USER (and optionally STAFF for staff users). (3) Do not expose ADMIN/STAFF articles on public or client routes.

### 3.14 Section 14 – Article status

| Requirement | Status |
|-------------|--------|
| Draft, Published, Archived | ✅ Enum has all three. |
| Draft not shown to users | ✅ Public list filters by status published; ensure archived is either hidden or shown as "archived" in admin only. |

**Conflict/clarification:** Codebase has soft delete (`is_active`). Task has "Archive" as status. **Recommendation:** Treat "archived" as status (article still visible in admin, not shown in public/user help). Keep soft delete (is_active) for permanent hide; "Archive" = set status to archived, not deactivate.

### 3.15 Section 15 – Future AI support

| Requirement | Status |
|-------------|--------|
| Schema ready for AI to suggest updates, generate drafts, flag outdated | **Missing.** No reserved fields. |

**Recommendation:** Add optional fields later without breaking schema, e.g. `last_reviewed_at`, `ai_suggested_changes`, `outdated_flagged_at`. Omit from required validation.

### 3.16 Section 16 – Acceptance criteria (summary)

| Criterion | Status |
|-----------|--------|
| Creating documentation articles | ✅ |
| Categorising them | ✅ (add audience/scoped categories) |
| Restricting visibility | ❌ (add audience + filtering) |
| Exporting manuals as PDF | ❌ |
| Searching documentation | ✅ (add relevance) |
| Linking help articles from product UI | ❌ |
| Version tracking | ❌ |
| Updating manuals when system changes | ✅ (edit/versioning to be added) |

---

## 4. Conflicts and Safest Options

### 4.1 Naming

- **Task:** "Knowledge Centre" / "Help Centre". **Codebase:** "Knowledge Base", "Knowledge base".
- **Option:** Use "Knowledge Centre" and "Help Centre" in UI (admin menu, page titles, user menu). Keep API paths and collection names (`kb_articles`, `/api/kb/`, `/api/admin/kb/`) unchanged to avoid breaking changes.

### 4.2 Collection and model

- **Task:** `knowledge_articles` with specific fields. **Codebase:** `kb_articles` with slightly different set.
- **Option:** Keep `kb_articles`; add new fields (`audience`, `version`, `summary` or align with `excerpt`, `related_feature_flags`, `product_module`, release-notes fields). Do not rename collection unless a one-off migration is planned and communicated.

### 4.3 Archive vs Unpublish vs Delete

- **Task:** Archive as an action; status archived. **Codebase:** Unpublish (→ draft), Delete (soft → is_active False).
- **Option:** (1) Add "Archive" action: set `status = archived`; archived articles excluded from public and user help, shown in admin with filter. (2) Keep Unpublish (→ draft) and Delete (deactivate). (3) In admin list, show Status column including "Archived" and allow filter by status.

### 4.4 Public KB vs User Help Centre

- **Task:** User Help Centre for logged-in users with USER-audience articles only. **Codebase:** Public KB at `/support/knowledge-base` (unauthenticated, all published).
- **Option (safest):** (1) Introduce audience and filter: when calling from client app (authenticated), return only USER (and STAFF if staff) articles. (2) Add in-app Help Centre at `/help` (or `/app/help`) that uses this filtered API and replaces or complements current "Knowledge base" link. (3) Keep `/support/knowledge-base` for anonymous/marketing if desired, with option to restrict it to USER-only or to deprecate it in favour of in-app Help Centre only. Document decision.

### 4.5 Permissions (staff read-only)

- **Task:** Staff may read internal (ADMIN/STAFF) articles but not edit. **Codebase:** Only admin_route_guard; no staff role in KB.
- **Option:** Phase 1: only admins have write; only admins see admin Knowledge Centre. Phase 2: introduce staff role and allow staff to read ADMIN/STAFF articles in admin Knowledge Centre (read-only). Requires role checks in backend and optional UI tweaks.

---

## 5. Recommended Implementation Order (No Code Yet)

Implement in this order to minimise risk and duplication:

1. **Schema and audience (backend)**  
   Add to `kb_articles`: `audience` (ADMIN | STAFF | USER), `version` (string), use `excerpt` as summary or add `summary`. Add optional `related_feature_flags`, `product_module`. Default existing articles to USER so current behaviour remains. Add category scope (e.g. audience or category_audience) and seed ADMIN + USER default categories per task.

2. **Visibility and APIs**  
   - Admin list: include audience, version, last updated; filter by audience/status.  
   - New client endpoint or existing public endpoint with auth: return only USER (and STAFF if staff) articles when caller is authenticated; unauthenticated can remain all published or USER-only by policy.  
   - Ensure draft/archived never returned to non-admin.

3. **Admin UI (additive)**  
   Rename menu to "Knowledge Centre". Add columns: Audience, Version, Last Updated. Add action: Archive (set status to archived). Add Export PDF: new endpoint + "Download Training Guide" button; PDF with title, version, date, content, branding, page numbers (reportlab).

4. **Versioning**  
   Store `version` on create/update; optional version history (e.g. append-only array or separate collection) in a later phase. Show Version and Last Updated in admin and in PDF.

5. **User Help Centre (client)**  
   New or replacement page at `/help`: "Help Centre", categories, search, list/detail of articles from authenticated USER (and STAFF) API. Keep email support link. Optionally keep link to full KB if policy allows.

6. **Search relevance**  
   Add text index or application-level relevance and sort "most relevant first" when search query is present.

7. **Release notes**  
   Add article type and fields (or dedicated structure); admin UI to create/list release notes; optional user-facing "Release notes" section.

8. **Product linking**  
   Add help link config or slug per product area; add "Need help? See: …" on Evidence Upload, Dashboard, Compliance Score, and other key pages.

9. **Editor and tagging (optional)**  
   Enhance editor (rich or markdown with images/code); add tagging by product_module/feature_flag/role if needed.

10. **Future AI**  
    Add optional fields (e.g. last_reviewed_at, ai_suggested_changes) when needed; do not break existing schema.

---

## 6. Files Referenced (Current)

| Layer | File(s) |
|-------|---------|
| Backend routes | `backend/routes/knowledge_base.py` |
| Frontend admin | `frontend/src/pages/AdminKnowledgeBasePage.js` |
| Frontend public KB | `frontend/src/pages/public/PublicKnowledgeBasePage.js` |
| Frontend help | `frontend/src/pages/HelpPage.js` |
| Routing | `frontend/src/App.js` |
| Admin layout/menu | `frontend/src/components/admin/UnifiedAdminLayout.js` |
| Client layout (help link) | `frontend/src/components/ClientPortalLayout.jsx` |
| PDF/reporting | `backend/routes/reporting.py`, `backend/services/compliance_pack.py`, `backend/services/template_renderer.py` |
| CMS export (distinct) | `backend/scripts/export_cms_to_kb.py` (CMS → assistant_kb; not KB articles) |

---

## 7. Summary Table

| Item | Implemented | Missing | Safe approach |
|------|-------------|---------|----------------|
| Two portals (Admin KC + User HC) | Single KB + admin | Audience-based split, in-app Help Centre | Add audience; add client Help Centre UI and filtered API |
| Model knowledge_articles | kb_articles with partial fields | audience, version, summary, optional fields | Keep kb_articles; add fields |
| ADMIN / USER categories | User-oriented only | ADMIN set + align USER set | Category scope + seed both |
| Admin list (Audience, Version, Archive, PDF) | Partial | Audience, Version, Archive, Export PDF | Add columns and actions |
| Rich editor + tagging | Markdown textarea | Rich editor, product/module/role tags | Enhance in later phase |
| Version control | None | version, display | Add version field; show in UI/PDF |
| PDF export | None | Endpoint + button + branded PDF | New endpoint + reportlab |
| User Help Centre | Link to public KB | In-app list/search/categories (USER only) | New page + auth API filter |
| Visibility (ADMIN/STAFF/USER) | None | audience + filter by role/route | Add audience; filter in APIs |
| Search relevance | Regex + sort | "Most relevant first" | Text index or score sort |
| Release notes type | None | Type + version, date, changes, modules | New type/fields or collection |
| Product page links | None | "Need help? See: …" | Config + links on key pages |
| Permissions (staff read) | Admin only | Staff read internal | Phase 2 role check |
| Status (Draft/Published/Archived) | Present | Clarify Archive vs deactivate | Archive = status; keep is_active |
| Future AI | None | Optional fields | Add later without breaking schema |

---

*End of audit. No code or assets were changed. Proceed with implementation only after approval; follow the recommended implementation order and safest options above.*
