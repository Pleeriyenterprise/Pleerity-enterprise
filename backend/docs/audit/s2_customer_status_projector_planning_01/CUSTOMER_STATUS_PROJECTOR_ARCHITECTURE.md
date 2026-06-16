# Customer status projector v2 — architecture

**Programme:** S2-CUSTOMER-STATUS-PROJECTOR-PLANNING-01  
**Status:** PLANNING ONLY — not implemented  
**Authority:** `REVIEW_POLICY_VOCABULARY.md`, `CUSTOMER_STATUS_VOCABULARY.json`, `SEMANTIC_CONTRACT.md`

---

## 1. Purpose

Introduce **one authoritative backend projector** that maps enrich-time requirement signals to approved customer obligation status vocabulary.

**Does not change:** evidence authority writes, queue membership rules, satisfaction truth, scoring formulas, Mongo schemas.

**Does change (when flag=active):** API-emitted `customer_status_*` fields and downstream consumers that read them on enrich payloads.

---

## 2. Module placement

| Item | Decision |
|------|----------|
| **New module** | `backend/services/customer_status_projector_v2.py` |
| **Integration point** | `requirement_truth.enrich_requirement_dict` after `attach_cer_governance_presentation` + satisfaction reconcile |
| **Vocabulary** | Import from `customer_status_vocabulary.py` only — no hardcoded labels |
| **Legacy** | `derive_truth_presentation` remains callable in shadow/disabled modes |

**Rationale:** Avoid bloating `cer_governance_presentation.py` further; projector is class/path logic + gates, governance meta stays in CER module.

---

## 3. Inputs (projector context)

Built from enriched requirement row **before** customer status emission:

| Input field / signal | Source module | Use |
|--------------------|---------------|-----|
| `requirement_code` / `requirement_type` | requirement row | Workflow class resolution (A/B/C) |
| `governance_family` | `cer_governance_presentation.resolve_governance_meta` | Class A vs B vs platform-opt |
| `evidence_authority.state` | `requirement_evidence_authority` | EA states, semantic triggers |
| `evidence_authority.state_reason` | same | Follow-up, expiry, component gaps |
| `semantic_state` | EA / CER | Declaration recorded, etc. |
| `client_lifecycle_state` | `client_requirement_lifecycle` | Internal enum — not emitted as badge |
| `verification_status` | linked document / CER | Class B verify path |
| `linked_primary_document.status` | document load in enrich | UPLOADED gate |
| `queue_backed_review` (computed) | `review_queue_service` + document id | **emit_under_review** gate |
| `escalation_active` | exception flags, manual_review_flag | **emit_escalation_required** |
| `satisfaction_state` | `requirement_satisfaction_service` | Satisfied overlay vs base |
| `components_incomplete` | CER guards | Additional action required |
| `followup_unresolved` | legionella/lead/HMO fire | Follow-up required |
| `has_persisted_submission` | CER helper | Recorded gate |
| `truth_presentation_stage` (legacy) | shadow compare only | Not an input when active |

### Workflow class resolution

| Class | Resolution rule |
|-------|-----------------|
| **A** | `governance_family == SELF_CERTIFIED` (and not certificate-primary) |
| **B** | `governance_family == PLATFORM_VERIFIED` OR code in `DOCUMENT_PRIMARY_CODES` |
| **C** | Escalation overlay — not a standalone path |

---

## 4. Outputs (API contract)

Emitted on **every client enrich** row when projector runs (shadow always computes; active emits):

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `customer_status_key` | string | yes | Machine enum from `CUSTOMER_STATUS_KEYS` |
| `customer_status_label` | string | yes | Human badge — `CUSTOMER_STATUS_LABEL_BY_KEY` |
| `customer_status_subline` | string | no | One-line explanation; may be empty |
| `customer_status_class` | string | yes | `A` \| `B` \| `C_overlay` |
| `customer_status_reason` | string[] | no | Machine reason codes e.g. `QUEUE_PROVEN`, `ESCALATION_ACTIVE`, `COMPONENTS_INCOMPLETE` |
| `customer_status_overlay` | string \| null | no | Active overlay key if any |
| `vocabulary_version` | string | yes | From `customer_status_vocabulary.VOCABULARY_VERSION` |
| `customer_status_projector_version` | string | yes | Projector semver e.g. `2.0.0` |

### Backward compatibility (shadow / transition)

| Legacy field | Active-mode behaviour |
|--------------|----------------------|
| `truth_presentation_label` | **Mirrored** from `customer_status_label` for one release OR deprecated with shadow warning |
| `truth_presentation_subline` | Mirrored from `customer_status_subline` |
| `truth_presentation_stage` | Mapped from `customer_status_key` via `PRESENTATION_STAGE_TO_STATUS_KEY` inverse |
| `client_lifecycle_label` | Set from `customer_status_label` (existing enrich line 804-806) |

**S2 recommendation:** Mirror legacy fields from projector output when `flag=active` to avoid breaking S3-not-yet-deployed frontend. Remove mirroring in S3.

### Invariants (enforced in projector)

- I1–I7 from `SEMANTIC_CONTRACT.md`
- No retired phrase in `customer_status_label` / `customer_status_subline` (assert against `RETIRED_REVIEW_PHRASES`)
- Class-disjoint forbidden badges per `CLASS_*_FORBIDDEN_PRIMARY_BADGES`

---

## 5. Gate evaluation order

Per `CUSTOMER_STATUS_VOCABULARY.json` `overlay_precedence`:

1. `escalation_required` — exception active + admin resolution path
2. `rejected` — class B admin reject
3. `under_review` — class B + UPLOADED + `document_pending_verification` queue
4. `expiry_date_needed` — blocking expiry semantics
5. `followup_required` / `additional_action_required`
6. Base path state per class A/B lifecycle

**forbid_review_language:** If neither under_review nor escalation_required gates pass → labels must not contain review vocabulary.

---

## 6. Enrich pipeline (target)

```
enrich_requirement_dict (client)
  → derive_client_lifecycle_fields          [input]
  → attach_cer_governance_presentation      [meta + legacy truth in shadow/disabled]
  → reconcile_satisfaction / attach_satisfaction [input]
  → customer_status_projector_v2.project()  [NEW — authoritative when active]
  → mirror legacy truth_* if active         [compat]
  → audience_interpretation (reads customer_status_*)
  → apply_actionability_cta_override        [reads customer_status_*]
  → build_envelope_for_requirement          [reads customer_status_*]
```

---

## 7. Non-goals (S2)

- Frontend changes
- Report/email copy
- New Mongo fields / migrations
- New queues or workflow states
- Admin UI rename (S5)

---

## 8. Related artefacts

- `PROJECTOR_STATUS_MAPPING_MATRIX.json` — row-level mapping
- `SHADOW_MODE_STRATEGY.md` — rollout
- `FEATURE_FLAG_STRATEGY.md` — flag states (design only)
