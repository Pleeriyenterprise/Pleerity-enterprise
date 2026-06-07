# PLAN-BASED-BUSINESS-OUTCOME-RUNTIME-AUDIT-01

**Classification:** `PARTIAL`  
**Run tag:** `20260607T155626Z`  
**Marker:** `PLAN-OUTCOME-AUDIT-20260607T155626Z`  
**Generated:** 2026-06-07

## Executive summary

Plan feature governance inventory and local regression **pass**. Staging discovery dynamically sampled **11 Solo**, **7 Portfolio**, and **30 Professional** active clients without hardcoding a single account.

**Not `VERIFIED_OPERATIONALLY`:** no all-satisfied staging persona was found per plan in the sampled set; Professional tier end-to-end was not completed; browser proof and entitlement cross-check were blocked by impersonation session expiry and subsequent API **429 rate limit**.

## Plan feature governance (Part 1)

| Plan | Property limit | PDF reports | CSV reports | Tenant portal | Rent ops default | Contractor network |
|------|----------------|-------------|-------------|---------------|------------------|-------------------|
| Solo | 2 | No | No | No | No | No |
| Portfolio | 10 | Yes | No | No | Yes | No |
| Professional | 25 | Yes | Yes | Yes | Yes | Yes |

Artifact: `plan_feature_governance_runtime.json`

## Test matrix (Part 2)

| Scenario | Plan | Found | Client |
|----------|------|-------|--------|
| A | Solo all satisfied 1 prop | No | — |
| B | Solo all satisfied 2 prop mixed | No | — |
| C | Solo partial | **Yes** | David Harrison `616258a5…` |
| D | Solo property limit | Local | PLAN_DEFINITIONS max=2 |
| E–F | Portfolio all satisfied | No | — |
| G–H | Portfolio partial mixed | **Yes** | David Miller `6bcc43c0…` |
| I–L | Professional | No | 30 clients inventoried; profiling incomplete |

## Business outcomes

### All satisfied (Part 7) — **FAIL**

No sampled Solo/Portfolio/Professional client had `all_satisfied=true` with calm Today. Reference account PLE-CVP-2026-000023 (Sophie Walker) is all-satisfied per prior convergence programme but was not in Portfolio sample criteria for this run.

### Partial satisfied (Part 8) — **PASS**

- **Solo C:** 8/8 unsatisfied, score 19, 2 AMBER properties, Today in_progress=2 (real action, not false calm)
- **Portfolio G:** 19/48 unsatisfied, score 76, 9 urgent Today items, 4 UK jurisdictions (Scotland, England, Wales, NI)

## Jurisdiction (Part 6) — **PASS**

Mixed-jurisdiction portfolio (David Miller) shows all four UK labels without cross-contamination in requirement rollups.

## Regression (Part 13) — **PASS**

52 targeted tests passed.

## Blockers

1. **BUSINESS_OUTCOME_DRIFT** — no per-plan all-satisfied staging persona in discovery sample
2. **USER_OUTCOME_DRIFT** — Professional tier scenarios I–L not proven
3. **PLAN_ENTITLEMENT_DRIFT** — entitlements API vs FEATURE_MATRIX not cross-checked (session expired)
4. **CROSS_SURFACE_DRIFT** — dashboard/score convergence not re-probed
5. **FAIL_OPERATIONAL** — browser screenshots not captured; API 429 on re-run

## Harness

`backend/scripts/plan_based_business_outcome_runtime_audit_01_execute.py`
