# Test plan — S2 customer status projector

**Programme:** S2-CUSTOMER-STATUS-PROJECTOR-IMPLEMENTATION-PLAN-01  
**Extends:** `s2_customer_status_projector_planning_01/S2_TEST_STRATEGY.md`

---

## 1. Projector unit tests

**File:** `backend/tests/test_customer_status_projector_v2.py`

| Test ID | Class | Input | Expected key |
|---------|-------|-------|--------------|
| U-01 | A | has_submission, SELF_CERT, no queue | `recorded` |
| U-02 | A | PENDING_REVIEW lifecycle, no queue | `recorded` (not `under_review`) |
| U-03 | B | UPLOADED + in_queue | `under_review` |
| U-04 | B | UPLOADED, not in_queue | `uploaded` |
| U-05 | B | EA_VERIFIED | `verified` |
| U-06 | B | admin reject | `rejected` |
| U-07 | B+C | queue + escalation | `escalation_required` |
| U-08 | B | expiry gate | `expiry_date_needed` |
| U-09 | A-opt | legionella followup open | `followup_required` |
| U-10 | A | smoke components incomplete | `additional_action_required` |
| U-11 | all | any output | label ∉ RETIRED_REVIEW_PHRASES |
| U-12 | A | any | key ∉ CLASS_A_FORBIDDEN |
| U-13 | B | any | key ∉ CLASS_B_FORBIDDEN |

---

## 2. Vocabulary parity tests

**File:** `backend/tests/test_customer_status_projector_vocabulary.py`

| Test | Assertion |
|------|-----------|
| V-01 | Every emitted key ∈ CUSTOMER_STATUS_KEYS |
| V-02 | Every emitted label == CUSTOMER_STATUS_LABEL_BY_KEY[key] |
| V-03 | vocabulary_version matches governance JSON |
| V-04 | Overlay keys ⊆ OVERLAY_PRECEDENCE |

---

## 3. Enrich integration tests

**File:** `backend/tests/test_requirement_truth_customer_status.py`

| Test ID | Flag mode | Assertion |
|---------|-----------|-----------|
| I-01 | disabled | No customer_status_* fields |
| I-02 | shadow | customer_status_* present; truth_presentation_label legacy |
| I-03 | active | customer_status_* authoritative; legacy mirrored |
| I-04 | active | client_lifecycle_label == customer_status_label |
| I-05 | all | enrich does not throw on missing optional inputs |
| I-06 | active | take_action resolved after customer_status_* |
| I-07 | active | operational_cognition uses customer_status_label |

---

## 4. Shadow-mode tests

**File:** `backend/tests/test_customer_status_projector_shadow.py`

| Test ID | Scenario | Assertion |
|---------|----------|-----------|
| S-01 | legionella recorded fixture | divergence logged; projector=Recorded on file |
| S-02 | gas queue fixture | expected_normalization from Platform verification pending |
| S-03 | class A no queue | review_without_gate if legacy has review phrase |
| S-04 | escalation fixture | escalation_normalization |
| S-05 | no mismatch | divergence_type null or not emitted |

Pattern:

```python
legacy = attach_cer_governance_presentation(row)
projected = project_customer_status(row)
result = compare_legacy_vs_projector(row, legacy, projected)
assert result.divergence_type == "expected_normalization"
```

---

## 5. Feature flag tests

**File:** `backend/tests/test_customer_status_projector_config.py` (or section in integration file)

| Test | Assertion |
|------|-----------|
| F-01 | unset env → disabled |
| F-02 | CUSTOMER_STATUS_PROJECTOR_V2_MODE=shadow → shadow |
| F-03 | invalid env → disabled + warning |
| F-04 | client bootstrap exposes mode |

---

## 6. Five backend remediation tests

| Remediation | Test file | Test IDs |
|-------------|-----------|----------|
| REM-01 | test_requirement_truth_customer_status.py | I-04, I-03 |
| REM-02 | test_cer_governance_presentation.py | G-01 shadow legacy, G-02 active skip |
| REM-03 | test_operational_cognition_service.py | C-01..C-04 |
| REM-04 | test_cer_actionability_presentation.py | B-01..B-04 |
| REM-05 | test_requirement_truth_customer_status.py | I-06 + test_take_action_policy.py |

---

## 7. D1–D12 consistency tests

**File:** `backend/tests/test_consistency_audit_regression.py`

| Case | Test | Pass criterion |
|------|------|----------------|
| D1 | satisfied_no_review_subline | subline has no Review pending |
| D2 | recorded_cta_not_review_pending | take_action ≠ Review pending |
| D3 | class_b_under_review_or_a_recorded | no Platform verification pending |
| D4 | escalation_not_review | Escalation required |
| D5 | no_phantom_tier_review | class A + no queue → not under_review |
| D6 | verified_not_valid | label == Verified |
| D7 | doc_vs_req scoping | requirement under_review only class B+queue |
| D8 | export deferred | skip in S2 — mark xfail until S4 |
| D9 | cognition_recorded_not_verified | class A copy |
| D10 | score_vs_obligation | score widget unchanged — smoke only |
| D11 | no presentationLanguage | FE deferred — skip S2 |
| D12 | smoke_assurance_recorded | class A recorded |

S2 automated scope: **D1–D7, D9, D12** (backend). D8, D10–D11 manual/deferred.

---

## 8. Regression tests (known defects)

**Extend:** `test_evidence_authority_convergence_fix_01.py`

| Defect | Assertion |
|--------|-----------|
| Legionella contradictions | overlay precedence correct |
| Smoke duplicate CTA | take_action stable |
| Class A review pending leak | customer_status_label clean |
| Uploaded not verified | uploaded vs under_review |
| Verified routing | cognition "No further evidence required" |

---

## 9. CI gates (S2 PR)

| Gate | Command |
|------|---------|
| Vocabulary parity | `pytest backend/tests/test_customer_status_vocabulary.py` |
| Projector + shadow | `pytest backend/tests/test_customer_status_projector_v2.py backend/tests/test_customer_status_projector_shadow.py` |
| Integration | `pytest backend/tests/test_requirement_truth_customer_status.py` |
| Remediation | `pytest backend/tests/test_operational_cognition_service.py backend/tests/test_cer_actionability_presentation.py` |
| Governance lint | `python backend/scripts/vocabulary_governance_ci_gate.py` |
| Full suite | `.github/workflows/backend-tests.yml` |

---

## 10. Staging manual QA

- [ ] 12-family spot check per FIXTURE_PACK_PLAN.json
- [ ] Admin explain shows projector debug
- [ ] flag=shadow: API identical to pre-S2 on truth_presentation_label
- [ ] flag=active on staging pilot only: API customer_status_* correct
- [ ] CONSISTENCY_AUDIT D1–D12 checklist

---

## Out of scope (S2)

- Frontend component tests (S3)
- PDF snapshot tests (S4)
- E2E Playwright
- Mongo integration tests
