# Score Explanation PDF & Score Drivers CSV — Implementation Audit

**Purpose:** Check the codebase against the task requirements for enabling “Download score explanation (PDF)” and “Export score drivers (CSV)” (removing “Coming soon”), and for producing professionally branded exports. Identify what is implemented, what is missing, conflicts, and the safest implementation path. **No implementation in this step.**

---

## 1. Is implementation possible now?

**Yes.** The codebase already has the building blocks:

| Capability | Status | Where |
|------------|--------|--------|
| PDF generation | ✅ Present | ReportLab in `requirements.txt`; used in `compliance_pack.py`, `pdf_report_builder.py`, `professional_reports.py`, scripts |
| Client-scoped auth on reports | ✅ Present | `reports.py` uses `client_route_guard(request)` for Evidence Readiness and other client report endpoints |
| Plan gating (reports_pdf / reports_csv) | ✅ Present | `plan_registry.enforce_feature(client_id, "reports_pdf" | "reports_csv")` in `reports.py` |
| Audit logging | ✅ Present | `utils/audit.py` + `create_audit_log`; Evidence Readiness uses `AuditAction.ADMIN_ACTION` with `metadata.report_type` |
| Compliance score payload (drivers, breakdown, model version, etc.) | ✅ Present | `GET /client/compliance-score` returns `score`, `grade`, `stats`, `breakdown`, `components`, `drivers`, `property_breakdown`, `score_last_calculated_at`, `score_model_version`, `model_updated_at`, `data_completeness_percent` |
| Branding for reports | ✅ Present | `professional_reports.get_branding(client_id)`; `pdf_report_builder` and Evidence Readiness use `primary_color`, `secondary_color`, company name; footer disclaimer pattern exists |

**Conclusion:** The “Coming soon” can be removed and the two exports implemented using existing patterns (ReportLab, client auth, plan gating, audit, compliance-score data). Branded PDF is achievable with the current stack.

---

## 2. What exists vs what the task requires

### A) Score Explanation PDF (task spec)

| Task requirement | Current codebase | Gap |
|------------------|------------------|-----|
| Dedicated “Score Explanation” report | ❌ | No endpoint or builder for this exact report. |
| Evidence Readiness PDF | ✅ `POST /api/reports/generate`, `build_portfolio_report` | Different purpose (evidence readiness, different sections). Not a substitute for “Compliance Score Summary (Informational)”. |
| Professional compliance summary PDF | ✅ `download_compliance_summary_pdf` → `professional_report_generator.generate_compliance_summary_pdf` | Different content/layout; task specifies a defined section list (cover, portfolio snapshot, what score means, weighting model, top drivers, property breakdown, appendix). |
| Sections 1–7 (cover, snapshot, what score means, weighting, drivers, property breakdown, appendix) | ❌ | Would need a dedicated builder that consumes the compliance-score payload and outputs this structure. |
| Branding: navy + teal, footer “Pleerity Enterprise Ltd…”, CRN, Page X of Y, generated timestamp | ✅ Partially | `professional_reports` and `pdf_report_builder` have branding and footers; would need to align footer text and page numbering with the task. |
| Audit-style / compliance-safe language | ✅ | Existing reports use disclaimers (“This report does not constitute legal advice”, “Evidence-based”, “Not a legal compliance opinion”). Same approach applies. |

**Verdict:** A **new** “Score Explanation” PDF is required: new endpoint + new ReportLab builder (or dedicated function in an existing module) that takes the compliance-score response and renders the specified sections. Existing Evidence Readiness and professional compliance summary are different products; reusing their builders as-is would not satisfy the spec.

### B) Score Drivers CSV (task spec)

| Task requirement | Current codebase | Gap |
|------------------|------------------|-----|
| Dedicated “Score drivers” CSV | ❌ | No endpoint that returns only score drivers in CSV form. |
| Columns: CRN, Property name/postcode, Requirement, Status, Date used, Date confidence, Evidence uploaded, Next step label, Last updated | ❌ | `reporting_service.generate_requirements_report` CSV has different columns (property_address, requirement_type, status, due_date, documents_count, etc.). No “Next step label” or “Date confidence”. |
| Data source | ✅ | `drivers[]` from `GET /client/compliance-score` has property_name, postcode (from property_breakdown/properties), requirement_name, status, date_used, date_confidence, evidence_uploaded, actions. CRN from client; “Next step” can be derived from `actions`; “Last updated” can be score timestamp or a per-driver field if added. |

**Verdict:** A **new** CSV endpoint that builds rows from `drivers[]` (plus client CRN and optional “last updated”) and returns `text/csv` with the specified columns is required. No existing CSV report matches this shape.

### C) Endpoints and security (task spec)

| Task suggestion | Current pattern | Recommendation |
|----------------|-----------------|----------------|
| `GET /api/reports/score-explanation.pdf?scope=portfolio` | Reports router uses `client_route_guard`; Evidence Readiness uses `POST /reports/generate` with body | **Add** `GET /api/reports/score-explanation.pdf` (optional `scope=portfolio\|property`, `property_id=`) on existing `reports` router. Same auth and plan gate as other client reports. |
| `GET /api/reports/score-drivers.csv?scope=portfolio` | — | **Add** `GET /api/reports/score-drivers.csv` on same router. |
| Auth: client can only access own CRN | ✅ | Enforced by `client_route_guard` and using `user["client_id"]` for all data. |
| Audit log entry per export | ✅ Pattern exists | Use same pattern: `create_audit_log(..., resource_type="report", metadata={"report_type": "score_explanation_pdf"|"score_drivers_csv", "scope": ...})`. Optionally add `AuditAction.REPORT_EXPORTED` for clarity. |
| Short-lived caching (5–15 min) | ❌ | Not implemented for other reports. Can be added later; not blocking. |

### D) Frontend (task spec)

| Task requirement | Current state | Gap |
|------------------|---------------|-----|
| “Download score explanation (PDF)” button | ✅ Present | Disabled with tooltip “Coming soon”. |
| “Export score drivers (CSV)” button | ✅ Present | Disabled with tooltip “Coming soon”. |
| Buttons call endpoints and trigger download | ❌ | Need to enable buttons, call `GET /reports/score-explanation.pdf` and `GET /reports/score-drivers.csv` with `responseType: 'blob'`, create object URL, trigger download, revoke URL. |
| Loading state + error handling | ❌ | Add loading flag and “Export failed, please try again” toast on non-2xx. |
| Toast “Export generated” with timestamp reference | ❌ | Optional; can add on success. |

**Verdict:** Frontend changes are small: enable buttons, wire to new endpoints, blob download, loading/error/success feedback. Plan gate: if user lacks `reports_pdf` / `reports_csv`, show upgrade prompt or keep disabled with tooltip (align with existing Reports page behaviour).

---

## 3. Technical approach: Option 1 vs Option 2

- **Option 1 (HTML template → PDF, e.g. WeasyPrint):** Not in use. Adding WeasyPrint + Jinja templates would introduce a new pattern and dependency; iteration might be easier for design-heavy docs.
- **Option 2 (ReportLab):** **Already the standard** for all PDF reports (Evidence Readiness, compliance pack, professional reports, checklist script). No new dependency; full control; consistent with the rest of the app.

**Recommendation:** Use **Option 2 (ReportLab)** for the Score Explanation PDF. No HTML/Jinja layer for this report; keep a single, consistent PDF approach. If later you want HTML-based reports, that can be a separate initiative.

---

## 4. Conflicts and safest choices

### 4.1 Endpoint path and method

- Task suggests **GET** `/api/reports/score-explanation.pdf` and `/api/reports/score-drivers.csv`.
- Current Evidence Readiness uses **POST** `/api/reports/generate` with body.
- **Recommendation:** Add **GET** endpoints as specified. No conflict; they are new routes. Keep existing POST for Evidence Readiness unchanged.

### 4.2 Where the PDF builder lives

- Task suggests `backend/templates/score_report.html` + Jinja + HTML-to-PDF. There is no `backend/templates/` today and no HTML-based report pipeline.
- **Recommendation:** Implement the Score Explanation PDF in **ReportLab** only. Options: (a) New module e.g. `services/score_report_pdf.py` with a single entrypoint `build_score_explanation_pdf(client_id, score_payload, branding) -> bytes`, or (b) Add a function in `pdf_report_builder.py` (e.g. `build_score_explanation_report`) and keep all report builders in one place. **(b)** is slightly simpler and keeps “deterministic report builders” together.

### 4.3 Plan gating

- Existing client reports are gated by `reports_pdf` (PDF) and `reports_csv` (CSV).
- **Recommendation:** Gate Score Explanation PDF with `reports_pdf` and Score Drivers CSV with `reports_csv`. If the client lacks the feature, return 403 with the same detail shape as other report endpoints so the frontend can show upgrade prompt or leave buttons disabled with tooltip.

### 4.4 Audit action

- Evidence Readiness uses `AuditAction.ADMIN_ACTION` with `metadata.report_type`.
- **Recommendation:** Either (a) add `AuditAction.REPORT_EXPORTED = "REPORT_EXPORTED"` and use it with `metadata.report_type` and `scope`, or (b) keep using `ADMIN_ACTION` with the same metadata. **(a)** is clearer for filtering and reporting; **(b)** avoids a model change. Prefer **(a)** if you want a clean audit taxonomy.

### 4.5 “Last updated” for CSV

- Task asks for “Last updated timestamp” per row. Current `drivers[]` does not have a per-row `updated_at`.
- **Recommendation:** Use a single “Data as of” timestamp for the whole export (e.g. `score_last_calculated_at` or generation time). Add a column e.g. `Last updated` with that value for every row. If later the backend adds per-requirement `updated_at`, the CSV can be extended without breaking the contract.

---

## 5. Data contract and reuse

- **Score Explanation PDF:** Input = compliance-score response (from `calculate_compliance_score(client_id)` or from internal call). No new API contract; reuse existing payload. Optional: `scope=property` + `property_id` could restrict to one property’s breakdown/drivers (task says optional).
- **Score Drivers CSV:** Input = `drivers[]` + client CRN (from client record) + `score_last_calculated_at` (or generation time). All available from current compliance-score + client lookup.

---

## 6. Branding rules (task)

- Use existing brand header (navy + teal). **Supported** via `get_branding` / `primary_color` / `secondary_color` in existing builders.
- Footer every page: “Pleerity Enterprise Ltd – AI-Driven Solutions & Compliance”, CRN, Page X of Y, Generated timestamp. **To be implemented** in the new Score Explanation builder (same idea as existing report footers).
- Language: “Status based on portal records”, “May apply depending on your situation”, no “you are compliant”. **Already the pattern** in disclaimers; apply consistently in the new PDF text.

---

## 7. Recommended implementation order (no blind implementation)

1. **Backend – Score Drivers CSV**
   - Add `GET /api/reports/score-drivers.csv` on `reports` router.
   - Guard with `client_route_guard` and `reports_csv`.
   - Call compliance score (or reuse cached payload if you add caching later); get client for CRN.
   - Build CSV rows from `drivers[]`: CRN, Property name, Postcode, Requirement, Status, Date used, Date confidence, Evidence uploaded (Y/N), Next step label (from `actions`), Last updated (e.g. `score_last_calculated_at`).
   - Return `StreamingResponse` with `media_type="text/csv"` and `Content-Disposition: attachment; filename="score_drivers_YYYYMMDD_HHMM.csv"`.
   - Call `create_audit_log` with report_type `score_drivers_csv`, scope, client_id, actor_id.

2. **Backend – Score Explanation PDF**
   - Add `GET /api/reports/score-explanation.pdf` (optional query: `scope=portfolio|property`, `property_id=`).
   - Guard with `client_route_guard` and `reports_pdf`.
   - Load compliance score payload; load client (name, CRN) and branding.
   - Implement `build_score_explanation_report(client_id, score_payload, client_doc, branding) -> bytes` in `pdf_report_builder.py` (or `score_report_pdf.py`) with ReportLab, sections 1–7, footer with “Pleerity Enterprise Ltd…”, CRN, Page X of Y, generated timestamp.
   - Return `StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=..."}`).
   - Call `create_audit_log` with report_type `score_explanation_pdf`, scope, client_id, actor_id. Optionally store report_id in metadata for “Audit log reference ID” in appendix.

3. **Frontend**
   - ComplianceScorePage: Enable “Download score explanation (PDF)” and “Export score drivers (CSV)” when the user has `reports_pdf` / `reports_csv` (or always show buttons and handle 403 with upgrade toast).
   - On click: set loading, `api.get('/reports/score-explanation.pdf', { responseType: 'blob' })` (and same for CSV), then create blob URL, trigger download, revoke URL, clear loading, toast success or “Export failed, please try again” on error.

4. **Optional**
   - Add `AuditAction.REPORT_EXPORTED` and use it for both exports.
   - Add short-lived in-memory cache (e.g. 5–15 min) for compliance-score payload when generating both PDF and CSV in quick succession (reduces duplicate work only).

---

## 8. Definition of done (exports)

- [ ] `GET /api/reports/score-explanation.pdf` returns a branded, audit-style PDF with sections 1–7 and compliance-safe language.
- [ ] `GET /api/reports/score-drivers.csv` returns CSV with the specified columns (CRN, property, requirement, status, date used, date confidence, evidence, next step, last updated).
- [ ] Both endpoints require auth and are scoped to the client’s data; plan gating applied (reports_pdf / reports_csv).
- [ ] Each export creates an audit log entry (who, when, what).
- [ ] Frontend: “Coming soon” removed; buttons trigger download; loading and error handling in place.

---

## 9. Files to touch (summary)

| Area | Files |
|------|--------|
| Backend | `backend/routes/reports.py` (add 2 GET routes), `backend/services/pdf_report_builder.py` or new `backend/services/score_report_pdf.py` (Score Explanation builder), optionally `backend/models/core.py` (AuditAction.REPORT_EXPORTED) |
| Frontend | `frontend/src/pages/ComplianceScorePage.js` (enable buttons, wire download, loading/error/success) |
| Docs | This audit |

Implement only after approving this audit and the chosen options (ReportLab vs HTML, audit action, plan gating, and CSV “Last updated” semantics).
