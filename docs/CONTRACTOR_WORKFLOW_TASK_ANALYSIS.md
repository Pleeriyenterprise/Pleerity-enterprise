# Contractor Workflow — Task vs Codebase Analysis

This document compares the **new task requirements** (Parts 1–9: secure job links + optional portal, payment tracking, etc.) with the **current implementation** to identify what is implemented, what is missing, and any conflicts. **No implementation is done in this document;** it is for review and planning only.

---

## Conflict: Access Model

| Requirement | Current implementation | Conflict |
|-------------|------------------------|----------|
| **"Do not require contractor login to interact with assigned jobs"** and **"Secure job links (no login required)"** as primary | Contractor interaction is **login-only** via `/api/contractor/*` (JWT with `ROLE_CONTRACTOR` and `contractor_id`). No token-based job link exists. | **Yes.** Current design requires portal login (or invite → set password → login) to view/accept/update work orders or submit invoices. |
| **"Optional contractor portal accounts"** | Portal is the **only** way contractors can interact. | Adding **secure job links** would introduce a second, login-free path. |

**Recommended approach (safest and most professional):**

1. **Keep the existing contractor portal** as the “optional portal” path (Part 7). No removal or breaking change.
2. **Add the secure job link path** as a **parallel** access method:
   - On **contractor assignment**, generate a **job access token** (scoped to that work_order_id + contractor_id), store it (e.g. hashed), set expiry (e.g. 90 days).
   - **Assignment notification email** includes a **secure job link** (e.g. `{frontend_base}/job/{token}` or `?job_token=...`) in addition to any existing body text.
   - **New public (or semi-public) API** and **new frontend page**: accept `job_token` (in URL or header); validate token → return single work order and allow accept/decline, status updates, notes, evidence keys, invoice submission. No JWT required for that path.
3. **Single backend service layer** for work order updates and invoice submission: both the **contractor portal** (JWT) and the **job link** (token) paths call the same business logic; only auth differs (JWT vs job_token validation).
4. **Audit:** Both paths log the same events; actor can be `contractor_id` (and optionally “via_job_link: true” in metadata for analytics).

This avoids duplication of business logic and keeps the portal as the optional, richer experience (list all jobs, profile, invoice history).

---

## Part 1 — Contractor assignment notification

| Requirement | Status | Notes |
|-------------|--------|--------|
| When contractor assigned: generate secure job access token | **Missing** | No job token is created. Assignment only sends email and records in `contractor_assignments`. |
| Send contractor email: property, job description, due date, secure job link | **Partial** | Email is sent via `CONTRACTOR_ASSIGNED` (template alias `admin-manual`) with body containing work_order_id, description, property_address. **No** due date in body, **no** secure job link. |
| Log notification event | **Partial** | Notification send is logged as `EMAIL_SENT` with `event_type=CONTRACTOR_ASSIGNED` in metadata (in notification_orchestrator). No dedicated audit log entry for “contractor assigned to work order” in `maintenance_service` when admin assigns (client path logs `CONTRACTOR_ASSIGNED_TO_WORK_ORDER` in client_maintenance). |

**To fulfil Part 1:**

- Add job token generation and storage when a contractor is assigned (in `maintenance_service.update_work_order` or caller).
- Include in assignment email: due date (e.g. `sla_complete_by`), secure job link (URL containing or using the token).
- Optionally: add explicit audit log for “contractor assigned” from admin path (e.g. `CONTRACTOR_ASSIGNED_TO_WORK_ORDER` or reuse existing) so both client and admin assignment are audited.

---

## Part 2 — Secure work order page (token-based)

| Requirement | Status | Notes |
|-------------|--------|--------|
| Page accessible via secure token | **Missing** | No token-based route or page. Only portal routes exist (`/contractor`, `/contractor/login`, etc.). |
| Contractor can: view job details, accept, decline, update status, upload photos/documents, add notes, mark complete, submit invoice | **N/A for token path** | All of this exists for **portal** (JWT) in `contractor_portal.py` and `ContractorDashboardPage.js`. For **token** path: need new public/semi-public API and a single-job page that use the job token instead of JWT. |
| Contractor cannot view unrelated jobs | **N/A** | Token must be scoped to one work_order_id (and optionally contractor_id) so the token-based page only exposes that job. |

**To fulfil Part 2:**

- Implement token validation middleware or helper (validate job_token → work_order_id, contractor_id, expiry).
- Add API routes that accept job_token (e.g. query param or header) and expose: GET work order (single), PATCH (status, notes, evidence_keys), POST accept, POST decline, POST invoice (same payload as portal). Reuse `maintenance_service` and `invoice_service` from contractor_portal.
- Add frontend route (e.g. `/job/:token` or `/job?token=...`) and a “secure work order” page that uses the token for all API calls and does not require login.

---

## Part 3 — Contractor status updates

| Requirement | Status | Notes |
|-------------|--------|--------|
| Statuses: accepted, scheduled, in_progress, awaiting_parts, completed | **Implemented (portal)** | Portal: accept sets status to `SCHEDULED`; contractor can set `SCHEDULED`, `IN_PROGRESS`, `AWAITING_PARTS`, `COMPLETED`. “accepted” is the action; status after accept is `SCHEDULED`. Align with task by treating “accepted” as the transition (already done). |
| Each change creates audit log | **Implemented** | `CONTRACTOR_WORK_ORDER_STATUS_CHANGED` (and accept/decline logs) in `contractor_portal.py`. |

**Gap:** If Part 2 (job link) is implemented, the same status update API must be callable with job_token and must write the same audit logs.

---

## Part 4 — Contractor invoice submission

| Requirement | Status | Notes |
|-------------|--------|--------|
| Submit invoice linked to work order | **Implemented (portal)** | `POST /api/contractor/invoices` with work_order_id, reference, description, amount, optional attachment_storage_key. |
| Stored: contractor_id, work_order_id, property_id, client_id | **Implemented** | `invoice_service.create_invoice` and DB store these. |
| Submitted invoices appear in Approvals | **Implemented** | Invoices with status `pending` appear in client Approvals; contractor source is supported. |

**Gap:** Task mentions “invoice_reference” — we have `reference`. “optional_attachment” — we have `attachment_storage_key`. No change needed. For job link path: same submit endpoint or a token-authenticated variant must be available.

---

## Part 5 — Client approval flow

| Requirement | Status | Notes |
|-------------|--------|--------|
| Client/admin: approve, reject, request_more_information | **Implemented** | `PATCH /api/client/approvals/:invoice_id` with action `approved` \| `rejected` \| `needs_info`. |
| Approval actions generate audit logs | **Implemented** | `INVOICE_APPROVED`, `INVOICE_REJECTED`, `INVOICE_NEEDS_INFO` in `approval_service.update_approval`. |

No gap.

---

## Part 6 — Payment tracking (no contractor payouts)

| Requirement | Status | Notes |
|-------------|--------|--------|
| After approval, client can mark invoice as paid | **Missing** | No “mark as paid” action or UI. |
| Invoice fields: payment_method, paid_at, payment_reference, notes | **Missing** | Invoice document has no `payment_method`, `paid_at`, `payment_reference`. Optional `notes` could be general; task likely means payment notes. |
| payment_method enum: bank_transfer, cash, card, cheque, other | **Missing** | Not in schema. |
| Lifecycle: pending, approved, rejected, needs_info, paid, overdue | **Partial** | Current statuses: pending, approved, rejected, needs_info. **paid** and **overdue** are not present. |

**To fulfil Part 6:**

- Add to invoice schema (or service layer): `payment_method` (enum), `paid_at` (datetime), `payment_reference` (string), `payment_notes` (string).
- Add status `paid` (and optionally `overdue` if business rules define it; e.g. approved but not paid past a threshold).
- Add API for client (and optionally admin): e.g. `PATCH /api/client/approvals/:invoice_id` with action `mark_paid` and body `payment_method`, `payment_reference`, `notes` (and set `paid_at` server-side).
- Add audit action e.g. `INVOICE_MARKED_PAID` and log it when marking paid.
- Client Approvals UI: for approved invoices, show “Mark as paid” with method/reference/notes.

---

## Part 7 — Optional contractor portal

| Requirement | Status | Notes |
|-------------|--------|--------|
| Contractors can optionally create accounts | **Partial** | Portal accounts are **invite-only** (admin sends invite; contractor sets password). No self-service “create account” for portal; self-registration creates contractor record with `pending_review`, not a portal account. |
| Portal shows: assigned work orders, submitted invoices, invoice status, profile | **Partial** | Dashboard shows **assigned work orders** and **profile** (via `/api/contractor/profile`). **Submitted invoices** list and **invoice status** are not shown; only “Submit invoice” per work order in the UI. No `GET /api/contractor/invoices` or similar. |

**To fulfil Part 7:**

- Either keep “optional portal” as invite-only (task says “optionally create accounts”; can mean “optional to use” not “self-sign-up”) or add self-service portal sign-up (e.g. if contractor has email and is active, allow set password from a link). Current behaviour is acceptable if interpreted as “optional to use once invited.”
- Add contractor-facing list of their submitted invoices and status: e.g. `GET /api/contractor/invoices` (scoped to contractor_id from JWT) and a small “My invoices” section or tab on the dashboard.

---

## Part 8 — Audit and observability

| Requirement | Status | Notes |
|-------------|--------|--------|
| Log: contractor assignment | **Partial** | Client assign: `CONTRACTOR_ASSIGNED_TO_WORK_ORDER` in client_maintenance. Admin assign: no audit log in maintenance_service; only email send (EMAIL_SENT with event_type). |
| Log: contractor acceptance, status update, evidence upload, invoice submission | **Implemented** | contractor_portal: CONTRACTOR_ACCEPTED_ASSIGNMENT, CONTRACTOR_DECLINED_ASSIGNMENT, CONTRACTOR_WORK_ORDER_STATUS_CHANGED, CONTRACTOR_EVIDENCE_UPLOADED, CONTRACTOR_INVOICE_SUBMITTED. |
| Log: invoice approval/rejection | **Implemented** | approval_service: INVOICE_APPROVED, INVOICE_REJECTED, INVOICE_NEEDS_INFO. |
| Log: invoice marked paid | **Missing** | No “marked paid” action or audit yet (see Part 6). |

**To fulfil Part 8:**

- Add audit log when admin assigns contractor (e.g. `CONTRACTOR_ASSIGNED_TO_WORK_ORDER` from maintenance_service or admin route).
- Add `INVOICE_MARKED_PAID` (or equivalent) when implementing Part 6.

---

## Part 9 — Documentation

| Requirement | Status | Notes |
|-------------|--------|--------|
| Create `docs/CONTRACTOR_WORKFLOW.md` | **Missing** | Does not exist. `CONTRACTOR_WORKFLOW_DELIVERABLES.md` exists and describes current portal implementation. |
| Include: contractor access methods, job notification flow, invoice lifecycle, payment tracking, limitations and future improvements | **N/A** | To be written once design is fixed (job link + portal, payment tracking). |

**To fulfil Part 9:**

- Add `docs/CONTRACTOR_WORKFLOW.md` describing: (1) two access methods (secure job link vs optional portal), (2) job notification flow (assignment → token → email with link), (3) invoice lifecycle (pending → approved/rejected/needs_info → paid) and payment recording, (4) limitations (e.g. no contractor payouts, evidence upload keys only until upload flow exists) and future improvements.

---

## Summary table

| Part | Implemented | Missing / To do |
|------|-------------|------------------|
| 1 – Assignment notification | Email sent; no job token, no link, no due date in email; assignment audit only from client path | Job token generation; secure job link in email; due date in email; assignment audit from admin path |
| 2 – Secure work order page | — | Token-based API + frontend page (view/accept/decline/status/notes/evidence/invoice) |
| 3 – Status updates | Yes (portal) | Same behaviour for job-link path when added |
| 4 – Invoice submission | Yes (portal) | Same for job-link path; optional contractor invoices list in portal |
| 5 – Client approval | Yes | — |
| 6 – Payment tracking | — | paid_at, payment_method, payment_reference, notes; status paid (and optionally overdue); mark-paid API + UI + audit |
| 7 – Optional portal | Work orders + profile; invite-only | Contractor “My invoices” list + status on dashboard |
| 8 – Audit | Most events; no assignment from admin, no “marked paid” | Audit on admin assign; INVOICE_MARKED_PAID when Part 6 done |
| 9 – Documentation | CONTRACTOR_WORKFLOW_DELIVERABLES.md only | Create CONTRACTOR_WORKFLOW.md per spec |

---

## Recommended implementation order

1. **Part 6 (payment tracking)** — Schema and API change; no conflict with job links. Enables “mark as paid” and audit.
2. **Part 1 (job token + email)** — Generate token on assign; add link and due date to assignment email; add assignment audit for admin path.
3. **Part 2 (secure work order page)** — Token validation, token-scoped API routes, frontend page. Reuse existing service layer.
4. **Part 7 (portal)** — Add `GET /api/contractor/invoices` and “My invoices” (and status) on dashboard.
5. **Part 8** — Ensure admin assignment and “marked paid” are audited (covered by steps 1–2).
6. **Part 9** — Write `docs/CONTRACTOR_WORKFLOW.md` reflecting the final design.

This order avoids duplication, keeps the existing portal intact, and adds the secure job link path and payment tracking in a controlled way.
