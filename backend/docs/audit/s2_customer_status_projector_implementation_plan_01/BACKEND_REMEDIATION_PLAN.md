# Backend remediation plan — five mandatory fixes

**Programme:** S2-CUSTOMER-STATUS-PROJECTOR-IMPLEMENTATION-PLAN-01  
**Authority:** `s2_projection_source_disposition_audit_01` — conditions before S2 code

All five remediations are **in scope for S2** and **required before `flag=active`**. None may be deferred without explicit risk acceptance.

---

## REM-01 — requirement_truth enrich overwrite

### Current problem

After `attach_cer_governance_presentation`, enrich unconditionally overwrites `client_lifecycle_label` from `truth_presentation_label` (lines 804–806). This re-asserts legacy status authority and would override projector output when active.

### Location

| Item | Value |
|------|-------|
| **File** | `backend/services/requirement_truth.py` |
| **Function** | `enrich_requirement_dict` |
| **Lines** | 804–806 |

### Proposed change

1. Insert `apply_customer_status_projection()` after satisfaction attach.
2. When `mode=active`: set `client_lifecycle_label = customer_status_label` (from projector).
3. When `mode=shadow`: retain current overwrite from legacy truth label.
4. When `mode=disabled`: unchanged.

Remove unconditional `truth_label` overwrite — branch on flag mode.

### Tests required

| Test | Assertion |
|------|-----------|
| `test_enrich_active_client_lifecycle_label_from_projector` | active → `client_lifecycle_label == customer_status_label` |
| `test_enrich_shadow_preserves_legacy_label` | shadow → legacy label unchanged on customer-visible fields |
| `test_enrich_active_does_not_read_legacy_derive` | active → changing legacy derive output does not change `customer_status_label` |

### Rollback

`CUSTOMER_STATUS_PROJECTOR_V2_MODE=shadow` restores legacy overwrite path.

### Risk

| Level | **CRITICAL** |
|-------|--------------|
| If excluded | Projector output masked; second authority survives; PC-02 remains |

---

## REM-02 — derive_truth_presentation label emission

### Current problem

`derive_truth_presentation` emits retired customer-facing phrases (`Platform verification pending`, `Escalated for platform review`) and acts as primary status authority today (PC-01).

### Location

| Item | Value |
|------|-------|
| **File** | `backend/services/cer_governance_presentation.py` |
| **Functions** | `derive_truth_presentation`, `attach_cer_governance_presentation` |

### Proposed change

| Mode | Behaviour |
|------|-----------|
| `disabled` | Full legacy derive (unchanged) |
| `shadow` | Full legacy derive (comparator) |
| `active` | `attach_cer_governance_presentation` emits **governance meta only** (`governance_family`, `assurance_tier`, `review_owner`, `queue_backed_review`) — **skip** label/subline/stage from derive; fill via `mirror_legacy_truth_fields_from_projector()` after projector |

Alternative (acceptable): run derive internally but **do not attach** label fields to outbound dict when active.

### Tests required

| Test | Assertion |
|------|-----------|
| `test_cer_governance_active_skips_legacy_labels` | active → no retired phrase in truth_presentation_label source path |
| `test_cer_governance_shadow_runs_legacy` | shadow → legacy labels preserved |
| `test_cer_governance_meta_always_present` | all modes → governance_family present |

### Rollback

`shadow` or `disabled` re-enables full derive.

### Risk

| Level | **CRITICAL** |
|-------|--------------|
| If excluded | PS-02 remains customer authority; projector is decorative; PC-01 |

---

## REM-03 — operational_cognition_service alignment

### Current problem

`recommended_next_step` branches on `truth_presentation_stage` and emits `Awaiting review — submission not yet verified` (retired phrase). Cognition independently derives customer status copy (PC-05, D9).

### Location

| Item | Value |
|------|-------|
| **File** | `backend/services/operational_cognition_service.py` |
| **Function** | `build_envelope_for_requirement` → `recommended_next_step` logic (~736–773) |

### Proposed change

1. When `customer_status_label` present: use as primary `recommended_next_step` (or vocabulary-approved cognition template keyed on `customer_status_key`).
2. Class A `recorded`: `"Recorded on file — not independently verified"` (per D9 resolution) — from subline table, not hardcoded in cognition if subline exists.
3. Class B `under_review`: use `customer_status_subline` or default `"Our team is verifying your uploaded certificate"`.
4. Remove branches that emit `RETIRED_REVIEW_PHRASES`.
5. `truth_presentation_stage` branches become fallback only when `mode=disabled`.

### Tests required

| Test | Assertion |
|------|-----------|
| `test_cognition_class_a_no_review_phrase` | recorded → no retired review phrase |
| `test_cognition_d9_recorded_not_verified` | class A post-submit → D9 approved copy |
| `test_cognition_class_b_under_review` | queue proven → under review copy |
| `test_cognition_verified_no_further_evidence` | verified → "No further evidence required" |

### Rollback

Flag `disabled` — legacy cognition branches.

### Risk

| Level | **HIGH** |
|-------|----------|
| If excluded | Today/Command Centre contradicts projector when active; D9 persists |

---

## REM-04 — cer_actionability_presentation banners / stage mutation

### Current problem

`resolve_existing_submission_banner_copy` returns `Submission on file — awaiting review` and escalation review banners without vocabulary gate. `build_reopen_prefill_from_record` copies `truth_presentation_stage` into prefill output (stage mutation on derived objects).

### Location

| Item | Value |
|------|-------|
| **File** | `backend/services/cer_actionability_presentation.py` |
| **Functions** | `resolve_existing_submission_banner_copy`, `apply_actionability_cta_override`, `build_reopen_prefill_from_record` |

### Proposed change

1. **Banners**: When `customer_status_subline` present, use it for banner; else queue-gated templates only:
   - queue + class B → approved under_review subline
   - no queue → `"Submission on file. You can update your submission below."` (no review language)
2. Remove `"Submission on file — awaiting review"` and `"escalated for platform review"` retired strings.
3. **CTA override**: Read `customer_status_key` for stage-equivalent decisions instead of `truth_presentation_stage` when projector fields present.
4. **Prefill**: Do not mutate `truth_presentation_stage` on prefill dict — use `customer_status_key` if needed.

### Tests required

| Test | Assertion |
|------|-----------|
| `test_banner_class_a_no_review_without_queue` | no queue → no review banner |
| `test_banner_class_b_queue_backed` | queue → vocabulary subline |
| `test_banner_escalation_uses_projector` | escalation_required → no retired escalation phrase |
| `test_actionability_cta_no_contradiction` | CTA label ≠ contradicting customer_status_label |

### Rollback

Flag `disabled`.

### Risk

| Level | **HIGH** |
|-------|----------|
| If excluded | Modal banners and CTAs contradict projector; PC-04 |

---

## REM-05 — requirement_action_resolver after projector

### Current problem

`resolve_take_action_envelope` runs at enrich line ~631 **before** lifecycle, governance, and projector. CTA labels are derived from pre-projection state and may emit review-coupled copy (PC-17).

### Location

| Item | Value |
|------|-------|
| **File** | `backend/services/requirement_truth.py` |
| **Function** | `enrich_requirement_dict` — move call site |
| **File** | `backend/services/requirement_action_resolver.py` |
| **Function** | `resolve_take_action_envelope` |

### Proposed change

1. **Move** `resolve_take_action_envelope` + `enrich_take_action_envelope_for_client` to **after** projector (see INTEGRATION_MAP.md).
2. In `resolve_take_action_envelope`: when `customer_status_key` present, select CTA primary label from `CTA_POLICY_MATRIX.json` keyed on `(customer_status_key, customer_status_class)` instead of legacy stage.
3. Keep initial `action_type` / `infer_action_type` before projector if needed for non-CTA fields — only CTA envelope moves.
4. `apply_actionability_cta_override` remains after take_action for component-specific labels.

### Tests required

| Test | Assertion |
|------|-----------|
| `test_take_action_after_projector_ordering` | enrich payload has customer_status before take_action |
| `test_take_action_recorded_class_a` | recorded → "View submission" not "Review pending" |
| `test_take_action_under_review_class_b` | under_review → approved CTA from matrix |
| `test_take_action_escalation` | escalation_required → no review CTA |

### Rollback

Flag `disabled` — restore early take_action resolution (document ordering regression).

### Risk

| Level | **HIGH** |
|-------|----------|
| If excluded | Today/tasks CTAs pre-date canonical status; PC-17; D2 persists on backend surfaces |

---

## Remediation summary

| ID | Remediation | Risk if excluded | In S2 PR |
|----|-------------|-------------------|----------|
| REM-01 | enrich overwrite | CRITICAL | **Required** |
| REM-02 | legacy label emission | CRITICAL | **Required** |
| REM-03 | cognition alignment | HIGH | **Required** |
| REM-04 | banners/stage | HIGH | **Required** |
| REM-05 | take_action ordering | HIGH | **Required** |

**No exclusions permitted for production `active` promotion.**

Optional S2 partial: `audience_governance_v1` read-through (REM-06) — export buckets remain S4.
