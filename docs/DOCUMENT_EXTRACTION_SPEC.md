# Document Extraction Spec – AI-Assisted Field Extraction

## Purpose

AI is used **only** to extract and normalize fields from user-uploaded compliance documents and to suggest mappings to requirements. It **does not** provide legal advice or compliance verdicts. All AI output is treated as **suggested**; user or admin must confirm before any value is applied to compliance evidence.

---

## Flow (high level)

1. **Upload** (vault or intake migration) creates a document record. Extraction is **enqueued** asynchronously (non-blocking).
2. **Extraction job** runs in background: read file → extract text (PDF text or OCR, capped) → call AI with text only → validate JSON → compute confidence and status → store result in `extracted_documents` and set `documents.extraction_id` / `documents.extraction_status`.
3. **Status** is set by rules: e.g. high confidence + expiry_date present → EXTRACTED; else → NEEDS_REVIEW; errors → FAILED.
4. **User/Admin** sees status badge and can open “Review extraction”: view suggested fields and confidence, then **Confirm & apply** (writes to requirement, marks CONFIRMED), **Edit then confirm**, or **Reject** (marks REJECTED, nothing applied).
5. **Apply** is explicit only: no automatic application of AI output to compliance evidence.

---

## Status meanings

| Status | Meaning |
|--------|--------|
| **PENDING** | Extraction job queued or in progress; no result yet. |
| **EXTRACTED** | AI returned valid output; confidence ≥ threshold and key fields (e.g. expiry_date) present. Ready for user review; not yet applied. |
| **NEEDS_REVIEW** | AI returned output but confidence below threshold and/or key fields missing. User must review before applying. |
| **CONFIRMED** | User (or admin) confirmed and applied; suggested values have been written to the requirement/evidence. |
| **REJECTED** | User (or admin) rejected the suggestion; no values applied. |
| **FAILED** | Extraction failed (e.g. parse error, AI disabled, rate limit, AI_NOT_CONFIGURED). |

---

## No legal advice

- The system and its prompts **must not** state or imply that the document is legally compliant or that it satisfies any regulatory obligation.
- Wording must be limited to: extraction of visible fields (dates, numbers, addresses, document type), suggestion of mapping to a requirement, and confidence in the extraction. No “compliant”, “valid”, “certified” or similar legal conclusions.
- If AI returns any such language, it is not used; extraction is for **field population and mapping suggestion** only. Compliance status remains determined by the deterministic compliance engine after evidence is applied and verified.

---

## Data model (target)

- **extracted_documents** (or equivalent): one record per extraction run; fields include document_id, client_id, property_id (nullable), source (vault_upload | intake_upload), extracted fields (doc_type, certificate_number, issue_date, expiry_date, inspector_company, inspector_id, address_line_1, postcode, property_match_confidence, overall_confidence, notes), mapping_suggestion (requirement_key, suggested_property_id), status, errors, and **audit** (model, prompt_version, tokens if available, **raw_response_json**, created_at, updated_at).
- **documents**: `extraction_id` (reference to extracted_documents), `extraction_status` (denormalized for list/badge).

---

## Auditability

- Every extraction stores: **model name**, **prompt_version**, **timestamp**, and **raw_response_json** (full). Optionally: text snippet used (capped) or hash. This supports reproducibility and audit.

---

## Safety

- AI output **never** overwrites user-entered values without explicit confirm.
- If confidence is below threshold or key fields are missing, status is NEEDS_REVIEW; CONFIRMED is only set after explicit user/admin action.
- If AI is disabled or misconfigured, extraction is marked FAILED with a clear error_code (e.g. AI_NOT_CONFIGURED); upload and other flows continue unchanged.
- Rate limiting (global and per client/day) prevents runaway usage.
