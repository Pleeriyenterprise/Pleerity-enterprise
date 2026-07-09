# Root Cause Analysis

**Programme:** P0-PROFESSIONAL-PLAN-CAPABILITY-MAPPING-01  
**Generated:** 2026-07-07T20:43:15Z

## Symptom

ACTIVE Professional customers received `CAP_OPS_MAINTENANCE` grant `DENY` despite `lifecycle_state=ACTIVE` and `portal_mode=FULL_ACCESS`. Operational navigation and APIs returned governed `capability_denied`.

## First incorrect authority point

`account_lifecycle_runtime_contract._load_plan_context()` loaded `plan_features` exclusively from `plan_registry.FEATURE_MATRIX`, which defined commercial/reporting features but **omitted operational module keys** (`maintenance_workflows`, `contractor_network`, `predictive_maintenance`, `compliance_engine`, `rent_operations`, `ai_assistant`).

Ops capabilities in `_BASE_CAPABILITY_MATRIX` are marked `PLAN_GATED` (`P`) and resolve via `_CAP_PLAN_KEYS`. Missing plan feature keys evaluate falsy → **`DENY`** for every tier including `PLAN_3_PRO`.

A parallel duplicate source existed in `ops_compliance_feature_flags.DEFAULTS_BY_PLAN` with correct values, but Runtime Contract never consumed it after portal convergence.

## Fix

1. Extended `plan_registry.FEATURE_MATRIX` with operational features for Solo / Portfolio / Professional (canonical SSOT).
2. Derived `ops_compliance_feature_flags.DEFAULTS_BY_PLAN` from `plan_registry` (eliminates drift).
3. Added missing capability rows `CAP_OPS_ISSUES_VIEW` and `CAP_RISK_VIEW` to runtime contract matrix.
4. Normalized display aliases (`PROFESSIONAL`, `PORTFOLIO`, `SOLO`, etc.) in `resolve_plan_code`.

## Not the cause

- Lifecycle resolver (ACTIVE correct)
- Portal mode overlay (FULL_ACCESS correct)
- Route-local duplicate contract resolution (addressed in prior convergence work)
- Account-specific overrides (none applied)
