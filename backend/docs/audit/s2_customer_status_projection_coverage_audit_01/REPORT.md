# S2 customer status projection coverage audit

**Programme:** S2-CUSTOMER-STATUS-PROJECTION-COVERAGE-AUDIT-01  
**Date:** 2026-06-02  
**Status:** AUDIT ONLY

---

## Objective

Verify the approved customer status model fully and deterministically represents every supported requirement state before S2 implementation.

---

## Verdict

| Metric | Result |
|--------|--------|
| **Platform coverage** | 100% (19/19 obligation-scoped states) |
| **12-family coverage** | 100% (71/71 family-state rows) |
| **Unsupported states** | 0 |
| **Unresolved ambiguities** | 0 (12 resolved via gates/precedence) |
| **D1–D12** | 12/12 deterministic projector outcomes |
| **Vocabulary change needed** | No |
| **Fallback language needed** | No |
| **Legacy truth_presentation needed** | No (shadow only) |

**GO WITH CONDITIONS** for S2 implementation — see `GO_NO_GO_RECOMMENDATION.md`.

---

## Deliverables

| # | Deliverable | File |
|---|-------------|------|
| 1 | Projection coverage matrix | `PROJECTION_COVERAGE_MATRIX.json` |
| 2 | Family-state matrix | `FAMILY_STATE_MATRIX.json` |
| 3 | Ambiguity inventory | `AMBIGUITY_INVENTORY.json` |
| 4 | Unsupported-state inventory | `UNSUPPORTED_STATE_INVENTORY.json` |
| 5 | Overlay validation | `OVERLAY_VALIDATION.md` |
| 6 | D1–D12 validation | `D1_D12_VALIDATION.md` |
| 7 | Projection completeness score | `PROJECTION_COMPLETENESS_SCORE.json` |
| 8 | Risk assessment | `RISK_ASSESSMENT.md` |
| 9 | GO / NO-GO | `GO_NO_GO_RECOMMENDATION.md` |

---

## Key findings

### Vocabulary is sufficient

All required customer-facing states map to the approved primary set:

- Action required, Submitted (transient), Recorded on file, Satisfied  
- Uploaded, Under review, Verified, Rejected  
- Follow-up required, Additional action required, Expiry date needed  
- Escalation required, Issue resolved  

### Legacy labels normalize — not gaps

| Legacy | Approved projection |
|--------|---------------------|
| Supporting evidence uploaded | Action required + subline |
| Evidence recorded / Assessment recorded | Recorded on file (badge); modal headline from supporting_phrases |
| Platform verification pending | Under review (B+queue) or Recorded on file (A) |
| Escalated for platform review | Escalation required |
| Valid | Verified |
| Follow-up evidence required | Follow-up required |

### Critical gates (must implement in S2)

1. **Class A + no queue** → never `under_review` (D5, AMB-06)  
2. **Class B + no queue** → `uploaded` not `under_review` (AMB-07)  
3. **Escalation** supersedes under_review (I5, D4)  
4. **followup_required** supersedes satisfied display when follow-up open (AMB-05)  

### Surface-scoped items (not vocabulary gaps)

- **D7** — Documents page "Awaiting verification" (document-scoped; retained per vocabulary constraints)  
- **D8** — Report aggregates (S4)  
- **D10** — Score vs obligation (valid divergence)  
- **D11** — FE filter map (S3)  

---

## Completeness score

```json
{
  "platform_states_covered": 19,
  "platform_states_unsupported": 0,
  "family_state_rows_covered": 71,
  "d12_deterministic": 12,
  "verdict": "COMPLETE"
}
```

Full detail: `PROJECTION_COMPLETENESS_SCORE.json`

---

## Related artefacts

- `docs/governance/CUSTOMER_STATUS_VOCABULARY.json`
- `p1_status_semantics_signoff_01/FAMILY_LIFECYCLE_MATRIX.json`
- `p1_status_semantics_signoff_01/SEMANTIC_CONTRACT.md`
- `s2_customer_status_projector_implementation_plan_01/`
