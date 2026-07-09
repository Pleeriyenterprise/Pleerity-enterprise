# Replay Architecture

**Programme:** COMPLIANCE-INTELLIGENCE-ENGINE-01  
**Refinement:** COMPLIANCE-INTELLIGENCE-ENGINE-ARCHITECTURE-REFINEMENT-02

---

## Purpose

Define **Intelligence Replay** — the architectural capability to deterministically reconstruct what CIE would have generated using historical inputs, registries, and evidence at a specified point in time.

**Example question:** *"What would CIE version 1.2 have generated using the evidence available on 17 June 2026?"*

Replay must use historical snapshots, rules, weights, strategies, legislation, and provenance — **no current-state substitutions**.

---

## Replay types

| Type | Input | Output |
|------|-------|--------|
| **Exact replay** | Existing `provenance_id` | Verify `response_hash` matches stored artefact |
| **Point-in-time replay** | `as_of`, scope, artefact_type, `engine_version` pin | New calculation under frozen historical context |
| **Counterfactual replay** | Point-in-time + single registry version override | Hypothetical artefact (labelled non-authoritative) |
| **Migration replay** | Old `engine_version` on historical inputs | Validation artefact for engine upgrade testing |

---

## Replay authority model

| Replay output | Authoritative? |
|---------------|----------------|
| Exact replay verification | Diagnostic only |
| Point-in-time regeneration | New artefact + new provenance (if run in production mode) |
| Counterfactual | **Never** authoritative — `payload.replay_mode: counterfactual` |
| Migration validation | Staging / shadow only |

Replay never mutates existing artefacts or provenance.

---

## Historical input freeze

Point-in-time replay resolves **frozen context** at `as_of`:

```
as_of timestamp
    ↓
Historical snapshots (source_snapshot_ids at as_of)
    ↓
Historical decision graph (Graph Service time-travel or snapshot replay)
    ↓
Rule versions effective at as_of
    ↓
Jurisdiction / legislation versions effective at as_of
    ↓
Evidence IDs existing at as_of
    ↓
Registry versions published ≤ as_of (strategies, weights, constraints)
    ↓
engine_version pin (explicit or from provenance)
```

**Forbidden:** Substituting current rule store, current weights, or live graph state when `as_of` is historical.

---

## Replay pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│ ISL: replay_intelligence(request)                                │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ Replay Orchestrator                                              │
│ 1. Resolve replay type                                           │
│ 2. Load provenance (if exact) or build frozen context (if as_of) │
│ 3. Resolve registry versions at as_of                            │
│ 4. Invoke CIE engines under engine_version pin                     │
│ 5. Compare response_hash to expected (if exact)                    │
│ 6. Emit replay report envelope (no artefact persist unless requested)│
└─────────────────────────────────────────────────────────────────┘
```

---

## Exact replay (integrity verification)

```
Input:  provenance_id
Steps:
  1. Load provenance + linked artefact
  2. Load registry versions from provenance pins
  3. Re-run calculation pipeline with frozen inputs
  4. Assert response_hash match
  5. Assert trace_hash match
Output: { "replay_verified": true, "response_hash_match": true }
```

Used in staging validation, migration testing, and audit spot-checks.

---

## Point-in-time replay

```
Input: {
  "client_id": "…",
  "artefact_type": "recommendation",
  "as_of": "2026-06-17T00:00:00Z",
  "engine_version": "cie-1.2.0",
  "scope": { … }
}
Steps:
  1. Build frozen context at as_of
  2. Resolve strategies/weights/constraints published ≤ as_of
  3. Run engines
  4. Write new provenance + artefact (optional persist flag)
Output: IntelligenceEnvelope with replay metadata
```

---

## Graph Service integration

Replay consumes Graph Service in **historical mode**:

| Method (future) | Purpose |
|-----------------|---------|
| `replay_decision(decision_id, as_of)` | Frozen decision at timestamp |
| `find_historical_decision(scope, as_of)` | Decision discovery |
| `trace_evidence(snapshot_id)` | Evidence at snapshot |

CIE read adapter must pass `as_of` to all graph reads during replay — never default to "now".

---

## Storage

| Artifact | Collection | Notes |
|----------|------------|-------|
| Replay request log | `compliance_intelligence_replay_log` (optional) | Audit of who replayed what |
| Replay output | Not persisted by default | `persist_replay_result=true` for staging |

Replay log is append-only; does not modify provenance or artefacts.

---

## Feature gating

| Mode | Replay behaviour |
|------|------------------|
| `COMPLIANCE_INTELLIGENCE_ENGINE_MODE=disabled` | Unavailable envelope |
| `shadow` | Replay allowed; results non-operational |
| `enabled` | Exact replay + point-in-time for admin |

Counterfactual replay: **admin + shadow only** until explicit authorisation.

---

## Validation scenarios (future)

| ID | Assertion |
|----|-----------|
| R1 | Exact replay of staging artefact → `response_hash` match |
| R2 | Point-in-time replay at known `as_of` → identical to original provenance |
| R3 | Replay with current weights on historical `as_of` → **must differ** from original (proves no substitution) |
| R4 | Migration replay `cie-1.2.0` vs `cie-2.0.0` → diff report without artefact mutation |

See `RUNTIME_VALIDATION_PLAN.md` (updated).

---

## Non-goals

- Replay does not restore deleted evidence
- Replay does not change compliance scores or authority stores
- Replay is not AI summarisation — output is deterministic artefact or verification report
