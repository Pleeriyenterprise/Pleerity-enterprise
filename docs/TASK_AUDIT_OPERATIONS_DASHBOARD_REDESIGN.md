# Task Audit: Operations Dashboard Redesign

**Task:** Redesign and extend the user-facing dashboard/navigation for users with access to Maintenance, Predictive Maintenance, and Contractors so the system feels like an enterprise-grade property operations platform.

**Audit date:** Based on codebase state at time of analysis. No implementation was performed; this document identifies what exists, what is missing, and where conflicts or decisions are required.

---

## 1. Current vs Required Navigation

### 1.1 Current client portal nav (ClientPortalLayout.jsx)

| Current top-level item | Feature flag | Route |
|------------------------|--------------|--------|
| Dashboard | — | `/dashboard` |
| Properties | — | `/properties` |
| Requirements | — | `/requirements` |
| Documents | — | `/documents` |
| Calendar | — | `/calendar` |
| Reports | reports_pdf / reports_csv | `/reports` |
| Maintenance | maintenance_workflows | `/maintenance` |
| Contractors | contractor_network | `/contractors` |
| Tenants | tenant_portal | `/tenants` |
| Billing | invoicing | `/settings/billing` |
| Settings | — | `/settings` (end) |

Tabs are flat; no parent “Operations” or “Compliance” group. Feature-gating is already in place via `hasFeature(t.feature)` and filter on `/reports` by `showReports`.

### 1.2 Required nav structure (from task)

- Dashboard  
- Properties  
- Compliance  
- **Operations** (parent)
  - Issues  
  - Work Orders  
  - Contractors  
  - Risk Signals  
  - Approvals  
- Reports  
- Settings  

Task explicitly states:
- Predictive Maintenance must **not** be a separate top-level menu; it must live under Operations as **“Risk Signals”**.
- Contractors must live **under Operations**, not as an isolated page.

### 1.3 Gap and conflict

- **Gap:** No “Compliance” parent; current has separate Requirements, Documents, and a separate Compliance Score page. Task asks for a single “Compliance” entry.
- **Gap:** No “Operations” parent with sub-items; Maintenance and Contractors are top-level; Predictive is currently surfaced only inside the Maintenance page (no “Risk Signals” menu).
- **Conflict / choice:**  
  - **Option A:** Replace current flat list with the new structure: one “Compliance” (hub or default to requirements), and one “Operations” with sub-routes (e.g. `/operations/issues`, `/operations/work-orders`, `/operations/contractors`, `/operations/risk-signals`, `/operations/approvals`). Remove top-level Maintenance and Contractors; keep feature flags but apply them to the Operations section or sub-items.  
  - **Option B:** Add Operations as a collapsible/expandable group and Compliance as a single entry (or hub) while keeping existing routes for backward compatibility and deep links.  

**Recommendation:** Option B for safety: introduce “Operations” as a nav group whose sub-items are shown/hidden by existing feature flags (maintenance_workflows → Issues + Work Orders; contractor_network → Contractors; predictive_maintenance → Risk Signals; invoicing → Approvals). Add “Compliance” as one nav item that routes to a compliance hub (or to `/requirements` as default) and keep existing `/requirements`, `/documents`, `/compliance-score` as reachable from that hub or from deep links. This avoids breaking existing links and keeps a single source of truth for gating (current entitlements).

---

## 2. Dashboard (command centre)

### 2.1 Current dashboard (ClientDashboard.js)

- **Compliance-focused:** Portfolio score, risk, “What changed”, score trend (portfolio vs property), audit readiness.
- **Stats row:** Requirements count, Valid count, Days to next expiry (links to `/requirements` with filters).
- **Portfolio summary table:** Property, Score, Risk level, Overdue, Expiring soon, Missing evidence; row click → property detail.
- **4 KPI cards:** Score & Risk, Overdue, Expiring soon, Missing evidence (deep links to compliance-score and requirements).
- **Next Actions:** Items needing evidence or expiring; deep link to `/properties/:id#req=code`.
- **Onboarding checklist** and setup views for first-time users.
- **No** Operations KPIs, **no** “Action Required” queue in the task sense, **no** issue/work-order funnel, **no** Property Health table with Maintenance risk / Open jobs / SLA breaches / Spend.

### 2.2 Required dashboard sections

| Section | Required | Current |
|--------|----------|---------|
| **A) Executive KPI row** | Portfolio Compliance Score, Open Issues, SLA Breaches, Predicted Risks, Contractor Performance, This Month’s Spend | Only compliance KPIs (score, overdue, expiring, missing). No Open Issues, SLA Breaches, Predicted Risks, Contractor Performance, Spend. |
| **B) Action Required queue** | Cards: e.g. boiler risk flagged, 2 work orders exceed SLA, invoice awaiting approval, contractor credentials expiring; each deep-linking to workflow | No such queue. “Next Actions” is compliance-only (evidence/expiry). |
| **C) Operations overview** | Issue/Work Order status funnel, Risk Signals summary | None. |
| **D) Property Health table** | Columns: Property, Compliance score, Maintenance risk, Open jobs, SLA breaches, Spend, View | Portfolio summary exists with Property, Score, Risk, Overdue, Expiring, Missing evidence only. No Maintenance risk, Open jobs, SLA breaches, Spend. |

**Backend:**  
- `/client/dashboard` and `/client/compliance-score` (and related) exist.  
- No single client endpoint that returns Open Issues count, SLA breach count, Predicted Risks count, Contractor Performance, or This Month’s Spend.  
- Work orders are in `maintenance_service`; client can list via `/client/maintenance/work-orders`. Predictive insights via `/client/maintenance/predictive-insights`. No aggregated “SLA breaches” or “this month’s spend” for client dashboard.

**Recommendation:** Implement in phases: (1) Add backend support for dashboard operations KPIs (open work orders, SLA-breach count, predicted risks count, optional contractor performance and spend) and a small “action items” structure. (2) Add Executive KPI row and Action Required queue to the dashboard using these APIs. (3) Add Operations overview (funnel + risk signals summary) and extend Property Health table with maintenance/SLA/spend columns where data exists. Avoid removing existing compliance content; add new sections so the dashboard becomes the “command centre” without breaking current behaviour.

---

## 3. Property detail page

### 3.1 Current (PropertyDetailPage.js)

- Single scrollable page: property header, compliance detail (evidence readiness score, risk level, score delta, change history), then **Requirements** matrix (requirement, evidence status, expiry, days left, actions).
- **No tabs.** No Overview, Maintenance, Evidence, Contractors, Timeline, or Risk Signals tabs.

### 3.2 Required tabs

| Tab | Required behaviour | Current |
|-----|--------------------|---------|
| Overview | Snapshot cards, current alerts, next due compliance, open maintenance, recommended actions | Not present. Content is effectively “Compliance” only. |
| Compliance | — | Exists as current main content (requirements matrix). |
| Maintenance | List issues + work orders, SLA status, Add issue | Not on property page. Maintenance is only on `/maintenance` (global work orders). |
| Evidence | — | Documents/evidence are reached via `/documents?property_id=...`; not a tab here. |
| Contractors | Assigned contractors, past job history, contractor score | Not on property page. Contractors are only on `/contractors` (global list). |
| Timeline | Unified chronological log (documents, compliance updates, maintenance, work orders, contractor assignments, invoice approvals) | No timeline. No backend for unified property timeline. |
| Risk Signals | Boiler/Damp/Electrical risk, explanation/drivers, recommended action, Create inspection / Create work order | Not on property page. Predictive insights are only on `/maintenance` (client) or admin APIs. |

**Recommendation:** Refactor property detail into tabs: **Overview** (new: snapshot + alerts + next due + open maintenance + actions), **Compliance** (current requirements matrix), **Maintenance** (list work orders for this property + add issue; reuse existing client maintenance API filtered by `property_id`), **Evidence** (link or embed documents filtered by property), **Contractors** (list contractors assigned to this property or with jobs here; backend may need “assigned to property” or derive from work orders), **Timeline** (new; needs backend for unified log), **Risk Signals** (per-property predictive insights + Create inspection / Create work order). Implement Overview, Compliance, Maintenance first; Evidence can link to existing documents flow; Contractors and Timeline depend on backend; Risk Signals can reuse predictive API per property.

---

## 4. Operations pages (client-facing)

### 4.1 Issues page

- **Required:** List/filter issues by severity, property, status; Create issue; Open issue detail.
- **Current:** No dedicated “Issues” page. “Report issue” on Maintenance page creates a **work order**. There is no separate “Issue” entity in the backend; only work orders exist.
- **Conflict:** Task distinguishes “Issues” and “Work Orders”. Backend has only work orders.
- **Recommendation:** Do **not** introduce a new “Issue” entity without product/backend agreement. Implement “Issues” as a **view of work orders** (e.g. open/reported, filterable by severity, property, status) with “Create issue” creating a work order. Reuse existing `maintenance_service` and client work-order APIs. If later the product wants Issues as a separate concept (e.g. issue → work order), that can be a separate change.

### 4.2 Work Orders page

- **Required:** Kanban or table with statuses: Open / Assigned / Scheduled / In Progress / Completed / Verified / Closed.
- **Current:** Client Maintenance page is a **list** of work orders with status badges (OPEN, ASSIGNED, IN_PROGRESS, COMPLETED, CANCELLED). No Kanban. No Scheduled, Verified, or Closed.
- **Backend:** `maintenance_service` uses OPEN, ASSIGNED, IN_PROGRESS, COMPLETED, CANCELLED.
- **Recommendation:** (1) Add Work Orders under Operations (or keep current Maintenance route but restyle as “Work Orders” under Operations). (2) Add Kanban or table view with columns for the requested statuses. (3) Backend: either add SCHEDULED, VERIFIED, CLOSED to the status enum and migration for existing data, or map “Verified” to COMPLETED and “Closed” to a new CLOSED (or keep CANCELLED and add CLOSED for completed-and-closed). Align with existing SLA fields (`sla_respond_by`, `sla_complete_by`) for “SLA status” and breach detection.

### 4.3 Contractors page

- **Required:** Table columns: Name, Trade, Region, Credentials, SLA compliance, Rework rate, Avg cost range, Score. Contractor **detail** page with tabs: Overview / Credentials / Performance / Jobs / Pricing.
- **Current:** Client Contractors page is a **simple list** (name, vetted, company, trade types, contact). No Region, Credentials, SLA compliance, Rework rate, Avg cost range, Score. No contractor detail page. Backend: `contractor_service` and client list return basic fields; no performance or pricing aggregates.
- **Recommendation:** Keep current list as first step. Add table columns as backend supports them (region, credentials, SLA compliance, rework rate, cost range, score). Add contractor detail route and tabs (Overview, Credentials, Performance, Jobs, Pricing); backend will need endpoints for contractor detail and for jobs/pricing/performance per contractor. Do not duplicate admin contractor CRUD; client sees read-only + assigned contractors.

### 4.4 Risk Signals page

- **Required:** Table/cards: Property, Risk Type, Score, Trend, Recommended Action, Status; per row: Create inspection / Create work order.
- **Current:** Predictive insights are shown only **inside** the Maintenance page (card “Predictive insights”). API: `get_insights_for_client` returns properties with `insights[]` (recommendation, detail, risk, type, asset_type). No dedicated Risk Signals page; no “Create inspection” or “Create work order” from a risk row.
- **Recommendation:** Add Operations → Risk Signals page that consumes existing predictive API and displays Property, Risk type (from insight type/asset_type), Score/risk, Recommended action; add buttons “Create inspection” / “Create work order” that deep-link to work order creation with pre-filled property (and optionally description from recommendation). Backend already has asset types (e.g. boiler, electrical) and risk levels; map to “Risk Type” and “Score/Trend” as needed.

### 4.5 Approvals page

- **Required:** Invoice approvals queue; columns: Invoice, Work Order, Property, Contractor, Amount, Benchmark Range, Status; actions: Approve / Reject / Needs Info.
- **Current:** Client “Billing” (`/settings/billing`, BillingPage) is **subscription billing** (plan, invoices, payment method). There is **no** work-order–related invoice approval workflow in the backend (no table for job invoices, approval status, or Approve/Reject/Needs Info). Admin billing is client subscription management, not job invoices.
- **Conflict:** Task groups “Approvals / Invoicing” and describes an operational approval queue. Current “invoicing” feature flag gates **subscription** Billing, not job-invoice approvals.
- **Recommendation:** Treat “Approvals” as **new scope**: it requires a new backend (invoices linked to work orders, approval state, amounts, benchmark). Do **not** repurpose existing Billing. Options: (1) Add Approvals under Operations as a **placeholder** (empty state: “Invoice approvals will appear here when your plan supports them” or “Coming soon”) and keep Billing under Settings as is. (2) Or hide Approvals from nav until the backend exists. Document the gap for product/backend.

---

## 5. Cross-module workflow and UX rules

### 5.1 Required relationships

- Predictive risk signal → can create preventive work order.  
  **Current:** No UI path from a risk signal to “Create work order”. Backend can create work orders; predictive returns recommendations. **Gap:** Wire Risk Signals UI to work order creation with property (and optional description).
- Maintenance issue → work order → contractor assignment → invoice approval.  
  **Current:** Issue creates work order; admin can assign contractor (maintenance_service.update_work_order). No invoice or approval step. **Gap:** Invoice approval is not implemented.
- Completed work order → updates property timeline + contractor performance + risk recalculation.  
  **Current:** On COMPLETED, maintenance_service records a maintenance_event for predictive. No property “timeline” entity; no contractor performance aggregation. **Gap:** Timeline and contractor performance need backend support.
- Compliance failure/expired evidence → alert in dashboard action queue.  
  **Current:** Dashboard “Next Actions” is compliance-based (evidence/expiry). **Gap:** Ensure these appear in the new “Action Required” queue and deep-link to the right property/requirement.

### 5.2 UX rules (task)

- Dashboard and property pages must drive users into workflows via action cards and deep links.  
  **Current:** Dashboard has some deep links (requirements, properties). **Gap:** Add operations actions and links.
- Menus for management and history; dashboard as primary operational driver.  
  **Current:** Dashboard is already central but compliance-only. **Gap:** Add operations KPIs and actions.
- Enterprise-grade: structured, calm, data-rich, no flashy gimmicks.  
  **Current:** UI is already structured and calm. **Recommendation:** Keep same tone when adding operations.

---

## 6. Feature flags

- **Current:** Plan-based defaults and overrides for maintenance_workflows, predictive_maintenance, contractor_network, invoicing (ops_compliance_feature_flags + client entitlements). Client portal filters nav tabs by `hasFeature(t.feature)`.
- **Task:** Only show Operations submenus if plan/feature flags allow; if disabled, hide or show locked state per existing gating.
- **Status:** Aligns. When introducing Operations group, show sub-items (Issues, Work Orders, Contractors, Risk Signals, Approvals) only when the corresponding feature is enabled; use same entitlements. No conflict.

---

## 7. Summary: implemented vs missing

| Area | Implemented | Missing / to do |
|------|-------------|------------------|
| **Nav** | Flat tabs; feature flags for Maintenance, Contractors, Reports, Billing | Operations parent group; Compliance as single entry; Risk Signals as sub-item; Approvals sub-item; Predictive not a top-level item (move under Operations as Risk Signals). |
| **Dashboard** | Compliance KPIs, portfolio table, Next Actions (compliance), deep links to requirements/properties | Executive KPI row (Open Issues, SLA Breaches, Predicted Risks, Contractor Performance, This Month’s Spend); Action Required queue (operations items); Operations overview (funnel, risk summary); Property Health table (maintenance risk, open jobs, SLA breaches, spend). |
| **Property detail** | Single page: compliance detail + requirements matrix | Tabs: Overview, Compliance, Maintenance, Evidence, Contractors, Timeline, Risk Signals; Overview content; Maintenance list + Add issue; Evidence link/embed; Contractors list; Timeline (unified log); Risk Signals + Create inspection/work order. |
| **Issues** | — | Page under Operations; treat as filtered view of work orders + Create issue (creates WO) unless product adds separate Issue entity. |
| **Work Orders** | Client list + create on Maintenance page; backend OPEN→ASSIGNED→IN_PROGRESS→COMPLETED→CANCELLED | Dedicated Work Orders page under Operations; Kanban or table; statuses Scheduled, Verified, Closed if required; SLA status/breach in UI. |
| **Contractors** | Client list (basic) + feature gate | Table columns (Region, Credentials, SLA, Rework, Cost, Score); contractor detail page with tabs (Overview, Credentials, Performance, Jobs, Pricing); backend for performance/jobs/pricing. |
| **Risk Signals** | Predictive insights card on Maintenance page; API per client | Dedicated Risk Signals page under Operations; table/cards; Create inspection / Create work order from row. |
| **Approvals** | — | Full workflow: backend (invoice + WO + approval state) and Approvals page under Operations; or placeholder/hidden until backend exists. |
| **Deep links** | Some (properties, requirements, compliance-score) | Dashboard action queue → workflows; Risk Signals → Create work order; consistent routing from dashboard/property to Operations pages. |

---

## 8. Conflicting instructions and recommended approach

1. **“Compliance” vs Requirements/Documents**  
   Task wants one “Compliance” entry. Current has Requirements, Documents, Compliance score.  
   **Recommendation:** Add one “Compliance” nav item that either routes to a hub (with links to Requirements, Documents, Score) or to `/requirements` as default, and keep existing routes for deep links. Do not remove Documents or Requirements URLs.

2. **Issues vs Work Orders**  
   Task has both; backend has only work orders.  
   **Recommendation:** Implement Issues as a filtered view of work orders and “Create issue” as create work order. No new entity without product/backend agreement.

3. **Work order statuses**  
   Task: Open, Assigned, Scheduled, In Progress, Completed, Verified, Closed. Current: OPEN, ASSIGNED, IN_PROGRESS, COMPLETED, CANCELLED.  
   **Recommendation:** Add SCHEDULED, VERIFIED, CLOSED to backend if product confirms; otherwise map Verified → COMPLETED and keep current set and add CLOSED for “closed” state.

4. **Approvals / Invoicing**  
   Task: Approvals page for job invoices (Approve/Reject/Needs Info). Current: Invoicing = subscription Billing.  
   **Recommendation:** Do not merge. Keep Billing as is. Add Approvals under Operations as new scope (backend + UI) or as placeholder until backend exists.

5. **Predictive not top-level; Contractors under Operations**  
   No conflict with codebase; current nav just does not follow this.  
   **Recommendation:** Restructure nav so that Maintenance (or Issues + Work Orders), Contractors, Risk Signals (predictive), and Approvals are under Operations; remove top-level Maintenance and Contractors from nav (keep routes for deep links if needed).

---

## 9. Suggested file/route map (for implementation)

- **Layout / nav:** `ClientPortalLayout.jsx` – add Operations group and Compliance entry; feature-gate sub-items.
- **Routes (App.js):** Add `/operations/issues`, `/operations/work-orders`, `/operations/contractors`, `/operations/risk-signals`, `/operations/approvals` (or keep `/maintenance`, `/contractors` and use them as Operations sub-routes for backward compatibility). Add `/compliance` hub if used.
- **Dashboard:** `ClientDashboard.js` – add Executive KPI row, Action Required queue, Operations overview, Property Health table (new sections; new or extended API).
- **Property detail:** `PropertyDetailPage.js` – refactor to tabbed layout; add Overview, Maintenance, Evidence, Contractors, Timeline, Risk Signals (new components or sections).
- **New or refactored pages:** Issues (or reuse Maintenance with filter), Work Orders (Kanban/table), Risk Signals (new page using predictive API), Approvals (new or placeholder). Contractor detail page (new) with tabs.
- **Backend:** Optional new endpoints for dashboard KPIs, action queue, property timeline, contractor detail/performance; work order status extension; approvals/invoice model if Approvals is implemented.

---

## 10. Conclusion

- **Already in place:** Feature flags, client maintenance work orders, client contractors list, predictive insights (API + card on Maintenance), compliance-focused dashboard, property compliance detail and requirements matrix, Billing (subscription).
- **Missing and non-conflicting:** Operations nav group and sub-routes, Risk Signals as “Operations → Risk Signals”, dashboard operations KPIs and action queue, property detail tabs, dedicated Work Orders and Risk Signals pages, deep links from dashboard to operations workflows.
- **Conflicts / decisions:** (1) Compliance = one entry vs current Requirements/Documents/Score — use hub or default to requirements. (2) Issues = view of work orders unless product adds separate entity. (3) Work order statuses = extend backend or map. (4) Approvals = new scope or placeholder; do not repurpose Billing.

Safest path: **implement nav and dashboard sections first (with optional new APIs), then property tabs and Operations pages, and treat Approvals as placeholder or later phase** until backend and product are aligned.
