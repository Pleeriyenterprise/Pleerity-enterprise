# Maintenance, Contractors & Predictive Maintenance — Runbook

**Purpose:** How to enable and use maintenance workflows, the contractor network, predictive maintenance insights, and the data that feeds them. Complements the Admin + Intake Runbook.

---

## 1. Feature flags that control access

| Flag | Default (Solo / Portfolio / Pro) | Effect when **on** |
|------|----------------------------------|---------------------|
| **MAINTENANCE_WORKFLOWS** | Off / Off / On | Client can list and create work orders; tenant can report a repair. Admin can manage work orders and assign contractors. |
| **CONTRACTOR_NETWORK** | Off | Admin can manage contractors (list, create, edit, delete). Work orders can be assigned to a contractor. |
| **PREDICTIVE_MAINTENANCE** | Off | Client and admin can view predictive insights (property age, assets, maintenance events). Client can add property assets and maintenance events. |

**How to turn on for a client:** Admin → **Operations & Compliance** → **Feature Controls** → select client → toggle the flag (Owner/Admin only). See `ADMIN_INTAKE_RUNBOOK.md` §1.

---

## 2. Contractors (admin)

**Where:** Admin → **Operations & Compliance** → **Contractors**.

**Actions:**

- **List:** All contractors, or filter by client (preferred contractor for that client) and/or “Vetted only”.
- **Create:** Add contractor with name, trade types (e.g. plumbing, electrical, gas), email, phone, company, areas served, vetted flag. Optionally link to a **client_id** (client-preferred) or leave blank (system-wide).
- **Edit / Delete:** Use row actions. Only Owner/Admin can create/update/delete.

**API (admin):**

- `GET /api/admin/ops/contractors` — list (query: `client_id`, `vetted_only`, `skip`, `limit`).
- `GET /api/admin/ops/contractors/{contractor_id}` — one contractor.
- `POST /api/admin/ops/contractors` — create (body: name, trade_types, vetted, email, phone, company_name, client_id, areas_served, notes). Owner/Admin only.
- `PATCH /api/admin/ops/contractors/{contractor_id}` — update. Owner/Admin only.
- `DELETE /api/admin/ops/contractors/{contractor_id}` — delete. Owner/Admin only.

**Data:** Stored in `contractors` collection (`contractor_id`, `client_id`, `name`, `trade_types`, `vetted`, etc.).

---

## 3. Work orders (maintenance)

**Flow:** Tenant or client creates a “report” → work order is created with status **OPEN**. Admin (or future contractor flow) can **assign** a contractor and update **status** (OPEN → ASSIGNED → IN_PROGRESS → COMPLETED or CANCELLED). SLA fields (`sla_respond_by`, `sla_complete_by`) are set on create; optional jobs can use them later.

### 3.1 Client portal (landlord)

**Where:** Client portal → **Maintenance** (nav). Visible when the client has **MAINTENANCE_WORKFLOWS** (backend returns 403 otherwise; UI shows a friendly message).

**Actions:**

- **List** work orders for the client (optional filters: property, status).
- **Create** work order: select property, description, optional category/severity.

**API (client):**

- `GET /api/client/maintenance/work-orders` — list (query: `property_id`, `status`, `skip`, `limit`). Requires MAINTENANCE_WORKFLOWS.
- `POST /api/client/maintenance/work-orders` — create (body: `property_id`, `description`, `category?`, `severity?`). Requires MAINTENANCE_WORKFLOWS.

### 3.2 Tenant portal

**Where:** Tenant dashboard → expand a property → **Report a repair**.

**Actions:**

- Tenant describes the issue; submits → `POST /api/tenant/report-maintenance` with `property_id` and `description`. Creates a work order with `source: tenant_request`. Landlord’s account must have **MAINTENANCE_WORKFLOWS** enabled, and tenant must have access to that property.

**API (tenant):**

- `POST /api/tenant/report-maintenance` — body: `property_id`, `description` (optional: `category`, `severity`). Creates work order; server may set severity from description (e.g. “leak” → urgent).

### 3.3 Admin

**Where:** Admin → **Operations & Compliance** → **Maintenance**.

**Actions:**

- List work orders (filter by client, status, contractor).
- Create work order (client, property, description).
- **Assign contractor** to a work order (dropdown).
- **Update status** (OPEN → ASSIGNED → IN_PROGRESS → COMPLETED / CANCELLED).

**API (admin):**

- `GET /api/admin/ops/work-orders` — list (query: `client_id`, `property_id`, `status`, `contractor_id`, `skip`, `limit`).
- `GET /api/admin/ops/work-orders/{work_order_id}` — one.
- `POST /api/admin/ops/work-orders` — create (body: `client_id`, `property_id`, `description`, `category?`, `severity?`). Owner/Admin only.
- `PATCH /api/admin/ops/work-orders/{work_order_id}` — update (body: `status?`, `contractor_id?`). Owner/Admin only.

**Data:** `work_orders` collection (`work_order_id`, `client_id`, `property_id`, `description`, `source`, `reporter_id`, `category`, `severity`, `status`, `contractor_id`, `sla_respond_by`, `sla_complete_by`, `created_at`, `completed_at`, etc.).

---

## 4. Predictive maintenance (insights)

**What it does:** Reads **property_assets**, **maintenance_events**, and property **building_age_years**; runs simple heuristics (e.g. boiler >15 years or last service >12 months, building >50 years) and returns **insights** per property (risk, recommendation).

**Gating:** **PREDICTIVE_MAINTENANCE** must be on for the client.

### 4.1 Client

**Where:** Client portal → **Maintenance** page can show a “Predictive insights” section (if the feature is enabled and API returns data).

**API (client):**

- `GET /api/client/maintenance/predictive-insights` — returns `{ client_id, properties: [ { property_id, nickname, address_line_1, postcode, building_age_years, insights[], assets_count, events_count } ] }`. Requires PREDICTIVE_MAINTENANCE.

### 4.2 Admin

**Where:** Admin can view a client’s predictive insights (e.g. Feature Controls or a dedicated client drill-down).

**API (admin):**

- `GET /api/admin/ops/clients/{client_id}/predictive-insights` — same shape as client response, for that client’s properties. Admin only.

**Data used:**

- **properties.building_age_years** — already on property (intake/provisioning).
- **property_assets** — per-property assets (e.g. boiler, install_date, last_service_date). See §5.
- **maintenance_events** — history of repairs/services per property. See §5.

---

## 5. Data for predictive (property assets & maintenance events)

To get useful predictive insights, properties should have **assets** (e.g. boiler with install date and last service) and optionally **maintenance_events** (repairs, inspections).

### 5.1 Client (when PREDICTIVE_MAINTENANCE is on)

**APIs (client):**

- `GET /api/client/maintenance/properties/{property_id}/assets` — list assets for a property. Requires PREDICTIVE_MAINTENANCE.
- `POST /api/client/maintenance/properties/{property_id}/assets` — add asset (body: `asset_type`, `install_date?`, `last_service_date?`, `notes?`). Requires PREDICTIVE_MAINTENANCE.
- `GET /api/client/maintenance/properties/{property_id}/events` — list maintenance events (query: `limit`). Requires PREDICTIVE_MAINTENANCE.
- `POST /api/client/maintenance/properties/{property_id}/events` — add event (body: `event_type`, `occurred_at?`, `outcome?`, `asset_id?`, `notes?`). Requires PREDICTIVE_MAINTENANCE.

### 5.2 Admin

**Where:** Admin → **Operations & Compliance** → use **Predictive data** (or equivalent) if a dedicated UI exists; otherwise use APIs.

**API (admin):** See `routes/predictive_data.py` for admin-only endpoints to create/update property assets and maintenance events for any client/property.

**Collections:**

- **property_assets:** `property_id`, `asset_id`, `client_id`, `asset_type`, `install_date`, `last_service_date`, `notes`, etc. Unique on `(property_id, asset_id)`.
- **maintenance_events:** `event_id`, `property_id`, `client_id`, `event_type`, `occurred_at`, `outcome`, `asset_id?`, `notes`. Indexed by `property_id` and `occurred_at`.

---

## 6. Quick reference: enable maintenance for a landlord

1. Admin → **Operations & Compliance** → **Feature Controls** → select the client.
2. Turn **MAINTENANCE_WORKFLOWS** **On** (override if plan default is off).
3. (Optional) Turn **CONTRACTOR_NETWORK** **On** and add contractors under **Contractors**.
4. Client: they see **Maintenance** in the portal; they can list/create work orders.
5. Tenants: they see **Report a repair** on the tenant dashboard (per property); submissions create work orders for that client.
6. Admin: use **Maintenance** to assign contractors and update status.

---

## 7. Quick reference: enable predictive for a client

1. Admin → **Feature Controls** → select client → turn **PREDICTIVE_MAINTENANCE** **On**.
2. Client (or admin) adds **property assets** (e.g. boiler, install date, last service date) via client APIs or admin predictive-data APIs.
3. Optionally add **maintenance_events** (past repairs/services) so insights can use history.
4. Client and admin can call **predictive-insights** to see risk and recommendations per property.

---

## 8. Smoke test (maintenance & predictive)

**Prerequisites:** Admin access; at least one client with properties; optional: tenant user assigned to a property.

| Step | Action | Expected |
|------|--------|----------|
| 1 | Admin → **Feature Controls** → select client → turn **MAINTENANCE_WORKFLOWS** On. | Flag saved; client can use maintenance. |
| 2 | Log in as that client → open **Maintenance** in nav. | Maintenance tab visible; Work orders list loads (or empty). |
| 3 | Client → **Report issue** → select property, enter description → Submit. | Work order created; appears in list with status OPEN. |
| 4 | Admin → **Operations & Compliance** → **Maintenance** → find the work order → Assign contractor (dropdown) → set Status to ASSIGNED or COMPLETED. | Work order updated. |
| 5 | (Tenant) Log in as tenant → open property card → **Report a repair** → enter description → Submit. | Work order created with source `tenant_request`; landlord sees it in Maintenance. |
| 6 | Admin → **Feature Controls** → turn **PREDICTIVE_MAINTENANCE** On for client. | Flag saved. |
| 7 | Client → **Maintenance** page. | If assets/events or building_age exist, "Predictive insights" section shows recommendations; otherwise section may be empty or absent. |
| 8 | Admin → **Feature Controls** → select client → open **predictive-insights** (or Admin Ops API) `GET /api/admin/ops/clients/{client_id}/predictive-insights`. | Returns `{ client_id, properties: [ ... insights ] }`. |
| 9 | (Optional) Run predictive job manually: Admin → **Automation Control Centre** (or jobs API) → run `predictive_insights_job`. | Job completes; log shows "Predictive insights precomputed for N client(s)". |

**Duplicate admin route:** Predictive insights for a client are served only by `GET /api/admin/ops/clients/{client_id}/predictive-insights` (under **ops_compliance**). There is no duplicate under the maintenance router.

**Scheduled job:** `predictive_insights_job` runs daily at 04:00 UTC; it iterates clients with PREDICTIVE_MAINTENANCE and calls the insights logic (no persistent cache in current implementation; API computes on demand).

**Automated smoke test:** Run `pytest tests/test_maintenance_predictive_smoke.py -v` (backend must be running). Without env vars only unauthenticated behaviour is checked (401/403). Set `ADMIN_TOKEN` and optionally `CLIENT_TOKEN` to exercise authenticated endpoints; `BASE_URL` defaults to `http://localhost:8000` if not set.

---

## 9. Related docs

- **ADMIN_INTAKE_RUNBOOK.md** — feature flags, onboarding checklist, roles, plan limits.
- **CENTRAL_INTELLIGENCE_LAYER_ASSESSMENT.md** — vision vs build; what’s implemented (compliance, maintenance, contractors, predictive).
- **BUSINESS_FLOW_AND_USER_JOURNEY_REPORT.md** — end-to-end flow, triggers, collections.
