# S2 test strategy

**Programme:** S2-CUSTOMER-STATUS-PROJECTOR-PLANNING-01

---

## 1. Test layers

| Layer | Purpose | Location (proposed) |
|-------|---------|---------------------|
| **Unit** | Gate logic per class A/B/C | `test_customer_status_projector_v2.py` |
| **Parity** | Projector output ⊆ vocabulary JSON | `test_customer_status_projector_vocabulary.py` |
| **Shadow** | Legacy vs projector fixture pairs | `test_customer_status_projector_shadow.py` |
| **Divergence** | CONSISTENCY_AUDIT D1–D12 regression | `test_consistency_audit_regression.py` |
| **Integration** | Full enrich_requirement_dict payload | `test_requirement_truth_customer_status.py` |
| **Regression** | Known defect families | `test_evidence_authority_convergence_fix_01.py` (extend) |

---

## 2. Unit test matrix (gates)

| Test case | Class | Input signals | Expected key |
|-----------|-------|---------------|--------------|
| A_post_submit_no_queue | A | has_submission, SELF_CERT | `recorded` |
| A_never_under_review | A | PENDING_REVIEW lifecycle, no queue | `recorded` not `under_review` |
| B_queue_proven | B | UPLOADED + in_queue | `under_review` |
| B_uploaded_pre_queue | B | UPLOADED, not in_queue | `uploaded` |
| B_verified | B | EA_VERIFIED | `verified` |
| B_rejected | B | admin reject | `rejected` |
| C_escalation_supersedes_review | B+C | queue + escalation | `escalation_required` |
| overlay_expiry_blocks_base | B | expiry gate | `expiry_date_needed` |
| overlay_followup_legionella | A-opt | followup open | `followup_required` |
| forbid_retired_phrases | all | any | label ∉ RETIRED_REVIEW_PHRASES |

---

## 3. Shadow tests

```python
# Pattern: fixture row → legacy attach → projector → assert divergence logged
assert compare(legacy, projector).divergence_type == "label_mismatch"
assert projector.customer_status_label == "Recorded on file"
assert legacy.truth_presentation_label == "Platform verification pending"
```

**Fixtures:** Extend `tests/fixtures/` from `p1_status_semantics_signoff_01/FAMILY_LIFECYCLE_MATRIX.json` — min 12 families.

---

## 4. Previously observed defects — regression targets

| Defect | Test assertion |
|--------|----------------|
| **Legionella contradictions** | Satisfied badge cannot pair with follow-up-required overlay without correct precedence |
| **Smoke duplicate CTA** | take_action primary unchanged; status does not imply duplicate upload path |
| **Review pending drift** | Class A row: `customer_status_label` never matches retired review phrases |
| **Uploaded not verified drift** | Class B without queue → `uploaded` not `under_review` |
| **Verified evidence routing** | `verified` key → cognition "No further evidence required"; not "Add compliance evidence" |
| **D1 Satisfied + Review pending** | Projector subline has no "review pending" |
| **D6 Valid vs Verified** | Label is `Verified` not `Valid` |

---

## 5. Files requiring updates (from impact audit)

| File | Change |
|------|--------|
| `test_cer_governance_presentation.py` | Shadow fixtures; legacy preserved |
| `test_operational_cognition_service.py` | Cognition reads customer_status_* |
| `test_cer_actionability_presentation.py` | Banner queue-gated |
| `test_client_requirement_lifecycle.py` | Lifecycle input-only |
| `test_requirement_attention_eligibility.py` | Class A review_pending suppressed |
| `test_evidence_authority_convergence_fix_01.py` | Projector integration |
| `test_customer_status_vocabulary.py` | Unchanged — still required in CI |

---

## 6. CI gates (S2 PR)

| Gate | Command |
|------|---------|
| Vocabulary parity | `pytest test_customer_status_vocabulary.py` |
| Projector unit + shadow | `pytest test_customer_status_projector_v2.py` |
| Governance lint | `vocabulary_governance_ci_gate.py` |
| Full backend | existing `backend-tests.yml` |

---

## 7. Staging validation (manual QA)

- CONSISTENCY_AUDIT D1–D12 checklist on staging with `flag=shadow` then `active`
- 12-family spot check per `FAMILY_LIFECYCLE_MATRIX.json`
- Admin explain API shows projector debug fields

---

## 8. Out of scope (S2 tests)

- Frontend component tests (S3)
- PDF snapshot tests (S4)
- E2E Playwright (optional S3 UAT)
