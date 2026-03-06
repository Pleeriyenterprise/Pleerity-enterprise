# Internal Review UI – Codebase Audit vs Task Requirements

**Scope:** Four services (AI automation, Market research, Compliance services, Document packs).  
**Audit date:** 2025-02 (codebase state at audit).  
**Do not implement blindly:** This document compares task requirements to the existing implementation and calls out gaps and the safest options.

---

## 1. Task summary (requirements)

**When order status = INTERNAL_REVIEW:**

- Show full PDF preview
- Show version history
- Show generation metadata (prompt version, created_at, status)
- **Actions:**
  1. **Approve & Finalise** – requires checkbox "I have reviewed this document"
  2. **Request Regeneration** – modal with: reason dropdown, notes text area (required), optional "sections to improve" checklist; store regen_reason + regen_notes; trigger new generation run and new doc version
  3. **Request More Information** – modal to write what is missing; send email to client with secure link to "Provide requested info"; order → CLIENT_INPUT_REQUIRED; SLA pauses

**Client response:**

- Client submits missing fields
- System resumes → QUEUED → GENERATING → INTERNAL_REVIEW

---

## 2. Current implementation overview

| Area | Location | Status |
|------|----------|--------|
| Admin order review | `AdminOrdersPage.js`, `OrderDetailsPane.jsx`, `DocumentPreviewModal.jsx`, `ActionModals.jsx` | Implemented |
| Document API | `GET /api/admin/orders/{order_id}/documents`, `.../documents/{version}/preview`, `.../token`, `.../view` | Implemented |
| Review actions API | `POST .../approve`, `POST .../request-regen`, `POST .../request-info` | Implemented |
| Client provide-info | `ClientProvideInfoPage.js`, `POST /api/client/orders/{order_id}/submit-input` | Implemented |

---

## 3. Requirement-by-requirement

### 3.1 When order status INTERNAL_REVIEW: show full PDF preview

| Requirement | Implemented | Notes |
|-------------|-------------|--------|
| Full PDF preview | ✅ Yes | `DocumentPreviewModal.jsx` shows PDF in an iframe. Preview URL is token-based (`GET .../documents/{version}/token?format=pdf`) then `.../view?format=pdf&token=...` for iframe. Fallback to direct `.../preview?format=pdf` when token fails. Height ~55vh. |

### 3.2 Show version history

| Requirement | Implemented | Notes |
|-------------|-------------|--------|
| Version history | ✅ Yes | `DocumentPreviewModal` has a `VersionHistory` component: list of versions (v1, v2, …) with status badge, date, regeneration note; clickable to switch the displayed version. Data from `documentVersions` (from `GET .../documents`). |

### 3.3 Show generation metadata (prompt version, created_at, status)

| Requirement | Implemented | Notes |
|-------------|-------------|--------|
| created_at | ✅ Yes | Shown as "Generated At" in `DocumentMetadata` (from `version.generated_at` or `version.created_at`). |
| status | ✅ Yes | Shown as "Status" in metadata and as version status badges (DRAFT, REGENERATED, FINAL, SUPERSEDED). |
| prompt version | ⚠️ Partial | **Backend:** `document_versions_v2` stores `prompt_version_used`. `get_document_versions()` in `document_generator.py` builds `DocumentVersion` from v2 but **does not** map `prompt_version_used` onto `DocumentVersion` (that model has no such field). So the API response `versions[].to_dict()` does **not** include prompt version. **Frontend:** No display of prompt version in metadata. **Gap:** Expose `prompt_version_used` (e.g. template_id + version) in the document versions API and show it in Internal Review metadata. |

### 3.4 Action 1: Approve & Finalise – requires checkbox "I have reviewed this document"

| Requirement | Implemented | Notes |
|-------------|-------------|--------|
| Approve & Finalise | ✅ Yes | `OrderDetailsPane` shows "Approve & Finalize" when status is INTERNAL_REVIEW. `DocumentPreviewModal` has a review gate: checkbox "I have reviewed this document" (`hasReviewed`); Approve is disabled until checked; on approve, `toast.error('Please confirm you have reviewed this document')` if unchecked. Backend `POST .../approve` locks version and transitions to FINALISING. |
| Checkbox required | ✅ Yes | Frontend enforces the checkbox before allowing approve. Backend does not validate it (relies on frontend). |

### 3.5 Action 2: Request Regeneration – modal (reason, notes, optional sections); store regen_reason + regen_notes; trigger new generation

| Requirement | Implemented | Notes |
|-------------|-------------|--------|
| Modal | ✅ Yes | `RegenerationModal` in `ActionModals.jsx`: opens from "Request Revision" (labelled "Request Regeneration" in task). |
| Reason dropdown | ✅ Yes | `REGEN_REASONS` (missing_info, incorrect_wording, tone_style, wrong_emphasis, formatting, factual_error, legal_compliance, other). Sent as `reason`. |
| Notes text area (required) | ✅ Yes | Required; min 10 characters; sent as `correction_notes`. Backend `RegenerationRequest` requires `correction_notes`. |
| Optional "sections to improve" checklist | ⚠️ Partial | Backend accepts `affected_sections: Optional[List[str]]` and stores it. Frontend has `sections` state and passes `affected_sections: sections.length > 0 ? sections : null` on submit, but there is **no UI** that lets the user select sections (no checklist of section names). So the payload supports it; the modal does not show a checklist. **Gap:** Add an optional checklist (e.g. section labels from the doc or a fixed list) and set `sections` from it. |
| Store regen_reason + regen_notes | ✅ Yes | Backend `create_regeneration_request` and `transition_order_state` store reason and notes; metadata includes `regen_reason`, `regen_notes`, `regen_sections`, `regen_guardrails`. |
| Trigger new generation run and new doc version | ✅ Yes | Order moves to REGEN_REQUESTED. Scheduled job `process_queued_orders` (or WF4) processes REGEN_REQUESTED, runs regeneration (orchestrator with regeneration_notes), then transitions back to INTERNAL_REVIEW with a new version. |

### 3.6 Action 3: Request More Information – modal; email with secure link; order → CLIENT_INPUT_REQUIRED; SLA pauses

| Requirement | Implemented | Notes |
|-------------|-------------|--------|
| Modal to write what is missing | ✅ Yes | `RequestInfoModal`: "What information do you need?" (required notes), optional "Quick Select Fields" checklist, optional deadline, optional request attachments. |
| Send email to client with secure link to "Provide requested info" | ✅ Yes | Backend `request_client_info` builds `provide_info_link = f"{frontend_url}/app/orders/{order_id}/provide-info"`, sends email via `build_client_input_required_email` and notification orchestrator. Link is not token-based; client must be logged in (or link is used in a context where client identity is known). |
| Order → CLIENT_INPUT_REQUIRED | ✅ Yes | `transition_order_state(..., new_status=OrderStatus.CLIENT_INPUT_REQUIRED, ...)`. |
| SLA pauses | ✅ Yes | Order workflow and SLA config treat CLIENT_INPUT_REQUIRED as a pause state; `order_service` / workflow set or expect `sla_paused_at` when entering that status. |

### 3.7 Client response: client submits missing fields; system resumes → QUEUED → GENERATING → INTERNAL_REVIEW

| Requirement | Implemented | Notes |
|-------------|-------------|--------|
| Client submits missing fields | ✅ Yes | `ClientProvideInfoPage.js` at `/orders/:orderId/provide-info`: fetches `GET /api/client/orders/{orderId}/input-required`, shows request_notes and requested_fields; client fills and submits via `POST /api/client/orders/{order_id}/submit-input` with `fields` and `confirmation`. |
| System resumes | ⚠️ Design choice | **Current:** Backend `submit_client_input` stores the response and transitions order **directly to INTERNAL_REVIEW** (no re-generation). So the order returns to review with the same document; the new client data is stored for admin to use (e.g. manual regen or next steps). **Task wording:** "system resumes -> QUEUED -> GENERATING -> INTERNAL_REVIEW" implies: after client submits, order goes to QUEUED, then a job runs GENERATING (new doc version using new client data), then INTERNAL_REVIEW. So there are two valid behaviours: (A) Current: client data stored, order → INTERNAL_REVIEW (no auto regen). (B) Task: order → QUEUED, worker runs generation with updated intake, then → INTERNAL_REVIEW. **Gap if task is strict:** Option B would require: on client submit, merge client `fields` into order intake/parameters, transition to QUEUED (not INTERNAL_REVIEW), and let the existing queue worker run generation so a new version is produced with the new data, then WF3 → INTERNAL_REVIEW. |

---

## 4. Gaps summary

| # | Gap | Severity | Recommendation |
|---|-----|----------|----------------|
| 1 | **Prompt version in generation metadata** | Low | Add `prompt_version_used` to the document version payload (e.g. in `document_generator.get_document_versions` when building from document_versions_v2, or return raw v2 fields for versions). Show in DocumentPreviewModal metadata (e.g. "Prompt: template_id vN"). |
| 2 | **"Sections to improve" checklist in Regeneration modal** | Low | Backend already accepts `affected_sections`. Add optional checklist in RegenerationModal (e.g. fixed list like "Executive summary", "Recommendations", "Appendix", or dynamic from doc type) and pass selected items as `affected_sections`. |
| 3 | **Client submit → QUEUED → GENERATING → INTERNAL_REVIEW** | Medium (if required) | If product wants a new document version after client provides info: on client submit, merge `payload.fields` into order (e.g. `parameters` or intake), set status to QUEUED (instead of INTERNAL_REVIEW), and let the existing queue job run (WF2 + WF3). If product is fine with "return to INTERNAL_REVIEW and admin triggers regen if needed", keep current behaviour and document it. |

---

## 5. Conflicts and safe options

- **Resume path:** No conflict in code; only in interpretation of the task. Safest is to document current behaviour (submit → INTERNAL_REVIEW) and, if stakeholders want auto re-gen with client data, add a small change: after storing client response, transition to QUEUED and merge client fields into order intake so the next run generates a new version.
- **Secure link:** The "Provide requested info" link is a URL to the client portal route; it is "secure" in the sense that the client must be authenticated to submit. If the requirement is a one-time token link (no login), that would require a separate tokenized provide-info route and token validation; current design assumes logged-in client. No change recommended unless product explicitly requires token-based access.

---

## 6. What is already in place (no change needed)

- INTERNAL_REVIEW state and pipeline column; admin order detail and document preview entry points.
- Full PDF preview in modal (token-based iframe + fallback).
- Version history list, switchable by version.
- Metadata: order ref, service code, version, status, generated_at, generated_by, hashes (SHA256, intake); only prompt version is missing from API/UI.
- Approve & Finalise with "I have reviewed this document" checkbox enforced in the modal; backend approve and lock version, transition to FINALISING.
- Request Regeneration: modal with reason dropdown and required notes; backend stores regen_reason and regen_notes and moves to REGEN_REQUESTED; job runs regeneration and returns to INTERNAL_REVIEW with new version.
- Request More Information: modal with notes and optional fields checklist; backend stores request, transitions to CLIENT_INPUT_REQUIRED, sends email with link to provide-info; SLA pause behaviour.
- Client provide-info page: load request, form for requested fields and free-form, submit; backend stores response and transitions to INTERNAL_REVIEW (or, if implemented, to QUEUED for re-gen).

---

## 7. Files reference

- **Frontend:** `frontend/src/pages/AdminOrdersPage.js`, `frontend/src/components/admin/orders/OrderDetailsPane.jsx`, `frontend/src/components/admin/orders/DocumentPreviewModal.jsx`, `frontend/src/components/admin/orders/ActionModals.jsx`, `frontend/src/pages/ClientProvideInfoPage.js`, `frontend/src/api/ordersApi.js`.
- **Backend:** `backend/routes/admin_orders.py` (documents, preview, approve, request-regen, request-info), `backend/routes/client_orders.py` (input-required, submit-input), `backend/services/document_generator.py` (get_document_versions, DocumentVersion), `backend/services/order_service.py` (lock_approved_version, create_regeneration_request, create_client_input_request, submit_client_input_response), `backend/services/workflow_automation_service.py` (WF3, WF4, WF5).

---

## 8. Recommended next steps (if implementing)

1. **Prompt version in metadata:** In `document_generator.get_document_versions`, when building from document_versions_v2, include `prompt_version_used` in the returned version (e.g. add optional field on DocumentVersion or a separate `versions` response that includes raw v2 fields). In DocumentPreviewModal, display e.g. "Prompt: {template_id} v{version}".
2. **Sections to improve:** In RegenerationModal, add an optional checklist (e.g. "Sections to focus on" with options like Executive summary, Main body, Recommendations, Other) and set `sections` from selected items so `affected_sections` is populated when present.
3. **Client submit → re-generate:** If product confirms that client submit should trigger a new generation: in `submit_client_input` (client_orders), after storing the response, merge `payload.fields` into the order's parameters/intake, then call `transition_order_state(..., new_status=OrderStatus.QUEUED, ...)` instead of INTERNAL_REVIEW. Rely on existing queue job to run WF2 (generation) and WF3 (→ INTERNAL_REVIEW). Optionally set a flag so the generator uses the updated intake.

This audit reflects the current codebase and is intended to guide decisions without duplicating or conflicting with existing behaviour.
