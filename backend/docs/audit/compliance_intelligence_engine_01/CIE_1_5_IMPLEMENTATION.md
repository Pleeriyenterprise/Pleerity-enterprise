# CIE-1.5 Provenance Foundation Implementation

**Programme:** CIE-1.5-PROVENANCE-FOUNDATION-AUTHORISATION  
**Branch:** `develop`  
**Verdict:** `CIE_1_5_FOUNDATION_VALIDATED`  
**Runtime evidence:** `CIE_1_5_RUNTIME_VALIDATION.json`  
**Gate script:** `backend/tmp_cie_phase1_5_provenance_gate.py`  
**Architecture:** Refinement-02 (`ARCHITECTURE_REFINEMENT_02.md`)

## Summary

CIE-1.5 implements the immutable Intelligence Provenance foundation required before CIE-2 domain engines emit real artefacts. This includes provenance schema, calculation trace skeleton, versioned registry seeds (strategy, weight, constraint), storage stubs, replay/compare interface stubs, artefact `provenance_id` enforcement, and ISL envelope provenance references.

No domain engines, recommendations, priorities, AI, routes, or production changes were introduced.

## Feature flag

| Variable | Default | CIE-1.5 behaviour |
|----------|---------|-------------------|
| `COMPLIANCE_INTELLIGENCE_ENGINE_MODE` | `disabled` | Unchanged; no domain activation |

## Packages and files

### Engine (`services/compliance_intelligence_engine/`)

| File | Purpose |
|------|---------|
| `constants.py` | Collection names, `cie-1.5.0` version pins, `cip_` prefix |
| `provenance_schema.py` | `IntelligenceProvenanceBase`, `CalculationTraceStage`, `VersionRef` |
| `registry_schema.py` | Strategy, weight, constraint registry Pydantic models |
| `provenance_trace.py` | Stub calculation trace builder |
| `provenance_validation.py` | Provenance, registry seed, artefact–provenance link validators |
| `hashing.py` | `trace_hash`, `provenance_record_hash` |
| `replay.py` | Replay dispatch stub (requires `as_of` / `provenance_id`) |
| `comparison.py` | Comparison dispatch stub |
| `schema.py` | `IntelligenceArtefactBase.provenance_id` required (`cip_` prefix) |
| `validation.py` | Artefact validation requires `provenance_id` |
| `registry/versions.py` | v1 registry version IDs |
| `registry/seeds_v1.py` | Immutable v1 seed documents with `content_hash` |
| `registry/strategies.py` | Strategy registry storage stub |
| `registry/weights.py` | Weight registry storage stub |
| `registry/constraints.py` | Constraint registry storage stub |
| `storage/provenance.py` | Provenance storage stub (insert/read deferred; update forbidden) |

### Intelligence Service Layer (`services/compliance_intelligence_service/`)

| File | Change |
|------|--------|
| `envelopes.py` | `provenance_id` on envelopes; replay/compare stub helpers |
| `service.py` | `get_intelligence_provenance`, `replay_intelligence`; `compare_intelligence` via provenance stub |
| `__init__.py` | Export new methods |

### Infrastructure

| File | Change |
|------|--------|
| `database.py` | Index stubs for provenance + three registry collections |
| `tests/test_compliance_intelligence_engine_cie1.py` | `provenance_id` on samples; rejection test |
| `tests/test_compliance_intelligence_engine_cie1_5.py` | Provenance, registry, immutability, replay/compare tests |
| `tests/test_graph_service_access_boundary.py` | ISL must not import CIE registry |

## Registry v1 seeds

| Registry | ID | Seeds |
|----------|-----|-------|
| Strategy | `rec_strategy_v1.0.0`, `priority_strategy_v1.0.0`, `dependency_strategy_v1.0.0`, `impact_strategy_v1.0.0` | 4 entries |
| Weight | `weights_v1.0.0` | 10 weight keys summing to 1.0 |
| Constraint | `constraints_v1.0.0` | 2 blocking constraints |

Seeds validate via Pydantic; storage publish deferred to CIE-2.

## Provenance invariants (enforced)

1. Every artefact schema requires `provenance_id` with `cip_` prefix
2. Provenance records require `calculation_trace`, `trace_hash`, `constraint_set_version`
3. Artefact–provenance link validator checks `inputs_hash` / `response_hash` alignment
4. Storage `update_*` on provenance and registries raises `NotImplementedError` (immutability)
5. Replay stub requires `provenance_id` (exact) or `as_of` (point-in-time); prohibits current-state substitution
6. Compare stub requires artefact IDs and provenance references (not implemented execution)

## Test results

| Suite | Result |
|-------|--------|
| `test_compliance_intelligence_engine_cie1.py` | 29 passed (regression) |
| `test_compliance_intelligence_engine_cie1_5.py` | 27 passed |
| `test_graph_service_access_boundary.py` | 12 passed |
| **Total** | **67 passed** |

```bash
cd backend
python -m pytest tests/test_compliance_intelligence_engine_cie1.py tests/test_compliance_intelligence_engine_cie1_5.py tests/test_graph_service_access_boundary.py -q
python tmp_cie_phase1_5_provenance_gate.py
```

## Runtime validation

All gate checks passed — see `CIE_1_5_RUNTIME_VALIDATION.json`:

- Feature flag defaults to `disabled`
- Provenance schema validates
- Artefact requires `provenance_id`
- Registry v1 seeds validate
- Replay/compare stubs safe
- Provenance immutability stub enforced
- No domain `engines/` package
- No customer-facing CIE routes
- No production CIE flag in `render.yaml`

## Remaining risks

1. **No persistence** — provenance/registry writes still stubbed until CIE-2
2. **Trace skeleton only** — full pipeline stages populated when domain engines land
3. **Replay/compare execution** — stubs only; CIE-6 validation targets full implementation
4. **CIE-1 + CIE-1.5 uncommitted** — commit requires separate authorisation

## CIE-2 readiness

CIE-1.5 foundation is **complete** for the approved scope. CIE-2 may be authorised to:

- Implement recommendation + priority engines
- Write provenance on every artefact emission
- Publish registry v1 seeds to Mongo
- Wire full calculation trace stages

**Do not proceed to CIE-2 without explicit approval.**
