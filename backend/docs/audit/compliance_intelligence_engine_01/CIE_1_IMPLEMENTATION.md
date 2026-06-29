# CIE-1 Foundation Implementation

**Programme:** CIE-1-FOUNDATION-AUTHORISATION  
**Branch:** `develop`  
**Verdict:** `CIE_1_FOUNDATION_VALIDATED`  
**Runtime evidence:** `CIE_1_RUNTIME_VALIDATION.json`  
**Gate script:** `backend/tmp_cie_phase1_foundation_gate.py`

## Summary

CIE-1 delivers the deterministic artefact infrastructure and Intelligence Service Layer (ISL) skeleton for the Compliance Intelligence Engine. No domain engines, AI, customer routes, or production flag changes were introduced.

## Feature flag

| Variable | Values | Default |
|----------|--------|---------|
| `COMPLIANCE_INTELLIGENCE_ENGINE_MODE` | `disabled` \| `shadow` \| `enabled` | `disabled` |

Behaviour in CIE-1:

- **disabled** — ISL returns safe unavailable envelopes (`COMPLIANCE_INTELLIGENCE_ENGINE_MODE_DISABLED`).
- **shadow** — same stub path as enabled for generation; reserved for internal/admin validation in later phases.
- **enabled** — ISL returns `CIE_DOMAIN_ENGINE_NOT_IMPLEMENTED` stubs; no domain calculation runs.

## Packages

### `services/compliance_intelligence_engine/` (internal)

| File | Purpose |
|------|---------|
| `__init__.py` | Public exports: config helpers, collection names, version pins |
| `config.py` | `COMPLIANCE_INTELLIGENCE_ENGINE_MODE` helpers |
| `constants.py` | Collection names, engine/deterministic version pins |
| `hashing.py` | Canonical JSON, `sha256:` digests, inputs/artefact/envelope hashing |
| `artefact_types.py` | 15 registered artefact types |
| `lifecycle.py` | Base + recommendation lifecycle states, transition validation |
| `schema.py` | Pydantic: `IntelligenceScope`, `IntelligenceArtefactBase`, `IntelligenceTransitionBase` |
| `validation.py` | Dict-level artefact and transition validators |
| `orchestrator.py` | `dispatch_generate` stub; unavailable / not-implemented envelopes |
| `read_adapter.py` | Graph read adapter stub (no live reads in CIE-1) |
| `storage/artefacts.py` | `compliance_intelligence_artefacts` stub (`NotImplementedError`) |
| `storage/transitions.py` | `compliance_intelligence_transitions` stub (`NotImplementedError`) |

### `services/compliance_intelligence_service/` (consumer API)

| File | Purpose |
|------|---------|
| `__init__.py` | ISL public method exports |
| `access.py` | Tenant scope guards (`resolve_client_id`, `enforce_tenant_access`) |
| `envelopes.py` | Response envelope builder with `response_hash` |
| `service.py` | ISL stub methods (generate/list/get/compare/explain/transition) |

### Other changes

| File | Change |
|------|--------|
| `database.py` | Index stubs for `compliance_intelligence_artefacts` and `compliance_intelligence_transitions` |
| `tests/test_compliance_intelligence_engine_cie1.py` | CIE-1 unit/integration tests |
| `tests/test_graph_service_access_boundary.py` | Extended CEG + CIE storage and AI import boundaries |

## Authority boundaries (enforced)

CIE-1 does **not**:

- Determine compliance or calculate scores
- Alter rules, evidence, recommendations, graph decisions, reports, reminders, or work orders
- Query raw CEG storage
- Call AI/LLM services
- Expose HTTP routes (`routes/compliance_intelligence_engine.py` absent)
- Change `render.yaml` or production flags

All consumer access must go through ISL; AST-based tests forbid ISL, routes, and Phase 5 AI package from importing `compliance_intelligence_engine.storage`.

## Test results

| Suite | Result |
|-------|--------|
| `tests/test_compliance_intelligence_engine_cie1.py` | **28 passed** |
| `tests/test_graph_service_access_boundary.py` | **11 passed** (incl. CIE boundaries) |
| `tests/test_compliance_graph_service.py` + `phase3` | **12 passed** (CEG regression) |
| **Total CIE gate** | **39 + 12 = 51** relevant tests, all green |

Run locally:

```bash
cd backend
python -m pytest tests/test_compliance_intelligence_engine_cie1.py tests/test_graph_service_access_boundary.py -q
python tmp_cie_phase1_foundation_gate.py
```

## Runtime validation

All gate checks passed (`CIE_1_RUNTIME_VALIDATION.json`):

- Feature flag defaults to `disabled`
- Hashing is deterministic (`sha256:` prefixed)
- Artefact schema validates sample CIA
- ISL returns safe unavailable envelopes when disabled
- Storage stubs raise `NotImplementedError` (bootstrap safe)
- No domain `engines/` package
- No customer-facing CIE routes
- No `COMPLIANCE_INTELLIGENCE_ENGINE_MODE` in `render.yaml`

## Remaining risks

1. **Storage not implemented** — artefact/transition persistence deferred to CIE-2; indexes exist but writes are stubbed.
2. **Graph read adapter stub** — `read_adapter.fetch_graph_envelope` returns `None`; CIE-2 must wire governed Graph Service reads.
3. **Envelope shape drift** — orchestrator envelopes omit `response_hash`; ISL `envelopes.py` adds it for read/compare paths. Generation stubs use orchestrator shape; align in CIE-2 if a single envelope contract is required.
4. **Shadow mode semantics** — shadow enables `intelligence_engine_enabled()` but has no distinct validation paths yet beyond shared stubs.
5. **Uncommitted work** — implementation is local on `develop`; commit and staging validation are separate steps.

## CIE-2 readiness recommendation

Proceed to CIE-2 only after explicit approval. Prerequisites for CIE-2 planning:

1. Implement artefact storage read/write behind engine package only.
2. Wire `read_adapter` to Graph Service (never CEG storage).
3. Implement first domain engine (likely recommendation) with lifecycle transitions.
4. Add admin/internal HTTP wrapper over ISL (not customer-facing).
5. Staging gate with `COMPLIANCE_INTELLIGENCE_ENGINE_MODE=shadow` before `enabled`.
6. Resolve envelope contract (orchestrator vs ISL `build_envelope`) before persistence.

CIE-1 foundation is **complete and validated** for the approved scope.
