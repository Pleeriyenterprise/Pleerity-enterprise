# Contractor Workflow Deliverables

This document summarizes the contractor-side operational flow implemented for Pleerity: contractor portal access, work order interaction, invoice self-submission, approval integration, optional application flow, and audit.

---

## 1. Files created or modified

### Backend – created
- `backend/services/contractor_portal_auth_service.py` – Contractor portal accounts (email, password); create, get by email/contractor_id, verify password.
- `backend/routes/contractor_portal.py` – Contractor API: list/my work orders, get one, update status/notes/evidence, accept/decline assignment, submit invoice, profile.

### Backend – modified
- `backend/models/core.py` – Added `UserRole.ROLE_CONTRACTOR`; added audit actions: `CONTRACTOR_ACCEPTED_ASSIGNMENT`, `CONTRACTOR_DECLINED_ASSIGNMENT`, `CONTRACTOR_WORK_ORDER_STATUS_CHANGED`, `CONTRACTOR_EVIDENCE_UPLOADED`, `CONTRACTOR_INVOICE_SUBMITTED`.
- `backend/database.py` – Indexes for `contractor_portal_accounts` (email unique, contractor_id unique, status).
- `backend/middleware.py` – `contractor_route_guard`: requires JWT with `role=ROLE_CONTRACTOR` and `contractor_id`.
- `backend/routes/auth.py` – `POST /api/auth/contractor-login` (email/password → JWT with contractor_id); `POST /api/auth/contractor-set-password` (token + password for contractor invite).
- `backend/routes/contractors.py` – `POST /api/admin/ops/contractors/:id/invite-portal`: create password token (purpose=contractor_invite, metadata contractor_id + email), send invite email (recipient in context), return setup_url.
- `backend/services/maintenance_service.py` – Work order fields: `contractor_notes`, `completion_notes`, `evidence_keys`; `update_work_order` accepts these and `evidence_keys_append`.
- `backend/server.py` – Registered `contractor_portal.router`.

### Frontend – created
- `frontend/src/pages/contractor/ContractorLoginPage.js` – Contractor login; stores token in localStorage; redirects to `/contractor`.
- `frontend/src/pages/contractor/ContractorSetPasswordPage.js` – Set password from invite link (`/contractor-set-password?token=...`); stores token and redirects to `/contractor`.
- `frontend/src/pages/contractor/ContractorDashboardPage.js` – Lists assigned work orders; detail drawer with accept/decline, status update, submit invoice.

### Frontend – modified
- `frontend/src/api/client.js` – `authAPI.contractorLogin`, `authAPI.contractorSetPassword`; `createContractorAPI(accessToken)` for contractor endpoints; `adminAPI.inviteContractorToPortal(contractorId)`.
- `frontend/src/App.js` – Routes: `/contractor/login`, `/contractor-set-password`, `/contractor` (dashboard).

---

## 2. Contractor portal / access

- **Auth:** Contractors do not use client portal accounts. Separate `contractor_portal_accounts` collection: `contractor_id`, `email` (unique), `password_hash`, `status` (active/inactive).
- **Login:** `POST /api/auth/contractor-login` (email, password) → JWT with `role=ROLE_CONTRACTOR`, `contractor_id`, `email`. Contractor must exist and have `status=active`.
- **Set password:** Invite link uses token with `purpose=contractor_invite` and `metadata: { contractor_id, email }`. `POST /api/auth/contractor-set-password` (token, password) creates or updates `contractor_portal_accounts` and returns access token.
- **Invite:** Admin calls `POST /api/admin/ops/contractors/:contractor_id/invite-portal`; backend creates token, sends email with link to `/contractor-set-password?token=...`, returns `setup_url` for copy-paste if needed.
- **Frontend:** Contractor login at `/contractor/login`; set-password at `/contractor-set-password`; dashboard at `/contractor`. Token stored in `localStorage` under `contractor_token`; dashboard reads it and uses `createContractorAPI(token)` for all contractor API calls.
- **Scope:** Contractors only see work orders where `contractor_id` matches their own.

---

## 3. Work order interaction

- **List:** `GET /api/contractor/work-orders` – returns work orders assigned to the authenticated contractor; response enriched with `property_address` where possible.
- **Detail:** `GET /api/contractor/work-orders/:id` – single work order; 404 if not assigned to contractor.
- **Update:** `PATCH /api/contractor/work-orders/:id` – body: `status`, `contractor_notes`, `completion_notes`, `evidence_keys` (append). Allowed statuses for contractor: `SCHEDULED`, `IN_PROGRESS`, `AWAITING_PARTS`, `COMPLETED`. Audit: `CONTRACTOR_WORK_ORDER_STATUS_CHANGED`, `CONTRACTOR_EVIDENCE_UPLOADED` when applicable.
- **Accept:** `POST /api/contractor/work-orders/:id/accept` – sets status to `SCHEDULED`. Audit: `CONTRACTOR_ACCEPTED_ASSIGNMENT`.
- **Decline:** `POST /api/contractor/work-orders/:id/decline` – sets `contractor_id` to null and status to `OPEN`. Audit: `CONTRACTOR_DECLINED_ASSIGNMENT`.
- **Evidence:** Evidence is passed as `evidence_keys` (array of storage keys) in PATCH. Actual file upload and storage key generation are not implemented in this phase; the API accepts keys for when upload is added later.

---

## 4. Invoice self-submission

- **Endpoint:** `POST /api/contractor/invoices` – body: `work_order_id`, optional `reference`, `description`, `submitted_amount`, `currency`, `attachment_storage_key`.
- **Checks:** Work order must exist and be assigned to the contractor; `property_id` and `client_id` taken from the work order.
- **Service:** Uses existing `invoice_service.create_invoice(..., source=SOURCE_CONTRACTOR, created_by_id=contractor_id)`. Invoice has `work_order_id`, `contractor_id`, `property_id`, `client_id`; status `pending` so it appears in Approvals.
- **Audit:** `CONTRACTOR_INVOICE_SUBMITTED`.
- **Approval:** Contractor cannot approve their own invoice; approval is done by client/admin via existing Approvals flow (`PATCH /api/client/approvals/:invoice_id` with action approve/reject/needs_info). Contractor-submitted invoices appear in client Approvals like any other invoice.

---

## 5. Admin / client approval flow

- Contractor-submitted invoices use the same `invoices` collection and approval workflow as admin/client-created invoices.
- They appear in **client** Approvals (`GET /api/client/approvals`) and can be approved, rejected, or marked needs_info via existing `PATCH /api/client/approvals/:invoice_id`.
- Admin can create invoices via `POST /api/admin/ops/invoices` and can oversee clients’ approvals in the same way as before. Audit actions `INVOICE_APPROVED`, `INVOICE_REJECTED`, `INVOICE_NEEDS_INFO` already exist and apply to contractor-originated invoices.
- Linkage: each invoice stores `work_order_id`, `contractor_id`, `property_id`, `client_id`; approval history is in `invoice_approvals`; audit logs reference these IDs.

---

## 6. Contractor profile / application flow

- **Self-registration:** Already present. Public `POST /api/public/contractors/register` (or equivalent under `/contractors/register`) creates a contractor with `status=pending_review`, `source_type=self_registered`, via `contractor_service.create_contractor_self_registered`. Gated by `CONTRACTOR_SELF_REGISTRATION_ENABLED` (or equivalent). No automatic activation; only approved contractors are visible/assignable.
- **Portal access:** No portal account is created at registration. Admin must invite the contractor to the portal via `POST /api/admin/ops/contractors/:id/invite-portal` after approval. So: application → pending_review → admin approves (status=active) → admin invites to portal → contractor sets password and logs in.

---

## 7. Observability / audit

- **Contractor actions:**  
  - `CONTRACTOR_ACCEPTED_ASSIGNMENT`  
  - `CONTRACTOR_DECLINED_ASSIGNMENT`  
  - `CONTRACTOR_WORK_ORDER_STATUS_CHANGED` (metadata: old_status, new_status)  
  - `CONTRACTOR_EVIDENCE_UPLOADED` (metadata: keys_count)  
  - `CONTRACTOR_INVOICE_SUBMITTED` (metadata: work_order_id, submitted_amount)
- **Approval decisions:** Existing `INVOICE_APPROVED`, `INVOICE_REJECTED`, `INVOICE_NEEDS_INFO` cover contractor-submitted invoices.
- All of these are written via `create_audit_log` with `resource_type`, `resource_id`, `client_id` where applicable, and `actor_id` (contractor_id for contractor actions).

---

## 8. Remaining gaps / future work

- **Evidence upload:** API accepts `evidence_keys` (array of storage keys). A proper upload flow (e.g. presigned URL or multipart upload to object storage and returning keys) is not implemented; can be added later and keys then sent in PATCH.
- **Contractor “forgot password”:** No self-service reset for contractor portal; admin can send a new invite link.
- **Contractor dashboard UX:** Notes/evidence can be extended (e.g. inline notes field, upload UI that calls a new upload endpoint and then PATCH with new keys).
- **Admin UI:** “Invite to portal” button on contractor detail in admin Ops Contractors; optional list of contractor portal accounts or invite status.
- **Email template:** Invite email uses `ADMIN_MANUAL` with `recipient` in context; a dedicated `CONTRACTOR_PORTAL_INVITE` template can be added for branding and copy.

---

## 9. Summary

| Item | Status |
|------|--------|
| Contractor portal / access | Implemented (separate auth, login, set-password, invite) |
| Work order list/detail (contractor-scoped) | Implemented |
| Accept / decline assignment | Implemented |
| Contractor status updates (scheduled, in progress, etc.) | Implemented |
| Contractor notes and evidence keys | Implemented (evidence as keys; upload flow deferred) |
| Contractor invoice self-submission | Implemented; flows to existing Approvals |
| Admin/client approval of contractor invoices | Confirmed (same approval flow) |
| Contractor self-registration/application | Already present (controlled, pending_review; no auto-activation) |
| Audit logging for contractor and approval actions | Implemented |
