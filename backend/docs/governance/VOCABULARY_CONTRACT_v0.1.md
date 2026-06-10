# Vocabulary Contract v0.1

**Status:** Ratified for S2-A codification  
**Module:** `backend/services/vocabulary_contract_v1.py`  
**Related:** `report_human_language_v1`, `reporting_semantics_v1`, `audience_governance_v1`, `trust_language_governance`

This contract governs **interpretation boundaries** across customer-facing surfaces. It does not alter scoring logic, satisfaction truth, or immutable export bytes.

---

## 1. Semantic axes

| Axis ID | Measures | Does NOT measure |
|---------|----------|------------------|
| `compliance_status` | Projected obligation state at generation boundary | Legal compliance |
| `evidence_confidence` | Evidence strength on file | Legal proof |
| `verification_maturity` | missing → recorded → review → verified | Legal satisfaction |
| `audit_readiness` | Operational external-review preparedness | Audit pass/fail |
| `operational_posture` | Dashboard directional indicator | Zero risk |
| `property_readiness` | Property-scoped unresolved burden | Portfolio audit-ready |
| `operational_exposure` | Overdue/missing/pending in scope | Litigation outcome |
| `risk_concentration` | Thematic exposure clustering | Legal merit |
| `monitoring_state` | Routine watch obligations | Verified compliance |
| `review_state` | Platform decision pending | Missing evidence |
| `temporal_confidence` | Recency/freshness (future) | Current status enum |

**Prohibited equivalences:** audit_readiness ≠ compliance_status; evidence_confidence ≠ compliance_status; operational_posture ≠ verification_maturity; property_readiness ≠ audit_readiness.

---

## 2. Authority hierarchy (§11)

| Tier | Label | Primary surfaces |
|------|-------|------------------|
| 1 | Evidentiary truth | Audit Evidence Pack, Audit Trail |
| 2 | Operational truth | Requirements Report, Evidence Readiness, live portal |
| 3 | Executive synthesis | Compliance Summary, Score Explanation |
| 4 | Directional intelligence | Monthly Digest |
| 5 | Directional indicator | Scheduled email, dashboard posture |

**Precedence:** Tier 1 wins evidentiary questions. Tier 2 wins action priority over Tier 3–5 calm language. Tier 4 movement ≠ absolute zero exposure.

---

## 3. Escalation ladders

### Posture (executive canonical)
Favourable posture → Attention advised → Elevated attention → Status under review

### Verification (strongest distinction)
Missing evidence → Recorded (not independently verified) → Awaiting platform review → Verified or accepted

### Property readiness
Strong → Adequate with review → Review recommended

---

## 4. Prohibited vocabulary

Blocked in customer-facing exports/emails/executive prose (enforced by `assert_semantic_safe_text`):

- fully compliant, legally compliant, risk free, audit-safe, regulator approved, guaranteed compliant, verified compliant, certified compliant, compliance guarantee, no risk, everything is fine

### Scoped terms (require boundary proximity when introduced)

- operationally compliant, favourable posture, audit-ready, compliance posture, verified or accepted

---

## 5. Cross-surface rules

1. No verification ladder inversion (recorded → verified collapse).
2. No raw score telemetry in customer text.
3. Requirements triage language must not leak into Compliance Summary executive prose.
4. Lower tiers may simplify higher tiers; never invert evidence hierarchy.
5. Registered posture variants (on track vs Favourable posture) are tracked in `POSTURE_SURFACE_VARIANTS` until S2-D convergence.

---

## 6. Report-class governance intensity

| Class | Intensity |
|-------|-----------|
| Audit Evidence Pack | very_high |
| Audit Trail | very_high |
| Evidence Readiness | high |
| Compliance Summary | moderate |
| Requirements Report | operational_first |
| Monthly Digest | lightest |
| Scheduled email | light |

---

## 7. Temporal confidence (§13 — placeholders only)

Ladder IDs: `current_at_boundary`, `valid_but_aging`, `renewal_approaching`, `stale_confidence`, `stale_and_risky`, `indeterminate`. No scoring behaviour in S2-A.

---

## 8. AI explanation governance (§12 — foundations only)

- AI must not issue legal verdicts or collapse verification axes.
- Grounding tuple (future): axis, tier, source_surface, generated_at.
- Verdict patterns: `vocabulary_contract_v1.ai_verdict_patterns()`.

---

## 9. Enforcement

- `assert_semantic_safe_text()` — prohibited phrases + telemetry leaks
- `find_semantic_drift()` — inventory + CI
- `scan_registered_customer_surfaces()` — cross-surface audit
- Tests: `test_vocabulary_contract_v1.py`, `test_cross_surface_semantic_parity.py`, `test_report_semantics_s1.py`

---

## 10. Ownership

| Concern | Owner module |
|---------|--------------|
| Enum → label | `report_human_language_v1` |
| Metric definitions | `reporting_semantics_v1` |
| Audience adaptation | `audience_governance_v1` |
| Contract rules & authority | `vocabulary_contract_v1` |

Changes to customer-facing labels must declare contract impact in PR review.
