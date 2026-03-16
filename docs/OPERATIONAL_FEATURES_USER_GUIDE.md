# Operational Features: User Guide and System Behaviour

This document explains how **Issues**, **Work Orders**, **Contractors**, **Risk Signals**, **Assets**, and **Approvals** work from a user’s perspective, how they connect to the rest of the platform, and their current implementation status.

---

## 1. User workflows (step by step)

### Issues (Maintenance issues)

**Where:** Client portal → **Operations** → **Issues** (`/operations/issues`). Also reachable from the dashboard “Issues” card and from Work Orders (“View Issues”).

**Gating:** Feature flag **MAINTENANCE_WORKFLOWS** must be enabled for the client (plan or override).

**User flow:**

1. User opens **Operations → Issues** and sees a list of issues (filters: property, status, category, severity, source, date range).
2. **Create issue:** Clicks “Add issue”, selects a property, enters description, optional category/asset/reporter/urgency/photos, and submits.
3. **Automatic triage:** On create, the system runs triage (severity, priority score, SLA hours, recommended contractor type, reasoning). The issue is stored with status `triaged` and the triage result is shown on the issue.
4. **View issue:** User can open an issue in a drawer or full page (`/operations/issues/:issueId`) and see description, category, severity, status, triage result (e.g. SLA hours, recommended contractor type), and linked asset if any.
5. **Create work order from issue:** From the issue detail, user clicks “Create work order”. The system creates a work order linked to that issue (`issue_id`), copies description/category/severity/asset from the issue, sets SLA from triage, and marks the issue as `ready_for_work_order`. User is taken to Work Orders or the new work order.

**Actions:** List/filter issues, create issue, view issue, create work order from issue. No “edit issue” or “close issue” in the described client API; status is updated when a work order is created from it.

---

### Work Orders

**Where:** Client portal → **Operations** → **Work Orders** (`/operations/work-orders`). Admin: **Admin → Ops → Maintenance** (`/admin/ops/maintenance`) and work order detail `/admin/ops/maintenance/work-orders/:workOrderId`.

**Gating:** **MAINTENANCE_WORKFLOWS**.

**User flow (client):**

1. User opens **Operations → Work Orders** and sees a list (filters: property, status, contractor, asset, date, SLA state: breached / near_breach / on_track).
2. **Create work order (two ways):**
   - **From Issues:** As above, “Create work order” from an issue (work order then has `issue_id`).
   - **Direct:** “Add work order” with property, description, optional category, severity, asset, issue (if already known), cost estimates. Triage can run on create if severity/SLA not provided.
3. **View work order:** Opens in a drawer or detail view: description, status, property, asset, issue link, contractor (if assigned), SLA respond-by/complete-by, breach state, cost estimates.
4. **Update work order:** Client can update status, assign a contractor (if **CONTRACTOR_NETWORK** is enabled and contractor is visible to them), set resolution outcome, cost estimates.
5. **Contractor recommendation:** On a work order, user can request “Recommend contractors”; the system returns suggested contractors by trade match and performance (requires **CONTRACTOR_NETWORK**).

**User flow (admin):**

- Admin sees all work orders (optional filter by client). Can create work orders (with client_id, property_id, etc.), assign contractors, update status and resolution. Work order detail page is fully implemented.

**Status lifecycle:** DRAFT → OPEN → ASSIGNED → SCHEDULED → IN_PROGRESS → AWAITING_PARTS → COMPLETED → VERIFIED → CLOSED, or CANCELLED.

---

### Contractors

**Where:** Client portal → **Operations** → **Contractors** (`/operations/contractors`). Admin: **Admin → Ops → Contractors** (`/admin/ops/contractors`).

**Gating:**  
- **Client:** Contractors list and assignment to work orders require **CONTRACTOR_NETWORK** (and **MAINTENANCE_WORKFLOWS** for work orders).  
- **Admin:** Contractors CRUD is under Ops; no separate feature flag for admin.

**User flow (client):**

1. User opens **Operations → Contractors** and sees contractors available to their organisation (client_id filter or network contractors with `client_id` null).
2. List shows name, company, trade types, contact, vetted status. User can use contractors when assigning a work order (dropdown or “Recommend contractors” on a work order).

**User flow (admin):**

1. **List:** Filter by client, vetted only, source_type, status.
2. **Create:** Add contractor (name, trade types, vetted, contact, company, client_id, areas_served, notes) or add to **Contractor Network** (company, trade types, contact, region, credentials, insurance; then `client_id=null`, vetted, visible to all orgs).
3. **Update/delete:** Edit contractor details, status, credentials, insurance.

**System:** Contractors are linked to work orders via `contractor_id`. “Recommend contractors” uses trade and performance to suggest who to assign. Client can only assign contractors that are “visible” to their client_id (their own or network).

---

### Risk Signals

**Where:** Client portal → **Operations** → **Risk Signals** (`/operations/risk-signals`). Also per-property: **Property detail** → **Risk signals** tab. Dashboard has a “Risk signals” card linking to `/operations/risk-signals`.

**Gating:** **PREDICTIVE_MAINTENANCE**.

**User flow:**

1. User opens **Operations → Risk Signals** (portfolio view) or a **Property** → **Risk signals** tab.
2. **List:** Sees stored risk signals with property, risk type, risk level, trend, status (active / acknowledged / resolved), reasons, recommended action. Filters: property, status, risk_level, risk_type, trend, date, search.
3. **Detail:** Opens a signal to see full reasons, recommended action, and (per property) which assets or compliance data contributed.
4. **Recalculate:** On a property, user can trigger “Recalculate risk signals” to regenerate signals from current property data (assets, work orders, issues, compliance).
5. **Status:** User can set a signal to **acknowledged** or **resolved** (no automatic creation of issues or work orders).

**Important:** Risk signals are **informational**. They do not auto-create issues or work orders. The user is expected to act on the “recommended action” (e.g. “Schedule boiler inspection”) by creating an issue or work order themselves if they choose.

**Risk types (examples):** Boiler Failure Risk, Damp/Moisture Risk, Electrical Risk, Recurring Repairs Risk, SLA Breach Risk, Compliance Churn Risk, Maintenance Frequency Risk. Signals are rule-based (property age, asset age, repeat issues, missed SLAs, compliance overdue, etc.).

---

### Assets

**Where:** **Property detail** → **Assets** tab. There is no top-level “Operations → Assets” route; assets are always in the context of a property.

**Gating:** **MAINTENANCE_WORKFLOWS** or **PREDICTIVE_MAINTENANCE** (either enables the Assets tab).

**User flow:**

1. User opens a **Property** and selects the **Assets** tab.
2. **List:** Sees assets for that property (type, name, status, install date, last service, make/model, age, notes). Summary may show counts or health.
3. **Add asset:** “Add asset” or “Initialise assets” (ensure default set). User provides asset_type, name, status, install_date, last_service_date, make, model, notes, etc.
4. **Ensure defaults:** “Initialise Assets” creates a default set of assets for the property if missing (idempotent).
5. **View asset:** Opens an asset with recent events (issue_created, repair_completed, inspection_completed, etc.).
6. **Update asset:** Edit name, status, last_service_date, make, model, age, notes.

**Links:** Issues and work orders can reference an `asset_id`. Creating an issue with a category can auto-infer and link an asset. Risk signals use asset data (e.g. boiler age). Asset events record when issues are created or other events occur for that asset.

---

### Approvals (Invoice approvals)

**Where:** Client portal → **Operations** → **Approvals** (`/operations/approvals`).

**Gating:** **INVOICING**.

**User flow:**

1. User opens **Operations → Approvals** and sees a list of invoices (approval items) with filters: status (pending / approved / rejected / needs_info), contractor, property, work order, benchmark fit, date range, search (ref, contractor, property, work order).
2. **Summary:** KPIs such as pending count, approved this month, rejected, needs info, out-of-range (above benchmark) value.
3. **Detail:** Opens an invoice to see reference, description, amount, contractor, property, work order link, benchmark fit, documents/notes.
4. **Action:** User **approves**, **rejects**, or **needs info** with optional notes. Status and audit (e.g. INVOICE_APPROVED, INVOICE_REJECTED, INVOICE_NEEDS_INFO) are updated.
5. **Export:** Export filtered list as CSV.

**Links:** Invoices reference `work_order_id`, `contractor_id`, `property_id`. So approvals are the step “after” work orders and contractors in the flow: work done → invoice submitted → approval/reject. Invoice creation (who submits invoices into the system) is not exposed in the client or admin routes reviewed; approvals assume invoices already exist (e.g. from admin or integration).

---

## 2. System connections

| Module        | Linked to                                                                 | How |
|---------------|---------------------------------------------------------------------------|-----|
| **Issues**    | Properties, Assets, Work orders                                           | Issue has property_id, optional asset_id. “Create work order from issue” sets issue_id on the work order and updates issue status. |
| **Work orders** | Properties, Assets, Issues, Contractors, Invoices                      | work_order has property_id, optional asset_id, issue_id, contractor_id. Invoices reference work_order_id. |
| **Contractors** | Work orders, Invoices                                                    | contractor_id on work orders and invoices. Visibility by client_id or network (client_id null). |
| **Risk signals** | Properties, Assets, Work orders, Issues, Compliance (requirements)     | Generated from property + assets + work_orders + issues + requirements (e.g. overdue EICR). Stored per property/client; no automatic issue/wo creation. |
| **Assets**    | Properties, Issues, Work orders, Risk signals, Events                    | asset_id on issues and work orders. Risk rules use asset age/type. Asset events log issue_created, repairs, etc. |
| **Approvals** | Invoices → Work orders, Contractors, Properties                          | Invoice has work_order_id, contractor_id, property_id; approval is the review step for that invoice. |

**Compliance:** Risk signals can use compliance data (e.g. overdue or missing requirements). Properties, requirements, and certificates are in the compliance side; issues/work orders/contractors/assets/approvals are the “operations” side, linked by property_id and optionally by reminders/evidence (e.g. completing a repair and uploading a cert could be done outside this flow; the platform links via property and assets).

**Reminders / automation:** No direct link from reminder jobs to creating issues or work orders in the code paths reviewed. Risk signals are generated by a scheduled job (`risk_signals_job`) for clients with PREDICTIVE_MAINTENANCE; that only writes risk_signals, it does not create issues.

---

## 3. Triggers and flows

**Risk signal → issue → work order → contractor → approval (conceptual):**

- **Risk signal:** Generated by scheduled job or manual “Recalculate” from property/assets/work orders/issues/compliance. **Does not** create issues or work orders.
- **Issue:** Created **manually** by user (or in future by tenant/API). Triage runs on create.
- **Work order:** Created **manually** either (1) from an issue (“Create work order from issue”) or (2) directly (Add work order). Optionally linked to issue_id and asset_id.
- **Contractor:** Assigned **manually** to a work order (client or admin). Recommendation API can suggest contractors.
- **Invoice/Approval:** Invoices are stored with work_order_id/contractor_id/property_id. User **approves/rejects/needs info** in Approvals. There is no automatic “work order completed → create invoice” in the routes reviewed; invoice creation is elsewhere (admin or integration).

**Event summary:**

| Event                         | Trigger                          | Result |
|------------------------------|-----------------------------------|--------|
| User creates issue           | Submit form on Issues             | Issue stored, triage run, optional asset event. |
| User clicks “Create work order from issue” | Button on issue detail      | Work order created with issue_id; issue status → ready_for_work_order. |
| User creates work order       | Add work order (client or admin)  | Work order stored; optional triage; optional issue_id/asset_id. |
| User assigns contractor       | Update work order with contractor_id | Work order updated; audit CONTRACTOR_ASSIGNED_TO_WORK_ORDER. |
| Scheduled job (risk_signals_job) | Cron                            | For clients with PREDICTIVE_MAINTENANCE, generates/refreshes risk_signals. |
| User recalculates risk signals | “Recalculate” on property        | Regenerates risk signals for that property. |
| User approves/rejects invoice | Action on Approvals               | Invoice status and audit updated. |

---

## 4. Value to the user

- **Issues:** Single place to report and triage problems (by property/asset). Triage gives severity, SLA, and recommended contractor type so the user can decide to create a work order and who to assign.
- **Work orders:** Track jobs from open to closed, SLA (respond/complete), breach state, and cost. Link to issue and asset keeps context. Assigning contractors connects to the contractor pool.
- **Contractors:** Reuse a vetted pool (own + network), match by trade, and use recommendations to assign the right contractor to a job.
- **Risk signals:** Proactive view of property/portfolio risk (boiler age, damp, electrical, SLA breaches, compliance churn). Recommended actions guide what to do (inspect, repair, review) without automating creation of issues/work orders.
- **Assets:** Record what equipment exists per property, link issues and work orders to the right asset, and feed risk rules (e.g. boiler age). Events give a simple history per asset.
- **Approvals:** Central place to approve or reject invoices linked to work orders and contractors, with benchmark fit and export for finance.

Together they support: **compliance** (risk and evidence context), **maintenance** (issue → work order → contractor), and **risk** (signals and SLAs).

---

## 5. Access and usage

| Feature        | Client portal (property manager / landlord)     | Admin (platform operator) |
|----------------|--------------------------------------------------|----------------------------|
| **Issues**     | Operations → Issues (MAINTENANCE_WORKFLOWS)      | Not a separate admin Issues UI; admin can create work orders with issue_id. |
| **Work orders**| Operations → Work Orders (MAINTENANCE_WORKFLOWS); create, list, update, assign contractor (if CONTRACTOR_NETWORK) | Ops → Maintenance; list all, create, assign, update; work order detail page. |
| **Contractors**| Operations → Contractors (CONTRACTOR_NETWORK); list and use for assignment | Ops → Contractors; full CRUD, network. |
| **Risk signals**| Operations → Risk Signals + Property → Risk signals tab (PREDICTIVE_MAINTENANCE) | Ops → Risk & Insights is a placeholder; risk data is client-scoped. |
| **Assets**     | Property detail → Assets tab (MAINTENANCE_WORKFLOWS or PREDICTIVE_MAINTENANCE) | No dedicated admin Assets page; assets are per property under client. |
| **Approvals**  | Operations → Approvals (INVOICING)               | No separate Approvals UI in admin routes reviewed; invoices are client-scoped. |

**Tenant:** No tenant-facing Issues/Work orders/Contractors/Risk/Assets/Approvals in the routes reviewed; tenants have property view and compliance pack, not operations.

---

## 6. Implementation status

| Module        | Client portal (UI + API)        | Admin (UI + API)           | Backend services / jobs      | Notes |
|---------------|----------------------------------|----------------------------|-----------------------------|--------|
| **Issues**    | Implemented: list, create, get, create WO from issue; gated by MAINTENANCE_WORKFLOWS | No dedicated Issues UI; APIs are client-scoped | maintenance_issues_service, triage; issue → work order flow implemented | End-to-end for client. |
| **Work orders** | Implemented: list, create, get, update, recommend contractors; SLA and filters | Implemented: list, create, update, assign; detail page | maintenance_service, SLA fields, contractor assignment | End-to-end. |
| **Contractors** | Implemented: list, use in assignment (CONTRACTOR_NETWORK) | Implemented: list, get, create, update, network create | contractor_service, visibility, recommend for work order | End-to-end. |
| **Risk signals** | Implemented: list (portfolio + by property), get, recalculate, update status (ack/resolve) | Ops “Risk & Insights” is placeholder text only | risk_signal_service, rule-based generation; job `risk_signals_job` runs for PREDICTIVE_MAINTENANCE clients | Client flow complete; admin has no risk UI. |
| **Assets**    | Implemented: list/add/ensure defaults/get/update/events per property (Property → Assets tab) | No dedicated admin Assets list; assets are under client properties | property_assets_service, asset events, default assets | End-to-end for client at property level. |
| **Approvals** | Implemented: list, get, approve/reject/needs_info, export CSV; gated by INVOICING | Invoice creation API not found in reviewed routes | approval_service, invoice labels, audit actions | Approval workflow implemented; invoice **creation** (who/how invoices get into `invoices`) is not in the reviewed code (may be admin-only or external). |

**Summary:**

- **Issues, Work orders, Contractors, Assets:** Implemented end-to-end for the client (and admin where applicable). Gated by feature flags (MAINTENANCE_WORKFLOWS, CONTRACTOR_NETWORK, PREDICTIVE_MAINTENANCE).
- **Risk signals:** Implemented for the client (view, recalculate, acknowledge/resolve); scheduled job generates signals. Admin has no risk UI (placeholder page).
- **Approvals:** Implemented for reviewing/approving invoices linked to work orders and contractors; invoice creation path is outside the documented routes.

**Gaps / partial:**

1. **Invoice creation:** No client or admin route found that inserts into `invoices`; approvals assume invoices exist. May exist in another module or integration.
2. **Admin Risk UI:** Admin → Ops → Risk & Insights is a placeholder; no list/detail of risk signals for all clients.
3. **Issue lifecycle:** No explicit “close issue” or “edit issue” in the described client APIs; issue status changes when “Create work order from issue” is used.
4. **Tenant-reported issues:** Work order source includes `tenant_request` in the model, but tenant-facing issue reporting was not found in the reviewed routes; may be planned or elsewhere.

---

## Quick reference: feature flags

- **MAINTENANCE_WORKFLOWS:** Issues, Work orders, client-side Assets tab, maintenance flows.
- **PREDICTIVE_MAINTENANCE:** Risk signals, predictive insights, Assets tab (if not already enabled by MAINTENANCE_WORKFLOWS), property events.
- **CONTRACTOR_NETWORK:** Contractor list and assignment to work orders for the client.
- **INVOICING:** Approvals (invoice approval workspace).

Defaults depend on plan (e.g. Solo: compliance only; Portfolio: + maintenance + predictive; Pro: + contractors). INVOICING is off by default in the plan defaults reviewed.
