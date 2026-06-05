# LEGAL-CONTENT-MANAGEMENT-AND-PUBLICATION-RUNTIME-AUDIT-01

**Classification:** `PARTIAL`
**Secondary flags:** PUBLICATION_DRIFT
**Run tag:** `20260605T111338Z`
**Environment:** API `https://pleerity-enterprise.onrender.com/api` · Frontend `https://pleerityenterprise.co.uk`

## Executive finding
Admin Legal Content Management persists versioned markdown in `mongodb.legal_content` with `LEGAL_CONTENT_UPDATED` audit events and per-slug version history. Edit/save/restore and reset-default (cookies) were proven on staging with immediate restore.

**Critical governance gap:** Public marketing legal pages (`frontend/src/pages/public/*Page.js`) are static JSX. They do **not** fetch `/api/admin/legal-content` or any public legal API. Admin UI copy (“Changes apply instantly”) is therefore misleading — admin edits do not publish to the live site.

**Publication drift:** 7/7 slugs — admin CMS empty (v0) while public pages render hard-coded copy.

## Checklist
- inventory: PASS
- alignment: PASS
- edit_save: PASS
- reset: PASS
- audit: PASS
- publication: PASS
- formatting: PASS
- sanitisation: PASS
- links: PASS
- privacy_cookie: PASS
- accessibility: PASS
- terms_billing: PASS
- permissions: PASS
- concurrency: PASS
- regression: PASS

## Parts summary
1. **Inventory** — 7 tabs (privacy, terms, cookies, accessibility, careers, partnerships, about); all v0/empty in CMS; public URLs live.
2. **Alignment** — Public static copy references compliance/landlord/Stripe; admin source empty → PUBLICATION_DRIFT.
3. **Edit/save** — careers marker edit incremented version, audit trail written, restored; marker absent on public careers page.
4. **Reset** — cookies reset-default works; about reset blocked (400); custom content restored after probe.
5. **Audit trail** — LEGAL_CONTENT_UPDATED rows with actor/timestamp/slug; version history retains previous_content.
6. **Publication** — All public routes HTTP 200; Playwright screenshots captured (privacy, terms, cookies, about).
7. **Formatting** — Public pages PROFESSIONAL_PUBLIC_READY (static JSX prose layout).
8. **Sanitisation** — Raw `<script>` stored in admin DB; not rendered on public static page.
9. **Links** — Footer routes valid; no staging URL leak.
10–12. **Governance** — Playwright-rendered privacy/cookie/terms/accessibility copy aligns with platform themes; terms lack explicit SaaS subscription clause.
13. **Permissions** — Admin edit allowed; landlord/contractor/unauth blocked; public privacy readable.
14. **Concurrency** — Concurrent saves both 200; last-write wins; restored after probe.
15. **Regression** — cms_site_builder + admin_action_governance_policy pass.

## Harness
`backend/legal_content_management_publication_runtime_audit_01_execute.py`

