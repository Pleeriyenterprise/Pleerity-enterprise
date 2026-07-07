# P0 — Platform Service Convergence Audit

**Programme:** P0-PLATFORM-SERVICE-CONVERGENCE-AUDIT-01  
**Date:** 2026-07-07  
**Branch:** `develop`  
**Status:** In progress — route authority convergence applied; service-layer overlays documented

---

## Premise

The authenticated **Runtime Contract** is authoritative and validated (`P0-RUNTIME-CONTRACT-STATE-MATRIX-VALIDATION-01`). Every remaining portal failure is treated as **service-level divergence** until proven otherwise.

---

## Authority chain (required for every service)

```
Browser → Auth (JWT) → client_route_guard → apply_session_runtime_validation
    → request.state.runtime_contract → CAP_* evaluation → Service → Repository → DB → Response → UI
```

---

## Remediation applied (FIX-01)

**Root cause class:** Route-local `_enforce_capability` helpers called `CapabilityEnforcementService.evaluate()` **without** the attached Runtime Contract, causing duplicate resolution — the same failure class fixed in `2427ecca` for middleware gating.

**Fix:** Added `enforce_route_capability()` in `middleware/capability_gating.py`. All route-local capability gates now evaluate from `request.state.runtime_contract` / `user.runtime_contract`.

**Affected routes:** Calendar, Assistant, Compliance Workflow (Jobs/Today), Compliance Execution, Maintenance (Issues/Jobs), Approvals, Rent Operations, Profile, inline checks in `client.py`.

---

## Service dependency matrix

| Service | Route | Capability | Service | Repository | UI |
|---------|-------|------------|---------|------------|-----|
| Today | `/api/today/items` | CAP_TODAY_VIEW / CAP_TODAY_ACT | today_projection_service | requirements, work_orders | `/today` |
| Dashboard | `/api/client/dashboard` | CAP_DASHBOARD_VIEW | compliance_scoring_service | properties, requirements | `/dashboard` |
| Command Center | `/api/client/command-center` | CAP_CMD_CTR_VIEW | command_center_service | maintenance_issues, risk_signals | `/command-center` |
| Properties | `/api/client/properties` | CAP_PROP_VIEW | properties routes | properties | `/properties` |
| Requirements | `/api/client/requirements` | CAP_REQ_VIEW | requirement_client_runtime_surface | requirements | `/requirements` |
| Documents | `/api/documents` | CAP_DOC_VIEW | documents upload pipeline | documents | `/documents` |
| Jobs | `/api/jobs/*`, `/api/client/maintenance/work-orders` | CAP_OPS_MAINTENANCE | compliance_workflow_service | work_orders | `/operations/work-orders` |
| Issues | `/api/client/maintenance/issues` | CAP_OPS_MAINTENANCE | maintenance_issues_service | maintenance_issues | `/operations/issues` |
| Calendar | `/api/calendar/events` | CAP_CALENDAR_VIEW | client_calendar_timeline_service | requirements, work_orders | `/calendar` |
| Notifications | `/api/profile/in-app-notifications` | CAP_PROFILE_VIEW/EDIT | order_service | in_app_notifications | header bell |
| Analytics | `/api/client/analytics/summary` | CAP_COMPLIANCE_ACTIVITY | product_analytics_service | product_analytics_events | Reports embed |
| Reports | `/api/reports/*` | CAP_REPORT_* | reporting_service | reports, audit_logs | `/reports` |
| Billing | `/api/billing/status` | CAP_BILLING_VIEW | stripe_service | client_billing | `/settings/billing` |
| Profile | `/api/profile/me` | CAP_PROFILE_VIEW | session runtime | portal_users | `/settings/profile` |
| Automation | `/api/webhooks/*` | CAP_INTEGRATION_WEBHOOKS | webhooks | webhooks | `/integrations` |
| Discovery | — | — | admin-only | — | — |

Full machine-readable matrix: `SERVICE_CONVERGENCE_MATRIX.json`

---

## 403 classification guide

| Symptom | First failing layer | How to prove |
|---------|---------------------|--------------|
| `runtime_unavailable` | Contract resolution | Headers have version but CAP eval failed → duplicate resolution (FIX-01) |
| `capability_denied` + lifecycle | Genuine authorization | Contract lifecycle + grant=DENY |
| `provisioning_required` | client_route_guard | onboarding_status != PROVISIONED |
| `archived` / `account_deleted` | Terminal lifecycle guard | contract.lifecycle_state terminal |
| Empty UI, 200 APIs | Frontend soft-deny | canView* false, fetch skipped (DIV-03) |
| Empty section, 200 API | Service overlay | get_effective_flags hides section despite CAP grant (DIV-01) |
| Property create 403 | Plan quota | plan_registry limit, not lifecycle |

---

## Remaining divergence (documented, not patched in this pass)

| ID | Layer | Description |
|----|-------|---------------|
| DIV-01 | Service response shaping | `get_effective_flags` in command_center_service for rent/predictive sections |
| DIV-02 | Plan quota | `plan_registry.enforce_property_limit` parallel to CAP_PROP_CREATE |
| DIV-03 | Frontend soft-deny | Today/Dashboard/Command Center empty chrome without explicit denial |

These are **not** account-specific fixes. Follow-up PRs should migrate overlays to Runtime Contract capability checks.

---

## Regression tests

```
backend/tests/test_p0_platform_service_convergence_audit_01.py
backend/tests/test_p0_runtime_contract_state_matrix_validation_01.py
backend/tests/test_p0_runtime_contract_state_convergence_01.py
```

---

## Phase 2 complete (2026-07-07)

- Removed `get_effective_flags` from all client portal routes (`client.py`, `client_maintenance.py`, `api_compliance_workflow.py`)
- Added `contract_feature_enabled` / `feature_enabled_for_client` — single Runtime Contract authority for feature visibility
- Command Center / Today rent sections gated on `CAP_OPS_RENT` from attached contract
- `/client/entitlements` ops features derived from contract capabilities
- Background jobs migrated to `feature_enabled_for_client`
- `InPageCapabilityGate` on Dashboard, Today, Command Center — no false-empty on permission deny

**95 targeted regression tests pass.** Staging browser matrix pending deploy to develop.

Evidence: `PHASE_2_CONVERGENCE_EVIDENCE.json`

### Remaining justified (not client portal)

| Location | Reason |
|----------|--------|
| `routes/ops_compliance.py` | Admin flag management |
| `routes/tenant.py`, `routes/maintenance.py` | Separate tenant/contractor portals |
| `plan_registry` property limits | Quota layer, not lifecycle permission |
