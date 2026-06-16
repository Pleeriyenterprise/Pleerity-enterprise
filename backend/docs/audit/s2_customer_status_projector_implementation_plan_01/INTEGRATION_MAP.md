# Integration map — enrich_requirement_dict

**Programme:** S2-CUSTOMER-STATUS-PROJECTOR-IMPLEMENTATION-PLAN-01  
**Integration point:** `backend/services/requirement_truth.py` → `enrich_requirement_dict`

---

## Current pipeline (client audience)

```
… engine payload, action_type …
→ resolve_take_action_envelope()          [line ~631 — PRE-PROJECTOR TODAY]
→ evidence_completeness / canon-specific status_label overrides
→ derive_client_lifecycle_fields()        [PS-01]
→ attach_cer_governance_presentation()  [PS-02 — legacy labels]
→ client_lifecycle_label ← truth_presentation_label  [804–806 — REM-01]
→ reconcile_satisfaction / attach_satisfaction       [PS-04]
→ audience_interpretation                              [PS-08]
→ apply_actionability_cta_override()                   [PS-05]
→ build_envelope_for_requirement()                     [PS-06]
```

---

## Target pipeline (S2)

```
… engine payload, action_type …
→ evidence_completeness / canon-specific status_label overrides  [unchanged — not customer_status authority]
→ derive_client_lifecycle_fields()                               [PS-01 input]
→ attach_cer_governance_presentation(meta_only_when_active=True) [PS-02 meta; labels if disabled/shadow legacy path]
→ reconcile_satisfaction / attach_satisfaction                   [PS-04 input]
→ [NEW] apply_customer_status_projection(mode)                     [projector + shadow compare]
→ [NEW] mirror_legacy_truth_fields_from_projector()                [active only — compat]
→ audience_interpretation(reads customer_status_*)               [PS-08 partial]
→ resolve_take_action_envelope()                                   [REM-05 — moved here]
→ apply_actionability_cta_override(reads customer_status_*)        [REM-04]
→ build_envelope_for_requirement(reads customer_status_*)          [REM-03]
```

### Ordering rationale

| Step | Must run after | Reason |
|------|----------------|--------|
| Projector | lifecycle + CER meta + satisfaction | Inputs complete |
| take_action | projector | CTA policy keyed on `customer_status_key` |
| actionability override | take_action + customer_status | Component CTAs must not contradict badge |
| cognition | all above | Consumes canonical pair |

---

## Where projector runs

| Attribute | Value |
|-----------|-------|
| **Function** | `enrich_requirement_dict` |
| **Audience** | `client` only (not `admin` in S2) |
| **Line region** | After satisfaction attach (~814), before audience (~816) |
| **Guard** | Skip if `applicability == NOT_REQUIRED` or row not applicable |

---

## Data required before projector

| Must exist | Produced by |
|------------|-------------|
| `client_lifecycle_state` | `derive_client_lifecycle_fields` |
| `governance_family`, `assurance_tier`, `queue_backed_review`, `review_owner` | `attach_cer_governance_presentation` |
| `satisfaction_state` | `attach_satisfaction_fields` |
| `evidence_authority` | pre-enrich sync |
| `linked_primary_document` | enrich caller document load |

### Pre-projector queue signal

Compute or confirm `queue_backed_review` via existing `review_queue_service.document_in_pending_verification_queue` inside CER attach or projector context builder — **no new queue**.

---

## Fields by flag mode

### disabled

| Field group | Behaviour |
|-------------|-----------|
| `customer_status_*` | **Absent** |
| `truth_presentation_*` | Legacy `derive_truth_presentation` |
| `client_lifecycle_label` | Overwritten from truth label (current behaviour) |
| `_customer_status_shadow` | Absent |

### shadow

| Field group | Behaviour |
|-------------|-----------|
| `customer_status_*` | **Present** on payload |
| `truth_presentation_*` | Legacy — **customer-visible authority** |
| `client_lifecycle_label` | From legacy truth label (unchanged customer impact) |
| `_customer_status_shadow` | `{ legacy_label, projector_label, divergence_type, compared_at }` — admin explain only or omit from public schema doc |

### active

| Field group | Behaviour |
|-------------|-----------|
| `customer_status_*` | **Authoritative** |
| `truth_presentation_*` | **Mirrored** from projector (compat until S3) |
| `client_lifecycle_label` | Set from `customer_status_label` (not from legacy derive) |
| `_customer_status_shadow` | Optional last divergence snapshot |

---

## New fields added (additive)

| Field | shadow | active |
|-------|--------|--------|
| `customer_status_key` | yes | yes |
| `customer_status_label` | yes | yes |
| `customer_status_subline` | yes | yes |
| `customer_status_class` | yes | yes |
| `customer_status_reason` | yes | yes |
| `customer_status_overlay` | yes | yes |
| `vocabulary_version` | yes | yes |
| `customer_status_projector_version` | yes | yes |

---

## Shadow-only fields

| Field | Purpose | Consumer |
|-------|---------|----------|
| `_customer_status_shadow.legacy_label` | Divergence compare | Admin explain, logs |
| `_customer_status_shadow.projector_label` | Divergence compare | Admin explain, logs |
| `_customer_status_shadow.divergence_type` | Metrics | Observability |
| `_customer_status_shadow.compared_at` | Audit | Logs |

**Not consumed by frontend in S2** — omit from client API schema documentation or mark `internal`.

---

## Old fields retained (S2)

| Field | shadow | active |
|-------|--------|--------|
| `truth_presentation_label` | legacy authority | mirrored |
| `truth_presentation_subline` | legacy | mirrored |
| `truth_presentation_stage` | legacy | inverse-mapped from key |
| `truth_presentation_tier_supplement` | legacy meta | optional mirror |
| `client_lifecycle_state` | yes | yes |
| `client_lifecycle_label` | legacy-driven | projector-driven |
| `review_owner`, `queue_backed_review` | yes | yes (internal — not for customer copy) |

**No field removals in S2.**

---

## Downstream consumer read order (post-integration)

| Consumer | Reads |
|----------|-------|
| `audience_governance_v1` | `customer_status_label` when present |
| `requirement_action_resolver` | `customer_status_key`, `customer_status_class` |
| `cer_actionability_presentation` | `customer_status_subline`, `customer_status_key` |
| `operational_cognition_service` | `customer_status_label`, `customer_status_subline`, `customer_status_class` |

---

## Admin audience (S2 scope)

| Item | S2 behaviour |
|------|--------------|
| Projector on admin enrich | **Optional** — recommend client-only S2; admin explain API adds projector debug via separate path |
| Admin explain API | Include `customer_status_*` + `_customer_status_shadow` when flag ≠ disabled |
