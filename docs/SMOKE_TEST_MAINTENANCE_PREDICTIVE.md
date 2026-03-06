# Smoke Test: Maintenance & Predictive Maintenance

**Purpose:** Manual verification that maintenance workflows, contractor assignment, tenant report, client maintenance page, and predictive insights work end-to-end. Run after deployment or major changes.

**Prerequisites:** Admin account, at least one client with portal access, optional tenant account linked to a property.

---

## 1. Feature flags (Admin)

1. Log in as **Admin** (or Owner).
2. Go to **Operations & Compliance** → **Feature Controls**.
3. Select a **client** that you will use for testing.
4. Turn **MAINTENANCE_WORKFLOWS** **On** (and optionally **PREDICTIVE_MAINTENANCE** **On**).
5. Save. Confirm the client’s plan usage and flags are shown correctly.

**Pass:** Flags toggle and persist; plan usage (properties used/allowed) is correct.

---

## 2. Contractors (Admin)

1. Go to **Operations & Compliance** → **Contractors**.
2. Click **Add contractor**. Enter name, trade types (e.g. `plumbing`, `electrical`), optional email/phone, optionally link to the test **client**, set **Vetted** if desired. Save.
3. Confirm the contractor appears in the list. Edit and change a field; save. Confirm the change is visible.
4. Filter by client (if you linked one) and by “Vetted only”; confirm filtering works.

**Pass:** Create, list, edit, and filter contractors without errors.

---

## 3. Work orders – Admin create & assign

1. Go to **Operations & Compliance** → **Maintenance**.
2. Click **Create work order**. Select the test **client**, enter a **property_id** that belongs to that client (e.g. from Properties list), enter a **description**. Save.
3. Confirm the work order appears in the list with status **OPEN**.
4. In the same row, use the **Assign…** dropdown to assign the contractor you created. Confirm status becomes **ASSIGNED** and the contractor name is shown.
5. Change **Status** to **IN_PROGRESS**, then to **COMPLETED**. Confirm updates persist.

**Pass:** Work order created, contractor assigned, status changes applied and visible.

---

## 4. Client portal – Maintenance page & nav

1. Log in as a **client user** whose account has **MAINTENANCE_WORKFLOWS** enabled (the one you toggled in §1).
2. In the client portal, confirm **Maintenance** appears in the top navigation.
3. Open **Maintenance**. You should see the work order(s) created in §3 (if for this client). No “Maintenance not enabled” message.
4. Click **Report issue**. Select a property, enter a description, submit. Confirm a new work order appears in the list.

**Pass:** Maintenance nav visible when flag is on; list and create work order succeed.

---

## 5. Client portal – Maintenance hidden when flag off

1. As **Admin**, go to **Feature Controls** and turn **MAINTENANCE_WORKFLOWS** **Off** for the same client (or use a different client that never had it).
2. Log in as that **client user**. Confirm **Maintenance** does **not** appear in the top navigation.
3. If the user manually goes to `/maintenance`, the page should show the “Maintenance not enabled” message (and API would return 403).

**Pass:** Nav item hidden and page shows friendly message when flag is off.

---

## 6. Predictive insights (Admin)

1. As **Admin**, go to **Operations & Compliance** → **Feature Controls** and ensure **PREDICTIVE_MAINTENANCE** is **On** for the test client (and that the client has at least one property).
2. Optionally add **property assets** or **maintenance events** via Admin APIs or client APIs (see runbook) so insights have data (e.g. building age, boiler last service).
3. Call **GET** `/api/admin/ops/clients/{client_id}/predictive-insights` (e.g. with Postman or curl) with admin auth. You should get `client_id` and `properties` array; each property may have `insights` (array of risk/recommendation/detail).

**Pass:** Response 200; structure has `properties[].insights`; no 404/500.

---

## 7. Predictive insights (Client) & block on Maintenance page

1. As **client user** with **PREDICTIVE_MAINTENANCE** enabled, open **Maintenance**.
2. If the client has any insights (from assets/events/building age), a **Predictive insights** card should appear above the work orders list, with property names and recommendations (e.g. “Boiler service overdue”, “Property over 50 years old”).
3. If there are no insights yet, the card may show “No insights yet” with a short explanation.
4. If **PREDICTIVE_MAINTENANCE** is off, the insights card should not appear (API returns 403; frontend does not show the block or shows empty).

**Pass:** When flag on and data exists, insights card shows; when no data or flag off, behaviour is correct.

---

## 8. Tenant – Report a repair

1. Ensure the test **client** has **MAINTENANCE_WORKFLOWS** enabled and has at least one property. Ensure a **tenant** is assigned to that property (tenant user with ROLE_TENANT and tenant_assignments for that property).
2. Log in as the **tenant**. Open the tenant dashboard.
3. Expand the property card. Click **Report a repair**.
4. Enter a short description (e.g. “Kitchen tap leaking”). Submit.
5. As **Admin**, go to **Maintenance**. Confirm a new work order with **source** “tenant_request” (or similar) and the same description. Optionally assign a contractor and update status.

**Pass:** Tenant can submit; work order appears in admin with correct client/property and source.

---

## 9. Scheduled job – Predictive insights precompute

1. Confirm the **predictive_insights_job** is scheduled (e.g. daily) in the backend (see `server.py` and `job_runner.py`).
2. In **Admin** → **System Health** or **Automation Control Centre**, check **Job runs** for `predictive_insights_job`. After a run, there should be a successful run record (or inspect logs for “Predictive insights precomputed for N client(s)”).
3. No functional change is required for the API: the job warms insights per client with PREDICTIVE_MAINTENANCE; the live API still computes on demand. This step only verifies the job runs without error.

**Pass:** Job appears in job runs and completes successfully (or logs show no errors).

---

## 10. Quick API checklist (optional)

| Role   | Method | Endpoint | Purpose |
|--------|--------|----------|---------|
| Admin  | GET    | `/api/admin/ops/contractors` | List contractors |
| Admin  | GET    | `/api/admin/ops/work-orders` | List work orders |
| Admin  | GET    | `/api/admin/ops/clients/{id}/predictive-insights` | Insights for client |
| Client | GET    | `/api/client/maintenance/work-orders` | List own work orders (requires MAINTENANCE_WORKFLOWS) |
| Client | POST   | `/api/client/maintenance/work-orders` | Create work order |
| Client | GET    | `/api/client/maintenance/predictive-insights` | Own insights (requires PREDICTIVE_MAINTENANCE) |
| Tenant | POST   | `/api/tenant/report-maintenance` | Report repair (body: `property_id`, `description`) |

Use 403 as expected when the relevant feature flag is off for that client.

---

**Sign-off:** Once all sections pass, the maintenance and predictive flow is smoke-tested. For automated regression, consider adding pytest or Playwright tests that call the APIs and assert on status and response shape.
