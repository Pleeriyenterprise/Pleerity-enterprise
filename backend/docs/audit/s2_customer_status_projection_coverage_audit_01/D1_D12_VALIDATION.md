# D1–D12 validation — projector outcomes

**Programme:** S2-CUSTOMER-STATUS-PROJECTION-COVERAGE-AUDIT-01  
**Source:** `p1_review_policy_signoff_01/CONSISTENCY_AUDIT.md`

---

## Validation matrix

| Case | Drift (current) | Deterministic projector outcome | Covered | S2 backend | Notes |
|------|-----------------|--------------------------------|---------|------------|-------|
| **D1** | Satisfied + Review pending subline | `customer_status_key=satisfied`, `customer_status_label=Satisfied`, subline without review vocabulary | **Yes** | Yes | REM-01/02/03 |
| **D2** | List CTA Review pending vs modal Submission recorded | `customer_status_key=recorded`, CTA=View submission per CTA_POLICY_MATRIX | **Yes** | Yes | REM-05 take_action after projector |
| **D3** | Platform verification pending / Awaiting platform review | Class B+queue → `under_review`; Class A → `recorded` | **Yes** | Yes | Gate emit_under_review |
| **D4** | Escalated for platform review + Review pending CTA | `escalation_required` + View submission CTA | **Yes** | Yes | Escalation precedence |
| **D5** | Awaiting review tier without queue | Class A → `recorded`; suppress under_review | **Yes** | Yes | AMB-06/07 |
| **D6** | Valid vs Verified | `verified` / label Verified | **Yes** | Yes | UNS-RES-06 |
| **D7** | Documents Awaiting verification vs requirement Review pending | Requirement: `under_review` (B+queue); doc row: Awaiting verification (retained constraint) | **Yes** | Partial | Doc row out of S2 projector scope — not a gap |
| **D8** | Export Awaiting review vs portal Recorded on file | Export buckets by `customer_status_class` — S4 | **Yes** | Deferred | Vocabulary supports; S4 implementation |
| **D9** | Cognition "not yet verified" vs modal Submission recorded | Class A `recorded` + subline "Recorded on file — not independently verified" (or vocabulary subline) | **Yes** | Yes | REM-03 |
| **D10** | Score recorded vs requirement Action required | Score widget independent; requirement projects `action_required` | **Yes** | N/A | Valid divergence — not projector defect |
| **D11** | presentationLanguage pending_review dual map | `customer_status_key` authoritative; FE retires map S3 | **Yes** | Partial | Backend supplies key; S3 consumes |
| **D12** | Assurance Awaiting platform review vs list Evidence on file | Class A smoke → `recorded`; assurance_tier SELF_RECORDED | **Yes** | Partial | FE assurance S3; backend class correct |

---

## Deterministic outcome detail

### D1 — Satisfied + Review pending

```json
{
  "customer_status_key": "satisfied",
  "customer_status_label": "Satisfied",
  "customer_status_subline": "Obligation met based on recorded evidence.",
  "customer_status_class": "A",
  "customer_status_overlay": null,
  "forbidden_in_subline": ["Review pending", "Awaiting review"]
}
```

### D3 — Platform verification pending (class B, queue proven)

```json
{
  "customer_status_key": "under_review",
  "customer_status_label": "Under review",
  "customer_status_subline": "Our team is verifying your uploaded certificate",
  "customer_status_class": "B"
}
```

### D3 variant — class A post-submit

```json
{
  "customer_status_key": "recorded",
  "customer_status_label": "Recorded on file",
  "customer_status_class": "A"
}
```

### D4 — Escalation

```json
{
  "customer_status_key": "escalation_required",
  "customer_status_label": "Escalation required",
  "customer_status_class": "A",
  "customer_status_overlay": "escalation_required"
}
```

### D9 — Class A cognition copy

```json
{
  "customer_status_key": "recorded",
  "customer_status_label": "Recorded on file",
  "customer_status_subline": "Self-recorded evidence on file — not independently verified by Pleerity.",
  "customer_status_class": "A"
}
```

*Subline exact wording from vocabulary subline table at implementation — must not use retired phrases.*

---

## S2 automated vs deferred

| Cases | S2 projector test | Deferred |
|-------|---------------------|----------|
| D1–D7, D9, D12 | Automated in `test_consistency_audit_regression.py` | — |
| D8 | — | S4 reports |
| D10 | Smoke only | Score widget |
| D11 | API key emission | S3 FE |

---

## Verdict

| Metric | Result |
|--------|--------|
| Cases with deterministic projector outcome | **12 / 12** |
| Cases requiring vocabulary change | **0** |
| Cases requiring projection logic only | **10** |
| Cases surface-scoped outside projector | **2** (D7 doc row, D10 score) |

**D1–D12 validation: PASS** for S2 backend projector scope.
