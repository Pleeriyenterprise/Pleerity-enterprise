# Client – Evidence Upload (Documents) – Training Manual

## 1. Module name
**Evidence Upload** (Documents page — Client)

## 2. Audience
**Client / end user.**

## 3. Purpose
Upload compliance evidence (e.g. Gas Safety Certificate, EICR, EPC) and link it to a property and requirement. The system may extract expiry/issue dates from the document; the user confirms or edits details in a “Confirm details” modal. Users can view, download, and delete existing documents.

## 4. Where to find it in the UI
- **URL:** `/documents`
- **Navigation:** Sidebar → **Documents** (icon FileText).
- **Deep link from property/requirements:** Property detail and Compliance pages may link to Documents; product link “Uploading Evidence guide” goes to `/help?article=uploading-evidence`.

## 5. What the user sees on the page
- **Header:** “Documents” or “Evidence”; short description.
- **Filters:** Property (dropdown), optional status filter.
- **Upload section:** Form: Property (required), Requirement (optional but recommended), Document type (dropdown: Gas Safety Certificate, EICR, EPC, Fire Risk Assessment, Legionella Assessment, Smoke/CO evidence, Other), Notes, File (choose file). **Upload** button.
- **Document list:** Table or cards: property, requirement, document type, upload date, status (e.g. pending extraction, completed, failed), expiry/issue date if set. Actions: View/Download, Confirm details (if extraction pending), Edit details, Delete.
- **Confirm details modal (after upload or when extraction completes):** Expiry date, Issue date, Certificate number (optional). User confirms or corrects; **Apply** saves to document. If extraction failed, user can still enter details manually.
- **“Need help? See: Uploading Evidence guide”** link to Help Centre.

## 6. Step-by-step actions

| Action | What to click | What happens |
|--------|----------------|--------------|
| Upload a document | Select property, requirement (optional), type, file → Upload | `POST /api/documents/upload` (or similar). File stored; async extraction may start. UI shows “analyzing” or “extracting”; frontend polls `GET /documents/{id}/extraction` until completed or failed. |
| Confirm details (extraction done) | When modal opens (auto after extraction) or “Confirm details” on a row | Modal shows extracted fields if any; user edits and clicks Apply. Backend updates document (expiry_date, issue_date, etc.). Requirement status may recalculate. |
| Confirm details (extraction failed) | Same modal; extraction_failed flag | User enters expiry/issue/cert number manually → Apply. Document is still linked to property/requirement. |
| View/Download | View or Download on a document row | Opens or downloads the stored file (backend serves file or redirect). |
| Delete document | Delete on a row → confirm | Soft delete or remove link; document no longer counts for that requirement. |
| Filter by property | Select property in filter | List filters to documents for that property. |

## 7. What happens after each action
- **Upload:** File is stored; extraction job runs (async). Frontend polls extraction status; when “completed,” Confirm details modal opens with pre-filled dates/number. When “failed,” modal opens with empty fields for manual entry. After Apply, document is fully recorded and linked to requirement; compliance score/status may update after recalc job.
- **Apply (confirm details):** Backend updates document record; modal closes; list refreshes. Recalculation is scheduled; score/status may update shortly after.
- **Delete:** Document is removed or deactivated; requirement may go back to PENDING if no other evidence.
- **Filter:** In-page or API filter; list updates.

## 8. Status/outcome examples
- **Pending extraction:** Document uploaded; extraction in progress. User waits; modal opens when done (or timeout).
- **Extraction completed:** Modal pre-fills expiry/issue/cert number; user confirms or edits → Apply.
- **Extraction failed:** Modal opens without pre-fill; user enters details manually → Apply. Document still counts once saved.
- **Upload error:** File type/size invalid or API error; toast or message shown. User retries or chooses different file.
- **Plan/entitlement:** Some plans may limit document count or types; 403 or upgrade prompt if over limit (implementation-specific).

## 9. Common errors or confusing points
- **“Analyzing” or “Extracting” takes long:** Extraction can take up to tens of seconds; frontend polls every few seconds. If it times out (e.g. 90s), modal may open with “extraction failed” and user enters manually.
- **Extraction failed:** No in-page explanation of why (e.g. poor image quality, unsupported format). Training: “If extraction fails, you can still enter the dates and certificate number by hand.”
- **Linking to requirement:** For best compliance tracking, user should select both property and requirement when uploading. “Other” type can be linked to requirement later if supported.
- **Document types:** Fixed list (Gas Safety, EICR, EPC, etc.); “Other” for anything else. Cannot create custom types from client UI.

## 10. Current limitations or known gaps
- **Needs runtime confirmation:** Exact timeout for extraction polling and behaviour when backend is slow (e.g. modal after 90s with failed state).
- No “bulk upload” from this page in base flow; bulk upload exists at `/documents/bulk-upload` (separate flow).
- Recalculation after Apply is not instant; score/status update depends on scheduled jobs.
- Some builds may restrict file types/sizes; confirm in environment.

## 11. Notes for training staff
- “Always choose property and, if possible, the requirement so the document counts toward compliance.”
- “After upload, wait for extraction; if it fails, you can still type in the expiry and issue dates.”
- “To fix an overdue requirement, upload the new certificate here and confirm the new expiry date.”
- Link to Help Centre “Uploading Evidence” article for self-service.

---

## Trainer walkthrough (5–10 minutes)

1. **Open Documents** → show filters and upload form.
2. **Upload flow:** Select property, requirement, type (e.g. Gas Safety), choose file → Upload. Show “analyzing” state.
3. **When modal opens:** Show pre-filled fields (if extraction succeeded) or blank (if failed). Edit if needed → Apply. “Now this document is linked and will help your compliance score.”
4. **Show document list:** Point out columns (property, requirement, type, status, dates). Show View/Download and Delete.
5. **Mention help link:** “If you’re stuck, use ‘Uploading Evidence guide’ in Help Centre.”
6. **Extraction failed:** “If you see extraction failed, don’t worry—enter the expiry and issue dates yourself and click Apply.”
