# Payment Responsibility Notices — Task vs Codebase

Quick check against the task (Parts 1–5). **No duplication** of existing behaviour.

---

## Part 1 — Contractor payment notice

| Location | Status | Action |
|----------|--------|--------|
| Contractor job page (`/job`) | **Missing** | Add notice on page and in invoice modal |
| Contractor invoice submission (job link modal + portal modal) | **Missing** | Add same notice in both modals |
| Contractor assignment notification email | **Missing** | Append payment-responsibility sentence(s) to email body |

**Notice content (task):** Pleerity coordinates work orders and invoice approval; payment responsibility lies with the client; Pleerity does not process contractor payments; contractors should follow up with the client for payment.

---

## Part 2 — Client payment notice

| Location | Status | Action |
|----------|--------|--------|
| Contractor assignment UI (client work order drawer) | **Missing** | Add notice near assign contractors section |
| Invoice approval screen (Client Approvals page) | **Missing** | Add notice (e.g. below intro or above table) |
| Invoice detail page (approval detail drawer) | **Missing** | Add notice in drawer |

**Notice content (task):** Contractors are independent service providers engaged by the client; the client is responsible for paying the contractor; Pleerity does not process contractor payments.

**Admin assignment UI:** Task lists only “contractor assignment UI” and “invoice approval/detail” — both are client-facing. Admin work order assignment (AdminWorkOrderDetailPage) can get the same client-facing notice for consistency (client is still the payer).

---

## Part 3 — Invoice payment tracking

| Requirement | Status |
|-------------|--------|
| Lifecycle: pending, approved, rejected, needs_info, paid | **Done** (approval_service, ClientApprovalsPage) |
| payment_method (bank_transfer, cash, card, cheque, other) | **Done** |
| paid_at, payment_reference, notes (payment_notes) | **Done** |
| Client can mark approved invoice as paid | **Done** |

**No implementation needed.**

---

## Part 4 — Terms of service alignment

| Requirement | Status | Action |
|-------------|--------|--------|
| Docs/terms: Pleerity facilitates coordination | **Partial** (CONTRACTOR_WORKFLOW.md) | Add explicit sentence in Terms page |
| Contractors paid by clients directly | **Partial** | Add to Terms and/or workflow doc |
| Pleerity does not process contractor payments unless stated | **Missing in Terms** | Add short clause (e.g. under Payments or new subsection) |

**Action:** Add a short “Contractor and work order payments” (or similar) subsection to the public Terms page; optionally add one line to CONTRACTOR_WORKFLOW.md if not already clear.

---

## Part 5 — Audit logging

| Event | Status |
|-------|--------|
| Invoice approved | **Done** — `INVOICE_APPROVED` in approval_service |
| Invoice rejected | **Done** — `INVOICE_REJECTED` |
| Invoice marked paid | **Done** — `INVOICE_MARKED_PAID` |
| Payment details updated | **Covered** — Only write path is mark_invoice_paid; that logs `INVOICE_MARKED_PAID` with payment_method, payment_reference. No separate “update payment details” endpoint exists; when/if added, a dedicated event can be introduced. |

**No implementation needed** for Part 5.

---

## Conflicts

None. Notices are additive; Part 3 and Part 5 are already satisfied.

---

## Implementation (done)

1. **Part 1:** Contractor notice added to JobPage (banner + invoice modal), ContractorDashboardPage (invoice modal), and assignment email body in maintenance_service.
2. **Part 2:** Client notice added to ClientMaintenancePage (work order detail drawer), ClientApprovalsPage (below intro + in approval detail drawer).
3. **Part 4:** New subsection "Contractor and work order coordination" under Terms §3 (Payments and Refunds) in TermsPage.js; CONTRACTOR_WORKFLOW.md §4 updated with explicit "Pleerity does not process contractor payments" line.
4. **Part 3 & Part 5:** No code changes; already implemented (invoice lifecycle, payment fields, mark paid, audit events).
