# Admin + Intake Runbook — Operations & Compliance

**Purpose:** How to use the Operations & Compliance admin features, onboarding checklist, feature flags, and plan limits.

---

## 1. How to enable a module for a client

Module access is controlled by **feature flags** (COMPLIANCE_ENGINE, COMPLIANCE_PACKS, MAINTENANCE_WORKFLOWS, PREDICTIVE_MAINTENANCE, CONTRACTOR_NETWORK, INVOICING). Defaults are derived from the client’s **billing plan**; you can override per client.

**Steps:**

1. In admin, go to **Operations & Compliance** → **Feature Controls**.
2. Select the **client** from the dropdown (by CRN or name).
3. View **Plan usage** (properties used/allowed, seats) and **Module flags** (On/Off, Source: plan_default or manual).
4. Click **Turn on** or **Turn off** for a module to set an override. Only **Owner** or **Admin** can change flags; changes are audited (FEATURE_FLAG_CHANGED).

**API (admin):**

- `GET /api/admin/ops/clients/{client_id}/feature-flags` — effective flags and source.
- `PATCH /api/admin/ops/clients/{client_id}/feature-flags` — body: `{ "updates": [ { "flag_key": "MAINTENANCE_WORKFLOWS", "enabled": true } ] }`. Owner/Admin only.

---

## 2. How the onboarding checklist works

The **server-driven onboarding checklist** appears for clients after first login (when the dashboard shows the setup flow). Items are derived from **plan** and **feature flags**.

**Checklist items (examples):**

- **Required:** Add properties, Set jurisdiction defaults.
- **Recommended:** Confirm property attributes, Invite team (Portfolio/Pro), Upload certificates (if compliance on), Enable maintenance (if flag on).

**Completion:**

- **Client:** Dashboard calls `GET /api/client/onboarding/checklist` for the list; completing a step calls `POST /api/client/onboarding/checklist/items/{item_id}/complete`. The server **validates** (e.g. “Add properties” only completes when the client has ≥1 property).
- **Stored on client:** `onboarding_checklist.items[]` (each with `id`, `completed_at`) and `onboarding_checklist.completed_at` when all required items are done.
- **Deep-links:** Each item has a `deep_link` (e.g. `/properties`, `/settings`) so the banner or checklist can send the user to the right screen.

**Admin:** No separate “edit checklist” UI; completion is driven by client actions and server validation. To reset or inspect, use the client document in MongoDB (`clients.onboarding_checklist`).

---

## 3. How to change roles

**Admin roles:** Owner, Admin, Support, Content, etc. (see `UserRole` in backend).

- **Owner / Admin:** Can change feature flags, plan-related settings, and other admin users’ roles. Use **Team Permissions** (or equivalent) in admin to invite, deactivate, or change role.
- **Auditor:** Read-only admin; implemented. Nav shows Dashboard, Operations & Compliance (view-only), and Settings → Audit Logs only. All write endpoints (e.g. PATCH feature flags, role changes) use `require_owner_or_admin` and return 403 for Auditor.

**API:**

- Role changes should be audited (`ROLE_CHANGED` or equivalent). Use existing admin user management endpoints; ensure only Owner/Admin can assign roles.

---

## 4. How to verify plan limits

**Property limit:**

- **Intake:** Submission is blocked if property count exceeds plan limit (Solo 2, Portfolio 10, Pro 25). Error: `PROPERTY_LIMIT_EXCEEDED` (403).
- **Post-login:** Adding a property calls `plan_registry.enforce_property_limit(client_id, new_count)`. If over limit, API returns 403 with upgrade message.
- **Admin:** In **Feature Controls**, after selecting a client, **Plan usage** shows “Properties: X / Y” and “(at limit)” when X ≥ Y.

**Seats:**

- **Plan usage** may show “Seats used: N” (portal_users count). `seats_allowed` can be added later per plan.

**API:**

- `GET /api/admin/ops/clients/{client_id}/plan-usage` — returns `properties_used`, `properties_allowed`, `properties_at_limit`, `seats_used`, `seats_allowed`.

---

## 5. Jurisdiction settings

- **Client:** `GET /api/client/settings/jurisdiction` and `PATCH /api/client/settings/jurisdiction` (body: `default_jurisdiction`, `enabled_jurisdictions`). Valid values: Scotland, England, Wales, Northern Ireland.
- **Default:** New clients can be migrated with `default_jurisdiction: "Scotland"` and `enabled_jurisdictions: ["Scotland", "England", "Wales", "Northern Ireland"]`.
- **Property:** Each property can have a `jurisdiction` field (same enum). Used by compliance rules and provisioning status.

---

## 6. Provisioning status (per property / module)

After a property is created or updated, the **provisioning hook** writes **provisioning_status** records (compliance, maintenance) with `status` (not_configured | configured | blocked) and `missing_fields[]`. This does **not** create obligations; it only records setup readiness for admin/UX.

**Collections:** `provisioning_status` — fields: `client_id`, `property_id`, `module_name`, `status`, `missing_fields`, `updated_at`.

---

*See also: docs/ADMIN_INTAKE_REPORT.md, docs/SENIOR_PRODUCT_ENGINEER_SPEC_ALIGNMENT_AND_RECOMMENDATION.md.*
