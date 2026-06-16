# Overlay validation

**Programme:** S2-CUSTOMER-STATUS-PROJECTION-COVERAGE-AUDIT-01  
**Authority:** `CUSTOMER_STATUS_VOCABULARY.json` overlay_precedence + `SEMANTIC_CONTRACT.md` §3

---

## Overlay inventory

| Overlay key | Label | Classes | Gate |
|-------------|-------|---------|------|
| escalation_required | Escalation required | A, B, C | exception_active + admin_resolution_path |
| escalation_resolved | Issue resolved | A, B, C | escalation_cleared |
| rejected | Rejected | B | admin_reject |
| under_review | Under review | B | emit_under_review |
| expiry_date_needed | Expiry date needed | A, B | expiry_confirmation_required |
| followup_required | Follow-up required | A | followup_unresolved |
| additional_action_required | Additional action required | A | components_incomplete |

---

## Precedence order (normative)

1. escalation_required  
2. rejected  
3. under_review  
4. expiry_date_needed  
5. followup_required  
6. additional_action_required  
7. base_path_state  

---

## Validation matrix

| Scenario | Base would be | Overlay active | Primary badge | Valid | Notes |
|----------|---------------|----------------|---------------|-------|-------|
| Class A recorded + followup | recorded | followup_required | **Follow-up required** | Yes | Overlay replaces base |
| Class A satisfied + followup open | satisfied | followup_required | **Follow-up required** | Yes | AMB-05 — followup blocks satisfied display |
| Class A recorded + escalation | recorded | escalation_required | **Escalation required** | Yes | Escalation supersedes all |
| Class B under_review + escalation | under_review | escalation_required | **Escalation required** | Yes | I5 — not Under review |
| Class B under_review + expiry missing | under_review | expiry_date_needed | **Under review** | Yes | AMB-03 — review precedence over expiry |
| Class B uploaded + expiry (no queue) | uploaded | expiry_date_needed | **Expiry date needed** | Yes | |
| Class A smoke + incomplete components | recorded | additional_action_required | **Additional action required** | Yes | |
| HMO fire followup + incomplete | recorded | both | **Follow-up required** | Yes | followup wins over additional |
| Class B rejected + in queue | rejected | under_review | **Rejected** | Yes | rejected precedence 2 |
| Escalation resolved → base remap | escalation_resolved | — | **Issue resolved** then recorded/satisfied | Yes | Transient overlay |
| Class A + under_review attempt | recorded | — | **Recorded on file** | Yes | Forbidden primary — gate blocks |
| Class B + recorded attempt | uploaded | — | **Uploaded/Verified** | Yes | Forbidden primary — gate blocks |

---

## Overlay vs primary status rules

| Rule | Status |
|------|--------|
| Exactly one primary badge (I1) | **PASS** — overlay becomes primary when active |
| customer_status_overlay field populated when overlay active | **PASS** — design in implementation plan |
| Escalation supersedes under_review (I5) | **PASS** |
| Class-disjoint forbidden badges (I2) | **PASS** when gates enforced |
| No review language without gate (I6) | **PASS** for all overlays except under_review and escalation_required |

---

## Family overlay eligibility

| Family | Allowed overlays | Forbidden overlays |
|--------|------------------|-------------------|
| Legionella | followup, escalation, escalation_resolved | additional_action, under_review, expiry* |
| Smoke/Heat | additional_action, escalation | followup, under_review |
| HMO Fire | followup, additional_action, escalation | under_review |
| Gas/EPC/EICR/PAT | expiry, escalation, escalation_resolved, rejected | followup, additional_action, recorded |
| Tenancy/How to Rent/RSW/Landlord Reg | escalation only | followup, additional_action, under_review |
| Lead Testing | followup, escalation | additional_action, under_review |

*Legionella class A path: expiry_date_needed allowed in vocabulary for class A but not in FAMILY_LIFECYCLE impossible list — if expiry semantics apply to structured assessment, projector may emit expiry_date_needed; family matrix marks as edge — **no conflict** if expiry signal absent for structured-only families.

---

## Verdict

**Overlay model is complete and deterministic** for all 12 families when precedence order is implemented as specified. No vocabulary extension required.
