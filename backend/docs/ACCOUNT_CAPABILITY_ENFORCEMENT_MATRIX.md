# Account Capability Enforcement Matrix

**Programme:** ILP-4-CAPABILITY-ENFORCEMENT-01 (Phase 0–1 scaffold; Phase 2A pilot; Phase 2B Wave 1)  
**Authority:** `ACCOUNT_CAPABILITY_AUTHORITY.md`, `ACCOUNT_CAPABILITY_CATALOG.md`  
**Status:** Phase 2B Wave 1 — evidence, reports, and documents modules fully capability-governed

---

## Phase 2B Wave 1 migrated modules (CAP_* only)

### `routes/client_compliance_evidence.py` (full)

| Endpoint | Method | Capability | Action |
|----------|--------|------------|--------|
| `/api/client/compliance-evidence/org-review-queue` | GET | `CAP_EVIDENCE_VIEW` | read |
| `/api/client/properties/{id}/requirements/{id}/evidence-resolution` | GET | `CAP_EVIDENCE_VIEW` | read |
| `/api/client/properties/{id}/requirements/{id}/compliance-evidence` | GET | `CAP_EVIDENCE_VIEW` | read |
| `/api/client/properties/{id}/requirements/{id}/compliance-evidence` | POST | `CAP_REQ_RESOLVE` | write |
| `/api/client/properties/{id}/requirements/{id}/compliance-evidence/{id}/verification` | POST | `CAP_REQ_RESOLVE` | write |

### `routes/reports.py` (client routes — full)

| Endpoint | Method | Capability | Action | Notes |
|----------|--------|------------|--------|-------|
| `/api/reports/generate` | POST | `CAP_REPORT_GENERATE_PDF` | write | |
| `/api/reports`, `/api/reports/list` | GET | `CAP_REPORT_VIEW` | read | |
| `/api/reports/score-drivers.csv` | GET | `CAP_REPORT_GENERATE_CSV` | write | |
| `/api/reports/score-explanation.pdf` | GET | `CAP_REPORT_GENERATE_PDF` | write | |
| `/api/reports/compliance-summary` | GET | `CAP_REPORT_VIEW` + format assert | read/write | `format=pdf` → `CAP_REPORT_GENERATE_PDF`; `format=csv` → `CAP_REPORT_GENERATE_CSV` |
| `/api/reports/requirements` | GET | `CAP_REPORT_VIEW` + format assert | read/write | same pattern |
| `/api/reports/{report_id}/download` | GET | `CAP_REPORT_DOWNLOAD` | read | |
| `/api/reports/artifacts/{artifact_id}/download` | GET | `CAP_REPORT_DOWNLOAD` | read | |
| `/api/reports/available` | GET | `CAP_REPORT_VIEW` | read | |
| `/api/reports/schedules` | GET | `CAP_REPORT_SCHEDULE` | read | |
| `/api/reports/schedules` | POST | `CAP_REPORT_SCHEDULE` | write | |
| `/api/reports/schedules/{id}` | DELETE | `CAP_REPORT_SCHEDULE` | write | |
| `/api/reports/schedules/{id}/toggle` | PATCH | `CAP_REPORT_SCHEDULE` | write | |
| `/api/reports/professional/*` | GET | `CAP_REPORT_GENERATE_PDF` | write | compliance-summary, requirements, expiry-schedule |
| `/api/reports/professional/audit-log` | GET | `CAP_AUDIT_LOG_EXPORT` | read | |
| `/api/reports/audit-logs` | GET | — | — | **Admin only** (`admin_route_guard`); not customer lifecycle |

`CAP_REPORT_AUDIT_PACK` added to runtime matrix for governed audit-pack flows; **deferred** to Wave 2 (`client.py` evidence-pack routes).

No `enforce_feature()` remains in `reports.py` client handlers.

### `routes/documents.py` (client routes — full)

| Endpoint | Method | Capability | Action | Notes |
|----------|--------|------------|--------|-------|
| `/api/documents` | GET | `CAP_DOC_VIEW` | read | |
| `/api/documents/{id}/file` | GET | `CAP_DOC_VIEW` | read | |
| `/api/documents/{id}/extraction` | GET | `CAP_DOC_VIEW` | read | |
| `/api/documents/{id}/details` | GET | `CAP_DOC_VIEW` | read | |
| `/api/documents/upload` | POST | `CAP_DOC_UPLOAD` | write | |
| `/api/documents/bulk-upload` | POST | `CAP_DOC_BULK_ZIP` | write | |
| `/api/documents/zip-upload` | POST | `CAP_DOC_BULK_ZIP` | write | |
| `/api/documents/validate` | POST | `CAP_DOC_UPLOAD` | write | |
| `/api/documents/{id}` | DELETE | `CAP_DOC_UPLOAD` | write | |
| `/api/documents/{id}/apply-extraction` | POST | `CAP_DOC_UPLOAD` | write | |
| `/api/documents/{id}/reject-extraction` | POST | `CAP_DOC_UPLOAD` | write | |
| `/api/documents/{id}/reconcile-linkage` | POST | `CAP_DOC_UPLOAD` | write | |
| `/api/documents/analyze/{id}` | POST | `CAP_DOC_VIEW` | read | `return_advanced=true` → in-handler `CAP_AI_EXTRACTION_ADVANCED` write |

Admin routes (`/api/documents/admin/*`, verify/reject) remain **`admin_route_guard`** — not customer lifecycle.

No `enforce_feature()` / `require_feature()` remains in client document handlers.

---

## Phase 2A pilot routes (retained)

| Endpoint | Method | Capability | Action | File |
|----------|--------|------------|--------|------|
| `/api/client/properties` | GET | `CAP_PROP_VIEW` | read | `routes/client.py` |
| `/api/client/properties/{id}/requirements/mark-not-applicable` | POST | `CAP_REQ_RESOLVE` | write | `routes/client.py` |
| `/api/reports/{report_id}/download` | GET | `CAP_REPORT_DOWNLOAD` | read | `routes/reports.py` |
| `/api/documents` | GET | `CAP_DOC_VIEW` | read | `routes/documents.py` |

- Dependency: `client_require_capability()` / `assert_client_capability()` in `middleware/capability_gating.py`
- Denied responses: governed `capability_denied` payload via `capability_denied_http_detail()`
- Tests: `test_account_capability_enforcement_pilot.py`, `test_account_capability_enforcement_wave1.py`

---

## Runtime contract extensions (Wave 1)

New `_BASE_CAPABILITY_MATRIX` rows (schema unchanged):

| Capability | Plan key | Distinct from |
|------------|----------|---------------|
| `CAP_REPORT_GENERATE_CSV` | `reports_csv` | `CAP_REPORT_GENERATE_PDF` |
| `CAP_AUDIT_LOG_EXPORT` | `audit_log_export` | `CAP_REPORT_VIEW` |
| `CAP_REPORT_AUDIT_PACK` | `audit_log_export` (matrix row; route deferred) | `CAP_AUDIT_LOG_EXPORT` |
| `CAP_DOC_BULK_ZIP` | `zip_upload` | `CAP_DOC_UPLOAD` |
| `CAP_AI_EXTRACTION_ADVANCED` | `ai_extraction_advanced` | `CAP_AI_ASSISTANT` |

Portal ceilings updated for `BILLING_RECOVERY`, `READ_ONLY`, `SUSPENDED`.

---

## Purpose

This document is the implementation verification checklist for `CAP_*` enforcement.

| Column | Meaning |
|--------|---------|
| **Capability** | Governed `CAP_*` identifier |
| **Runtime status** | Whether ILP-2 resolver produces a grant |
| **Enforcement status** | Phase 0–1 service / Phase 2+ route wiring |
| **Expected grant** | ACA matrix intent |
| **Read-only behaviour** | `READ` contract grant → `READ_ONLY` enforcement semantic |
| **Recovery path** | From `customer_experience.primary_cta` |
| **Regression** | Test reference |

---

## Enforcement semantics

| Contract grant | Enforcement semantic | Read action | Write action |
|----------------|---------------------|-------------|--------------|
| `ALLOW` | ALLOW | ✓ | ✓ |
| `READ` | **READ_ONLY** | ✓ | ✗ (governed reason) |
| `LIMITED` | LIMITED | ✓ | ✓ (grace-limited) |
| `DENY` | DENY | ✗ | ✗ |
| `HIDDEN` | HIDDEN | ✗ | ✗ |
| `PLAN_GATED` | Pre-resolved to ALLOW/DENY in contract | per resolved grant | per resolved grant |

**Source of truth:** `CapabilityEnforcementService` → Runtime Contract `capabilities` map only.

---

## Runtime-resolved capabilities (38) — ENFORCEMENT_READY

Wave 1 adds five capabilities to the prior 33-capability runtime set.

| Capability | Runtime | Enforcement (Wave 1) | Tests |
|------------|---------|------------------------|-------|
| `CAP_EVIDENCE_VIEW` | ✓ | **Wave 1 routes** | wave1 lifecycle matrix |
| `CAP_REQ_RESOLVE` | ✓ | pilot + **Wave 1 evidence write** | wave1 lifecycle matrix |
| `CAP_REPORT_VIEW` | ✓ | **Wave 1 reports** | wave1 lifecycle matrix |
| `CAP_REPORT_GENERATE_PDF` | ✓ | **Wave 1 reports** | wave1 + plan-gated |
| `CAP_REPORT_GENERATE_CSV` | ✓ | **Wave 1 reports** | wave1 + plan-gated |
| `CAP_REPORT_DOWNLOAD` | ✓ | pilot + **Wave 1 reports** | wave1 lifecycle matrix |
| `CAP_REPORT_SCHEDULE` | ✓ | **Wave 1 reports** | wave1 lifecycle matrix |
| `CAP_AUDIT_LOG_EXPORT` | ✓ | **Wave 1 reports** | wave1 lifecycle matrix |
| `CAP_REPORT_AUDIT_PACK` | ✓ | matrix only (route deferred) | — |
| `CAP_DOC_VIEW` | ✓ | pilot + **Wave 1 documents** | wave1 lifecycle matrix |
| `CAP_DOC_UPLOAD` | ✓ | **Wave 1 documents** | wave1 lifecycle matrix |
| `CAP_DOC_BULK_ZIP` | ✓ | **Wave 1 documents** | wave1 lifecycle matrix |
| `CAP_AI_EXTRACTION_ADVANCED` | ✓ | **Wave 1 analyze advanced** | wave1 + plan-gated |

(Remaining 25 capabilities from Phase 0–1 remain service-only until Wave 2+.)

---

## Wave 1 lifecycle test coverage

`test_account_capability_enforcement_wave1.py` parametrizes:

`ACTIVE`, `TRIAL`, `GRACE_PERIOD`, `CANCELLATION_SCHEDULED`, `READ_ONLY`, `CANCELLED_IMMEDIATE`, `SUBSCRIPTION_EXPIRED`, `SUSPENDED`, `ARCHIVED`, `UNKNOWN`

Across evidence read/write, reports view/CSV/schedule/audit-log, documents list/delete/details/analyze-advanced.

---

## Deferred (Wave 2+)

- `routes/client.py` evidence-pack job routes (`CAP_REPORT_AUDIT_PACK` consumer)
- Properties / requirements / portfolio module migration
- Frontend `useCapability()` consumption
- `client_route_guard` capability integration
- Resolver matrix extension for remaining catalog-gap capabilities

---

## Deliverables

| Component | Path |
|-----------|------|
| Enforcement service | `backend/services/account_capability_enforcement.py` |
| Runtime contract | `backend/services/account_lifecycle_runtime_contract.py` |
| Route helpers | `backend/middleware/capability_gating.py` |
| Wave 1 routes | `client_compliance_evidence.py`, `reports.py`, `documents.py` |
| Unit tests | `test_account_capability_enforcement.py` |
| Pilot tests | `test_account_capability_enforcement_pilot.py` |
| Wave 1 tests | `test_account_capability_enforcement_wave1.py` |
| Audit evidence | `docs/audit/account_lifecycle_ilp_04/` |

---

## Regression proof (Wave 1)

- `client_route_guard` unchanged in `middleware/__init__.py`
- Runtime Contract **schema** unchanged (new capability rows only)
- `client.py` evidence-pack routes **not** migrated
- Non-Wave-1 routes may still use `enforce_feature()`
- Frontend unchanged
