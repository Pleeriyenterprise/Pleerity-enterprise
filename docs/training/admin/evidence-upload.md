# Admin – Evidence Upload / Documents (Training Manual)

## 1. Module name
**Evidence Upload (Admin side) / Document Management**

## 2. Audience
**Admin / internal staff.** Clients upload evidence from the client Documents page; this manual covers admin-side document handling and visibility.

## 3. Purpose
Admins may need to: view client-uploaded documents (evidence), support extraction or verification workflows, and use admin-only tools such as extraction queue or document management. Client-facing upload flow is documented in the client Evidence Upload manual.

## 4. Where to find it in the UI
- **Admin document/evidence views:** May be under **Operations & Compliance**, **Support**, or a dedicated **Document Management** / **Extraction Queue** (e.g. `AdminExtractionQueuePage` at `/admin/extraction-queue` or similar). *Exact path needs runtime confirmation.*
- **Client context:** When viewing a client, documents linked to that client’s properties may be listed in a documents or evidence section.
- **Backend:** Documents are stored and linked to `client_id`, `property_id`, `requirement_id`; admin APIs may allow listing/filtering by client.

## 5. What the user sees
- **Extraction queue (if implemented):** List of documents pending or in extraction; status (pending, completed, failed). Admin may retry or reassign.
- **Document list per client:** Documents for a selected client with property, requirement, type, upload date, status.
- **No dedicated “admin upload for client” in base implementation:** Clients upload their own evidence; admin may only view or manage queue.

## 6. Step-by-step actions
| Action | What to do | What happens |
|--------|------------|--------------|
| View client documents | Open client and go to documents/evidence section, or use extraction queue filtered by client | List of documents with metadata; links to view/download if permitted. |
| Check extraction status | Open Extraction Queue (if available); filter by status | See pending/completed/failed; backend uses `GET /documents/{id}/extraction` for status. |
| Retry failed extraction (if UI exists) | Select document → Retry or similar | Backend may re-queue or re-run extraction; behaviour is implementation-specific. |

## 7. What happens after each action
- View: Read-only; no change to document.
- Retry: Extraction job may run again; document status may update to completed or fail again.

## 8. Status/outcome examples
- **Extraction pending:** Document uploaded; extraction not yet completed; client may still be on “Confirm details” or waiting.
- **Extraction completed:** Extracted data (e.g. expiry date) available; client can confirm or edit in Confirm details modal.
- **Extraction failed:** Client sees “extraction failed” in Confirm details; they can enter details manually or re-upload. Admin may see failure reason in queue if exposed.

## 9. Common errors or confusing points
- **Who uploads?** Only the client (or a user with client role) uploads evidence from the client portal. Admin does not typically “upload on behalf of client” unless a specific feature exists.
- **Extraction queue vs client view:** Queue is for processing status; client view is for their own documents. Don’t confuse “queue” with “all documents.”

## 10. Current limitations or known gaps
- Extraction queue and admin document list routes/pages **need runtime confirmation** (paths and exact features).
- Admin cannot upload a document “as” a client in the standard client flow; that would require client login or a separate admin upload feature.
- Document types (Gas Safety, EICR, EPC, etc.) are defined in client UI and backend; admin may not have a separate type manager.

## 11. Notes for training staff
- “Evidence = documents clients upload for compliance. We can see them in admin when we open the client or in the extraction queue.”
- If extraction fails repeatedly, advise client to enter details manually in Confirm details or re-upload a clearer file.
- Link to client manual for “how the client uploads” so support can talk clients through it.

---

## Trainer walkthrough (5 minutes)

1. **Open admin** → locate Extraction Queue or client document list (path may be under Ops or Support).
2. **Show one client’s documents** (by opening client or filtering queue) → explain columns (property, requirement, type, status, date).
3. **Explain extraction:** “After upload, the system tries to extract expiry/issue date; if it fails, the client can still enter details manually.”
4. **Clarify:** “We don’t upload for the client; we view and sometimes retry or troubleshoot.”
