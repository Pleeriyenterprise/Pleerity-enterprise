# Operations → Approvals Page: Codebase Audit

**Task:** Implement the top-level Operations → Approvals page as an enterprise-grade invoice and work-order approval workspace.  
**Constraint:** Additive only; preserve existing routes and schemas; no full accounting integration; gate behind INVOICING feature flag.

This document records what is **implemented**, what is **missing**, any **conflicts**, and a **recommended implementation plan**. No implementation was done until the plan is approved.

---

## 1. Current State Summary

| Area | Status | Notes |
|------|--------|--------|
| **Route** | Exists | `/operations/approvals` → `ClientApprovalsPage` (App.js) |
| **Page** | Placeholder only | "Coming soon" card; no queue, KPIs, filters, or drawer |
| **Feature flag** | Exists | `invoicing` in nav (ClientPortalLayout); INVOICING in backend |
| **Backend API** | **Missing** | No `/api/approvals` or invoice/approval endpoints |
| **DB collections** | **Missing** | No `invoices` or `invoiceApprovals`; no indexes |
| **Locked state** | Partial | EntitlementProtectedRoute shows UpgradeRequired; no Approvals-specific copy |

---

## 2. Implemented vs Missing (by requirement)

### 2.1 Page purpose and structure

- **Implemented:** Route and placeholder page; Operations nav item "Approvals" (feature: `invoicing`).
- **Missing:** All five sections: Summary KPI row, Filter + Search bar, Approval queue table, Benchmark/Exception panel, Approval detail drawer.

### 2.2 Summary KPI row (Section 3)

- **Implemented:** Nothing.
- **Missing:** Backend summary (pending, approvedThisMonth, rejected, needsInfo, outOfRange, totalPendingValue); frontend cards; click-to-apply filter behaviour.

### 2.3 Filter + search bar (Section 4)

- **Implemented:** Nothing.
- **Missing:** Filters (approval status, contractor, property, work order, benchmark fit, date range); search (invoice ref, contractor name, property name/address, work order ref). Backend must support query params: `status`, `contractorId`, `propertyId`, `workOrderId`, `benchmarkFit`, `q`, `from`, `to`.

### 2.4 Approval queue table (Section 5)

- **Implemented:** Nothing.
- **Missing:** Table columns (Invoice Ref, Property, Work Order, Contractor, Submitted Amount, Benchmark Range, Benchmark Fit, Approval Status, Submitted At, Actions); actions View / Approve / Reject / Needs Info; visual cues for above-benchmark.

### 2.5 Approval detail drawer (Section 6)

- **Implemented:** Nothing.
- **Missing:** Right-side drawer with header, linked context (property, work order, asset, issue), financial review block, approval actions, history/timeline.

### 2.6 Approval action rules (Section 7)

- **Implemented:** Nothing.
- **Missing:** Statuses Pending / Approved / Rejected / Needs Info; on action: timeline event, audit log, reviewer + timestamp + optional reason. **Audit pattern exists:** `utils/audit.create_audit_log` with `AuditAction`, `resource_type`/`resource_id`, `actor_id`, `metadata`. **No** `AuditAction` enum value for invoice approval yet (e.g. `INVOICE_APPROVED`, `INVOICE_REJECTED`, `INVOICE_NEEDS_INFO`).

### 2.7 Benchmark / exception panel (Section 8)

- **Implemented:** Nothing.
- **Missing:** "Review Exceptions" panel: above benchmark, missing work order, missing contractor, missing attachment; per-item quick action.

### 2.8 Work order linkage (Section 9)

- **Implemented:** Work orders exist: `work_orders` collection, `client_maintenance` and `maintenance` routes; client can list/get work orders via `clientAPI.getMaintenanceWorkOrders`, `getMaintenanceWorkOrder`.
- **Missing:** Approval records linking to `work_order_id`; exception badge and "Link Work Order" when missing (if safe).

### 2.9 Contractor linkage (Section 10)

- **Implemented:** Contractors and performance: `contractors`, `contractor_performance`; client `GET /client/contractors`; contractor list returns company_name, etc.
- **Missing:** Approval records linking to `contractor_id`; contractor detail link and prior performance in approval UI.

### 2.10 Backend expectations (Section 11)

- **Implemented:** None of the suggested model or API.
- **Missing:**
  - Collections: `invoices` (or equivalent), `invoice_approvals` (or `invoiceApprovals`). Task suggests `invoices` + `invoiceApprovals`; naming: codebase uses snake_case for collections (e.g. `work_orders`, `audit_logs`). **Recommendation:** Use `invoices` and `invoice_approvals` for consistency.
  - Invoice fields: _id, orgId → use `client_id` (codebase standard), propertyId → `property_id`, workOrderId → `work_order_id`, contractorId → `contractor_id`, reference, submittedAmount, currency, description, attachmentStorageKey, benchmarkMin/Max, benchmarkFit ("below"|"within"|"above"|"none"), submittedAt, status.
  - invoiceApprovals fields: _id, invoiceId → `invoice_id`, reviewerId → `reviewer_id`, action ("approved"|"rejected"|"needs_info"), notes, createdAt.
  - Endpoint: task says `GET /api/approvals`. All client-scoped APIs live under `/api/client` (e.g. `/api/client/contractors`, `/api/client/maintenance/work-orders`). **Recommendation:** Use `GET /api/client/approvals` (and `PATCH /api/client/approvals/{id}` or similar for actions) to stay consistent and reuse client_route_guard + INVOICING check.

### 2.11 Export (Section 12)

- **Implemented:** Nothing.
- **Missing:** CSV export of current filtered queue with columns: Invoice Ref, Property, Work Order, Contractor, Submitted Amount, Benchmark Range, Benchmark Fit, Approval Status, Submitted At, Reviewed At, Reviewer. Can be same endpoint with `?format=csv` or a dedicated `GET /api/client/approvals/export`.

### 2.12 Feature flag / locked state (Section 13)

- **Implemented:** Approvals nav item uses `feature: 'invoicing'`; page wrapped in `<EntitlementProtectedRoute requiredFeature="invoicing">`. When disabled, user sees generic `UpgradeRequired` (card + "Back to Dashboard"). Backend exposes `features.invoicing` from `get_effective_flags(INVOICING)` (client.py).
- **Missing:** Task asks for "locked page state" that "explain[s] what the Approvals page does" and "upgrade CTA". Current behaviour already shows upgrade CTA. **Gap:** `UpgradePrompt.js` has no `invoicing` in `FEATURE_DISPLAY` (or `FEATURE_MIN_PLAN`), so the title/description fall back to "invoicing" and empty. **Recommendation:** Add `invoicing` to `FEATURE_DISPLAY` (and optionally `FEATURE_MIN_PLAN`) so the locked state says e.g. "Invoice & work order approvals" and a short description.

### 2.13 Empty states (Section 14)

- **Implemented:** Nothing.
- **Missing:** Empty state copy and buttons (View Work Orders, View Contractors); filtered-empty copy.

### 2.14 Design rules (Section 15)

- **Implemented:** N/A (design).
- **Missing:** Apply enterprise tone, status badges, benchmark labels, drawer workflow, responsive layout (no accounting clutter).

---

## 3. Conflicts and Recommendations

### 3.1 Endpoint path: `/api/approvals` vs `/api/client/approvals`

- **Spec:** "Suggested endpoint: GET /api/approvals".
- **Codebase:** Client operations use `/api/client/*` and `client_route_guard`.
- **Recommendation:** Implement **GET /api/client/approvals** (and action PATCH on same resource or sub-path). Do not add a separate `/api/approvals` without client context; that would bypass client guard and require a different auth story. If product explicitly requires a shared "approvals" prefix for future multi-tenant or admin view, add a separate admin route later; for this task, client-only is correct.

### 3.2 Collection naming: `invoiceApprovals` vs `invoice_approvals`

- **Spec:** "invoiceApprovals".
- **Codebase:** MongoDB collections use snake_case (`work_orders`, `contractor_ratings`, `audit_logs`).
- **Recommendation:** Use **invoice_approvals** (and **invoices**) for consistency and to avoid mixing conventions.

### 3.3 Org vs client

- **Spec:** "orgId" for invoices.
- **Codebase:** Client-scoped data uses `client_id` everywhere (properties, work_orders, contractors, etc.).
- **Recommendation:** Use **client_id** on invoices and approval records. No "org" abstraction in this scope.

### 3.4 Locked state: generic vs Approvals-specific copy

- **Spec:** "show locked page state; explain what the Approvals page does; show upgrade CTA."
- **Current:** EntitlementProtectedRoute shows UpgradeRequired with generic feature name/description when feature not in FEATURE_DISPLAY.
- **Recommendation:** Add **invoicing** to **FEATURE_DISPLAY** in `UpgradePrompt.js` with name e.g. "Invoice & work order approvals" and description explaining the page (review/approve invoices linked to work orders). No need for a separate Approvals-specific locked component unless product requests it.

### 3.5 Timeline / history for approvals

- **Spec:** "log timeline event; log audit event" and drawer "History / timeline: submitted, reviewed, approved/rejected/info requested."
- **Codebase:** `create_audit_log` in `utils/audit.py`; `AuditAction` enum in `models/core.py` has no invoice-related actions. Portfolio timeline filters by `_TIMELINE_ACTIONS` and does not include approval actions.
- **Recommendation:** (1) Add audit actions for approval decisions (e.g. `INVOICE_APPROVED`, `INVOICE_REJECTED`, `INVOICE_NEEDS_INFO`) and call `create_audit_log` on each action with `resource_type="invoice"`, `resource_id=invoice_id`, and metadata (reviewer, amount, status). (2) Drawer "History" can be built from **invoice_approvals** records (and optional audit_log entries for same resource_id). No need to expose approval actions in the portfolio-wide audit timeline for this task; keep timeline scoped to existing event set unless product asks to show approval events there.

---

## 4. Reuse and Integration Points

- **Auth:** Use existing `client_route_guard` (client.py pattern) and require INVOICING from `get_effective_flags(client_id)`; 403 with clear message if disabled.
- **Work orders:** `maintenance_service.get_work_order`, `list_work_orders`; client API `getMaintenanceWorkOrders`, `getMaintenanceWorkOrder`. Approvals API can return embedded or resolved property/work order labels for list/drawer.
- **Contractors:** `contractor_service.list_contractors_for_client`, single contractor by id; client API `getContractors`. Contractor name/link and optional performance summary in approval UI.
- **Properties:** Client properties list for filters and labels; no new endpoint needed if approvals response includes property_id and frontend has property list (or backend resolves names).
- **Audit:** `create_audit_log(AuditAction.INVOICE_*, ...)` with client_id, resource_type="invoice", resource_id=invoice_id, actor_id=portal_user_id, metadata={ notes, amount, status }.
- **Feature flag:** Same as today: nav shows Approvals only when `invoicing` enabled; page guard and backend check INVOICING.

---

## 5. Recommended Implementation Plan (additive only)

1. **Backend – data and indexes**
   - Add collections **invoices** and **invoice_approvals** (no schema change to existing collections).
   - In `database.py` (or equivalent index creation), add indexes for:
     - invoices: (client_id, status), (client_id, submitted_at), (work_order_id sparse), (contractor_id sparse), (property_id); unique id if using invoice_id.
     - invoice_approvals: (invoice_id), (invoice_id, created_at).

2. **Backend – models**
   - Define lightweight Pydantic/models for invoice and invoice_approval (optional; can work with raw dicts). Add **AuditAction** values: e.g. INVOICE_APPROVED, INVOICE_REJECTED, INVOICE_NEEDS_INFO.

3. **Backend – API**
   - New module (e.g. `routes/client_approvals.py` or under `client.py`) under prefix `/api/client`:
     - **GET /api/client/approvals** – query params: status, contractorId, propertyId, workOrderId, benchmarkFit, q, from, to; return `{ summary, approvals, exceptions }`; gate with INVOICING.
     - **GET /api/client/approvals/{id}** – single approval/invoice detail for drawer (optional if list is enough; else implement for drawer).
     - **PATCH /api/client/approvals/{id}** – body: action (approved|rejected|needs_info), notes; update invoice status, insert invoice_approvals row, call create_audit_log.
     - **GET /api/client/approvals/export** (or `?format=csv` on list) – CSV of current filtered list with required columns.
   - Register router in server.py; ensure client_route_guard and INVOICING check on all handlers.

4. **Frontend – feature display**
   - In `UpgradePrompt.js`, add **invoicing** to FEATURE_DISPLAY (and optionally FEATURE_MIN_PLAN) so locked state shows correct title and description.

5. **Frontend – API client**
   - In `client.js` (clientAPI): add getApprovals(params), getApproval(id), updateApproval(id, body), exportApprovals(params) (or equivalent).

6. **Frontend – ClientApprovalsPage**
   - Replace placeholder with:
     - **Summary KPI row:** Cards from API summary; click to set filter where practical.
     - **Filter + search bar:** Status, contractor, property, work order, benchmark fit, date range; free text search; call API with params.
     - **Approval queue table:** Columns and actions as per spec; link to work order and contractor where available.
     - **Review Exceptions panel:** From API exceptions array; show reason and quick action.
     - **Detail drawer:** On row click or View: header, linked context, financial block, actions (Approve/Reject/Needs Info), history from invoice_approvals (and optional audit).
   - Empty states: no items vs no results for filters; buttons View Work Orders / View Contractors.
   - Export: button calling export API and triggering download.

7. **Placeholders / fallbacks**
   - If no work orders or contractors in DB, filters can still work; "Link Work Order" only if product allows (e.g. optional in phase 1 or behind same INVOICING flag).
   - Benchmark range: "No benchmark" when benchmarkMin/Max missing; benchmarkFit "none".
   - Attachment: attachmentStorageKey optional; drawer shows "No document attached" when null.

8. **Testing**
   - Manual: enable INVOICING for a client, create test invoices (via seed or minimal admin endpoint if needed), verify list/filter/drawer/approve/reject/export and locked state when INVOICING off.
   - No existing routes or flows changed; only new collections, new routes, and replacement of placeholder page content.

---

## 6. Files to Touch (summary)

| Location | Action |
|----------|--------|
| `backend/database.py` | Add indexes for `invoices`, `invoice_approvals` |
| `backend/models/core.py` | Add AuditAction values for invoice approval |
| `backend/routes/client_approvals.py` (new) or `client.py` | GET/PATCH approvals, export; INVOICING gate |
| `backend/server.py` | Register client approvals router |
| `frontend/src/components/UpgradePrompt.js` | Add invoicing to FEATURE_DISPLAY (and optionally FEATURE_MIN_PLAN) |
| `frontend/src/api/client.js` | getApprovals, getApproval, updateApproval, exportApprovals |
| `frontend/src/pages/ClientApprovalsPage.js` | Full page: KPIs, filters, table, exceptions panel, drawer, empty states, export |

---

## 7. Acceptance Criteria Checklist (post-implementation)

- [x] Approvals page loads portfolio-wide approval items (via GET /api/client/approvals).
- [x] Summary cards and filters work; drawer supports review actions.
- [x] Benchmark exception panel present; work order and contractor linkage visible.
- [x] Export CSV works for current filtered set.
- [x] Locked state when invoicing disabled: explains Approvals and shows upgrade CTA.
- [x] No existing routes or flows broken.

---

*Audit completed. Implementation to follow only after approval of this plan.*
