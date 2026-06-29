# Recommendation Lifecycle

**Programme:** COMPLIANCE-INTELLIGENCE-ENGINE-01

---

## Purpose

Define immutable lifecycle progression for recommendations. Every transition is a **new graph event** — never an in-place status update.

---

## Lifecycle states

```
                    ┌─────────────┐
                    │  generated  │ ← initial emit
                    └──────┬──────┘
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
     ┌──────────┐    ┌──────────┐    ┌──────────┐
     │ accepted │    │ cancelled│    │ superseded│ (by new rec)
     └────┬─────┘    └──────────┘    └──────────┘
          ▼
     ┌──────────┐
     │ scheduled│
     └────┬─────┘
          ▼
     ┌────────────┐
     │ in_progress│
     └─────┬──────┘
           ▼
     ┌──────────┐         ┌──────────┐
     │ completed│────────►│ archived │
     └──────────┘         └──────────┘
```

| State | Meaning | Operational hook |
|-------|---------|------------------|
| `generated` | CIE created recommendation | None |
| `accepted` | User/system acknowledged intent | Audit only |
| `scheduled` | Date/contractor assigned | May link `work_order_id` |
| `in_progress` | Work underway | WO status sync |
| `completed` | Action verified complete | May trigger compliance recalc (existing engine) |
| `superseded` | Replaced by newer recommendation | `superseded_by_recommendation_id` |
| `cancelled` | Explicitly rejected / no longer applicable | Reason required |
| `archived` | Terminal retention state | Read-only |

---

## Transition rules

1. **Append-only** — transition creates new `compliance_intelligence_recommendation_transitions` record
2. **Recommendation row** — current `status` is denormalised pointer to latest transition (for query ergonomics only; history is authoritative)
3. **Every transition** emits `compliance_decisions` with `decision_type=recommendation_lifecycle`
4. **Invalid transitions** rejected deterministically (e.g. `completed` → `generated`)

### Valid transition matrix

| From \ To | accepted | scheduled | in_progress | completed | superseded | cancelled | archived |
|-----------|----------|-----------|-------------|-----------|------------|-----------|----------|
| generated | ✓ | ✓ | | | ✓ | ✓ | |
| accepted | | ✓ | ✓ | | ✓ | ✓ | |
| scheduled | | | ✓ | | ✓ | ✓ | |
| in_progress | | | | ✓ | ✓ | ✓ | |
| completed | | | | | | | ✓ |
| superseded | | | | | | | ✓ |
| cancelled | | | | | | | ✓ |

---

## Transition record schema

**Collection:** `compliance_intelligence_recommendation_transitions`

```json
{
  "transition_id": "rect_<uuid>",
  "recommendation_id": "rec_<uuid>",
  "from_status": "generated",
  "to_status": "accepted",
  "transitioned_at": "2026-06-02T14:00:00+00:00",
  "transition_decision_id": "dec_<uuid>",
  "actor": {
    "actor_type": "portal_user | admin | system",
    "actor_id": "uuid"
  },
  "reason_code": "user_accepted",
  "reason_summary": "Landlord accepted renewal recommendation",
  "linked_artefacts": {
    "work_order_id": null,
    "reminder_id": null,
    "document_id": null
  },
  "client_id": "uuid",
  "correlation_id": "uuid",
  "inputs_hash": "sha256:…",
  "environment": "staging"
}
```

---

## Graph integration

Each transition creates:

| Graph artefact | Relationship |
|----------------|--------------|
| `compliance_decisions` | `decision_type=recommendation_lifecycle` |
| `compliance_decision_snapshots` | Frozen recommendation state at transition |
| Graph edge | `recommendation` → `transitioned_to` → `status:{to_status}` |
| Graph edge | `transition` → `references` → `decision` (compliance assessment that completed action) |

Completion transition **may** reference the compliance assessment decision that resulted from uploaded evidence — CIE does not create that assessment.

---

## Completion verification

`completed` transition requires **one of**:

1. Linked compliance assessment decision showing requirement satisfied (Graph `explain_decision`)
2. Linked document/CER with verified status (authority pointer)
3. Explicit admin override with `reason_code=manual_completion` + mandatory audit note

Without verification → transition rejected or remains `in_progress`.

---

## Supersession

When CIE regenerates recommendations:

1. New `rec_B` created with `supersedes_recommendation_id=rec_A`
2. Transition `rec_A: generated → superseded` emitted automatically
3. Priority ranks recalculated for portfolio scope
4. Open work orders on `rec_A` flagged for review (notification only — WO service owns state)

---

## Shadow mode behaviour

In `COMPLIANCE_INTELLIGENCE_ENGINE_MODE=shadow`:

- Lifecycle transitions **logged** and **graph-emitted**
- No work order creation, no reminder scheduling, no customer notifications

---

## API surface (future)

```text
transition_recommendation(recommendation_id, to_status, actor, reason)
get_recommendation_lifecycle(recommendation_id) → ordered transitions
```

Both return deterministic envelopes with full transition history.
