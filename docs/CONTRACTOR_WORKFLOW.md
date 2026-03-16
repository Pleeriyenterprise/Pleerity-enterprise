# Contractor Workflow

This document describes how contractors participate in work orders, update job progress, and submit invoices on the Pleerity platform. The design supports **two access methods**: secure job links (no login) and an optional contractor portal.

---

## 1. Contractor access methods

### 1.1 Secure job link (no login required)

When a contractor is **assigned** to a work order, the system:

- Generates a **secure job access token** (scoped to that work order and contractor), stored hashed in `contractor_job_tokens` with a 90-day expiry.
- Sends an **assignment notification email** that includes:
  - Property, job description, due date (SLA complete-by).
  - A **secure job link**: `{frontend_base}/job?token={raw_token}`.

The contractor can open that link in a browser and:

- View the single work order (no access to other jobs).
- Accept or decline the assignment.
- Update status (Scheduled, In progress, Awaiting parts, Completed).
- Add contractor and completion notes.
- Submit an invoice for that work order (when status is Completed).

**API:** All job-link actions use the token as authentication. Requests go to `/api/job/*` with the token in the query string (`?token=...`) or in the header `X-Job-Token`. No JWT or portal account is required.

**Frontend:** The page at `/job` reads `?token=` from the URL and uses it for every API call. No login screen is shown.

### 1.2 Optional contractor portal

Contractors can optionally use a **portal account** (invite-only):

- **Invite:** An admin sends a portal invite from the admin contractors page (“Invite to portal”). The contractor receives an email with a link to set a password (`/contractor-set-password?token=...`).
- **Login:** After setting a password, the contractor signs in at `/contractor/login` with email and password. They receive a JWT that identifies them as that contractor.
- **Dashboard:** At `/contractor`, the contractor sees:
  - **Assigned work orders** (list with property, status, due date). Clicking a row opens a detail drawer where they can accept/decline, update status, add notes, and submit an invoice for completed jobs.
  - **My invoices** (reference, amount, status, submitted date) for all invoices they have submitted.

Portal and job-link flows use the same backend business logic (work order updates, invoice submission); only the authentication method differs (JWT vs job token).

---

## 2. Job notification flow

1. **Assignment:** A client or admin assigns a contractor to a work order (e.g. from the work order detail or maintenance list). The backend:
   - Updates the work order with `contractor_id` and `assigned_at`.
   - Records the assignment in `contractor_assignments`.
   - Creates a **job token** (hash stored in `contractor_job_tokens`, 90-day expiry).
   - Sends an email (template `CONTRACTOR_ASSIGNED`) to the contractor’s email address with:
     - Subject and body including work order id, description, property, **due date**, and **secure job link**.
   - Writes an **audit log** entry: `CONTRACTOR_ASSIGNED_TO_WORK_ORDER` (for both client and admin assignment paths).

2. **Contractor response:** The contractor uses either:
   - The **job link** from the email (no login), or
   - The **portal** (if they have an account) to accept/decline and update the job.

---

## 3. Invoice lifecycle

- **Submission:** The contractor submits an invoice (from the job link page or portal) for a completed work order. The invoice is created with `work_order_id`, `contractor_id`, `property_id`, `client_id`, and status **pending**.
- **Approval:** Invoices appear in the client **Approvals** module (`/operations/approvals`). The client (or admin) can:
  - **Approve**
  - **Reject**
  - **Request more information** (needs_info)
- **Payment recording:** After an invoice is **approved**, the client can **mark as paid** and record:
  - **Payment method:** bank_transfer, cash, card, cheque, other
  - **Payment reference**
  - **Notes**  
  The invoice status becomes **paid** and `paid_at` is set. Audit: `INVOICE_MARKED_PAID`.

**Invoice statuses:** `pending` → `approved` | `rejected` | `needs_info` → (if approved) `paid`. The lifecycle also supports **overdue** (e.g. for reporting) where applicable.

---

## 4. Payment tracking

- **Pleerity does not process contractor payments:** The platform facilitates coordination and invoice approval only. Contractors are paid by the client directly; payment responsibility lies with the client.
- **No contractor payouts:** The system does **not** implement contractor payouts or disbursements. It only records that the **client** has marked an invoice as paid.
- **Fields stored on the invoice when marked paid:**
  - `payment_method` (enum: bank_transfer, cash, card, cheque, other)
  - `paid_at` (timestamp)
  - `payment_reference`
  - `payment_notes`
- **Client UI:** In Approvals, approved invoices show a “Mark as paid” form (payment method, reference, notes). Paid invoices display paid date, method, and reference in the detail drawer.

---

## 5. Audit and observability

The following events are logged (audit log):

- **Contractor assignment** – `CONTRACTOR_ASSIGNED_TO_WORK_ORDER` (when a contractor is assigned to a work order, from either client or admin).
- **Contractor acceptance** – `CONTRACTOR_ACCEPTED_ASSIGNMENT`.
- **Contractor decline** – `CONTRACTOR_DECLINED_ASSIGNMENT`.
- **Contractor status update** – `CONTRACTOR_WORK_ORDER_STATUS_CHANGED` (with old/new status; optional metadata `via: job_link` when using the secure link).
- **Contractor evidence upload** – `CONTRACTOR_EVIDENCE_UPLOADED` (e.g. keys count).
- **Contractor invoice submission** – `CONTRACTOR_INVOICE_SUBMITTED`.
- **Invoice approval / rejection / needs_info** – `INVOICE_APPROVED`, `INVOICE_REJECTED`, `INVOICE_NEEDS_INFO`.
- **Invoice marked paid** – `INVOICE_MARKED_PAID`.

---

## 6. Limitations and future improvements

- **Evidence upload:** The API accepts `evidence_keys` (storage keys) on work orders. A dedicated **file upload** flow (e.g. presigned URL or multipart upload) that returns keys for `evidence_keys` is not yet implemented.
- **Overdue status:** Invoice lifecycle includes “overdue” as a possible status; automatic setting of overdue (e.g. by a scheduled job) can be added later.
- **Contractor forgot password:** No self-service password reset for the portal; the admin can send a new invite link.
- **Job link reuse:** Each assignment creates a new job token. Old links for the same work order remain valid until expiry (90 days). Optionally, tokens could be invalidated or replaced when the assignment is changed.
- **Email template:** The assignment email uses a generic template; a dedicated `CONTRACTOR_ASSIGNED` template (with placeholders for job_link, due_date, etc.) can improve branding and clarity.

---

## 7. Related documentation

- **CONTRACTOR_WORKFLOW_DELIVERABLES.md** – Implementation summary and file-level changes for the contractor portal and job link.
- **CONTRACTOR_WORKFLOW_TASK_ANALYSIS.md** – Gap analysis of task requirements vs. codebase (for reference).
