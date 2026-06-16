# S2 customer status projector — implementation plan

**Programme:** S2-CUSTOMER-STATUS-PROJECTOR-IMPLEMENTATION-PLAN-01  
**Date:** 2026-06-02  
**Status:** PLANNING ONLY — no code, flags, or data changes

---

## Objective

Convert approved S2 architecture and projection-source disposition audit into a concrete implementation plan introducing `customer_status_projector_v2` as the single **backend** customer-status authority at enrich time.

---

## Approved inputs

| Input | Location |
|-------|----------|
| PR-1A vocabulary | `docs/governance/CUSTOMER_STATUS_VOCABULARY.json` |
| PR-1B hardening | `vocabulary_governance_ci_gate.py` |
| S2 planning | `s2_customer_status_projector_planning_01/` |
| Disposition audit | `s2_projection_source_disposition_audit_01/` |

---

## S2 constraints (confirmed)

| Constraint | Plan compliance |
|------------|-----------------|
| No frontend changes | Yes — FE in override inventory only |
| No reports/emails | Yes — PS-13..15 unchanged |
| No data mutations | Yes — flag flip only |
| Shadow mode support | Yes — FEATURE_FLAG_DESIGN.md |
| Five backend remediations | Yes — BACKEND_REMEDIATION_PLAN.md |

---

## Deliverables

| # | Deliverable | File |
|---|-------------|------|
| 1 | Implementation file list | `IMPLEMENTATION_FILE_LIST.json` |
| 2 | Module design | `MODULE_DESIGN.md` |
| 3 | Integration map | `INTEGRATION_MAP.md` |
| 4 | Flag design | `FEATURE_FLAG_DESIGN.md` |
| 5 | Shadow comparison design | `SHADOW_COMPARISON_DESIGN.md` |
| 6 | Backend remediation plan | `BACKEND_REMEDIATION_PLAN.md` |
| 7 | Fixture pack plan | `FIXTURE_PACK_PLAN.json` |
| 8 | Test plan | `TEST_PLAN.md` |
| 9 | Rollout plan | `ROLLOUT_PLAN.md` |
| 10 | API compatibility | `API_COMPATIBILITY.md` |
| 11 | Risk assessment | `RISK_ASSESSMENT.md` |
| 12 | GO / NO-GO | `GO_NO_GO_RECOMMENDATION.md` |

---

## Executive summary

### New module

`backend/services/customer_status_projector_v2.py` — maps enrich-time signals to `customer_status_*` using `customer_status_vocabulary.py` only.

### Integration

Insert after lifecycle + CER meta + satisfaction in `enrich_requirement_dict`; **move** `take_action` resolution to after projector.

### Flag

`CUSTOMER_STATUS_PROJECTOR_V2_MODE` = `disabled` | `shadow` | `active`  
Default: `disabled` everywhere; CI uses `shadow`.

### Five mandatory remediations

| ID | Fix |
|----|-----|
| REM-01 | Remove unconditional truth_label → client_lifecycle_label overwrite when active |
| REM-02 | Disable legacy label emission from derive_truth_presentation when active |
| REM-03 | Cognition reads customer_status_* |
| REM-04 | Queue-gated banners; no retired review copy |
| REM-05 | take_action after projector |

### 12-family fixtures

Legionella, Smoke/Heat/CO, HMO Fire, Gas Safety, EPC, EICR, PAT, Tenancy Agreement, How to Rent, Rent Smart Wales, Landlord Registration, Lead Testing — see `FIXTURE_PACK_PLAN.json`.

### Rollout

disabled → shadow (≥5d staging, ≥7d prod) → **active only after G1–G6**.

---

## GO / NO-GO

| Scope | Verdict |
|-------|---------|
| Implementation plan | **GO** |
| Code start | **GO WITH CONDITIONS** |
| Production active | **NO-GO** until shadow acceptance |

See `GO_NO_GO_RECOMMENDATION.md`.

---

## Related artefacts

- `s2_customer_status_projector_planning_01/CUSTOMER_STATUS_PROJECTOR_ARCHITECTURE.md`
- `s2_customer_status_projector_planning_01/PROJECTOR_STATUS_MAPPING_MATRIX.json`
- `s2_projection_source_disposition_audit_01/PROJECTION_SOURCE_DISPOSITION_MATRIX.json`
- `p1_review_policy_signoff_01/CONSISTENCY_AUDIT.md`
