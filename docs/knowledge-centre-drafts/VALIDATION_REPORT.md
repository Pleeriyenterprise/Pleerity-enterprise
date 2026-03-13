# Knowledge Centre Documentation – Validation Report

**Purpose:** Review and validation of generated draft Knowledge Centre articles against the current codebase. No product code was modified. This is a REVIEW AND VALIDATION process only.

**Update:** The recommended fixes in Sections 6–7 have been applied to the draft articles (Help Centre placement, Daily/Expiry Reminders labels, Automation Control Centre, Compliance Score access, password_status NOT_SET/SET, Re-run Provisioning and force-provision in the playbook, product-name note in template). Re-import or re-run the import script to pick up the revised drafts.

**Scope:** All draft articles in `docs/knowledge-centre-drafts/drafts/*.md` (status = draft).

**Validation date:** 2025-02-20 (codebase state at review).

---

## 1. Total Articles Reviewed

| # | Title | Slug | Audience | Category |
|---|--------|------|----------|----------|
| 1 | Getting Started | getting-started | USER | getting-started |
| 2 | Dashboard Guide | dashboard-guide | USER | dashboard-guide |
| 3 | Admin Console Overview | admin-console-overview | ADMIN | admin-console |
| 4 | How to Monitor Reminder Jobs | monitor-reminder-jobs | ADMIN | job-monitoring |
| 5 | Failed Provisioning Recovery | playbook-failed-provisioning | ADMIN | operations-playbooks |
| 6 | Release Note (Template) | release-note-template | ADMIN | release-notes |

**Total: 6 articles.**

---

## 2. Ready for Publication

**Count: 0**

No articles are recommended for direct publication without at least minor edits (see Section 3).

---

## 3. Ready With Minor Edits

**Count: 2**

| Article | Slug | Required edits |
|---------|------|----------------|
| **Release Note (Template)** | release-note-template | Template-only; no product behaviour. Align wording: "Article type" and "Release Notes" match AdminKnowledgeBasePage. Add note that Compliance Vault Pro / product name may vary. |
| **How to Monitor Reminder Jobs** | monitor-reminder-jobs | **UI label:** Use **"Automation Control Centre"** (not "Automation Centre") to match `UnifiedAdminLayout.js`. Optional: state that job ID in UI is `daily_reminders`. |

---

## 4. Needs Revision

**Count: 4**

| Article | Slug | Issues |
|---------|------|--------|
| **Getting Started** | getting-started | (1) **UI label:** Help Centre is in the **footer**, not the sidebar; sidebar has Dashboard, Properties, Compliance, Documents, etc. (2) **Notification label:** Settings → Notifications shows **"Daily Reminders"** (section) and **"Expiry Reminders"** (notification type); doc says "Daily compliance reminders" — align to "Daily Reminders" and "Expiry Reminders" or add "(or Expiry Reminders)". (3) **Step 4:** Doc says "Open **Compliance**" — UI label is **"Compliance"** (correct). (4) **Compliance Score:** Not in main nav; reached via Dashboard card or `/compliance-score`. Clarify "from the Dashboard you can go to … Compliance Score" (link/card). |
| **Dashboard Guide** | dashboard-guide | (1) **Help Centre:** Same as above — in footer, not sidebar. (2) **Score trend:** UI uses **"Score Trend (90 days)"** and toggle **"Portfolio" | "Property"** — doc is accurate; optional: add "(90 days)". (3) **Setup checklist:** Card title is "Welcome to Compliance Vault Pro"; doc says "setup checklist" — OK. (4) **Compliance Score:** Not in sidebar; clarify "via the Compliance Score card/link on the Dashboard". |
| **Admin Console Overview** | admin-console-overview | (1) **UI label:** Use **"Automation Control Centre"** (not "Automation Centre"). (2) **Find a client:** Nav section is **"Customers"**; item is **"Clients"** (opens Dashboard with clients tab). Doc says "Dashboard → Overview (or Customers) and … **Clients** tab" — correct but "Overview" is the first Dashboard sub-item; clarify "Dashboard → Overview, then open the **Clients** tab" or "Customers → Clients". (3) **Email delivery:** Under Settings & System, label is "Email delivery" (correct). (4) **Incidents:** Under Settings & System (correct). |
| **Failed Provisioning Recovery** | playbook-failed-provisioning | (1) **API path:** Resend activation is **`POST /api/portal/resend-activation`** — confirmed in `portal.py`. (2) **Rate limit:** **3 per hour per client** — confirmed (`RESEND_ACTIVATION_MAX_PER_HOUR`, `RESEND_ACTIVATION_WINDOW_MINUTES = 60`). (3) **password_status:** Doc says "e.g. not_sent, set". Backend uses **`NOT_SET`** and **`SET`** (`PasswordStatus` in `core.py`). Change to "NOT_SET, SET" or "not set, set". (4) **Retry provisioning:** Product **does** support it: **"Re-run Provisioning"** on Admin Billing (`AdminBillingPage.js`), backend `POST /api/admin/billing/clients/{client_id}/force-provision`. Update playbook to name the UI action and that it is under Billing/client context (or equivalent). |

---

## 5. Blocked — Incorrect

**Count: 0**

No article is blocked as fundamentally incorrect. All describe real features; issues are labelling, completeness, or wording.

---

## 6. Common Documentation Issues

| Issue type | Occurrences | Notes |
|------------|-------------|--------|
| **UI label mismatch** | 3 | "Automation Centre" → "Automation Control Centre"; "Daily compliance reminders" → "Daily Reminders" / "Expiry Reminders"; Help Centre in footer not sidebar. |
| **Navigation / placement** | 2 | Compliance Score and Help Centre: where they appear (footer vs sidebar, Dashboard link). |
| **Terminology** | 1 | password_status: "not_sent" → NOT_SET. |
| **Missing product detail** | 1 | Playbook does not name "Re-run Provisioning" and force-provision endpoint; both exist. |
| **Audience / security** | 0 | No USER article exposes admin-only procedures. |
| **Version / metadata** | 0 | Drafts have no version number or last-updated in frontmatter; template suggests 1.0 and updated date — add in import or CMS. |

---

## 7. Recommended Fixes

1. **Global (all USER articles):**
   - Where "Help Centre" is mentioned, state it is in the **footer** (or "bottom of the page") unless the product adds it to the sidebar later.
   - Where "Daily compliance reminders" is used, align to UI: **"Daily Reminders"** (master toggle) and/or **"Expiry Reminders"** (notification type) in Settings → Notifications.

2. **Global (admin articles):**
   - Use **"Automation Control Centre"** consistently (matches `UnifiedAdminLayout.js`).

3. **Getting Started & Dashboard Guide:**
   - Clarify that **Compliance Score** is reached via the Dashboard (card/link to `/compliance-score`), not a top-level sidebar item.

4. **Admin Console Overview:**
   - Clarify client lookup: **Customers → Clients** (or Dashboard with Clients tab).

5. **Failed Provisioning Recovery:**
   - Replace "not_sent" with **"NOT_SET"** (or "not set").
   - Add step or bullet: **Retry provisioning:** In admin, use **Re-run Provisioning** (e.g. from Billing/client context); backend `POST /api/admin/billing/clients/{client_id}/force-provision`. Rate limits and idempotency as per product.

6. **Versioning:**
   - Ensure each article has **version** and **last updated** (and optionally author) in the Knowledge Centre model when publishing; drafts currently omit these in frontmatter.

---

## 8. Articles Requiring Product Team Verification

| Article | What to verify |
|---------|----------------|
| **Getting Started** | Login URLs and client portal URL by environment; exact behaviour of "setup checklist" (when it appears, dismiss vs complete). |
| **Dashboard Guide** | Whether "Portfolio" / "Property" labels or score trend timeframe (90 days) are configurable. Which Operations/plan-gated items show on Dashboard. |
| **Admin Console Overview** | Which menu items are owner-only vs admin (e.g. Analytics, Operations & Compliance); exact tab order on Admin Dashboard. |
| **How to Monitor Reminder Jobs** | That "Run Now" for `daily_reminders` is safe (idempotent, no duplicate sends); reminder schedule (e.g. 09:00 UTC) if documented. |
| **Failed Provisioning Recovery** | Where "Re-run Provisioning" is exposed in UI (Billing vs client detail); any extra guardrails or limits. |
| **Release Note (Template)** | N/A (template only). |

---

## 9. Documentation Coverage Score (0–100)

**Score: 72**

- **Rationale:**
  - **Strengths:** All 6 drafts map to real routes, features, and APIs. No invented features. Audience (USER vs ADMIN) is correct. Security: no inappropriate exposure of internal APIs or admin-only steps in USER content. Step-by-step structure (Purpose, When to use, Steps, What happens next, Troubleshooting, Related) is present.
  - **Gaps:** UI label and placement details need alignment (see Sections 6–7). Playbook omitted an existing "Re-run Provisioning" flow. No version/last-updated in draft frontmatter. Some steps (e.g. "Confirm details" after upload) are correct but could be more precise (e.g. where "Confirm details" appears — Documents / property detail).
  - **Deductions:** −10 (label/placement inaccuracies), −10 (missing retry provisioning in playbook), −8 (versioning/metadata and minor completeness).

---

## 10. Feature Verification Summary (Step 2)

| Article | Routes | Pages | API/Backend | Feature flags | Verdict |
|---------|--------|--------|-------------|----------------|---------|
| Getting Started | ✅ /dashboard, /properties, /requirements, /documents, /settings, /help | ✅ ClientDashboard, PropertiesPage, etc. | ✅ compliance score, reminders | ✅ Operations/Billing gated | Features exist |
| Dashboard Guide | ✅ /dashboard, /compliance-score | ✅ ClientDashboard, score trend | ✅ Portfolio/Property trend API | ✅ Operations mentioned | Features exist |
| Admin Console Overview | ✅ /admin/* | ✅ UnifiedAdminLayout nav | ✅ Admin APIs | ✅ ownerOrAdminOnly | Features exist |
| Monitor Reminder Jobs | ✅ /admin/automation, /admin/notification-health | ✅ AdminAutomationCentrePage | ✅ daily_reminders, job_runs, COMPLIANCE_EXPIRY_REMINDER | N/A | Features exist |
| Failed Provisioning Recovery | ✅ /api/portal/resend-activation, force-provision | N/A (API/playbook) | ✅ onboarding_status, password_status, resend rate limit | N/A | Features exist; retry flow was understated |
| Release Note (Template) | N/A | ✅ Admin KB article type | ✅ article_type release_notes, fields | N/A | Template only |

---

## 11. Workflow Validation Summary (Step 3)

| Article | Workflow checked | Result |
|---------|------------------|--------|
| Getting Started | Login → Dashboard → Properties → Add Property → Compliance → Documents (upload, Confirm details) → Settings → Notifications | **Accurate.** Upload and "Confirm details" exist on DocumentsPage and PropertyDetailPage. |
| Dashboard Guide | Dashboard → score, trend (Portfolio/Property), properties (Green/Amber/Red), checklist, links | **Accurate.** Score trend toggle and checklist behaviour present. |
| Admin Console Overview | Admin login → sidebar → Clients, Billing, Automation, Notification Health, Knowledge Centre, Incidents | **Accurate.** Paths and labels need minor alignment (Automation Control Centre, Customers/Clients). |
| Monitor Reminder Jobs | Open Automation Centre → find daily_reminders → interpret status → Notification Health → Run Now for recovery | **Accurate.** Job name and templates verified. |
| Failed Provisioning Recovery | Identify client → check onboarding_status/password_status → resend activation (rate limit) → retry provisioning → escalate | **Incomplete.** Resend and escalation are correct; "retry provisioning" exists (force-provision, Re-run Provisioning) but was not explicitly named. |
| Release Note (Template) | Author workflow for creating release notes in KB | **N/A** (template). |

---

## 12. UI Label Consistency (Step 4)

| Doc wording | Actual UI | Location |
|-------------|-----------|----------|
| "Automation Centre" | **Automation Control Centre** | UnifiedAdminLayout.js |
| "Daily compliance reminders" | **Daily Reminders** (section), **Expiry Reminders** (type) | NotificationPreferencesPage.js |
| "Help Centre (sidebar)" | Help Centre in **footer** | ClientPortalLayout.jsx |
| "Open Compliance" | **Compliance** (sidebar) | PORTAL_TABS |
| "Add Property" | **Add Property** | PropertiesPage.js |
| "Confirm details" | **Confirm details** | DocumentsPage.js, PropertyDetailPage.js |
| "Compliance Score" | Reached via Dashboard card, not sidebar | ClientDashboard.js, App.js |

---

## 13. Audience & Security (Steps 5–6)

- **USER articles (Getting Started, Dashboard Guide):** No admin tools, provisioning, or feature-flag details. **Audience correct.**
- **ADMIN articles (Admin Console, Monitor Reminder Jobs, Playbook, Template):** Internal procedures and APIs (e.g. resend-activation, force-provision) are appropriate for ADMIN/STAFF only. No unnecessary exposure of internal architecture; API paths are support/ops-level. **No security issues flagged.**

---

## 14. Completeness (Step 7)

| Article | Purpose | When to use | Steps | Outcome | Troubleshooting | Related | Version/Updated |
|---------|---------|--------------|-------|---------|-----------------|---------|------------------|
| Getting Started | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ (not in frontmatter) |
| Dashboard Guide | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| Admin Console Overview | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| Monitor Reminder Jobs | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| Failed Provisioning Recovery | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| Release Note (Template) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | N/A |

**Recommendation:** Add `version` and `updated_at` (and optionally `author`) when importing or publishing so "Version & Change Control" (Step 10) is satisfied.

---

## 15. Final Article Status (Step 11)

| Article | Final status | Explanation |
|---------|----------------|-------------|
| Getting Started | **NEEDS REVISION** | Help Centre placement, notification labels, Compliance Score access. |
| Dashboard Guide | **NEEDS REVISION** | Help Centre placement, Compliance Score access. |
| Admin Console Overview | **NEEDS REVISION** | Automation Control Centre label, Customers/Clients clarification. |
| How to Monitor Reminder Jobs | **READY WITH MINOR EDITS** | Use "Automation Control Centre". |
| Failed Provisioning Recovery | **NEEDS REVISION** | password_status wording, add Re-run Provisioning / force-provision. |
| Release Note (Template) | **READY WITH MINOR EDITS** | Template only; optional product-name note. |

---

**Report end.** Do not auto-publish; apply recommended fixes and product-team verification where indicated before publishing to the Knowledge Centre.
