# Operations Gap Closure Summary

This document describes the platform upgrade that closed the key operational gaps to make Pleerity a more enterprise-grade Property Compliance OS. It covers what was implemented, end-to-end flows, premium/enterprise value added, what remains partial, and what needs runtime QA.

---

## 1. Gaps Closed

### 1.1 Invoice creation flow (Part 1)

**Problem:** Approvals existed but invoice creation was missing; the chain Issue → Work Order → Contractor → Invoice → Approval was broken.

**Implemented:**

- **Backend**
  - New `services/invoice_service.py`: `create_invoice()` with validation of work order, contractor, and property belonging to client. Sets `status=pending`, computes `benchmark_fit` from optional benchmark_min/max. Audit: `INVOICE_CREATED`.
  - **Admin:** `POST /api/admin/ops/invoices` — admin can create an invoice for any client (body: client_id, property_id, contractor_id, work_order_id, reference, description, submitted_amount, currency, benchmark_min/max, attachment_storage_key). Router: `routes/admin_invoices.py`.
  - **Client:** `POST /api/client/invoices` — client can create an invoice for their own work order (body: property_id, contractor_id, work_order_id, reference, description, submitted_amount, etc.). Gated by INVOICING. In `routes/client_approvals.py`.
  - New audit action: `AuditAction.INVOICE_CREATED`.

**End-to-end chain now:** Issue → Work Order → Contractor assigned → Work completed → **Invoice created** (admin or client) → Approval decision → Audit trail.

**Remains partial:** Contractor self-submission of invoices (e.g. contractor portal upload) was not implemented; only admin and client manual creation. Attachment upload (e.g. S3 key) is passed as `attachment_storage_key` if the client already has an upload flow.

---

### 1.2 Risk signals → actionable operations (Part 2)

**Problem:** Risk signals were informational only; users had to manually bridge from insight to action.

**Implemented:**

- **Backend**
  - `maintenance_issues_service.create_issue()`: optional `risk_signal_id` stored on the issue.
  - `maintenance_service.create_work_order()`: optional `risk_signal_id` stored on the work order.
  - `risk_signal_service.create_issue_from_risk_signal(signal_id, client_id, description_override, reporter_id)`: loads signal, creates issue with description from risk_type + recommended_action, links `risk_signal_id`, audits `ISSUE_CREATED_FROM_RISK_SIGNAL`.
  - `risk_signal_service.create_work_order_from_risk_signal(...)`: same pattern for work order; audits `WORK_ORDER_CREATED_FROM_RISK_SIGNAL`.
  - **Client API:** `POST /api/client/maintenance/risk-signals/{signal_id}/create-issue` and `POST .../create-work-order` (optional body: `description_override`). Require PREDICTIVE_MAINTENANCE and MAINTENANCE_WORKFLOWS.
- **Frontend**
  - Client Risk Signals page: in the signal detail drawer, "Create issue from signal" and "Create work order from signal" buttons call the new APIs. Success toasts and optional navigate to Operations.

**Value:** Users can one-click create an issue or work order from a risk signal; the new record is linked back to the signal for traceability and audit.

---

### 1.3 Tenant issue reporting (Part 3)

**Problem:** Model supported `source=tenant_request` but there was no tenant-facing issue submission path.

**Implemented:**

- **Backend**
  - `maintenance_issues_service`: added `SOURCE_TENANT_REQUEST = "tenant_request"`.
  - **Tenant API:** `POST /api/tenant/report-issue` — body: property_id, description, category (optional), photos (optional). Validates tenant has access to the property (tenant_route_guard + assignment). Creates a maintenance **issue** (not work order) via `create_issue()` with `source=SOURCE_TENANT_REQUEST`, reporter name/contact from tenant user. Triage runs automatically. Audit: `TENANT_ISSUE_REPORTED`.
  - Existing `POST /api/tenant/report-maintenance` remains and still creates a work order directly (backward compatible).

**Flow:** Tenant reports issue → issue created with triage → landlord sees it in Operations → Issues. Optional: landlord creates work order from issue.

**Remains partial:** Tenant UI for "Report issue" (form calling `POST /api/tenant/report-issue`) was not added in this pass; only the API. Photo upload for tenant is accepted in the API (photos array) but storage/upload flow is not implemented.

---

### 1.4 Admin risk dashboard (Part 4)

**Problem:** Admin "Risk & Insights" was a placeholder.

**Implemented:**

- **Backend**
  - `risk_signal_service.get_risk_signals_admin_summary(client_id_filter, risk_level, risk_type, status_filter, limit_signals)`: aggregates risk signals across clients (or one client). Returns totalActive, totalSignals, byLevel, byType, topProperties (property_id + count), topClients (client_id + count), recentSignals.
  - **Admin API:** `GET /api/admin/ops/risk-signals/summary` with query params: client_id, risk_level, risk_type, status, limit.
- **Frontend**
  - New `AdminRiskDashboardPage.js`: replaces placeholder at `/admin/ops/risk`. Shows KPIs (active signals, by level, top properties/clients), filters (client, risk level, status), by-type breakdown, top affected properties/clients, and a recent signals table. Uses `adminAPI.getRiskSignalsSummary(params)`.

---

### 1.5 Issue lifecycle completion (Part 5)

**Problem:** Issue lifecycle was incomplete; no clear edit/close path; status set was limited.

**Implemented:**

- **Backend**
  - Extended status set: `open`, `new`, `triaged`, `monitoring`, `investigating`, `ready_for_work_order`, `in_progress`, `resolved`, `closed`, `cancelled` (and `ALL_ISSUE_STATUSES`).
  - `maintenance_issues_service.update_issue(issue_id, client_id, status=..., description=..., category=..., updated_by_id)`: updates status and/or description, category. Does not allow reopening closed/cancelled. On status change, audits `ISSUE_STATUS_UPDATED` or `ISSUE_CLOSED` (when new status is resolved/closed/cancelled).
  - **Client API:** `PATCH /api/client/maintenance/issues/{issue_id}` — body: status, description, category (all optional).
- **Frontend:** No dedicated issue detail page was changed in this pass; the API supports issue edit/close from any client UI that calls it.

**Remains partial:** Issue detail page "timeline/history" of status changes would require either storing a separate history collection or reading from audit_logs filtered by resource_type=maintenance_issue and resource_id=issue_id. Not implemented.

---

### 1.6 Compliance → operations integration (Part 6)

**Existing behaviour (retained):** The risk signal engine already bridges compliance to operations:

- `_rule_compliance_churn`: overdue/missing compliance items (requirements) produce risk signals with recommended actions.
- `_rule_electrical`: EICR-related and electrical compliance data feed into risk signals.

So compliance findings already lead to risk signals; with Part 2, users can then create issues/work orders from those signals. No new automation was added (e.g. auto-create issue on EICR expiry) to avoid noisy false positives; the bridge is "compliance → risk signal → user confirms → issue/work order".

**Documentation:** This flow is described in OPERATIONAL_FEATURES_USER_GUIDE.md and in the architecture doc.

---

### 1.7 Enterprise value / retention (Part 7)

**Implemented:**

- **Cross-linking:** Issues and work orders now store `risk_signal_id` when created from a risk signal. Client Risk Signals UI has explicit "Create issue from signal" and "Create work order from signal" actions.
- **Client API:** `createInvoice` for client; `createIssueFromRiskSignal`, `createWorkOrderFromRiskSignal` for risk signal actions.
- **Admin:** Risk dashboard is operational (filters, drill-down via recent list). Admin can create invoices via `POST /api/admin/ops/invoices`.
- **Gating:** All new endpoints respect existing feature flags (INVOICING, MAINTENANCE_WORKFLOWS, PREDICTIVE_MAINTENANCE). No new placeholder pages were left for these flows.

**Client "Record invoice" (added):** On the client Work Orders page, when viewing a work order that has a contractor assigned, a "Record invoice" button opens a modal to create an invoice linked to that work order (property_id, contractor_id, work_order_id, optional reference, description, amount). Submit calls `clientAPI.createInvoice()`; on success the user is directed to Operations → Approvals. Gated by `invoicing` feature.

**Remains partial:** Issue detail and work order detail UIs could show a direct link to the linked risk signal (e.g. "Created from risk signal: …"). These cross-links are in the data model but not all wired in the UI.

---

### 1.8 Audit / observability (Part 8)

**Implemented:**

- **New audit actions (models/core.py):** `INVOICE_CREATED`, `ISSUE_CREATED_FROM_RISK_SIGNAL`, `WORK_ORDER_CREATED_FROM_RISK_SIGNAL`, `ISSUE_STATUS_UPDATED`, `ISSUE_CLOSED`, `TENANT_ISSUE_REPORTED`.
- **Logged flows:**
  - Invoice creation (admin and client).
  - Issue/work order created from risk signal.
  - Issue status updates and closure.
  - Tenant issue report.

Metadata on audit records include resource_type, resource_id, and relevant IDs (e.g. signal_id, work_order_id, old_status/new_status) for traceability.

---

## 2. End-to-end flows now supported

| Flow | Status |
|------|--------|
| Issue → Work order → Contractor → **Invoice created** → Approval | ✅ Supported (admin or client creates invoice) |
| Risk signal → **Create issue** (user confirm) → Issue in Operations | ✅ Supported |
| Risk signal → **Create work order** (user confirm) → Work order in Operations | ✅ Supported |
| **Tenant report issue** → Issue created (triage) → Landlord sees in Issues | ✅ API + tenant UI (dashboard modal + property page form) |
| Admin risk dashboard: portfolio risk visibility, filters, top properties/clients | ✅ Supported |
| Issue status lifecycle: edit status, resolve, close, cancel | ✅ Supported (API); UI can call PATCH |

---

## 3. What remains partial / future work

- **Contractor invoice submission:** No contractor portal flow to submit an invoice; only admin and client creation.
- **Tenant report-issue UI:** Implemented: dashboard modal (Issue vs Work order + category) and property detail page "Report maintenance issue" form.
- **Tenant photo upload:** `photos` array accepted in report-issue; actual file upload and storage keys not implemented.
- **Issue timeline:** No dedicated issue history/timeline UI; data can be derived from audit logs.
- **UI cross-links:** Issue detail showing linked risk_signal and work order detail showing linked invoice/approval could be added for clarity.

---

## 4. Runtime QA suggestions

- **Invoice creation:** Create a work order, assign contractor, then use "Record invoice" in the work order drawer (client) or admin API; confirm invoice appears in Approvals and can be approved/rejected.
- **Risk signal actions:** As a client with PREDICTIVE_MAINTENANCE and MAINTENANCE_WORKFLOWS, open a risk signal, click "Create issue from signal" and "Create work order from signal"; confirm new issue/work order have `risk_signal_id` and appear in Operations.
- **Tenant report-issue:** Call `POST /api/tenant/report-issue` with a tenant token and valid property_id; confirm issue is created with source=tenant_request and appears in client Issues list.
- **Admin risk dashboard:** As admin, open `/admin/ops/risk`; confirm summary, filters, and recent signals load; optional: run risk signal generation job for a client first.
- **Issue update/close:** PATCH an issue with status=resolved or status=closed; confirm audit log has ISSUE_STATUS_UPDATED/ISSUE_CLOSED and issue no longer allows creating work order.

---

## 5. Files created/modified (summary)

**Created:**

- `backend/services/invoice_service.py`
- `backend/routes/admin_invoices.py`
- `frontend/src/pages/admin/AdminRiskDashboardPage.js`
- `docs/OPERATIONS_GAP_CLOSURE_SUMMARY.md` (this file)
- `docs/PLEERITY_SYSTEM_ARCHITECTURE.md` (see below)

**Modified:**

- `backend/models/core.py` — new AuditAction values
- `backend/services/approval_service.py` — (unchanged; invoice creation is in invoice_service)
- `backend/services/maintenance_issues_service.py` — SOURCE_TENANT_REQUEST, risk_signal_id, status set, update_issue()
- `backend/services/maintenance_service.py` — risk_signal_id on work order
- `backend/services/risk_signal_service.py` — get_risk_signals_admin_summary(), create_issue_from_risk_signal(), create_work_order_from_risk_signal()
- `backend/routes/client_approvals.py` — POST /invoices, CreateInvoiceBody
- `backend/routes/client_maintenance.py` — PATCH /maintenance/issues/:id, create-issue/create-work-order from risk signal
- `backend/routes/ops_compliance.py` — GET /risk-signals/summary
- `backend/routes/tenant.py` — ReportIssueBody, POST /report-issue
- `backend/server.py` — include admin_invoices router
- `frontend/src/App.js` — AdminRiskDashboardPage route for /admin/ops/risk
- `frontend/src/api/client.js` — getRiskSignalsSummary, createInvoice (admin + client), createIssueFromRiskSignal, createWorkOrderFromRiskSignal
- `frontend/src/pages/ClientRiskSignalsPage.js` — Suggested actions: Create issue from signal, Create work order from signal
- `frontend/src/pages/ClientMaintenancePage.js` — "Record invoice" button in work order drawer + modal (gated by invoicing)
- `frontend/src/pages/TenantDashboard.js` — Report modal: Issue (report-issue) vs Work order (report-maintenance), category for issue
- `frontend/src/pages/TenantPropertyDetailPage.js` — "Report maintenance issue" card with form (report-issue)
