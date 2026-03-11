# Operations → Issues Page – Task vs Codebase Audit

**Task:** Implement the top-level Operations → Issues page as an enterprise-grade portfolio-wide issue intake and triage workspace.

**Audit purpose:** Identify what is implemented, what is missing, how it was implemented, and any conflicts. **No implementation in this document** – audit only.

**References:** `ClientIssuesPage.js`, `ClientIssueDetailPage.js`, `client_maintenance.py`, `maintenance_issues_service.py`, `maintenance_triage.py`, `risk_signal_service.py`, `PropertyDetailPage.js` (Maintenance tab).

---

## 1. EXECUTIVE SUMMARY

| Task section | Implemented | Missing / partial |
|--------------|-------------|------------------|
| **§1 Page purpose** | Page exists; shows “issues” and work orders. | Page is **work-order led** (first card = open WOs); task wants **issue-centric** portfolio intake queue. |
| **§2 Page structure** | Two cards: “Open issues” (WOs) + “Triaged issues” (issues). | No **Summary KPI row (A)**; Filter bar partial **(B)**; no single **Issues Queue Table (C)** with required columns; no **Recurring/Flagged panel (D)**; no **Quick Action Drawer (E)** (detail is full-page). |
| **§3 Summary KPI row** | — | No cards: Total Open Issues, New, High Severity, Ready for Work Order, Monitoring, Recurring. |
| **§4 Filter + search** | Filters: Property, Status (WOs), Category, Severity. | No **Source**, **Asset**, **Date range**; no **Search (q)** (title/description/property/ref). Severity options: task wants “Critical”, backend uses “urgent”. |
| **§5 Issues queue table** | Triaged issues list (cards): property, description, created, severity, status; View → full page. | No **table** with Issue Ref/Title, Priority Score, Asset, Source, SLA Recommendation, Actions (Triage, Create WO, Close, Link Asset). First card shows **work orders**, not issues – **conflict**. |
| **§6 Issue detail drawer** | Full-page detail at `/operations/issues/:issueId`: description, triage (severity, priority, SLA, contractor, reasoning), Create Work Order. | No **drawer**; no photos/attachments, property/source/asset in header; no related WO link, timeline; no **Edit**, **Link Asset**, **Close**, **View Property** in UI. |
| **§7 Triage support** | Triage shown on detail page (severity, priority_score, sla_hours, recommended_contractor_type, reasoning). | No **override**; task says “surface prominently” – current is one card; no priority **band** display. |
| **§8 Recurring/Flagged panel** | Backend: `recurrence_flag` on issue; risk_signal_service has recurring-repairs rules (per property). | No **Recurring/Flagged panel** on page; no endpoint returning **recurringPatterns** (pattern, property, asset, count, suggested action). |
| **§9 Work order handoff** | Create Work Order from issue (detail page); backend prefills propertyId, assetId, category, severity, SLA from issue. | Issue doc does **not** store `work_order_id`; “View Work Order” would require lookup by `issue_id` on work_orders (doable). List has no “Create Work Order” action. |
| **§10 Property/asset linkage** | Issues have `property_id`, `asset_id`; triage can infer asset. | List does not show **asset** column; no “Unlinked” / “Link Asset” (no PATCH issue for asset). |
| **§11 Feature flag** | `EntitlementProtectedRoute(requiredFeature="maintenance_workflows")`; 403 shows locked message. | Aligned. |
| **§12 Backend** | GET `/client/maintenance/issues` with property_id, status, category, severity, skip, limit; returns `{ issues, total, skip, limit }`. | No **summary** (totalOpen, new, highSeverity, readyForWorkOrder, monitoring, recurring); no **q**, **source**, **assetId**, **from/to**; no **recurringPatterns**; no **pagination/sort** in response. |
| **§13 Empty states** | “No open issues” / “No triaged issues” with CTAs. | Task wants: “No maintenance issues have been recorded across your portfolio” + Add Issue, View Properties; filtered: “No issues match your current filters.” |
| **§14 Design** | Simple lists; some badges. | Task: calm enterprise layout, strong filters, status/severity badges, drawer-based workflow, mobile responsive. |
| **§15 Acceptance** | Page loads; filters apply to issues; Create WO from detail; locked state. | Summary cards, full filters/search, issue drawer, recurring panel, work order handoff from list, asset/property linkage in list and drawer, “View Work Order” when WO exists – all missing or partial. |

---

## 2. CURRENT IMPLEMENTATION

### 2.1 Route and entry

- **Route:** `/operations/issues` → `ClientIssuesPage` (inside ClientPortal); `/operations/issues/:issueId` → `ClientIssueDetailPage`.
- **Feature gate:** `EntitlementProtectedRoute(requiredFeature="maintenance_workflows")`. On 403, page shows message and “View Work Orders”.

### 2.2 ClientIssuesPage (Operations → Issues)

**Data:**

- **Work orders:** `getMaintenanceWorkOrders({ property_id?, status?, skip, limit })` – first card uses this (open WOs by default).
- **Issues:** `getMaintenanceIssues({ property_id?, status?, category?, severity?, skip, limit })` – second card.

**UI:**

1. **Header:** “Issues” + “View all work orders” | “Create issue (triaged)” | “Report issue”.
2. **Filters:** Property, Status (work orders: Open/Assigned/In progress/Completed/Cancelled), Category (issues), Severity (issues: low/medium/high/urgent). No source, asset, date range, or search.
3. **Card 1 – “Open issues”:** List of **work orders** (property, description, created, source label, status badge). Empty: “No open issues. Use Report issue…”
4. **Card 2 – “Triaged issues”:** List of **issues** (property, description, created, severity, status); “View” → `navigate(/operations/issues/:issueId)`.
5. **Modals:** “Report issue” (creates WO via `createMaintenanceWorkOrder`); “Create issue (triaged)” (creates issue via `createMaintenanceIssue`, then navigates to detail).

**Conflict (task vs current):**

- Task: “Issues must remain visually distinct from Work Orders. Do NOT mix them into one list.” and “This page is the portfolio-wide **intake and triage queue**” (issue-centric).
- Current: First section is **work orders** labeled “Open issues”; second is issues. So the main focus is mixed and the first list is mislabeled (WOs, not issues). Task expects a single **Issues** queue as primary, with work order creation as an **action from an issue**, not a separate list of WOs.

### 2.3 ClientIssueDetailPage

- **Route:** `/operations/issues/:issueId`.
- **Data:** `getMaintenanceIssue(issueId)`.
- **UI:** Back to Issues; description; triage card (severity, priority score, SLA hours, recommended contractor type, reasoning); “Create Work Order” (calls `createWorkOrderFromIssue`, then navigates to work orders).
- **Missing vs task:** No drawer (full page); no photos/attachments, no “Edit issue”, “Link Asset”, “Close Issue”, “View Property”; no related work order link; no timeline.

### 2.4 Backend (client)

- **GET /api/client/maintenance/issues**  
  Params: `property_id`, `status`, `category`, `severity`, `skip`, `limit`.  
  Response: `{ issues, total, skip, limit }`. No summary, no `q`, no `source`, no `asset_id`, no `from`/`to`.
- **GET /api/client/maintenance/issues/:id**  
  Returns full issue (including `triage`).
- **POST /api/client/maintenance/issues**  
  Body: property_id, description, category (optional). Creates issue with triage; returns issue (issue_id, etc.).
- **POST /api/client/maintenance/issues/:id/create-work-order**  
  Creates WO from issue; sets issue status to `ready_for_work_order`. Work order has `issue_id`; issue does **not** get `work_order_id` stored.

**Issue model (relevant):** issue_id, client_id, property_id, asset_id, source, category, description, severity, priority_score, status, recurrence_flag, created_at, updated_at, triage { severity, priority_score, sla_hours, recommended_contractor_type, reasoning }.

**Statuses (backend):** new, triaged, monitoring, ready_for_work_order, closed.  
**Severity (triage):** low, medium, high, urgent (task also asks “Critical” – can map urgent ↔ critical or add).

---

## 3. CONFLICTS AND SAFEST OPTIONS

| Topic | Task | Current | Recommended approach |
|-------|------|--------|----------------------|
| **Primary content** | Issues-only queue as main content; work orders only as handoff from issues. | Two sections: first = work orders (“Open issues”), second = issues. | **Make the main content the Issues queue only.** Remove or relocate the “Open issues” (work orders) card: either (1) remove it and add a single “View work orders” link in header, or (2) move it to a collapsible/secondary section so the **Issues** table is clearly the primary control queue. Do **not** mix issues and WOs in one list; keep labels accurate (“Work orders” not “Open issues”). |
| **Detail UX** | Quick-action **drawer** (no full-page navigation). | Full page `/operations/issues/:issueId`. | **Option A:** Add a **drawer** on the Issues page that opens when clicking an issue; keep existing route for deep links / refresh. **Option B:** Keep full page only. Task prefers drawer for “action without full-page navigation”; A is aligned with task and Property Detail pattern (issue/WO drawers). |
| **Summary** | Backend returns `summary: { totalOpen, new, highSeverity, readyForWorkOrder, monitoring, recurring }`. | No summary in API. | **Option A:** Extend GET issues (or add GET issues/summary) to return `summary` (counts from same filters). **Option B:** Compute summary client-side from `issues` (and, for “recurring”, from issues where `recurrence_flag` true). B is additive and avoids backend change; A gives one source of truth and supports “click card to apply filter”. |
| **Recurring panel** | “Recurring/Flagged Issues” with pattern, property, asset, recurrence count, suggested action. | Only `recurrence_flag` on issue; recurring logic in risk_signal_service (per-property signals). | **Option A:** New endpoint (e.g. GET issues with `recurring_only=true` or GET issues/recurring-patterns) returning aggregated patterns (e.g. by property+asset+category, count, suggested action). **Option B:** Client-side: group issues (and optionally WOs) by property+category/asset, show rows with count ≥ 2 as “recurring”; or show issues where `recurrence_flag === true` in a simple list. B is quicker and reuses data; A matches task “recurringPatterns” and allows backend-driven suggestions. |
| **Search (q)** | Search issue title, description, property name/address, issue reference. | Not supported. | Add `q` to backend list_issues (regex or text index on description, issue_id, and optionally join property for address); pass through client. If no backend change: filter client-side by description/issue_id (and property label) – weaker for large portfolios. |
| **Filters: source, asset, date** | Status, Severity, Property, Category, Source, Asset, Date range. | Backend has property, status, category, severity. Missing: source, asset_id, from/to. | Add optional query params `source`, `asset_id`, `from_date`, `to_date` (on created_at or updated_at) to list_issues and route; add corresponding filter controls on page. |
| **Severity: Critical** | Severity: Low, Medium, High, **Critical**. | Backend/triage: low, medium, high, **urgent**. | Treat **Critical** as **urgent** in API and UI (single band). No schema change; document mapping. |
| **Edit / Link Asset / Close issue** | Drawer buttons: Edit issue, Link Asset, Close Issue. | No client PATCH for issues. | Backend: add PATCH `/client/maintenance/issues/:id` (e.g. status, asset_id, description) with client check. Then add Edit (modal), Link Asset (asset picker), Close (status → closed) in drawer. |
| **“View Work Order” when WO exists** | When issue has linked WO, show “View Work Order” instead of “Create Work Order”. | Work orders have `issue_id`; issues do not store `work_order_id`. | **Option A:** When returning issue (get or list), backend resolves linked WO (e.g. one WO where `issue_id` = this issue) and adds `linked_work_order_id` (or similar). **Option B:** Frontend fetches WOs and matches by issue_id. A is cleaner for list and detail; B needs no backend change but extra call or combined endpoint. |

---

## 4. WHAT EXISTS AND CAN BE REUSED

- **APIs:** `getMaintenanceIssues`, `getMaintenanceIssue`, `createMaintenanceIssue`, `createWorkOrderFromIssue` – all used. Add params/response extensions as above.
- **Triage:** Stored in issue; shown on detail page. Reuse for drawer and table (severity, priority, SLA, contractor type, reasoning).
- **Property list:** Already loaded for filters and labels; reuse for property filter and “View Property”.
- **Assets:** No asset list on Issues page today. For “Asset” filter and “Link Asset”, need either (1) portfolio-wide asset list (new or from existing property-assets aggregation), or (2) per-issue asset resolved from issue.asset_id + property assets when opening drawer.
- **ClientIssueDetailPage:** Keep for deep link and “Back to Issues”; can coexist with drawer (drawer for in-page flow, page for direct URL).
- **Property Detail Maintenance tab:** Already has issue drawer, summary, filters, Create WO from issue, asset label – patterns and structure can be mirrored on the Issues page (portfolio-wide, no property_id pre-filter).

---

## 5. BACKEND GAPS (SUMMARY)

| Item | Current | Task expectation | Suggested change |
|------|--------|-------------------|------------------|
| List issues params | property_id, status, category, severity, skip, limit | + q, source, assetId, from, to | Add optional `q`, `source`, `asset_id`, `from_date`, `to_date` to route and list_issues. |
| List issues response | { issues, total, skip, limit } | + summary, recurringPatterns, pagination/sort | Optionally add `summary` (counts); optionally add `recurring_patterns` (or separate endpoint). |
| Get issue / list | — | Linked work order when exists | Optionally add `linked_work_order_id` (lookup work_orders by issue_id). |
| PATCH issue | None | Edit, Link Asset, Close | Add PATCH `/client/maintenance/issues/:id` (e.g. status, asset_id, description). |

---

## 6. FRONTEND GAPS (SUMMARY)

| Item | Current | Task expectation |
|------|--------|-------------------|
| Page focus | Two cards: WOs + issues | Single **Issues** queue as main content; WOs only via actions. |
| Summary KPI row | None | 6 cards: Total Open, New, High Severity, Ready for WO, Monitoring, Recurring (click to filter if practical). |
| Filters | Property, Status (WO), Category, Severity | + Source, Asset, Date range, **Search (q)**. Clarify status filter is for **issues** (New, Triaged, etc.). |
| Issues table | Card list (property, description, date, severity, status, View) | **Table:** Ref/Title, Property, Category, Severity, Priority, Asset, Source, Status, Created, SLA, Actions (View, Triage, Create WO, Close, Link Asset). |
| Detail | Full page only | **Drawer** with full description, photos, property, source, triage, related WO, timeline; actions: Edit, Create WO / View WO, Link Asset, Close, View Property. |
| Recurring panel | None | “Recurring/Flagged Issues” section with pattern, property, asset, count, suggested action. |
| Empty states | Per-card messages | Portfolio: “No maintenance issues have been recorded across your portfolio.” + Add Issue, View Properties. Filtered: “No issues match your current filters.” |

---

## 7. IMPLEMENTATION ORDER (SAFEST, ADDITIVE)

1. **Clarify primary content (no mixed list):** Make the main block the **Issues** queue only. Relabel or move the current “Open issues” (work orders) so it’s clearly “Work orders” and secondary (e.g. link in header or compact section). No deletion of behaviour yet – just structure and labels.
2. **Summary row:** Compute client-side from loaded issues (total open, new, high severity, ready for WO, monitoring, recurring from recurrence_flag). Optional: backend summary later for click-to-filter.
3. **Filters:** Add Source, Asset (if backend adds asset_id filter), Date range (from/to); add Search (q) when backend supports it, or client-side filter on description/issue_id/property label.
4. **Issues table:** Replace triaged-issues list with a proper table (columns per task); add row actions: View (open drawer), Create Work Order (and show “View Work Order” when linked WO exists once backend or frontend supports it).
5. **Issue detail drawer:** Add drawer on Issues page that opens on View; load issue by id; show full detail and triage; actions: Create WO / View WO, View Property, Close (and Edit, Link Asset when PATCH exists). Keep `/operations/issues/:issueId` for direct links.
6. **Recurring panel:** Simple version: list issues where `recurrence_flag === true` with property/asset/category and “Investigate / Create inspection” style copy. Richer: backend recurring-patterns endpoint + panel.
7. **Backend (additive):** Optional summary and/or extended list params (q, source, asset_id, from, to); optional linked_work_order_id; PATCH issue for status/asset_id (and optionally description) for Edit/Link Asset/Close.

---

## 8. FILES TO TOUCH (WHEN IMPLEMENTING)

- **Frontend:** `ClientIssuesPage.js` (structure, summary, filters, issues table, drawer, recurring panel, empty states); optionally `ClientIssueDetailPage.js` (link back, or keep as-is for deep link).
- **API:** `frontend/src/api/client.js` – add params to getMaintenanceIssues if backend extends; add updateMaintenanceIssue if PATCH added.
- **Backend:** `backend/routes/client_maintenance.py` (list params, optional summary, PATCH issue); `backend/services/maintenance_issues_service.py` (list_issues filters, optional summary, update_issue).

---

## 9. OUTPUT CHECKLIST (FOR TASK DELIVERABLES)

- **Files changed:** As in §8.
- **Endpoints reused:** GET/POST `/client/maintenance/issues`, GET `/client/maintenance/issues/:id`, POST `.../create-work-order`. Created: optional PATCH issue; optional summary/recurring in GET list or new route.
- **Filters implemented:** Status, Severity, Property, Category (existing); add Source, Asset, Date range, Search (q) when backend supports.
- **Issue → work order handoff:** Already implemented via `createWorkOrderFromIssue`; extend UI to “Create Work Order” from table/drawer; add “View Work Order” when linked (via backend linked_work_order_id or frontend match).
- **Placeholder/fallback:** Recurring panel can start with recurrence_flag list; “Link Asset” and “Close” depend on PATCH issue; “View Work Order” can be hidden or “Open work orders” link until linked WO is exposed.
