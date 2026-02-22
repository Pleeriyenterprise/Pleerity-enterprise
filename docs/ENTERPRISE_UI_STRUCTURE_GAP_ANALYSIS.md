# Enterprise UI Structure – Task vs Codebase Gap Analysis

**Constraint:** Do not hardcode requirement lists; use backend endpoints. If an endpoint is missing, show a friendly "Coming soon" or empty state.

This document compares the **enterprise UI structure task** (nav, routes, evidence chips, risk labels, dashboard layout, property detail, documents, requirements, empty states, footer, design tokens) to the **current implementation** and identifies what is done, what is missing, and any conflicts.

---

## Summary Table

| # | Task requirement | Current state | Status |
|---|------------------|---------------|--------|
| 1 | Nav tabs: Dashboard, Properties, Requirements, Documents, Calendar, Reports, Settings | Same 7 + **Audit Log** in ClientPortalLayout | **Partial** – Audit Log extra |
| 2 | Routes: /dashboard, /properties, /properties/:id, /requirements, /documents, /calendar, /reports, /settings (+ subroutes) | All present in App.js; also /audit-log, /properties/create, /properties/import, /documents/bulk-upload | **Done** |
| 3 | Replace "Compliant/Non-compliant" with Evidence Status chips: Valid, Expiring soon, Overdue, Missing evidence, Needs review | PropertyDetail: Valid, Expiring soon, Missing, Overdue; elsewhere "Compliant", "Compliant", "Non-compliant", "Fully Compliant" | **Gap** – wording not fully aligned |
| 4 | Risk labels: Low/Medium/High/Critical risk (no legal verdict) | Backend/UI use "Low Risk", "Moderate Risk", "High Risk", "Critical Risk" | **Partial** – "Moderate" vs "Medium" |
| 5 | Dashboard: 4 KPI cards (Score+Risk, Overdue, Expiring soon, Missing evidence) + links; Next Actions with "Fix now" → /properties/:id#req=code; Properties table sortable | 4 tiles (Total, Compliant, Attention Needed, Action Required); portfolio summary table; no Next Actions list; properties as cards not sortable table | **Gap** – layout and Next Actions |
| 6 | Property detail: Header card + score section + requirements matrix (Upload/View) | Present | **Done** |
| 7 | Documents: table + filters + upload flow | Table and upload exist; filters to be confirmed | **Partial** |
| 8 | Requirements: grouped-by-property accordion + "group by requirement" toggle | Flat list with status/search filters; no accordion, no toggle | **Gap** |
| 9 | Consistent empty states and error banners per spec | Some empty states; no single spec or pattern | **Gap** |
| 10 | CRN pill + Copy in header on all pages | In ClientPortalLayout (wraps all portal pages) | **Done** |
| 11 | Footer: support email info@pleerityenterprise.co.uk + CRN copy | Support mailto uses SUPPORT_EMAIL (config = info@pleerityenterprise.co.uk); Help link; no CRN in footer | **Partial** – add CRN to footer if required |
| 12 | Design tokens file (colors/spacing/typography) and use it | design-tokens.js exists; **not imported** anywhere; Tailwind uses midnight-blue, electric-teal in config | **Gap** – tokens unused |

---

## 1) Top nav tabs

- **Task:** Dashboard, Properties, Requirements, Documents, Calendar, Reports, Settings (7 items).
- **Current:** Same 7 plus **Audit Log** between Documents and Calendar in `ClientPortalLayout.jsx` (PORTAL_TABS). Reports is conditionally hidden by feature flag.
- **Conflict:** Task list does not include Audit Log. Removing it could reduce visibility of an existing feature.
- **Safest option:** Align with task by **reordering** to match exactly and **removing Audit Log from the main tab list** so the 7 tabs are exactly as specified. Keep the **route** `/audit-log` and expose it via a link in Settings, Help, or footer ("Audit log") so it remains available without being in the top nav. If the product owner prefers to keep Audit Log in the nav, treat the task as "at least these 7" and leave Audit Log as the 8th.

---

## 2) Routes

- **Task:** /dashboard, /properties, /properties/:propertyId, /requirements, /documents, /calendar, /reports, /settings (+ subroutes).
- **Current:** All implemented in App.js under ClientPortal. Settings has subroutes (profile, notifications, billing). Additional routes exist (e.g. /audit-log, /properties/create, /properties/import). No conflict; task does not require removing extra routes.

---

## 3) Evidence Status chips (replace Compliant/Non-compliant)

- **Task:** Chips: **Valid**, **Expiring soon**, **Overdue**, **Missing evidence**, **Needs review**.
- **Current:** PropertyDetailPage STATUS_CONFIG: Valid, Expiring soon, Missing, Overdue, Failed, COMPLIANT→Valid. ClientDashboard, RequirementsPage, PropertiesPage, ComplianceScorePage, CalendarPage, TenantDashboard, AdminDashboard use "Compliant", "Compliant", "Non-compliant", "Fully Compliant", "Compliant", "Expiring Soon", "Overdue", "Pending".
- **Conflict:** None. Backend statuses (COMPLIANT, EXPIRING_SOON, OVERDUE, PENDING, etc.) stay; only UI labels change.
- **Safest option:** (a) Use chip labels exactly: **Valid** (COMPLIANT/VALID), **Expiring soon** (EXPIRING_SOON), **Overdue** (OVERDUE/EXPIRED), **Missing evidence** (PENDING/MISSING), **Needs review** (e.g. when document in PENDING_VERIFICATION or similar – or map one existing status to it). (b) Replace all user-facing "Compliant" / "Non-compliant" / "Fully Compliant" in client portal with the new chip wording or with "Evidence status: Valid" etc. so we never imply a legal "compliant" verdict. (c) Leave admin dashboard wording as-is or align in a separate pass.

---

## 4) Risk labels

- **Task:** Low / Medium / High / Critical risk (no legal verdict language).
- **Current:** Backend and shared UI use "Low Risk", "Moderate Risk", "High Risk", "Critical Risk" (utils/risk_bands.py, portfolio, compliance_score).
- **Conflict:** "Moderate" vs "Medium". Task explicitly says "Medium".
- **Safest option:** In **frontend only**, map display label "Moderate Risk" → **"Medium risk"** (or "Medium Risk") so the spec wording is used in the client UI. Backend can keep "Moderate Risk" for APIs; frontend can alias when rendering. Alternatively change backend to "Medium Risk" once and use everywhere (small, consistent change).

---

## 5) Dashboard layout

- **Task:**  
  - 4 KPI cards: **Score+Risk**, **Overdue**, **Expiring soon**, **Missing evidence**, with correct links.  
  - **Next Actions** list with "Fix now" linking to `/properties/:id#req=<code>`.  
  - **Properties table** (sortable) with links to property detail.
- **Current:**  
  - 4 tiles: Total Requirements → /requirements; Compliant → /properties?status=COMPLIANT; Attention Needed (expiring_soon) → /requirements?status=DUE_SOON; Action Required (overdue) → /requirements?status=OVERDUE_OR_MISSING. Plus portfolio summary line (risk + score) and optional kpis row.  
  - No "Next Actions" list and no "Fix now" link to /properties/:id#req=code.  
  - "Your Properties" is a **card list**, not a sortable table; portfolio summary is a separate table (score, risk, overdue, expiring) with row click to property.
- **Gap:**  
  - Rename/restructure KPIs to: (1) Score+Risk (link e.g. to /compliance-score or dashboard anchor), (2) Overdue (link to /requirements?status=OVERDUE_OR_MISSING or overdue list), (3) Expiring soon (link to /requirements?status=DUE_SOON or expiring list), (4) Missing evidence (link to /requirements filtered by missing).  
  - Add **Next Actions**: from portfolio summary or a small API (overdue/expiring requirements with property_id + requirement code), render list with "Fix now" → `/properties/${property_id}#req=${requirement_code}`. Backend may need a lightweight "next actions" or use existing compliance-summary + requirements.  
  - Replace or supplement property cards with a **sortable table** (e.g. Property, Score, Risk, Overdue, Expiring, Action) linking to /properties/:id; use portfolio summary data or dashboard properties + scores.
- **Conflict:** None. Additive and reorder/relabel.

---

## 6) Property detail

- **Task:** Header card + score section + requirements matrix table with Upload/View actions.
- **Current:** Header card (address, type, HMO, gas); score/risk block when complianceDetail exists; requirements matrix table with Upload / View document and "Request help". **Done.**

---

## 7) Documents

- **Task:** Table + filters + upload flow.
- **Current:** DocumentsPage has table (documents list), upload form (property, requirement, file), analyze/review flow. Filters: property/requirement dropdowns in upload; no explicit filter bar on the table (e.g. by status, property).
- **Gap:** Add table filters (e.g. by property, requirement type, status) if not present; ensure upload flow is clear. No conflict.

---

## 8) Requirements page

- **Task:** Grouped-by-property **accordion** + **"group by requirement"** toggle.
- **Current:** RequirementsPage: flat list of requirements with status filters and search; no accordion by property; no group-by-requirement view.
- **Gap:** (a) Add view mode toggle: "Group by property" (accordion: property → list of requirements) and "Group by requirement" (e.g. requirement type → list of properties/rows). (b) Data from existing GET /client/requirements (and optionally compliance-detail per property). No conflict.

---

## 9) Empty states and error banners

- **Task:** Consistent empty states and error banners per spec.
- **Current:** Some pages have empty states ("No requirements found", "No properties", etc.); error handling and banner style vary (Alert, toast, inline).
- **Gap:** Define a small set of patterns (e.g. empty state: icon + title + short text + optional CTA; error: Alert with message + optional action) and apply across dashboard, properties, requirements, documents, calendar. No conflict.

---

## 10) CRN pill + Copy in header

- **Current:** ClientPortalLayout shows CRN pill and Copy button in the header for all portal pages. **Done.**

---

## 11) Footer

- **Task:** Support email info@pleerityenterprise.co.uk + CRN copy.
- **Current:** Footer has "Support" (mailto:SUPPORT_EMAIL) and "Help"; SUPPORT_EMAIL = info@pleerityenterprise.co.uk in config. No CRN in footer.
- **Safest option:** Keep Support as mailto:info@pleerityenterprise.co.uk (already via config). Add **CRN** in footer (e.g. "CRN: xxx" with copy button) so it appears on every page as specified; reuse same CRN state/copy handler as header.

---

## 12) Design tokens and brand styling

- **Task:** Small design-tokens file for colors/spacing/typography; use it. Navy header, teal CTAs, card spacing.
- **Current:** `frontend/src/design-tokens.js` exists (colors, spacing, typography, borderRadius) but is **not imported** anywhere. Tailwind uses theme colors (midnight-blue, electric-teal) in tailwind.config.js; components use Tailwind classes.
- **Conflict:** Tokens file is redundant with Tailwind theme if we do not use it.
- **Safest option:** (a) **Use the tokens**: Export tokens and reference them where it helps (e.g. inline styles for dynamic values, or a small CSS file that sets CSS variables from tokens). Or (b) **Document Tailwind as source of truth**: In tailwind.config.js, set theme colors from design-tokens.js (e.g. `colors: { 'midnight-blue': colors.navy, 'electric-teal': colors.teal }`) so one file drives both Tailwind and any future token use. Then use Tailwind classes as today. Prefer (b) to avoid duplicating values and to keep existing classes working.

---

## Conflicts and recommended approach

| Item | Conflict | Recommendation |
|------|----------|----------------|
| Audit Log in nav | Task lists 7 tabs only | Remove Audit Log from main nav; keep route and link from Settings/Help/footer. |
| Moderate vs Medium risk | Task says "Medium" | Use "Medium risk" in client UI (frontend alias or backend change once). |
| Design tokens | File exists but unused | Wire design-tokens.js into Tailwind theme and optionally use for CSS variables; keep using Tailwind classes. |

---

## Implementation order (safe)

1. **Nav:** Set PORTAL_TABS to exactly Dashboard, Properties, Requirements, Documents, Calendar, Reports, Settings; add "Audit log" link in footer or Settings.
2. **Evidence chips:** Replace "Compliant"/"Non-compliant"/"Fully Compliant" with Valid / Expiring soon / Overdue / Missing evidence / Needs review across client portal; add "Needs review" where a status fits (e.g. pending verification).
3. **Risk labels:** Show "Medium risk" instead of "Moderate Risk" in client UI (map in one place or backend).
4. **Dashboard:** (a) Replace/adjust 4 KPIs to Score+Risk, Overdue, Expiring soon, Missing evidence with correct links. (b) Add Next Actions (from compliance-summary or requirements) with "Fix now" → /properties/:id#req=code. (c) Add or convert properties to a sortable table linking to /properties/:id.
5. **Requirements page:** Add accordion view grouped by property and "Group by requirement" toggle; keep data from existing APIs.
6. **Documents:** Add table filters (property, status, type) if missing.
7. **Empty states / error banners:** Define one pattern and apply on main client pages.
8. **Footer:** Add CRN + copy in footer; keep support email as is.
9. **Design tokens:** Source Tailwind theme from design-tokens.js (or document tokens → Tailwind) and keep using existing classes.

No backend contract change required for (1)–(4), (10), (11), (12). (5) and (8) may need a small "next actions" or grouped-requirements response if we do not derive everything client-side from existing endpoints.
