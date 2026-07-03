# Account Capability Enforcement Matrix

**Programme:** ILP-4-CAPABILITY-ENFORCEMENT-01 (Phase 0–1 scaffold; Phase 2A pilot)  
**Authority:** `ACCOUNT_CAPABILITY_AUTHORITY.md`, `ACCOUNT_CAPABILITY_CATALOG.md`  
**Status:** Phase 2A pilot routes wired; broader migration deferred

---

## Phase 2A pilot routes (CAP_* only)

| Endpoint | Method | Capability | Action | File |
|----------|--------|------------|--------|------|
| `/api/client/properties` | GET | `CAP_PROP_VIEW` | read | `routes/client.py` |
| `/api/client/properties/{id}/requirements/mark-not-applicable` | POST | `CAP_REQ_RESOLVE` | write | `routes/client.py` |
| `/api/reports/{report_id}/download` | GET | `CAP_REPORT_DOWNLOAD` | read | `routes/reports.py` |
| `/api/documents` | GET | `CAP_DOC_VIEW` | read | `routes/documents.py` |

- Dependency: `client_require_capability()` in `middleware/capability_gating.py`
- `client_route_guard` unchanged (router-level + dependency-internal)
- Report download: `enforce_feature("reports_pdf")` **removed** from pilot handler only
- Tests: `backend/tests/test_account_capability_enforcement_pilot.py`

---

## Purpose

This document is the implementation verification checklist for `CAP_*` enforcement. Each capability row tracks:

| Column | Meaning |
|--------|---------|
| **Capability** | Governed `CAP_*` identifier |
| **Runtime status** | Whether ILP-2 resolver produces a grant |
| **Enforcement status** | Phase 0–1 service / Phase 2+ route wiring |
| **Frontend surface** | Primary UI (deferred until Phase 3+) |
| **Backend endpoint(s)** | API matrix reference (deferred until Phase 2) |
| **Expected grant** | ACA matrix intent |
| **Read-only behaviour** | `READ` contract grant → `READ_ONLY` enforcement semantic |
| **Recovery path** | From `customer_experience.primary_cta` |
| **Regression** | Test reference |

---

## Enforcement semantics (Phase 0–1)

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

## Runtime-resolved capabilities (33) — ENFORCEMENT_READY

These capabilities are present in `_BASE_CAPABILITY_MATRIX` and evaluable by `CapabilityEnforcementService` in Phase 0–1.

| Capability | Runtime | Enforcement | Tests |
|------------|---------|-------------|-------|
| `CAP_AUTH_LOGIN` | ✓ | Service only | `test_denied_deleted_login` |
| `CAP_PROFILE_VIEW` | ✓ | Service only | — |
| `CAP_PROFILE_EDIT` | ✓ | Service only | — |
| `CAP_PROP_VIEW` | ✓ | **Pilot route** | `test_read_only_blocks_write_allows_read`, pilot HTTP tests |
| `CAP_PROP_CREATE` | ✓ | Service only | — |
| `CAP_PROP_EDIT` | ✓ | Service only | — |
| `CAP_REQ_VIEW` | ✓ | Service only | — |
| `CAP_REQ_RESOLVE` | ✓ | **Pilot route** | pilot HTTP tests |
| `CAP_DOC_VIEW` | ✓ | **Pilot route** | pilot HTTP tests |
| `CAP_DOC_UPLOAD` | ✓ | Service only | `test_plan_gated_resolved_*` |
| `CAP_EVIDENCE_VIEW` | ✓ | Service only | — |
| `CAP_EVIDENCE_DOWNLOAD` | ✓ | Service only | — |
| `CAP_REPORT_VIEW` | ✓ | Service only | — |
| `CAP_REPORT_GENERATE_PDF` | ✓ | Service only | `test_plan_gated_resolved_*` |
| `CAP_REPORT_DOWNLOAD` | ✓ | **Pilot route** | pilot HTTP tests |
| `CAP_REPORT_SCHEDULE` | ✓ | Service only | — |
| `CAP_DASHBOARD_VIEW` | ✓ | Service only | — |
| `CAP_TODAY_VIEW` | ✓ | Service only | — |
| `CAP_TODAY_ACT` | ✓ | Service only | — |
| `CAP_CMD_CTR_VIEW` | ✓ | Service only | — |
| `CAP_SCORE_VIEW` | ✓ | Service only | — |
| `CAP_BILLING_VIEW` | ✓ | Service only | — |
| `CAP_BILLING_CHECKOUT` | ✓ | Service only | — |
| `CAP_SUB_VIEW` | ✓ | Service only | — |
| `CAP_SUB_MANAGE` | ✓ | Service only | — |
| `CAP_SUB_RENEW` | ✓ | Service only | — |
| `CAP_DATA_EXPORT` | ✓ | Service only | — |
| `CAP_SUPPORT_ACCESS` | ✓ | Service only | — |
| `CAP_NOTIF_EMAIL` | ✓ | Service only | — |
| `CAP_NOTIF_SMS` | ✓ | Service only | — |
| `CAP_AI_ASSISTANT` | ✓ | Service only | — |
| `CAP_OPS_MAINTENANCE` | ✓ | Service only | — |
| `CAP_TENANT_PORTAL` | ✓ | Service only | — |

---

## Catalog gap inventory — MISSING_FROM_RUNTIME (71)

Capabilities documented in `ACCOUNT_CAPABILITY_CATALOG.md` but **not** in the ILP-2 runtime resolver matrix. Phase 0–1 returns `UNKNOWN_CAPABILITY` / safe deny when evaluated. Rationale: extend resolver in a governed follow-up without changing Runtime Contract schema shape.

| Domain | Capability | Rationale |
|--------|------------|-----------|
| Auth | `CAP_AUTH_LOGOUT`, `CAP_AUTH_PASSWORD_RESET`, `CAP_AUTH_MFA`, `CAP_AUTH_SESSION_RECOVERY` | Session/auth endpoints use separate guards; deferred to Phase 2 API mapping |
| Profile | `CAP_PROFILE_JURISDICTION` | Settings route not in runtime matrix |
| Subscription | `CAP_SUB_UPGRADE`, `CAP_SUB_DOWNGRADE`, `CAP_SUB_CANCEL` | Billing actions share `CAP_SUB_MANAGE`; split in Phase 2 |
| Billing | `CAP_BILLING_INVOICES`, `CAP_BILLING_PAYMENT_METHODS` | Billing exempt routes; matrix extension deferred |
| Property | `CAP_PROP_ARCHIVE`, `CAP_PROP_DELETE`, `CAP_PROP_IMPORT` | Sub-actions of property module; deferred |
| Requirements | `CAP_REQ_MARK_N_A`, `CAP_REQ_COMPLETE` | API matrix documented; resolver row deferred |
| Documents | `CAP_DOC_REPLACE`, `CAP_DOC_DELETE`, `CAP_DOC_BULK_ZIP`, `CAP_DOC_MULTI_UPLOAD` | Map to `CAP_DOC_UPLOAD` family in Phase 2 |
| Evidence | `CAP_EVIDENCE_LINK`, `CAP_EVIDENCE_REGISTRY` | Evidence registry sub-capabilities deferred |
| Reports | `CAP_REPORT_GENERATE_CSV`, `CAP_REPORT_SHARE`, `CAP_REPORT_AUDIT_PACK` | Plan-gated variants; resolver extension deferred |
| Score | `CAP_SCORE_EXPLAIN`, `CAP_SCORE_TREND`, `CAP_SCORE_SNAPSHOT` | Score module caps deferred |
| Risk/Ops | `CAP_RISK_VIEW`, `CAP_RISK_ANALYSIS`, `CAP_COMPLIANCE_MONITOR`, `CAP_COMPLIANCE_ACTIVITY`, `CAP_CALENDAR_VIEW`, `CAP_WORK_QUEUE_VIEW`, `CAP_LEDGER_VIEW`, `CAP_LEDGER_EXPORT` | Ops/dashboard caps deferred |
| Notifications | `CAP_NOTIF_PORTAL`, `CAP_NOTIF_PREFS` | Notification prefs deferred |
| Export | `CAP_EXPORT_CSV`, `CAP_EXPORT_PDF`, `CAP_EXPORT_ZIP`, `CAP_EXPORT_API` | Alias caps; map to report/doc caps in Phase 2 |
| AI | `CAP_AI_EXTRACTION_BASIC`, `CAP_AI_EXTRACTION_ADVANCED`, `CAP_AI_REVIEW`, `CAP_KNOWLEDGE_CENTRE` | AI module deferred |
| Ops | `CAP_OPS_ISSUES_VIEW`, `CAP_OPS_CONTRACTORS`, `CAP_OPS_PREDICTIVE`, `CAP_OPS_RENT`, `CAP_OPS_APPROVALS`, `CAP_OPS_COMPLIANCE_REVIEW` | Ops module caps deferred (partial feature_key mapping exists) |
| Tenant | `CAP_TENANT_MANAGE`, `CAP_TENANT_MESSAGES` | Tenant portal deferred |
| Integration | `CAP_INTEGRATION_WEBHOOKS`, `CAP_INTEGRATION_READ_API` | Integration module deferred |
| Branding | `CAP_BRANDING_VIEW`, `CAP_BRANDING_EDIT`, `CAP_BRANDING_WHITE_LABEL` | Branding deferred |
| Support | `CAP_SUPPORT_REQUEST`, `CAP_ACCOUNT_RECOVERY`, `CAP_AUDIT_LOG_VIEW`, `CAP_AUDIT_LOG_EXPORT` | Support/audit deferred |
| Background | `CAP_BG_*` (9) | Governed by `background_policy` not customer `capabilities` map (ILP-8) |

Full machine-readable inventory: `backend/docs/audit/account_lifecycle_ilp_04/ACCOUNT_LIFECYCLE_ILP_04_EVIDENCE.json`.

---

## Phase 0–1 deliverables

| Component | Path |
|-----------|------|
| Enforcement service | `backend/services/account_capability_enforcement.py` |
| Compatibility mapping | `backend/services/capability_compatibility.py` |
| Route dependency helper | `backend/middleware/capability_gating.py` (`client_require_capability` — **4 pilot routes**) |
| Diagnostics API | `GET /api/client/capability-enforcement/diagnostic` |
| Drift script | `backend/scripts/account_capability_enforcement_drift_diagnostic.py` |
| Unit tests | `backend/tests/test_account_capability_enforcement.py` |
| Pilot route tests | `backend/tests/test_account_capability_enforcement_pilot.py` |

---

## Deferred (Phase 2B+)

- `client_route_guard` replacement
- Remaining route `require_capability()` wiring (beyond 4 pilot endpoints)
- Frontend `useCapability()` / guards
- `hasFeature()` internal delegation
- ILP-6 governed API error payloads

---

## Regression proof (Phase 0–1)

- No changes to `middleware/__init__.py` `client_route_guard`
- No changes to `plan_registry.enforce_feature` call sites
- No frontend changes
- Runtime Contract schema unchanged
- Portal Mode presentation unchanged (ILP-3)
- 82 backend tests passing (ILP-1/2 + ILP-4 Phase 0–1)
