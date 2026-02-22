# Deterministic PDF Report Builder – Gap Analysis

## Task requirements (summary)

- **A)** Create `backend/services/pdf_report_builder.py`: `build_portfolio_report(client_id) -> bytes`, `build_property_report(client_id, property_id) -> bytes`; deterministic template; uses stored data (clients, properties, documents, compliance status, score snapshots, audit logs); derived fields: counts, days_to_expiry, risk_level, top risk drivers, score_delta.
- **B)** POST /api/reports/generate: body `{ scope, property_id? }`; auth (client role); call builder; return application/pdf; **store metadata in reports collection**: `{ client_id, scope, property_id, created_at, score_at_time, risk_level_at_time, storage_url? }`.
- **C)** Frontend Reports page: Generate portfolio PDF; Generate property PDF; **List previous reports with download**.
- **D)** No legal language: replace "compliant/non-compliant" with "evidence readiness", "missing/expired evidence", "risk level". PDF footer: **"This report does not constitute legal advice."**
- **E)** Tests: report generation returns PDF bytes; **includes CRN + timestamp in PDF content**.

---

## Current state

| Requirement | Current implementation | Gap |
|-------------|------------------------|-----|
| **PDF builder module** | `backend/services/report_service.py`: async `generate_evidence_readiness_pdf(client_id, scope, property_id) -> BytesIO`. Single function; no separate `pdf_report_builder.py`. | Task asks for **`pdf_report_builder.py`** with **sync** `build_portfolio_report(client_id) -> bytes` and `build_property_report(client_id, property_id) -> bytes`. No such file. |
| **Data sources** | report_service uses: clients, properties, requirements, audit_logs. **No** documents collection, **no** score snapshots / score_delta in PDF. | Task: "Uses stored data (documents, compliance status, score snapshots, audit logs)" and derived **days_to_expiry, risk_level, top risk drivers, score_delta**. |
| **Endpoint** | POST /api/reports/generate exists; body `{ scope, property_id? }`; auth + reports_pdf; calls `generate_evidence_readiness_pdf`; returns PDF; **audit log only**, no DB store. | **Reports collection** not used; no metadata stored (score_at_time, risk_level_at_time, created_at, storage_url?). |
| **List previous reports** | GET /reports/available returns **report types** (compliance_summary, requirements, audit_logs), not past report runs. | Task: "List previous reports with download". No backend storage or endpoint for past runs. |
| **Frontend** | Reports page: one "Evidence Readiness Report" card with **Generate PDF** (portfolio only). No property selector; no "list previous reports" section. | Need: **Generate property PDF** (property dropdown); **List previous reports** with download links. |
| **Wording / disclaimer** | report_service: "This report reflects document status recorded within the platform and does not constitute legal advice." PDF and some UI use "evidence readiness" / risk; elsewhere still "compliant/non-compliant". | Task: PDF footer exactly **"This report does not constitute legal advice."** Replace compliant/non-compliant with evidence readiness, missing/expired evidence, risk level. |
| **Tests** | test_report_service: PDF returns bytes; disclaimer constant. | Task: add **CRN + timestamp in PDF content** assertion. |

---

## Conflicts and recommended approach

### 1. `report_service.py` vs `pdf_report_builder.py`

- **Conflict:** Task explicitly requires **`pdf_report_builder.py`** with sync `build_portfolio_report` / `build_property_report` returning **bytes**. Existing code is **`report_service.py`** with one async function returning BytesIO.
- **Recommendation:**  
  - **Create `pdf_report_builder.py`** as the single deterministic template layer: sync, returns `bytes`, implements `build_portfolio_report(client_id)` and `build_property_report(client_id, property_id)` using stored data and derived fields (counts, days_to_expiry, risk_level, top risk drivers, score_delta).  
  - **Do not duplicate** the full PDF layout in two places. Either:  
    - **Option A (recommended):** Implement the PDF in `pdf_report_builder.py` only; have POST /api/reports/generate call the builder (e.g. via `run_in_executor` or a one-line async wrapper). Keep `report_service.py` as a thin async wrapper that calls the builder so existing callers (if any) keep working, or switch the route to call the builder directly and leave `report_service` for legacy/compatibility only.  
    - **Option B:** Put all logic in `report_service` and add a second module `pdf_report_builder.py` that only delegates to it (sync wrapper). That contradicts the task’s "deterministic template" in a dedicated builder and keeps the current async/BytesIO API.  
  **Safest:** Option A – new `pdf_report_builder.py` is the source of truth; endpoint uses it; optionally refactor `report_service` to call the builder so one code path.

### 2. Reports collection and "list previous reports"

- **Conflict:** Task requires storing metadata in a **reports** collection and frontend "list previous reports with download". Today nothing is stored for report runs.
- **Recommendation:**  
  - **Introduce a `reports` collection** (or equivalent name, e.g. `report_runs`). On each successful POST /api/reports/generate, insert: `{ client_id, scope, property_id?, created_at, score_at_time, risk_level_at_time, storage_url? }`. Use a stable `report_id` (e.g. ObjectId or UUID) for each run.  
  - **List endpoint:** Add e.g. GET /api/reports (or GET /api/reports/list) returning, for the current client, recent report metadata (report_id, scope, property_id, created_at, score_at_time, risk_level_at_time, optional download link).  
  - **Download:** Task has `storage_url?` optional. Two approaches:  
    - **Minimal (no blob storage):** No storage_url; "download" = either "Regenerate" (same scope/property_id, current data) or a dedicated GET /api/reports/{report_id}/download that **re-generates** the PDF with stored scope/property_id (still current data).  
    - **With storage:** Persist PDF to blob/store and set storage_url; download = redirect or signed URL.  
  **Safest for scope:** Implement metadata + list + "download" as re-generate (same scope/property_id) so we don’t add blob storage unless required. Document that "past report" list shows metadata and download re-generates with current data.

### 3. Disclaimer and wording

- **Conflict:** Current disclaimer is longer; task wants short footer and no "compliant/non-compliant" in report wording.
- **Recommendation:**  
  - In the **PDF** (builder): Use footer text exactly: **"This report does not constitute legal advice."**  
  - In the **PDF body**: Use only "evidence readiness", "risk level", "missing or expired evidence" (no "compliant/non-compliant").  
  - Leave existing `EVIDENCE_READINESS_DISCLAIMER` in report_service/builder as this short line or remove it from PDF and use only the footer. No change to unrelated legal copy elsewhere unless part of this task.

### 4. Sync builder vs async endpoint

- **Conflict:** Builder must be sync (task: `-> bytes`); FastAPI endpoint is async.
- **Recommendation:** Endpoint remains async. Call sync builder with `asyncio.to_thread(build_portfolio_report, client_id)` (or `run_in_executor`) so we don’t block the event loop. No new thread pool needed on Python 3.9+.

---

## Implementation plan (for approval)

1. **Backend: `pdf_report_builder.py`**
   - Add `backend/services/pdf_report_builder.py`.
   - Implement `build_portfolio_report(client_id: str) -> bytes` and `build_property_report(client_id: str, property_id: str) -> bytes`.  
   - Use **stored data only** (clients, properties, requirements, audit_logs; optionally documents and score_change_log / score snapshots for score_delta and top risk drivers).  
   - Compute **derived fields**: counts (valid, expiring, overdue, missing), days_to_expiry where applicable, risk_level, top risk drivers, score_delta (from latest score_change_log or property).  
   - Deterministic template (e.g. ReportLab): cover (client, CRN, scope, timestamp), executive summary, portfolio breakdown or property detail, requirement matrix, methodology, audit snapshot, **footer: "This report does not constitute legal advice."** No "compliant/non-compliant" in text.  
   - **Sync only**; no async. Accept `db` (or get_db() inside if acceptable for a sync module – otherwise pass db in to keep builder testable without async).

2. **Backend: reports collection and endpoint**
   - On successful POST /api/reports/generate: build PDF via builder; then insert into **reports** collection: `{ report_id, client_id, scope, property_id?, created_at, score_at_time, risk_level_at_time, storage_url? }` (storage_url null if no blob). Return PDF as today.  
   - Add GET /api/reports (or /api/reports/list): auth client; return list of report metadata for client_id, sorted by created_at desc, with report_id for download.  
   - Add GET /api/reports/{report_id}/download (or query param on list): same auth; verify report belongs to client; **re-generate** PDF with stored scope/property_id and return application/pdf (no blob storage) – or later add storage_url and redirect/serve file.

3. **Backend: route wiring**
   - POST /api/reports/generate: keep body and auth; call `pdf_report_builder.build_portfolio_report` or `build_property_report` (via asyncio.to_thread); persist metadata; return StreamingResponse with PDF bytes.  
   - Optionally refactor `report_service.generate_evidence_readiness_pdf` to call the builder (same output) to avoid duplication; or leave as-is and only use the builder from the route.

4. **Frontend: Reports page**
   - **Generate portfolio PDF**: keep existing button; ensure it still calls POST /api/reports/generate with scope portfolio (no change if endpoint stays same).  
   - **Generate property PDF**: add property dropdown and a second button that calls POST /api/reports/generate with scope property and selected property_id.  
   - **List previous reports**: new section "Previous reports"; on load call GET /api/reports; show table/cards (date, scope, property, score_at_time, risk_level_at_time); "Download" calls GET /api/reports/{report_id}/download (or re-generate with scope/property_id) and triggers file download.

5. **Wording**
   - In `pdf_report_builder.py` (and any report_service code that still emits this PDF): replace any "compliant/non-compliant" with "evidence readiness" / "risk level" / "missing or expired evidence"; set PDF footer to exactly "This report does not constitute legal advice."  
   - No broad find-replace across the rest of the app in this task unless specified.

6. **Tests**
   - **Report generation returns PDF bytes:** Keep or move to builder test; call `build_portfolio_report(client_id)` (and optionally `build_property_report`) with mocked db; assert return is bytes, len > 0, starts with b"%PDF".  
   - **CRN + timestamp in PDF:** Add test that builds a PDF with known client (CRN e.g. "CRN-001") and fixed time (or mocked now); assert the raw bytes or extracted text contain "CRN-001" (or the CRN) and a timestamp string (e.g. "Generated" or ISO date).  
   - No regression to provisioning or billing (no changes there).

---

## File reference summary

| Action | File |
|--------|------|
| Create | `backend/services/pdf_report_builder.py` |
| Modify | `backend/routes/reports.py` (POST /generate → use builder + save to reports; add GET /reports, GET /reports/{id}/download) |
| Optional refactor | `backend/services/report_service.py` (call builder to avoid duplication) |
| Modify | `frontend/src/pages/ReportsPage.js` (property PDF button, previous reports list + download) |
| Add/update | `backend/tests/test_report_service.py` or `test_pdf_report_builder.py` (PDF bytes, CRN + timestamp in content) |

Once you approve this plan (or specify changes), implementation can proceed along these lines without blind duplication or conflict with existing reporting.
