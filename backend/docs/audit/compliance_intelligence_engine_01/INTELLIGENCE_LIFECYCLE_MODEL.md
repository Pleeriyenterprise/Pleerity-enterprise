# Intelligence Lifecycle Model

**Programme:** COMPLIANCE-INTELLIGENCE-ENGINE-01  
**Refinement:** COMPLIANCE-INTELLIGENCE-ENGINE-ARCHITECTURE-REFINEMENT-01

---

## Purpose

Define immutable lifecycle progression for **all Compliance Intelligence Artefacts**. Recommendation lifecycle (`RECOMMENDATION_LIFECYCLE.md`) extends this base with subtype-specific rules.

---

## Base lifecycle states

```
┌────────────┐
│ generated  │ ← CIE emit
└─────┬──────┘
      │
      ├──► validated ──► published ──► consumed
      │
      ├──► superseded
      ├──► cancelled
      ├──► expired
      └──► archived
```

| State | Meaning |
|-------|---------|
| `generated` | Artefact computed and stored |
| `validated` | Internal QA / integrity check passed (optional gate) |
| `published` | Eligible for consumer surfaces (digest, reports, dashboards) |
| `consumed` | Acknowledged by a consumer system (audit trail) |
| `superseded` | Replaced by newer artefact |
| `cancelled` | Explicitly voided with reason |
| `expired` | Time-bound artefact past `valid_until` |
| `archived` | Terminal retention state |

Not all artefact types use all states. Subtype declares **allowed states** and **valid transitions**.

---

## Transition records

**Collection:** `compliance_intelligence_artefact_transitions`

```json
{
  "transition_id": "ciat_<uuid>",
  "artefact_id": "cia_<uuid>",
  "artefact_type": "recommendation",
  "from_state": "generated",
  "to_state": "published",
  "transitioned_at": "2026-06-02T14:00:00+00:00",
  "transition_decision_id": "dec_<uuid>",
  "actor": {
    "actor_type": "system | admin | portal_user | consumer",
    "actor_id": "digest_service | uuid"
  },
  "consumer_id": "monthly_digest | null",
  "reason_code": "auto_publish_shadow_pass",
  "reason_summary": "Shadow validation passed; eligible for digest",
  "inputs_hash": "sha256:…",
  "client_id": "uuid",
  "correlation_id": "uuid"
}
```

Every transition emits `compliance_decisions` with `decision_type=intelligence_lifecycle`.

---

## Subtype extensions

### Recommendation

Additional states: `accepted`, `scheduled`, `in_progress`, `completed` (between `published` and terminal states).

See `RECOMMENDATION_LIFECYCLE.md` for full matrix. Recommendation states **compose** on base lifecycle — e.g. `published` → `accepted` → `scheduled` → `in_progress` → `completed` → `archived`.

### Portfolio insight / forecast

Typical path: `generated` → `published` → `consumed` → `expired` → `archived`. No operational execution states.

### Regulatory impact assessment

Typical path: `generated` → `validated` → `published` → `archived`. May `supersede` on rule re-analysis.

---

## Shadow mode

In `COMPLIANCE_INTELLIGENCE_ENGINE_MODE=shadow`:

- Artefacts reach `generated` (and optionally `validated`)
- Auto-transition to `published` **blocked** for operational consumers
- `consumed` transitions logged only in test harness

---

## Expiry

Artefacts may include `valid_until` in payload. Scheduler emits `expired` transition — no content mutation.

---

## Graph integration

Each transition:

- New `intelligence_lifecycle` decision
- Edge: `artefact` → `transitioned_to` → `state:{to_state}`
- Optional edge to consumer: `consumed_by` → `digest_run_id`

---

## API

```text
ISL.transition_intelligence(artefact_id, to_state, …)
ISL.get_intelligence_lifecycle(artefact_id)
```

Invalid transitions → 422 with allowed transitions list.
