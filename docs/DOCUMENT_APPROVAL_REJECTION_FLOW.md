# Document approval/rejection flow – current behaviour and recommendations

## 1. Current flow summary

| Actor | Action | Endpoint | What happens |
|-------|--------|----------|---------------|
| **Admin** | **Verify (approve)** | `POST /api/documents/verify/{document_id}` | Document status → `VERIFIED`. Linked requirement → `COMPLIANT`. Property compliance updated immediately + compliance recalc enqueued. Audit `DOCUMENT_VERIFIED`. Enablement event emitted. |
| **Admin** | **Reject** | `POST /api/documents/reject/{document_id}` (Form: `reason`) | Document status → `REJECTED`. If no other VERIFIED doc for that requirement, requirement reverted to `PENDING` and due_date cleared; property compliance synced. Compliance recalc enqueued. Audit `DOCUMENT_REJECTED` with `metadata.reason`. |

So: **approve** = document counts as evidence and requirement/property/score reflect it. **Reject** = document does not count; requirement may go back to “missing evidence”; score is recalculated. The **rejected document is not removed** from the DB or from the user’s document list; it remains with status `REJECTED`.

---

## 2. Score recalculation

- **On verify:**  
  - `provisioning_service._update_property_compliance(property_id)` is called.  
  - `enqueue_compliance_recalc(..., TRIGGER_DOC_STATUS_CHANGED, ...)` is called.  
  So property compliance is updated and a full compliance recalc is queued.

- **On reject:**  
  - If the document had a `requirement_id`, `_revert_requirement_if_no_verified_docs` runs (requirement → PENDING if no other VERIFIED doc; property compliance synced).  
  - `enqueue_compliance_recalc(..., TRIGGER_DOC_STATUS_CHANGED, ...)` is called.  
  So the score **is** recalculated (via the queue); the rejected document no longer contributes.

---

## 3. Is the rejected document removed from the user’s portal?

**No.** The document row stays in the `documents` collection with `status: "REJECTED"`. The client document list (e.g. Documents page) shows it with a REJECTED badge. Only **client delete** (`DELETE /api/documents/{document_id}`) or **admin delete** actually removes the document (and file) and triggers requirement revert + recalc where applicable.

---

## 4. Why does admin approve/reject when the user has already “confirmed”?

There are two different concepts:

- **User “confirmed” (AI extraction):** The user reviewed AI-extracted data and chose “Apply” or “Reject extraction”. That affects **extraction status** and whether extracted data is applied to the requirement. It does **not** by itself set the **document** status to VERIFIED for compliance.
- **Document verification (admin):** The design is that **admin is the authority** for whether an uploaded file is acceptable as evidence for the requirement. So:
  - User uploads → document is `UPLOADED` (or similar).
  - Admin verifies → document becomes `VERIFIED` and counts for compliance; or admin rejects → `REJECTED` and it does not count.

So “user confirmed” (extraction) and “admin verify/reject” (document) serve different purposes: one is about applying AI data; the other is about attesting that the document satisfies the requirement for compliance. Both can coexist.

---

## 5. Can the user see why a document was rejected?

**Currently no.** The rejection reason is:

- **Stored only in the audit log:** `create_audit_log(..., metadata={"reason": reason})` in `reject_document`.  
- **Not stored on the document.** The document has no `rejection_reason` (or similar) field.

So in the portal the user only sees the REJECTED badge; there is no hover/click to show the reason. The frontend does not display it because the API never returns it on the document.

---

## 6. Is it logged? How can admin access it?

- **Yes, it is logged.**  
  - Action: `DOCUMENT_REJECTED`.  
  - `resource_type`: `"document"`, `resource_id`: `document_id`.  
  - `metadata.reason`: the admin-entered reason.

- **How admin can access it:**  
  - **GET /api/admin/audit-logs** with filter `action=DOCUMENT_REJECTED` (and optionally `client_id`).  
  - The current API does **not** support filtering by `resource_id` (document_id), so to find logs for one document you either filter by client and scan, or add a `resource_id` query parameter and use it in the query.

---

## 7. Most professional way to handle this

Recommendations without changing product intent:

1. **Store rejection reason on the document**  
   In `reject_document`, in addition to setting `status: REJECTED`, set e.g. `rejection_reason: reason` and optionally `rejected_at`, `rejected_by` (admin id). That gives a single source of truth and allows the portal to show it without depending only on audit.

2. **Show reason in the portal**  
   On the Documents page, for documents with status REJECTED, show the reason (e.g. tooltip on the REJECTED badge, or a short line under the document). Use the new field from the document API so the user understands why they need to re-upload or correct.

3. **Keep audit as-is**  
   Continue writing `DOCUMENT_REJECTED` with `metadata.reason` so audit trail remains complete and admin can still use Audit Logs to review who rejected what and when.

4. **Optional: audit log filter**  
   Add an optional `resource_id` (and/or `resource_type`) filter to GET /api/admin/audit-logs so admins can quickly pull all events for a given document (e.g. “show me everything for document_id X”).

5. **Clarify “user confirmed” vs “admin verify” in UI**  
   Use copy that distinguishes “You applied the extracted data” from “This document has been verified by admin for compliance” so users understand why an extra admin step exists.

---

## 8. Reference: code locations

| Item | Location |
|------|----------|
| Admin verify document | `backend/routes/documents.py` – `verify_document` (~1205) |
| Admin reject document | `backend/routes/documents.py` – `reject_document` (~1295) |
| Revert requirement when no verified docs | `_revert_requirement_if_no_verified_docs` (~1461) |
| Compliance recalc enqueue | `services/compliance_recalc_queue.py` – `enqueue_compliance_recalc` |
| Audit log (admin) | `backend/routes/admin.py` – `get_audit_logs` (~843); filter by `action`, `client_id` |
| Client document list / REJECTED badge | `frontend/src/pages/DocumentsPage.js` – `getStatusBadge`, document list |
| Admin reject modal (reason) | `frontend/src/pages/AdminDashboard.js` – reject modal, `handleRejectDocument` |
