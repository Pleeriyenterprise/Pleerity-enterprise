# CIE-2 Recommendation + Priority Engine Implementation

**Programme:** CIE-2-RECOMMENDATION-AND-PRIORITY-ENGINE-AUTHORISATION  
**Branch:** `develop` (local)  
**Verdict:** `CIE_2_FOUNDATION_VALIDATED`  
**Runtime evidence:** `CIE_2_RUNTIME_VALIDATION.json`  
**Gate script:** `backend/tmp_cie_phase2_foundation_gate.py`

## Summary

CIE-2 implements deterministic Recommendation and Priority engines with full provenance persistence. Graph reads flow through `read_adapter` only. Artefacts and provenance are written append-only to `compliance_intelligence_artefacts` and `compliance_intelligence_provenance`. ISL exposes generation, list, get, explain, and provenance read paths without importing CIE storage.

Out of scope: decision impact, dependency, portfolio, regulatory, commercial, forecasting, AI, customer routes, production deployment.

## Feature flag

| Variable | Default | CIE-2 behaviour |
|----------|---------|-----------------|
| `COMPLIANCE_INTELLIGENCE_ENGINE_MODE` | `disabled` | `enabled` or `shadow` on staging for validation |

## Version pins

| Constant | Value |
|----------|-------|
| `ENGINE_VERSION` | `cie-2.0.0` |
| `DETERMINISTIC_VERSION` | `cie-deterministic-2.0.0` |
| `CALCULATION_VERSION` | `cie-calculation-2.0.0` |
| `TEMPLATE_VERSION_DEFAULT` | `recommendation_templates_v1` |

## Packages and files

### Engine (`services/compliance_intelligence_engine/`)

| File | Purpose |
|------|---------|
| `engines/recommendation/engine.py` | `generate_recommendations` — gap normalisation, dedupe, priority scoring, persistence |
| `engines/recommendation/templates.py` | Template catalogue v1, gap → template matching |
| `engines/priority/engine.py` | `generate_priority_assessment` — ranks stored recommendations |
| `engines/priority/scoring.py` | Registry-backed priority formula |
| `registry/loader.py` | In-memory v1 registry resolution and strategy pins |
| `read_adapter.py` | Governed Graph Service reads (`find_missing_evidence`, etc.) |
| `provenance_writer.py` | Provenance + calculation trace builder |
| `persist.py` | Atomic artefact + provenance write |
| `ids.py` | `cia_`, `cip_`, `ciat_` ID generation |
| `storage/artefacts.py` | Artefact insert/find/list (implemented) |
| `storage/provenance.py` | Provenance insert/find (implemented; update forbidden) |
| `orchestrator.py` | Routes generation + list/get/explain/provenance reads |

### Intelligence Service Layer

| Method | CIE-2 behaviour |
|--------|-----------------|
| `generate_recommendations` | Orchestrator → recommendation engine |
| `generate_priority_assessment` | Orchestrator → priority engine |
| `list_intelligence` | Orchestrator → artefact list |
| `get_intelligence` | Orchestrator → artefact by id |
| `explain_intelligence` | Deterministic explainability + provenance refs |
| `get_intelligence_provenance` | Provenance record by artefact id |
| `compare_intelligence` / `replay_intelligence` | CIE-1.5 stubs (unchanged) |

## Priority scoring formula (v1)

```
priority_score = Σ (registry_weight[factor] × raw_score[factor]) / Σ registry_weight[factor]
```

- Registry source: `weights_v1.0.0` via `registry/loader.py`
- Factor → weight key mapping in `engines/priority/scoring.py` (`FACTOR_WEIGHT_KEYS`)
- Bands: critical ≥ 80, high ≥ 60, medium ≥ 40, else low
- Every score is pinned in provenance via `weight_set_version` and calculation trace stage `priority_calculation`

## Invariants

1. Every emitted artefact has exactly one `provenance_id` (`cip_` prefix)
2. Provenance written before artefact insert (`persist.py`)
3. Idempotent recommendation generation via `dedupe_key` + active lifecycle filter
4. No direct CEG storage access — Graph Service via `read_adapter` only
5. ISL does not import CIE storage or registry (boundary tests enforced)
6. Replay/compare remain stubs until CIE-6

## Tests

| File | Coverage |
|------|----------|
| `tests/test_compliance_intelligence_engine_cie2.py` | Templates, scoring, generation, dedupe, provenance linkage, priority, ISL reads |
| `tests/test_compliance_intelligence_engine_cie1.py` | Updated for live storage + enabled recommendation path |
| `tests/test_compliance_intelligence_engine_cie1_5.py` | Updated provenance insert + get provenance not-found |

## CIE-3 readiness

Do not proceed to CIE-3 (Decision Impact + Dependency) without separate authorisation.
