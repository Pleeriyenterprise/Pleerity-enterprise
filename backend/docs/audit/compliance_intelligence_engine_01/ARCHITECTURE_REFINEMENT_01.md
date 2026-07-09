# Architecture Refinement 01 — Intelligence Artefact Generalisation

**Programme:** COMPLIANCE-INTELLIGENCE-ENGINE-01  
**Refinement:** COMPLIANCE-INTELLIGENCE-ENGINE-ARCHITECTURE-REFINEMENT-01  
**Status:** Approved for planning — supersedes CIE-0 entity hierarchy for implementation  
**Date:** 2026-06-02  
**Prerequisite:** CIE-0 committed (`f8da4fe5`)

---

## Executive summary

CIE-0 modelled **recommendations** as the primary intelligence output. Refinement-01 generalises the platform so that **every deterministic analytical output** is a **Compliance Intelligence Artefact (CIA)** — an immutable parent entity with typed payloads.

Recommendations become **one artefact subtype**. Priority assessments, impact projections, portfolio insights, regulatory reports, forecasts, readiness assessments, and future commercial intelligence all share the same storage, lifecycle, graph indexing, explainability, and service access patterns.

This positions Pleerity as a **Compliance Operations Intelligence Platform** — not a recommendation engine with bolt-ons.

---

## What changed (CIE-0 → Refinement-01)

| # | Requirement | Architectural response |
|---|-------------|------------------------|
| 1 | Compliance Intelligence Artefact parent entity | `INTELLIGENCE_ARTEFACT_MODEL.md` — `compliance_intelligence_artefacts` collection |
| 2 | Multiple artefact types | Registered `artefact_type` enum; extensible without schema redesign |
| 3 | Recommendation as subtype | `RECOMMENDATION_MODEL.md` — payload extends base artefact |
| 4 | Intelligence relationships in CEG | `GRAPH_INTEGRATION_MODEL.md` — decision → artefact → subtype chain |
| 5 | Generalised intelligence lifecycle | `INTELLIGENCE_LIFECYCLE_MODEL.md` — supersedes recommendation-only lifecycle as base |
| 6 | Multiple consumers | `INTELLIGENCE_CONSUMERS.md` — catalogue + access rules |
| 7 | Intelligence Service Layer | `INTELLIGENCE_SERVICE_LAYER.md` — sole public interface (parallel to Graph Service) |
| 8 | Generalised explainability | `explain_intelligence()` on any artefact type |
| 9 | Commercial intelligence | `COMMERCIAL_INTELLIGENCE_MODEL.md` — deterministic cost/effort fields |
| 10 | Future platform advisors | Consumers of CIA + ISL — not separate calculation engines |

---

## Authority stack (refined)

```
Authoritative Engines
        ↓
Compliance Evidence Graph / Graph Service
        ↓
Compliance Intelligence Engine (calculation)
        ↓
Compliance Intelligence Artefacts (immutable storage)
        ↓
Intelligence Service Layer (sole consumer API)
        ↓
Operational systems · Dashboards · Reports · AI Layer
```

**Key invariant:** No consumer queries `compliance_intelligence_artefacts` directly — same pattern as CEG graph storage.

---

## Refinement acceptance criteria

| Criterion | Status |
|-----------|--------|
| Compliance Intelligence Artefacts are the primary immutable intelligence entity | ✓ `INTELLIGENCE_ARTEFACT_MODEL.md` |
| Recommendations modelled as one subtype | ✓ `RECOMMENDATION_MODEL.md` § Subtype |
| Future intelligence types addable without redesign | ✓ `artefact_type` registry + typed payload |
| Intelligence remains deterministic | ✓ `inputs_hash` + `deterministic_version` |
| Intelligence remains reproducible | ✓ `response_hash` contract unchanged |
| Intelligence remains evidence-backed | ✓ `source_decision_ids` + evidence refs on base |
| Intelligence explainable without AI | ✓ `explain_intelligence()` |
| Clean CEG integration | ✓ `GRAPH_INTEGRATION_MODEL.md` refined |
| AI layer is consumer not producer | ✓ `INTELLIGENCE_CONSUMERS.md` |
| Future operational/commercial/regulatory/portfolio/audit intel without architecture change | ✓ artefact type extension model |

---

## Document index (post-refinement)

| Document | Role |
|----------|------|
| `COMPLIANCE_INTELLIGENCE_ENGINE_ARCHITECTURE.md` | Master architecture (updated) |
| `ARCHITECTURE_REFINEMENT_01.md` | This summary |
| `INTELLIGENCE_ARTEFACT_MODEL.md` | **New** — parent entity + type registry |
| `INTELLIGENCE_SERVICE_LAYER.md` | **New** — public service boundary |
| `INTELLIGENCE_LIFECYCLE_MODEL.md` | **New** — generalised lifecycle |
| `INTELLIGENCE_CONSUMERS.md` | **New** — consumer catalogue |
| `COMMERCIAL_INTELLIGENCE_MODEL.md` | **New** — commercial deterministic fields |
| `INTELLIGENCE_DOMAIN_MODEL.md` | Shared vocabulary (updated) |
| `RECOMMENDATION_MODEL.md` | Recommendation subtype (updated) |
| `RECOMMENDATION_LIFECYCLE.md` | Recommendation lifecycle extends base (updated) |
| Domain models | Produce typed artefact payloads |
| `GRAPH_INTEGRATION_MODEL.md` | Artefact-centric graph (updated) |
| `API_DESIGN.md` | ISL methods (updated) |
| `RUNTIME_VALIDATION_PLAN.md` | Artefact-level validation (updated) |
| `PHASED_IMPLEMENTATION_ROADMAP.md` | CIE-1 readiness (updated) |

---

## CIE-1 readiness recommendation

**Recommendation: READY FOR CIE-1 AUTHORISATION** (foundation slice only), subject to implementation scope below.

### Why ready

- Parent artefact model removes the risk of refactoring when portfolio, audit, insurance, and forecast types are added in CIE-2+.
- Intelligence Service Layer boundary is defined before any HTTP routes — prevents storage leakage.
- CIE-1 can implement **artefact base schema + hashing + ISL stub + access boundary** without building every artefact type.

### CIE-1 scope adjustment (from roadmap)

| Original CIE-1 | Refined CIE-1 |
|----------------|---------------|
| Package skeleton + config + hashing | **Unchanged** |
| `database.py` stubs for recommendations only | **Add** `compliance_intelligence_artefacts` base collection + transition collection stubs |
| No domain logic | **Add** artefact type registry (constants only); `IntelligenceArtefact` schema (pydantic/dataclass) |
| Access boundary vs graph storage | **Add** access boundary: consumers → ISL only; CIE → graph storage emit only via adapter |
| — | **Add** `services/compliance_intelligence_service/` package skeleton (ISL) — read facade, no engines yet |

### Not in CIE-1

- Recommendation generation, priority engine, commercial calculations
- Graph producers, HTTP routes
- Any artefact type beyond base envelope + registry

### Gate before CIE-2

- Base artefact emit/hash unit tests pass
- ISL `list_intelligence()` / `explain_intelligence()` return structured empty/stub envelopes
- Access boundary tests: ISL cannot import CIE storage; AI cannot import CIE storage

---

## Explicit non-goals (unchanged)

- No code in this refinement slice
- No production flags
- No AI, frontend, or customer portal implementation
- ML predictive planning remains a **separate labelled programme**; deterministic `forecast` artefact type reserved for CIE
