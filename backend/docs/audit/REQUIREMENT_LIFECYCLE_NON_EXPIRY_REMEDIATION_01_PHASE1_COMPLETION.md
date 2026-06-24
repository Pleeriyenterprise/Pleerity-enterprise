# Requirement Lifecycle Non-Expiry Remediation — Phase 1 Completion

**Authority:** REQUIREMENT-LIFECYCLE-NON-EXPIRY-REMEDIATION-01  
**Branch:** `feature/lifecycle-semantics-phase1` (from `develop`)  
**Completed:** 2026-06-02  
**Phase:** 1 only — resolver foundation + shadow observation  
**Status:** **COMPLETE** (pending staging browser validation)

---

## Executive summary

Phase 1 delivers the **Lifecycle Semantics Resolver** as an **observe-only** foundation. No reminder, scoring, extraction, dashboard, report, or status behaviour was changed. `LIFECYCLE_SEMANTICS_MODE=active` is **rejected at config** (treated as `disabled`).

| Gate | Result |
|------|--------|
| Resolver exists | **Yes** |
| Registry lifecycle blocks | **Yes** (coverage patches) |
| Shadow mode works | **Yes** |
| Existing behaviour unchanged | **Yes** (58 protected + lifecycle tests pass) |
| Prohibited systems modified | **No** |

---

## 1. Files created

| File | Purpose |
|------|---------|
| `backend/services/lifecycle_semantics_config.py` | Feature flag (`disabled` \| `shadow`; `active` prohibited) |
| `backend/services/lifecycle_semantics_types.py` | Enums, `FieldContract`, `ResolvedLifecycle`, date types |
| `backend/services/lifecycle_semantics_fallback_map.py` | Documentation-backed slug/canonical → semantics map |
| `backend/services/lifecycle_semantics_registry_loader.py` | Load/publish `lifecycle` registry blocks |
| `backend/services/lifecycle_semantics_resolver.py` | Core classifier (observe-only) |
| `backend/services/lifecycle_semantics_shadow.py` | Shadow logging path |
| `backend/services/lifecycle_semantics_validation.py` | Non-blocking validation + coverage reports |
| `backend/tests/test_lifecycle_semantics_resolver.py` | Unit, shadow, backward-compat tests |
| `backend/tests/fixtures/lifecycle_semantics_golden.json` | Golden classification fixtures |
| `backend/scripts/lifecycle_semantics_classification_report.py` | Classification coverage CLI |
| `backend/docs/audit/REQUIREMENT_LIFECYCLE_PHASE1_CLASSIFICATION_COVERAGE.json` | Generated coverage artefact |

---

## 2. Files modified

| File | Change |
|------|--------|
| `backend/services/published_registry_coverage_patch_specs.py` | Lifecycle blocks on key canonical patches |
| `backend/services/compliance_registry_admin_service.py` | Optional `lifecycle` validation in `validate_registry_draft` |
| `backend/services/governance_coverage_registry.py` | `lifecycle_resolver` surface entry (`shadow_only`) |
| `backend/services/requirement_client_runtime_surface.py` | Shadow observe hook (log only; output unchanged) |

**Forbidden files:** None modified (`jobs.py`, `expiry_utils.py`, scoring, extraction, frontend, etc.).

---

## 3. Resolver architecture summary

```
Requirement row + optional registry_row
    → lifecycle_semantics_registry_loader (registry lifecycle block)
    → fallback: canonical code → storage slug → expiry_type → expects_expiry → default
    → ResolvedLifecycle {
         lifecycle_semantics, field_contract, attention_kind (informational),
         canonical_dates, legacy_signals, validation_issues
       }
    → shadow path (if LIFECYCLE_SEMANTICS_MODE=shadow): structured log only
```

**Orthogonal to `workflow_class`.** Phase 1 consumers: **none** (no branching on resolver output in production paths).

**Env:** `LIFECYCLE_SEMANTICS_MODE=disabled` (default) \| `shadow`

---

## 4. Registry backfill summary

Lifecycle blocks added to coverage patches for:

| Canonical | `lifecycle.semantics` |
|-----------|----------------------|
| GAS_SAFETY, EICR, EPC, HMO_LICENSING | EXPIRY_BASED |
| LEGIONELLA | REVIEW_BASED |
| SMOKE_HEAT_ALARMS | EVENT_BASED |
| RIGHT_TO_RENT | OCCUPANCY_LIFECYCLE |
| HOW_TO_RENT, TENANCY_DEPOSIT_PROTECTION | DECLARATION_BASED |
| TENANCY_AGREEMENT | TENANCY_LIFECYCLE |
| HMO_FIRE_RISK, PAT_TESTING | EXPIRY_BASED |

Existing registry drafts **without** `lifecycle` remain valid; fallback map applies at resolve time.

---

## 5. Classification coverage report

**Staging scenario codes (10/10 resolved, 0% unresolved):**

| Scenario | Code | Semantics |
|----------|------|-----------|
| S1 Gas Safety | gas_safety | EXPIRY_BASED |
| S2 EICR | eicr | EXPIRY_BASED |
| S3 EPC | epc | EXPIRY_BASED |
| S4 HMO | hmo_license | EXPIRY_BASED |
| S5 Legionella | legionella | REVIEW_BASED |
| S6 Deposit PI | deposit_pi | DECLARATION_BASED |
| S7 Right to Rent | right_to_rent | OCCUPANCY_LIFECYCLE |
| S8 Tenancy Agreement | tenancy_agreement | TENANCY_LIFECYCLE |
| S9 Smoke Alarms | smoke_heat_alarms | EVENT_BASED |
| S10 Operational | fitness_for_human_habitation | OPERATIONAL |

**By semantics:** EXPIRY_BASED 4 · REVIEW_BASED 1 · DECLARATION_BASED 1 · OCCUPANCY_LIFECYCLE 1 · TENANCY_LIFECYCLE 1 · EVENT_BASED 1 · OPERATIONAL 1

**Fallback map:** 21 canonical codes · 29 storage slugs · 0 missing resolutions

**Known shadow signal:** `hmo_license` stub rows may log `conflict_expects_expiry_false_expiry_semantics` when engine `get_rule` misses without jurisdiction context — expected for Phase 1 divergence logging, not a behaviour change.

Full JSON: `backend/docs/audit/REQUIREMENT_LIFECYCLE_PHASE1_CLASSIFICATION_COVERAGE.json`

---

## 6. Shadow validation report

| Check | Result |
|-------|--------|
| `active` mode blocked | Config returns `disabled` |
| Shadow does not mutate projected rows | No `_lifecycle_semantics_shadow` on API output |
| Shadow does not alter `due_date` / `status` | Verified in tests |
| Divergence logging | `lifecycle_semantics_shadow_divergence` log event |
| Disable via env | `LIFECYCLE_SEMANTICS_MODE=disabled` → no-op |

**Hook location:** `project_requirement_row_client_runtime` → `observe_lifecycle_semantics_shadow_if_enabled` (logging only).

---

## 7. Test results

```
pytest tests/test_lifecycle_semantics_resolver.py \
       tests/test_certificate_expiry_tracking.py \
       tests/test_requirement_client_runtime_surface.py \
       tests/test_compliance_registry_publish.py

58 passed (lifecycle + protected compatibility + registry publish)
```

Lifecycle suite alone: **23 passed**

---

## 8. Staging validation results

**Status:** **Deferred** — no staging deployment executed in this implementation session.

**Proxy validation (CI/local):**

- Golden fixtures S1–S10 classify correctly
- Certificate expiry tracking tests unchanged
- Client runtime surface projection unchanged (disabled mode)
- Registry publish validation accepts optional `lifecycle` blocks

**Staging checklist (ops — before production shadow enable):**

1. Deploy with `LIFECYCLE_SEMANTICS_MODE=shadow`
2. Run `python scripts/lifecycle_semantics_classification_report.py`
3. Spot-check S1–S4 cert rows: semantics EXPIRY_BASED, scores/reminders unchanged vs baseline
4. Spot-check S6–S8 declaration/tenancy: not EXPIRY_BASED, no new expiry reminders
5. 48h soak: reminder volume ±2%, dashboard KPI parity

---

## 9. Risk findings

| ID | Finding | Severity | Mitigation |
|----|---------|----------|------------|
| R1 | HMO stub divergence vs `expects_expiry` without jurisdiction | Low | Shadow-only; resolve in registry publish backfill |
| R2 | Shadow hook on hot projection path | Low | No-op when `disabled`; early return in observe |
| R3 | Future accidental `active` enable | Medium | Config explicitly rejects `active` in Phase 1 |
| R4 | Staging not exercised live | Medium | Ops checklist above before prod shadow |

---

## 10. Phase 2 readiness recommendation

**Proceed to separate authority:** lifecycle-aware confirmation screens + extraction profiles.

**Prerequisites met:**

- [x] Resolver classifies all staging scenario codes  
- [x] Registry lifecycle blocks on primary patches  
- [x] Fallback map test-covered  
- [x] Shadow infrastructure proven  
- [x] No prohibited file changes  

**Phase 2 should:**

1. Add `confirm_fields` API from `field_contract`  
2. Branch `DocumentsPage` / extraction EXTRACTED rules by profile  
3. Gate `requirement_evidence_authority` expiry guard via resolver  
4. Keep `LIFECYCLE_SEMANTICS_MODE` shadow until Phase 2 staging sign-off  

**Do not enable `active` on reminders/scoring until Phase 4+ per ADR migration plan.**

---

## Completion gate

| Criterion | Met |
|-----------|-----|
| Resolver exists | Yes |
| Registry classifications exist | Yes |
| Shadow mode works | Yes |
| Existing behaviour unchanged | Yes |
| No prohibited systems modified | Yes |

**Phase 1 complete under REQUIREMENT-LIFECYCLE-NON-EXPIRY-REMEDIATION-01.**

---

*End of Phase 1 completion report.*
