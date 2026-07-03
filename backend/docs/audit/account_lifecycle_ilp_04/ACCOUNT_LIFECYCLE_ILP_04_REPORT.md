# ILP-4 Capability Enforcement — Phase 2B Wave 1 Report

**Programme:** ILP-4-CAPABILITY-ENFORCEMENT-01 (Phase 2B Wave 1)  
**Branch:** `develop`  
**Verdict:** `ILP_04_PHASE_2B_WAVE_1_COMPLETE`  
**Date:** 2026-07-03

---

## Summary

Phase 2B Wave 1 fully migrates three customer API modules to `client_require_capability()` / `assert_client_capability()` — eliminating hybrid `enforce_feature()` gates inside those modules while extending the Runtime Contract capability matrix for report and document capabilities required by the route mapping.

Phase 2A pilot routes remain in place. Wave 2 (properties/requirements/portfolio beyond pilot, `client.py` evidence-pack) is **not** started.

---

## Wave 1 scope delivered

| Module | Status | Client endpoints |
|--------|--------|------------------|
| `routes/client_compliance_evidence.py` | **Full** | 5 |
| `routes/reports.py` | **Full** (client) | 18 client routes |
| `routes/documents.py` | **Full** (client) | 12+ client routes |

**Explicitly deferred:** `client.py` evidence-pack job routes (`CAP_REPORT_AUDIT_PACK` consumer).

---

## Runtime contract extensions (schema unchanged)

New `_BASE_CAPABILITY_MATRIX` rows:

- `CAP_REPORT_GENERATE_CSV` → plan key `reports_csv`
- `CAP_AUDIT_LOG_EXPORT` → plan key `audit_log_export`
- `CAP_REPORT_AUDIT_PACK` → plan key `audit_log_export` (matrix ready; route deferred)
- `CAP_DOC_BULK_ZIP` → plan key `zip_upload`
- `CAP_AI_EXTRACTION_ADVANCED` → plan key `ai_extraction_advanced`

Portal ceilings updated for `BILLING_RECOVERY`, `READ_ONLY`, `SUSPENDED`.

Distinct capabilities are **not** aliased to broader caps unless the governance matrix defines equivalence.

---

## Admin-only routes (unchanged guard)

| Route | Guard | Rationale |
|-------|-------|-----------|
| `GET /api/reports/audit-logs` | `admin_route_guard` | Admin extract; not customer lifecycle |
| `routes/documents.py` `/admin/*`, verify/reject | `admin_route_guard` | Operational admin surfaces |

---

## Enforcement patterns

| Pattern | Usage |
|---------|--------|
| `client_require_capability(CAP, action)` | Route dependency — returns `user` when allowed |
| `assert_client_capability(user, CAP, action)` | In-handler conditional gates (`format=csv\|pdf`, `return_advanced=true`) |
| Denied | HTTP 403 `capability_denied` governed payload |
| `READ` contract grant | Read allowed; write blocked (`READ_ONLY` semantic) |
| `PLAN_GATED` | Resolved via Runtime Contract plan overlay — no local `enforce_feature()` |

---

## Objectives proved

| Objective | Evidence |
|-----------|----------|
| Full module migration (3 modules) | No `enforce_feature` / `require_feature` in migrated client handlers |
| Runtime matrix extended | 5 new CAP rows + plan keys + portal ceilings |
| Lifecycle matrix regression | `test_account_capability_enforcement_wave1.py` |
| READ_ONLY semantics | Read endpoints pass; write endpoints return governed 403 |
| Plan gating via contract | Solo plan CSV + advanced analyze denied without `enforce_feature` |
| Phase 2A regression | `test_account_capability_enforcement_pilot.py` |

---

## 403 payload shape (unchanged)

```json
{
  "error": "capability_denied",
  "error_code": "read_only_blocked",
  "message": "...",
  "capability_id": "CAP_DOC_UPLOAD",
  "action": "write",
  "grant": "READ",
  "effective_semantic": "READ_ONLY",
  "lifecycle_state": "READ_ONLY",
  "portal_mode": "READ_ONLY",
  "recovery": { "route": "/settings/billing", "label": "..." },
  "contract_version": "...",
  "runtime_version": 1
}
```

---

## Test suites (regression)

| Suite | Path |
|-------|------|
| ILP-1 resolver | `test_account_lifecycle_state_resolver.py` |
| ILP-2 runtime contract | `test_account_lifecycle_runtime_contract.py` |
| ILP-4 Phase 0–1 | `test_account_capability_enforcement.py` |
| ILP-4 Phase 2A pilot | `test_account_capability_enforcement_pilot.py` |
| ILP-4 Phase 2B Wave 1 | `test_account_capability_enforcement_wave1.py` |

---

## Prior phases

- Phase 0–1: `ILP_04_PHASE_01_COMPLETE` — enforcement service, compatibility layer, diagnostics
- Phase 2A: `ILP_04_PHASE_2A_PILOT_COMPLETE` — 4 pilot endpoints

---

## Deferred to Wave 2+

- `client.py` evidence-pack routes (`CAP_REPORT_AUDIT_PACK`)
- Properties / requirements / portfolio (beyond 2A pilot endpoints in `client.py`)
- Frontend `useCapability()` consumption
- `client_route_guard` capability integration
- Remaining catalog-gap capability resolver rows
