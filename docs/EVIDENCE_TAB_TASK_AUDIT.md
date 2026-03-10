# Evidence Tab – Task vs Codebase Audit

**Task:** Implement the Evidence tab for the Property Detail page as an enterprise-grade evidence vault and document confirmation workspace.

**Audit purpose:** Identify what is implemented, what is missing, how it was implemented, and any conflicting instructions with a recommended safest option. **No implementation in this document** – audit only.

**References:** [Property Command Centre audit](PROPERTY_COMMAND_CENTRE_TASK_AUDIT.md) (Evidence mentioned in §7); existing Evidence tab and Documents flow.

---

## 1. EVIDENCE TAB PURPOSE (Task §1)

**Task asks the tab to answer:**
- What documents are stored for this property?
- Which compliance requirements do they support?
- Have their dates/details been confirmed?
- What is missing?
- What changed after confirmation?

**Current state:**
- **Implemented:** Property-scoped document list (`getDocuments({ property_id })`), table with Document, Status, Requirement, Uploaded, View (navigates to Documents page). Empty state text.
- **Missing:** No summary metrics (total/linked/pending/missing/last uploaded). No "what is missing" or "what changed after confirmation" in-tab; those live on Compliance tab and Timeline/Documents page.

**Gap:** The tab does not yet act as a single source of truth or audit-ready index; it is a thin list plus CTA to Documents.

---

## 2. TAB STRUCTURE (Task §2)

**Task order:** A) Evidence Summary Bar → B) Upload / Add Evidence → C) Evidence Table / Cards → D) Pending Confirmations → E) Audit / History strip.

**Current structure:**
- Title + single primary button "Upload / open full list" (navigate to `/documents?property_id=...`).
- Short description.
- Table (or empty state).
- **No** summary bar, no dedicated in-tab upload area, no Pending Confirmations block, no audit/history strip.

**Gap:** All five sections need to be added or expanded; only a minimal table exists.

---

## 3. EVIDENCE SUMMARY BAR (Task §3)

**Task:** At top, summary row: Total documents, Linked to requirements, Pending confirmation, Missing critical evidence, Last uploaded.

**Current:** Not present. No summary data fetched or displayed.

**Backend:** `GET /documents` returns `{ documents, total }`. No `summary` object (linked count, pending confirmation count, missing critical evidence, lastUploadedAt). Counts can be derived client-side from `documents` and `requirements` (e.g. requirements with no evidence), but "missing critical" is requirement-level and would need either backend support or frontend logic using compliance matrix.

**Gap:** Add summary bar; backend either extends list response with `summary` or a dedicated evidence endpoint returns it.

---

## 4. UPLOAD / ADD EVIDENCE AREA (Task §4)

**Task:** Primary "Upload Evidence"; optional "Add from Intake Uploads"; drag-and-drop if supported. Upload with: file, property preselected, requirement type optional/preselected, document type selection, notes. Document types: Gas Safety Certificate, EICR, EPC, Fire Risk Assessment, Legionella Assessment, Smoke/CO evidence, Other (manual linking).

**Current:**
- **Property preselected:** Yes – user goes to `/documents?property_id=...`; Documents page uses `property_id` from query and can pass it to upload.
- **Upload flow:** Exists in Documents page (`POST /documents/upload`); backend accepts `property_id`, optional `requirement_id`. No document-type dropdown in upload (e.g. Gas Safety, EICR); requirement linkage via AI or manual.
- **Intake / drag-and-drop:** Not verified in this audit; assume existing behaviour on Documents page if present.

**Gap:** In-tab "Upload Evidence" in Property Detail is currently a link. Task wants a clear in-tab CTA and optional in-tab upload (or same flow with property preselected). Document type at upload is not in backend/UI; task list (Gas Safety, EICR, etc.) and "Other" with manual linking are not implemented.

**Safest:** Keep existing route and upload endpoint. Add in-tab "Upload Evidence" that either opens existing upload flow (e.g. modal or navigate with `property_id`) or embeds it. Add document type as an optional field on upload only if product agrees (additive backend + UI).

---

## 5. EVIDENCE TABLE / CARD LIST (Task §5)

**Task:** All evidence items; columns: Document name, Document type, Linked requirement(s), Status, Issue/expiry date if known, Uploaded by, Uploaded at, Actions. Status: Uploaded, Extracted, Pending Confirmation, Confirmed, Applied, Unlinked. Row actions: View, Download, Confirm Details, Link to Requirement, View History. Mobile: cards.

**Current (PropertyDetailPage.js):**
- Columns: Document, Status, Requirement, Uploaded, Action (only "View" → Documents page).
- Status mapping: VERIFIED → "Confirmed", UPLOADED → "Extracted", else "Pending". Task status set is different (Uploaded, Extracted, Pending Confirmation, Confirmed, Applied, Unlinked).
- No: document type, issue/expiry date, uploaded by, Download, Confirm Details, Link to Requirement, View History, or card layout for mobile.

**Backend document model (core.Document):** `document_id`, `client_id`, `property_id`, `requirement_id`, `file_name`, `file_path`, `file_size`, `mime_type`, `status` (DocumentStatus), `uploaded_by`, `ai_extracted_data`, `confidence_score`, `manual_review_flag`, `uploaded_at`. Stored docs may also have `ai_extraction`, `extraction_id` (extracted_documents). No `document_type` (e.g. Gas Safety), no `issue_date`/`expiry_date` on document (dates live on requirement after apply-extraction), no `linked_requirement_ids` (single `requirement_id`), no `confirmed_by`/`confirmed_at`, no `source` or `notes`.

**Gap:** Table needs new columns and actions. Backend has single `requirement_id` and no document_type/issue/expiry on document; status enum differs. Align status labels with task (map existing statuses); add columns from existing fields where present; add actions that delegate to existing Documents page (View, Download, Confirm Details, Link to Requirement) and Timeline or ledger (View History). Document type and issue/expiry on document are additive backend/UI if required.

---

## 6. PENDING CONFIRMATIONS SECTION (Task §6)

**Task:** If there are documents with extraction not yet confirmed, show "Pending Confirmation" with: document name, extracted fields, confidence, linked requirement suggestion, confirm button. Confirm Details opens confirm modal; user confirms issue/expiry/requirement/linked asset; only after confirmation update requirement, score, reminders, linked asset.

**Current:**
- **Confirm flow:** Lives on Documents page. Confirm-details modal; user edits expiry/issue/certificate number and submits; then apply-extraction is called; backend updates requirement and score (CERT_DETAILS_CONFIRMED in ledger). No automatic application of extracted dates without user confirmation – **safe and aligned with task**.
- **Evidence tab:** No "Pending Confirmation" block; no list of docs with extraction awaiting confirm.

**Gap:** Add Pending Confirmations section on Evidence tab: filter `documents` where extraction exists but not yet applied (e.g. has `ai_extraction`/extraction result and requirement not yet updated). Show doc name, extracted fields, confidence, suggested requirement, and "Confirm Details" opening the same confirm modal (reuse DocumentsPage flow or factor modal into shared component). No new backend contract required if list comes from existing documents API; optional backend flag "pending_confirmation" for clarity.

---

## 7. EVIDENCE HISTORY / AUDIT STRIP (Task §7)

**Task:** Bottom or side – recent evidence-related events: uploaded, linked, confirmed, replaced, removed, applied to score. Mini timeline or compact feed: timestamp, actor, action, document name.

**Current:**
- **Timeline:** `GET /api/portfolio/properties/{property_id}/timeline` exists. `property_timeline_service` merges score_ledger_events, score_change_log, work_orders. Ledger trigger types `DOCUMENT_UPLOADED`, `DOCUMENT_REMOVED`, `DOCUMENT_STATUS_CHANGED`, `CERT_DETAILS_CONFIRMED` map to category `EVIDENCE`. So evidence events for the property are already in the timeline when filtered by category.
- **Evidence tab:** No audit strip; Timeline tab shows full timeline (with category filter including EVIDENCE).

**Gap:** Add an "Evidence history" strip on the Evidence tab: call existing timeline API with `category=EVIDENCE` (or filter client-side), show last N events with timestamp, actor, action, document name. Reuse timeline event shape; no new endpoint required if timeline supports category filter.

---

## 8. DATA MODEL / BACKEND EXPECTATIONS (Task §8)

**Task suggests:** Evidence fields including `documentType`, `extractedFields`, `extractedConfidence`, `issueDate`, `expiryDate`, `confirmedBy`, `confirmedAt`, `linkedRequirementIds`, `linkedAssetId`, `source`, `notes`, `sha256`, `storageKey`; endpoint `GET /api/properties/:propertyId/evidence` with `{ summary, documents, recentEvents }`.

**Current:**
- **Document model:** See §5. Existing: `requirement_id` (single), `ai_extracted_data` / `confidence_score`, `uploaded_at`, `uploaded_by`. Missing: `document_type`, `issue_date`/`expiry_date` on document, `confirmed_by`/`confirmed_at`, `linked_requirement_ids` (only one), `linked_asset_id`, `source`, `notes`, `sha256`, `storage_key`.
- **Endpoint:** No `GET /properties/:id/evidence`. Documents: `GET /documents?property_id=...` → `{ documents, total }`. Timeline: `GET /api/portfolio/properties/{property_id}/timeline` (includes evidence events when filtered).

**Conflicts and safest option:**
- **orgId vs client_id:** Codebase uses `client_id`. Keep `client_id`; do not rename to orgId.
- **Single evidence endpoint vs existing:** Task suggests one "evidence" response. Safest: **additive** – keep `GET /documents?property_id=...` for list and all existing upload/download/apply-extraction routes. Optionally add a **new** endpoint (e.g. `GET /api/portfolio/properties/{property_id}/evidence`) that returns `{ summary, documents, recentEvents }` by composing:
  - existing list_documents by property_id,
  - summary computed from those documents + requirements (or from compliance detail),
  - recentEvents from ledger/timeline filtered by evidence trigger types.
  This gives the Evidence tab one contract without breaking existing flows.
- **Data model extensions:** Add only what is needed for the tab and compliance pack readiness: e.g. `document_type`, `source`, `notes`; optionally `confirmed_by`/`confirmed_at`, `issue_date`/`expiry_date` on document if product wants them there. Keep `requirement_id`; multi-requirement (`linked_requirement_ids`) is a larger change – document as future only unless required.

---

## 9. LINKAGE TO OTHER MODULES (Task §9)

**Task:** Evidence tab must link to Compliance (evidence supports requirements), Timeline (evidence events), Assets (confirmed evidence updates asset metadata), Dashboard score/trend (confirmation triggers score change).

**Current:**
- **Compliance:** Overview and Compliance tab reference "Upload evidence" / "Confirm expiry" and link to Evidence tab; Evidence table shows requirement_id; apply-extraction updates requirement status and score.
- **Timeline:** Property timeline includes evidence-related ledger events; Evidence tab does not yet show a strip of these.
- **Assets:** No "confirmed evidence → update asset metadata" (e.g. Gas Safety → boiler last service date) in this audit; treat as future.
- **Score:** Confirmation (apply-extraction) already triggers recalc and ledger (CERT_DETAILS_CONFIRMED).

**Gap:** Evidence tab should explicitly link to Compliance/Timeline/Assets (navigation or copy). Audit strip on Evidence tab will complete the Timeline link. Asset update from confirmed evidence is a separate feature (backend + Assets tab).

---

## 10. MISSING EVIDENCE EXPERIENCE (Task §10)

**Task:** If requirement missing critical evidence, surface in summary and CTA "Upload required evidence" (on upload, system updated and score/risk recalculated). If no documents at all: empty state "No evidence has been uploaded for this property yet." Buttons: Upload Evidence, View Compliance Requirements.

**Current:** Empty state: "No documents for this property yet. Upload evidence from the Documents page or use the button above." Single "Upload / open full list" button. No "View Compliance Requirements"; no "missing critical evidence" summary or CTA.

**Gap:** Refine empty state copy to match task and add "View Compliance Requirements". Add missing-critical summary + CTA when summary is implemented.

---

## 11. COMPLIANCE PACK / FUTURE EXPORT (Task §11)

**Task:** Evidence tab data should be structured so every document can export: file index, document type, linked requirement, dates, confirmation status (for future PDF/compliance pack).

**Current:** Document list and requirement linkage exist; document_type and explicit confirmation metadata on document are missing. Export pipeline not in scope of this audit.

**Gap:** When adding document_type and confirmation fields, keep them export-friendly (flat, indexable). No change to existing export flows until compliance pack is implemented.

---

## 12. SECURITY + SAFETY (Task §12)

**Task:** Only users with property access view evidence; signed/secured download URLs; no automatic application of extracted dates without user confirmation; audit trail for evidence changes; append-only logs where present.

**Current:**
- Access: Document list and details are guarded by client/property; same as existing Documents page.
- Download: Use existing document download route; if storage supports signed URLs, keep/use that.
- Confirmation: Apply-extraction runs only after user confirms in modal – **no automatic application** – aligned with task.
- Audit: Score ledger logs DOCUMENT_UPLOADED, CERT_DETAILS_CONFIRMED, DOCUMENT_REMOVED, DOCUMENT_STATUS_CHANGED with property_id, document_id, actor; timeline exposes these. Append-only ledger.

**Gap:** None for core safety; ensure any new Evidence tab actions use same guards and do not introduce auto-apply.

---

## 13. DESIGN RULES (Task §13)

**Task:** Professional document vault feel; clean cards/tables; emphasise confirmation; enterprise tone; mobile responsive.

**Current:** Property page uses Card, table, Button, badges; electric-teal/midnight-blue; responsive. Evidence tab is minimal but consistent.

**Gap:** When expanding the tab, keep same design system; add summary bar, table enhancements, pending block, and audit strip with clear hierarchy and confirmation emphasis.

---

## 14. ACCEPTANCE CRITERIA (Task §14)

| Criterion | Status | Notes |
|-----------|--------|--------|
| Evidence tab shows summary, documents, pending confirmations, and recent events | **Partial** | Documents only; summary, pending block, audit strip missing. |
| Upload flow works with property preselected | **Done** | Via navigate to `/documents?property_id=...`; upload uses property_id. |
| Confirm Details updates downstream only after user confirmation | **Done** | Modal then apply-extraction; no auto-apply. |
| Evidence links to requirements and optionally assets | **Partial** | requirement_id linked; asset update from evidence not implemented. |
| Empty states and missing evidence states clear | **Partial** | Empty state exists; missing-critical and "View Compliance Requirements" not. |
| No existing upload/download route broken | **Done** | Additive only so far. |

---

## 15. CONFLICTS AND RECOMMENDED OPTIONS

| Conflict | Recommendation |
|----------|-----------------|
| **orgId vs client_id** | Keep `client_id` everywhere; do not introduce orgId for evidence. |
| **GET /properties/:id/evidence vs GET /documents?property_id=** | Keep existing documents list and routes. Add optional **additive** endpoint (e.g. `GET /api/portfolio/properties/{property_id}/evidence`) that returns `{ summary, documents, recentEvents }` by composing existing list_documents + ledger/timeline, so the Evidence tab has one contract without breaking callers. |
| **Document type at upload** | Not required for MVP; add as optional field (backend + UI) if product wants it. |
| **Multiple linked requirements (linked_requirement_ids)** | Keep single `requirement_id` unless product explicitly needs multi-link; document as future. |
| **Evidence tab vs Documents page** | Evidence tab = property-scoped vault view + summary + pending + history; full upload/confirm/details remain on Documents page. Reuse confirm modal (or shared component) from Documents page when adding "Confirm Details" from Evidence tab. |

---

## 16. OUTPUT REQUIRED (Task "OUTPUT REQUIRED")

### Files to change (when implementing)

- **Frontend:** `frontend/src/pages/PropertyDetailPage.js` – Evidence tab only: add summary bar, upload area (or CTA that keeps property preselected), enrich table (columns + actions), Pending Confirmations section, Evidence history strip, empty/missing state copy and CTAs. Optionally shared component for confirm-details modal if used from both Evidence and Documents.
- **Backend (additive only):**
  - Optional: new route (e.g. in `portfolio.py` or `documents.py`) for `GET /api/portfolio/properties/{property_id}/evidence` returning `{ summary, documents, recentEvents }`.
  - Optional: extend document schema for `document_type`, `source`, `notes` (and if needed `confirmed_by`, `confirmed_at`, `issue_date`, `expiry_date` on document) with migrations/defaults.
- **Client API:** If new endpoint added: `getPropertyEvidence(propertyId)` in `frontend/src/api/client.js`. Otherwise keep using `getDocuments({ property_id })` and timeline with category filter.

### Endpoints

- **Reused:** `GET /documents?property_id=...` (list), `POST /documents/upload`, `GET /documents/{id}/details`, `POST /documents/{id}/apply-extraction`, document download route, `GET /api/portfolio/properties/{property_id}/timeline` (for audit strip with category=EVIDENCE).
- **Created (optional):** `GET /api/portfolio/properties/{property_id}/evidence` – composed summary + documents + recentEvents.

### New fields (if added)

- On document: `document_type` (optional enum or string), `source` (e.g. "intake" | "portal" | "system"), `notes` (optional). Optional later: `confirmed_by`, `confirmed_at`, `issue_date`, `expiry_date` on document for compliance pack.
- Response shape for new evidence endpoint: `summary: { totalDocuments, linked, pendingConfirmation, missingCriticalEvidence, lastUploadedAt }`, `documents` (array), `recentEvents` (array from ledger/timeline).

### Notes on how evidence updates compliance score / assets / timeline

- **Score:** Already: user confirms details → apply-extraction → requirement and score updated → `log_score_change(..., trigger_reason="AI_APPLIED", ...)` → CERT_DETAILS_CONFIRMED in ledger. No change needed.
- **Timeline:** Evidence events already in property timeline (EVIDENCE category). Evidence tab can show a strip from the same timeline filtered by EVIDENCE.
- **Assets:** Confirmed evidence updating asset metadata (e.g. boiler last service date from Gas Safety) is not implemented; treat as future; data model can reserve `linked_asset_id` if desired.

### Live vs placeholder

- **Live:** Document list, property preselection, confirm-details flow, apply-extraction, score/ledger/timeline integration, empty state, View to Documents.
- **Placeholder / future:** Compliance pack export (data structure ready when document_type/confirmation fields added); "Add from Intake Uploads" if not already present; asset update from confirmed evidence; optional document_type at upload; multi-requirement linkage.

---

**End of audit.** Implement only the Evidence tab with additive changes; reuse existing document and confirmation flows; do not break existing routes or duplicate logic unnecessarily.
