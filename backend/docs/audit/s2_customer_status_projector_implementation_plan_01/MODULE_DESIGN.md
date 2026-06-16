# Module design — customer_status_projector_v2

**Programme:** S2-CUSTOMER-STATUS-PROJECTOR-IMPLEMENTATION-PLAN-01  
**Status:** PLANNING ONLY

---

## Module

| Item | Value |
|------|-------|
| **Path** | `backend/services/customer_status_projector_v2.py` |
| **Companion** | `customer_status_projector_config.py`, `customer_status_projector_shadow.py` |
| **Semver** | `PROJECTOR_VERSION = "2.0.0"` (constant in module) |

---

## Public API

```python
def project_customer_status(
    requirement: dict[str, Any],
    *,
    linked_primary_document: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return customer_status_* fields only (no mutation)."""

def apply_customer_status_projection(
    requirement: dict[str, Any],
    *,
    linked_primary_document: dict[str, Any] | None = None,
    mode: str,  # disabled | shadow | active
) -> dict[str, Any]:
    """Mutate requirement in place per flag mode; invoke shadow compare when shadow|active."""
```

---

## Input contract

Built from enriched requirement row **after** lifecycle, CER governance meta, and satisfaction reconciliation. Projector **must not** read `truth_presentation_label` as an input when `mode=active`.

| Field / signal | Required | Source | Use |
|----------------|----------|--------|-----|
| `requirement_code` / `requirement_type` | yes | row | Canonical code → workflow class hints |
| `governance_family` | yes | `cer_governance_presentation` meta | Class A vs B resolution |
| `evidence_authority.state` | yes | `requirement_evidence_authority` | EA gates |
| `evidence_authority.state_reason` | no | same | Expiry, follow-up triggers |
| `semantic_state` | no | EA / CER | Declaration recorded, etc. |
| `client_lifecycle_state` | yes | `client_requirement_lifecycle` | Internal enum — not emitted as badge |
| `satisfaction_state` | no | `requirement_satisfaction_service` | Satisfied overlay |
| `linked_primary_document.status` | no | document load | UPLOADED gate (class B) |
| `document_id` / `evidence_doc_id` | no | row | Queue lookup key |
| `queue_backed_review` | no | computed pre-projector | **emit_under_review** gate |
| `review_owner` | no | CER / convergence | Queue gate validation |
| `escalation_active` | no | exception flags | **emit_escalation_required** |
| `components_incomplete` | no | CER guards | additional_action_required |
| `followup_unresolved` | no | legionella/lead/HMO | followup_required |
| `has_persisted_submission` | yes | CER helper | recorded gate |
| `assurance_tier` | no | CER meta | Subline hints only — not badge authority |

### Workflow class resolution

| Class | Rule |
|-------|------|
| **A** | `governance_family == SELF_CERTIFIED` (non certificate-primary) |
| **B** | `governance_family == PLATFORM_VERIFIED` OR code ∈ `DOCUMENT_PRIMARY_CODES` |
| **C_overlay** | Escalation overlay on A or B — not a parallel path |

### Gate evaluation order

Per `OVERLAY_PRECEDENCE` in `customer_status_vocabulary.py`:

1. `escalation_required`
2. `rejected`
3. `under_review` (class B + UPLOADED + `document_pending_verification` queue)
4. `expiry_date_needed`
5. `followup_required` / `additional_action_required`
6. Base path state per class

**forbid_review_language:** If `under_review` and `escalation_required` gates fail → label/subline must not match `RETIRED_REVIEW_PHRASES` or contain review vocabulary per class forbidden badges.

---

## Output contract

| Field | Type | Required | Source |
|-------|------|----------|--------|
| `customer_status_key` | string | yes | `CUSTOMER_STATUS_KEYS` |
| `customer_status_label` | string | yes | `CUSTOMER_STATUS_LABEL_BY_KEY[key]` |
| `customer_status_subline` | string | no | Vocabulary subline table + gate context |
| `customer_status_class` | string | yes | `A` \| `B` \| `C_overlay` |
| `customer_status_reason` | string[] | no | e.g. `QUEUE_PROVEN`, `ESCALATION_ACTIVE`, `COMPONENTS_INCOMPLETE` |
| `customer_status_overlay` | string \| null | no | Active overlay key if any |
| `vocabulary_version` | string | yes | `VOCABULARY_VERSION` from vocabulary module |
| `customer_status_projector_version` | string | yes | `2.0.0` |

### Invariants (assert in dev/test; log in prod)

- I1–I7 from `SEMANTIC_CONTRACT.md`
- `customer_status_label` ∉ `RETIRED_REVIEW_PHRASES` (case-insensitive substring check)
- Class A: `customer_status_key` ∉ `CLASS_A_FORBIDDEN_PRIMARY_BADGES`
- Class B: `customer_status_key` ∉ `CLASS_B_FORBIDDEN_PRIMARY_BADGES`
- Class A + no queue: `customer_status_key` ≠ `under_review`

---

## Vocabulary dependency

| Import | From | Rule |
|--------|------|------|
| Keys, labels, forbidden badges | `services.customer_status_vocabulary` | **Only** vocabulary source |
| Retired phrases | `services.retired_obligation_phrase_registry` OR `RETIRED_REVIEW_PHRASES` | Assert clean output |
| Subline templates | `CUSTOMER_STATUS_VOCABULARY.json` sublines section (mirror in vocabulary module if missing — add to vocabulary module in S2, not hardcoded in projector) |

**No hardcoded customer-facing strings in projector** except empty string defaults.

---

## Error behaviour

| Condition | Behaviour |
|-----------|-----------|
| Missing `governance_family` | Log warning; default class from requirement code map; emit `action_required` |
| Missing `evidence_authority` | Treat as `action_required` path |
| Queue lookup failure | `queue_backed_review=False`; do not emit `under_review` |
| Vocabulary key resolution failure | **Fail closed** — `action_required` + reason `PROJECTOR_FALLBACK` + structured error log |
| Invariant violation after projection | **Fail closed** in test; in prod log `customer_status_projector_invariant_violation` and emit safest label `action_required` |

No exception propagation to enrich caller — projector errors must not break enrich endpoints.

---

## Fallback behaviour by flag mode

| Mode | Projector runs | API customer fields | Legacy truth_* |
|------|----------------|---------------------|----------------|
| `disabled` | No | Not added | Legacy only |
| `shadow` | Yes | Added to payload **but not authoritative**; also in `_customer_status_shadow` debug object | Legacy emitted to client-visible fields |
| `active` | Yes | **Authoritative** `customer_status_*` | Mirrored from projector for one release (compat) |

---

## Versioning

| Version | Scope |
|---------|-------|
| `vocabulary_version` | Tracks `CUSTOMER_STATUS_VOCABULARY.json` — bump on governance change |
| `customer_status_projector_version` | Tracks gate logic — bump on projector rule change |
| Both emitted on every enrich row when projector runs |

---

## Non-responsibilities

- Evidence authority writes
- Queue membership mutations
- Satisfaction truth computation
- Scoring formulas
- Frontend/report/email copy
- Mongo persistence
