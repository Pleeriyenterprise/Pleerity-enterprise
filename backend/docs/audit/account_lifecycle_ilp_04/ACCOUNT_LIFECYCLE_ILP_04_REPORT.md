# ILP-4 Capability Enforcement — Phase 2A Pilot Report

**Programme:** ILP-4-CAPABILITY-ENFORCEMENT-01 (Phase 2A pilot)  
**Branch:** `develop`  
**Verdict:** `ILP_04_PHASE_2A_PILOT_COMPLETE`  
**Date:** 2026-07-03

---

## Summary

Phase 2A migrates four low-risk client API endpoints to `client_require_capability()` — proving end-to-end backend capability enforcement without replacing `client_route_guard`, migrating the frontend, or touching billing/Stripe/jobs.

---

## Pilot endpoints

| Type | Endpoint | Capability | Action |
|------|----------|------------|--------|
| Read | `GET /api/client/properties` | `CAP_PROP_VIEW` | read |
| Write | `POST /api/client/properties/{id}/requirements/mark-not-applicable` | `CAP_REQ_RESOLVE` | write |
| Report/download | `GET /api/reports/{report_id}/download` | `CAP_REPORT_DOWNLOAD` | read |
| Documents | `GET /api/documents` | `CAP_DOC_VIEW` | read |

Handlers contain **CAP_* only** — no hybrid `enforce_feature()` inside migrated handlers. Report download removed legacy `enforce_feature("reports_pdf")` gate.

---

## Objectives proved

| Objective | Evidence |
|-----------|----------|
| Backend capability enforcement end-to-end | Pilot routes + `client_require_capability()` |
| READ allows view, blocks write | `test_read_only_allows_properties_list`, `test_read_only_blocks_mark_not_applicable` |
| DENY/HIDDEN safe structured 403 | `capability_denied_http_detail()` + pilot HTTP tests |
| ACTIVE customer flows pass | `test_active_properties_read_allowed` |
| Legacy `enforce_feature()` compatibility | Non-pilot routes unchanged; `TestLegacyEnforceFeatureCompatibility` |

---

## 403 payload shape

```json
{
  "error": "capability_denied",
  "error_code": "read_only_blocked",
  "message": "...",
  "capability_id": "CAP_PROP_VIEW",
  "action": "write",
  "grant": "READ",
  "effective_semantic": "READ_ONLY",
  "lifecycle_state": "...",
  "portal_mode": "...",
  "recovery": { "route": "/settings/billing", "label": "..." },
  "contract_version": "...",
  "runtime_version": 1
}
```

---

## Unchanged (regression proof)

| Area | Changed? |
|------|----------|
| `middleware/__init__.py` `client_route_guard` | **No** |
| Non-pilot route `enforce_feature` call sites | **No** |
| Frontend | **No** |
| Runtime Contract schema | **No** |
| Billing / Stripe / jobs / sessions / comms | **No** |

---

## Deferred to Phase 2B+

- Wider route migration beyond 4 pilot endpoints
- Frontend `useCapability()` consumption
- `client_route_guard` capability integration
- Resolver matrix extension for 71 catalog-gap capabilities

---

## Prior phases

- Phase 0–1: `ILP_04_PHASE_01_COMPLETE` — enforcement service, compatibility layer, diagnostics (not wired to routes)
