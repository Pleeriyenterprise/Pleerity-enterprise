# Operations → Work Orders Page – Task vs Codebase Audit

**Task:** Implement the top-level Operations → Work Orders page as an enterprise-grade portfolio-wide execution and job control workspace.

**Audit purpose:** Identify what is implemented, what is missing, how it was implemented, and any conflicts. **No implementation in this document** – audit only.

**References:** `ClientMaintenancePage.js`, `client_maintenance.py`, `maintenance_service.py`, `job_runner.py` (SLA breach job), `PropertyDetailPage.js` (Maintenance tab + WO drawer), `ClientIssuesPage.js`, `docs/MAINTENANCE_TAB_PROPERTY_DETAIL_TASK_AUDIT.md`.

---

## 1. EXECUTIVE SUMMARY

| Task section | Implemented | Missing / partial |
|--------------|-------------|-------------------|
| **§1 Page purpose** | Page exists; shows work orders list. | No “active / draft / assigned / in progress / SLA risk / contractor” as a control panel; no summary or SLA focus. |
| **§2 Page structure** | Single “Work orders” card list + Predictive insights card + Create modal. | No **Summary KPI row (A)**; no **Filter + Search bar (B)**; no **Table (C)** with required columns; no **SLA Risk panel (D)**; no **Work Order Detail drawer (E)**. |
| **§3 Summary KPI row** | — | No cards: Total Active, Draft, Assigned, In Progress, Awaiting Parts, Completed Today, SLA Breaches. |
| **§4 Filter + Search** | — | No filters (status, severity, property, contractor, asset, SLA state, date range); no search (title, issue ref, property, contractor). |
| **§5 Work Orders table** | Card list: property, description, created, source, status badge. | No **table** with Ref/Title, Property, Linked Issue, Asset, Severity, Status, Assigned Contractor, SLA Due, SLA State, Last Updated, Actions (View, Assign, Update status, Mark completed, Verify/Close). |
| **§6 Work order detail drawer** | **Property Detail** has a WO drawer (description, status, severity, SLA, asset, linked issue, update status, recommend contractors, assign). | **Top-level Work Orders page has no drawer**; no “View” to open detail; no progress/timeline (created, assigned, scheduled, started, etc.); status dropdown on Property Detail omits DRAFT, SCHEDULED, AWAITING_PARTS, VERIFIED, CLOSED. |
| **§7 Status workflow** | Backend supports DRAFT, OPEN, ASSIGNED, SCHEDULED, IN_PROGRESS, AWAITING_PARTS, COMPLETED, VERIFIED, CLOSED, CANCELLED. | Client UI (Property Detail drawer) only shows OPEN, ASSIGNED, IN_PROGRESS, COMPLETED, CANCELLED. Task: “Do not collapse Completed and Verified” – **Verified** and **Closed** must be distinct in UI. |
| **§8 SLA Risk panel** | Backend: `sla_respond_by`, `sla_complete_by`, `sla_breach_risk_at`, `sla_breached_at`; `run_work_order_sla_breach_job` sets flags. | No **SLA Risk panel** on Work Orders page (near breach, breached, next deadlines, hours remaining/overdue, quick action). |
| **§9 Contractor linkage** | Backend: `contractor_id`, `assigned_at`; client PATCH supports assign; recommend-contractors endpoint. | List does not show **assigned contractor**; no “Unassigned” / “Assign Contractor” CTA; no contractor detail link. Contractor features exist on Property Detail WO drawer only. |
| **§10 Issue + Asset linkage** | Backend: `issue_id`, `asset_id` on work order. | List does not show **linked issue** or **asset**; no “View issue” / “View property” from list. |
| **§11 Completion / Verification effects** | Backend: on COMPLETED → maintenance event, asset event, contractor performance; no explicit “verified” hook that closes issue. | “When verified: close associated issue, recalculate risk signals” – backend may need explicit **verified** handling and issue-close hook; ensure logged. |
| **§12 Backend** | GET `/client/maintenance/work-orders` with `property_id`, `status`, `skip`, `limit`; returns `{ work_orders, total, skip, limit }`. | No **summary** (totalActive, draft, assigned, inProgress, awaitingParts, completedToday, slaBreaches); no **contractor_id**, **asset_id**, **sla_state**, **q**, **from**/ **to**; no **slaRisk** array. Service already supports `contractor_id` filter; client route does not pass it. |
| **§13 Feature flag** | Page shows “Maintenance not enabled” on API 403; no route-level EntitlementProtectedRoute. | Task: locked state + upgrade CTA – satisfied by current 403 message. Contractor: “hide or show locked” – not yet differentiated on this page (no contractor UI). |
| **§14 Empty states** | “No work orders yet. Use Report issue to create one.” | Task: “No work orders have been created across your portfolio yet.” + **View Issues**, **Add Issue**. Filtered: “No work orders match your current filters.” |
| **§15–16 Design / Acceptance** | Simple list; status badges. | Enterprise table, SLA indicators, drawer-based workflow, contractor/issue/asset visible, full status lifecycle in UI – all missing on this page. |

**Overall:** **Partially implemented.** The route and list exist; backend has full status lifecycle and SLA fields. The **top-level** Work Orders page lacks summary, filters, table, SLA panel, and detail drawer. Property Detail’s Maintenance tab already has a WO drawer and can be used as the **reference pattern** for the Work Orders page.

---

## 2. CURRENT IMPLEMENTATION

### 2.1 Route and entry

- **Route:** `/operations/work-orders` → `ClientMaintenancePage` (inside `ClientPortal`). Redirects: `/maintenance`, `/app/maintenance` → `/operations/work-orders`.
- **Feature gate:** No `EntitlementProtectedRoute` on the route. When `getMaintenanceWorkOrders` returns 403, the page shows “Maintenance not enabled” and explains that maintenance workflows must be enabled. So **locked state is implemented** via API response.

### 2.2 ClientMaintenancePage

**Data:**

- **Work orders:** `getMaintenanceWorkOrders({ skip: 0, limit: 100 })` – no filters passed.
- **Properties:** `getProperties()` for create-form and labels.
- **Insights:** `getPredictiveInsights({ limit: 20 })` (predictive card).

**UI:**

1. **Header:** “Maintenance” + “Report issue” button.
2. **Blurb:** “View and create work orders for repairs or maintenance. Your landlord or admin can assign contractors and update status.”
3. **Predictive insights card** (optional): list of insights by property when available.
4. **Work orders card:** Title “Work orders”; list of items: property label, description (truncate), “Created {date} · {source}”, status badge (OPEN/ASSIGNED/IN_PROGRESS = amber/blue, COMPLETED = green, CANCELLED = gray). No table; no columns for issue, asset, contractor, SLA, last updated; no row actions (View, Assign, Update status, etc.).
5. **Create modal:** “Report an issue” – property (required), description (required); submits `createMaintenanceWorkOrder`; no category/severity in UI (form state has them, not shown).
6. **Empty state:** “No work orders yet. Use Report issue to create one.” (no “View Issues” / “Add Issue” per task.)

**Conflict (task vs current):**

- Task: “This page must feel like an operational delivery control panel, not just a task list.”
- Current: Single card list, no KPIs, no filters, no table, no SLA panel, no detail drawer – effectively a simple task list.

### 2.3 Backend (client)

- **GET /api/client/maintenance/work-orders**  
  Params: `property_id`, `status`, `skip`, `limit`.  
  Response: `{ work_orders, total, skip, limit }`. No summary, no `contractor_id`, `asset_id`, `sla_state`, `q`, `from`/`to`, no `slaRisk`.

- **GET /api/client/maintenance/work-orders/:id**  
  Returns full work order (used by Property Detail drawer).

- **PATCH /api/client/maintenance/work-orders/:id**  
  Body: `status`, `contractor_id`, `resolution_outcome`, `cost_estimate_min`, `cost_estimate_max`. Used from Property Detail.

- **GET /api/client/maintenance/work-orders/:id/recommend-contractors**  
  Requires CONTRACTOR_NETWORK; returns suggested contractors.

**maintenance_service.list_work_orders** already accepts `contractor_id`; the **admin** route exposes it; the **client** route does not.

**Work order document (relevant):** work_order_id, client_id, property_id, description, source, status, contractor_id, created_at, updated_at, sla_respond_by, sla_complete_by, sla_breach_risk_at, sla_breached_at, completed_at, assigned_at, asset_id, issue_id, severity, cost_estimate_min/max, resolution_outcome, triage_reasoning, recommended_contractor_type.

**Status lifecycle (backend):** DRAFT, OPEN, ASSIGNED, SCHEDULED, IN_PROGRESS, AWAITING_PARTS, COMPLETED, VERIFIED, CLOSED, CANCELLED. Job `run_work_order_sla_breach_job` sets `sla_breach_risk_at` and `sla_breached_at`.

---

## 3. CONFLICTS AND SAFEST OPTIONS

| Topic | Task | Current | Recommended approach |
|-------|------|--------|----------------------|
| **Page title** | “Work Orders” as execution workspace. | “Maintenance” with “Report issue” as primary CTA. | Keep route label “Work Orders” in nav; page title can stay “Maintenance” or become “Work Orders” for consistency with Issues page. Prefer **“Work Orders”** for this page to match task and nav. |
| **Primary CTA** | Execution control (View, Assign, Update status, etc.). | “Report issue” (create WO). | Keep “Report issue” / “Create work order” as **one** CTA; add **View Issues** in header or empty state so the page is clearly WO-centric with links to Issues. |
| **Summary** | Backend returns `summary: { totalActive, draft, assigned, inProgress, awaitingParts, completedToday, slaBreaches }`. | No summary. | **Option A:** Extend GET work-orders (or add a summary sub-resource) to return `summary` computed from same filters. **Option B:** Compute summary **client-side** from loaded `work_orders` (counts by status, today’s completed, breach flags). B is additive and avoids backend change; A gives one source of truth and supports “click card to filter”. |
| **Status dropdown (drawer)** | Full lifecycle: Draft, Assigned, Scheduled, In Progress, Awaiting Parts, Completed, Verified, Closed. “Do not collapse Completed and Verified.” | Property Detail drawer: OPEN, ASSIGNED, IN_PROGRESS, COMPLETED, CANCELLED only. | Add **DRAFT, SCHEDULED, AWAITING_PARTS, VERIFIED, CLOSED** to the status dropdown wherever WO status is updated (Property Detail drawer and, when added, Work Orders page drawer). Keep COMPLETED and VERIFIED as separate options. |
| **SLA state filter** | On Track / Near Breach / Breached. | Not in API. | **Option A:** Add `sla_state` param to client list (e.g. `breached` → `sla_breached_at` exists; `near_breach` → `sla_breach_risk_at` exists; `on_track` → neither). **Option B:** Filter client-side from full list. B is simpler and additive; A reduces payload when only breached/near are needed. |
| **Contractor filter** | Filter by contractor. | Service supports `contractor_id`; client route does not. | Add `contractor_id` to client GET work-orders and pass through to `list_work_orders`. Low risk. |
| **Verified / completion effects** | When verified: close linked issue; recalculate risk signals; logged. | Completion updates timeline, asset, contractor performance; no explicit “verified” flow or issue-close. | Implement **verified** as a distinct status; in backend (or in a small hook), when status → VERIFIED: if `issue_id` present, update issue status to closed (or “resolved”); optionally trigger risk recalc; ensure audit/timeline log. No change to schema. |

---

## 4. WHAT EXISTS AND CAN BE REUSED

- **APIs:** `getMaintenanceWorkOrders`, `getMaintenanceWorkOrder`, `createMaintenanceWorkOrder`, `updateMaintenanceWorkOrder`, `getRecommendContractors` – all used from Property Detail or ClientMaintenancePage. Add params to list call as needed.
- **Property Detail WO drawer:** Full pattern: open by WO id, load WO, show description, status, severity, SLA, asset, linked issue, cost/outcome; update status dropdown; recommend contractors + assign. **Reuse this pattern** on the Work Orders page (drawer opened from table row “View”).
- **Property Detail Maintenance tab:** Summary row, filters, table, SLA panel, empty states – **same structure** can be applied to the Work Orders page (summary = WO counts; table = WOs; SLA panel = WOs with breach/risk; filters = status, property, contractor, etc.).
- **Client Issues page:** Summary row (client-side), filters, table, drawer, empty states – **same UX pattern** for Work Orders page.
- **Backend:** Full status set, SLA fields, contractor_id, asset_id, issue_id; list_work_orders supports contractor_id; client PATCH for status/contractor; recommend-contractors; SLA breach job. Only **client list** needs extended params and optionally summary/slaRisk.
- **Contractors:** `clientAPI.getContractors()` exists; can be used for “Assign contractor” dropdown or to resolve contractor names in the table.

---

## 5. BACKEND GAPS (SUMMARY)

| Item | Current | Task expectation | Suggested change |
|------|--------|-------------------|------------------|
| List params (client) | property_id, status, skip, limit | + contractor_id, asset_id, sla_state, q, from, to | Add optional `contractor_id`, `asset_id`, `from_date`, `to_date` to client route and service; optional `sla_state` (breached / near_breach / on_track); optional `q` (search description, work_order_id, issue_id, property_id – or client-side filter). |
| List response (client) | { work_orders, total, skip, limit } | + summary, slaRisk | Optionally add `summary` (counts) and `sla_risk` (WOs with sla_breached_at or sla_breach_risk_at) in same response or separate call. |
| Verified → issue close | — | When WO verified, close linked issue; log. | On status update to VERIFIED: if issue_id set, update maintenance_issues.status to closed (or equivalent); log; optional risk recalc. |

---

## 6. FRONTEND GAPS (SUMMARY)

| Item | Current | Task expectation |
|------|--------|-------------------|
| Page focus | “Maintenance” + list + Report issue | “Work Orders” execution control panel. |
| Summary KPI row | None | 7 cards: Total Active, Draft, Assigned, In Progress, Awaiting Parts, Completed Today, SLA Breaches (click to filter if practical). |
| Filters | None | Status, Severity, Property, Contractor, Asset, SLA State, Date range; Search (title, issue ref, property, contractor). |
| Table | Card list (property, description, created, source, status) | **Table:** Ref/Title, Property, Linked Issue, Asset, Severity, Status, Assigned Contractor, SLA Due, SLA State, Last Updated, Actions (View, Assign, Update status, Mark completed, Verify/Close). |
| Detail drawer | None on this page | **Drawer:** Header (title, status, severity, SLA due, contractor); core details (issue, property, asset, description/notes); progress/timeline (created, assigned, scheduled, started, awaiting parts, completed, verified, closed); actions (Assign/change contractor, Update status, Add note, Mark completed, Verify/Close, View issue, View property); optional financial block. |
| SLA Risk panel | None | Panel: near breach, breached, next deadlines; per row: WO, property, due, hours remaining/overdue, quick action. |
| Empty state (none) | “No work orders yet. Use Report issue to create one.” | “No work orders have been created across your portfolio yet.” + View Issues, Add Issue. |
| Empty state (filtered) | — | “No work orders match your current filters.” |
| Status dropdown (wherever WO is updated) | OPEN, ASSIGNED, IN_PROGRESS, COMPLETED, CANCELLED | Add DRAFT, SCHEDULED, AWAITING_PARTS, VERIFIED, CLOSED; keep Completed and Verified distinct. |

---

## 7. IMPLEMENTATION ORDER (SAFEST, ADDITIVE)

1. **Backend (additive):** Add optional query params to GET `/client/maintenance/work-orders`: `contractor_id`, `asset_id`, `from_date`, `to_date` (filter on created_at or updated_at). Optionally `sla_state` (breached / near_breach). Optionally `q` (search) or leave search client-side. Optionally extend response with `summary` and `sla_risk`; otherwise compute client-side.
2. **Summary row:** Compute client-side from loaded work_orders (total active, by status, completed today, sla breaches). Optional: backend summary later for click-to-filter.
3. **Filters:** Add filter bar (Status, Property, Contractor, SLA State, Date range); wire to API params where supported; client-side filter for search (description, ref, property label, contractor name) if backend `q` not added.
4. **Table:** Replace list with table; columns per task; SLA state column (On track / Near breach / Breached) from `sla_breached_at` and `sla_breach_risk_at`; contractor from `contractor_id` (resolve name via getContractors or embed in WO if API extended).
5. **Row actions:** View (open drawer), Assign contractor (if contractor_network), Update status (inline or in drawer). Reuse updateMaintenanceWorkOrder and getRecommendContractors.
6. **Work order detail drawer:** Add drawer on Work Orders page (same pattern as Property Detail): load WO by id; show header, details, timeline (created_at, assigned_at, completed_at, etc.); status dropdown with **full** lifecycle (Draft … Verified, Closed); Assign/change contractor (if contractor_network); View issue, View property. Reuse getMaintenanceWorkOrder, updateMaintenanceWorkOrder, getRecommendContractors.
7. **SLA Risk panel:** Compute from work_orders where sla_breached_at or sla_breach_risk_at; show list with WO, property, due, hours remaining/overdue, link to View.
8. **Empty states:** Update copy and add “View Issues” and “Add Issue” (or “Report issue”); filtered empty state with “Clear filters”.
9. **Verified behaviour:** Backend: on status → VERIFIED, close linked issue and log; optional risk recalc. Frontend: ensure VERIFIED and CLOSED are in dropdown and clearly labeled.

---

## 8. FILES TO TOUCH (WHEN IMPLEMENTING)

- **Frontend:** `ClientMaintenancePage.js` (rename/refactor to Work Orders workspace: summary, filters, table, SLA panel, drawer, empty states). Optionally align Property Detail WO drawer status dropdown with full lifecycle (same file).
- **API:** `frontend/src/api/client.js` – ensure getMaintenanceWorkOrders is called with new params when backend supports them.
- **Backend:** `backend/routes/client_maintenance.py` (list params: contractor_id, asset_id, from_date, to_date, sla_state?, q?); `backend/services/maintenance_service.py` (list_work_orders: optional date range, sla_state filter; optional summary/sla_risk in response or separate helper). Optional: hook on update_work_order when status → VERIFIED to close linked issue and log.

---

## 9. NOTES ON WORK ORDER → CONTRACTOR → COMPLETION FLOW

- **Current:** Client can assign contractor via PATCH (Property Detail drawer). Backend records contractor_id, assigned_at, and contractor_assignments; on COMPLETED updates contractor_performance (jobs_completed, jobs_on_time), sends maintenance event, asset event. No explicit “verified” step in UI that closes the linked issue.
- **Task:** “When verified: close associated issue; recalculate risk signals; these effects must be logged.” So:
  - Treat **Verified** as a distinct status; when status is set to VERIFIED, backend should (if issue_id present) update the linked issue to closed (or resolved) and log.
  - Recalculate risk signals can be a separate job or an optional call when WO is verified; ensure it is documented/logged.
- **Placeholder/fallback:** If contractor_network is disabled, hide “Assign contractor” and “Recommended contractors” in drawer and table; show “Unassigned” and optionally a locked CTA. If no linked issue/asset, show “—”; “View issue” / “View property” only when issue_id/property_id present.

---

## 10. OUTPUT CHECKLIST (FOR TASK DELIVERABLES)

- **Files changed:** ClientMaintenancePage.js (main); optionally PropertyDetailPage.js (status dropdown); client_maintenance.py; maintenance_service.py.
- **Endpoints reused:** GET/POST/PATCH `/client/maintenance/work-orders`, GET work-order by id, GET recommend-contractors. **Created/extended:** GET list with optional contractor_id, asset_id, from_date, to_date, sla_state, q; optional response summary and sla_risk.
- **Filters implemented:** Status, Severity, Property, Contractor, SLA State, Date range; Search (client-side or backend q).
- **Work order → contractor → completion flow:** Assign via PATCH; status dropdown includes Verified and Closed; backend on VERIFIED closes linked issue and logs; completion already updates timeline, asset, contractor performance.
- **Placeholder/fallback:** Contractor features hidden when contractor_network disabled; “Unassigned” when no contractor_id; View issue/View property only when ids present; optional backend summary/sla_risk omitted initially (client-side only).

---

*End of audit. No code or assets were changed.*
