# Risk assessment — S2 implementation

**Programme:** S2-CUSTOMER-STATUS-PROJECTOR-IMPLEMENTATION-PLAN-01  
**Date:** 2026-06-02

---

## Risk register

| ID | Risk | Likelihood | Impact | Mitigation | Owner |
|----|------|------------|--------|------------|-------|
| R-01 | PS-02 remains authority when active | Medium | Critical | REM-02; flag gating; G2 | Engineering |
| R-02 | enrich overwrite masks projector | Medium | Critical | REM-01 | Engineering |
| R-03 | take_action pre-dates projector | High | High | REM-05 reorder | Engineering |
| R-04 | Cognition emits retired phrases | High | High | REM-03 | Engineering |
| R-05 | FE fallbacks hide API changes | High | Medium | Accepted until S3; shadow populates fields | Product |
| R-06 | Active promoted without shadow soak | Low | Critical | G1–G6 gates; rollout plan | Ops/Product |
| R-07 | Enrich latency regression | Medium | Medium | G4; projector pure function | Engineering |
| R-08 | Report/email drift continues | High | Low | Deferred S4 — documented | Product |
| R-09 | Vocabulary drift vs projector | Low | High | Parity tests; import-only vocabulary | Engineering |
| R-10 | Partial remediation merge | Medium | Critical | PR checklist — all 5 REM required | Engineering |
| R-11 | class A review leak via lifecycle PENDING_REVIEW | Medium | High | Gate logic U-02; G2 metric | Engineering |
| R-12 | Queue gate false negative → no under_review when needed | Low | High | PS-10 input tests; gas fixture | Engineering |
| R-13 | Invariant violation in prod | Low | High | Fail closed to action_required + alert | Engineering |
| R-14 | Shadow log PII leak | Low | High | Log safety spec in SHADOW_COMPARISON_DESIGN | Engineering |

---

## Remediation exclusion risks

| If excluded | Risk level | Consequence |
|-------------|------------|-------------|
| REM-01 | **CRITICAL** | Second authority; projector decorative |
| REM-02 | **CRITICAL** | Retired phrases continue on API |
| REM-03 | **HIGH** | Today/CC contradict badge |
| REM-04 | **HIGH** | Banners/CTAs contradict badge |
| REM-05 | **HIGH** | Task CTAs pre-canonical status |

**No exclusions permitted for production active.**

---

## Blast radius

| Surface | S2 shadow | S2 active |
|---------|-----------|-----------|
| Enrich API | Additive fields only | Label semantics change on legacy fields (mirrored) |
| Frontend | None | Partial — FE still uses fallbacks |
| Reports | None | None |
| Emails | None | None |
| Mongo | None | None |
| Scoring | None | None |

**Bounded to enrich path** — confirmed.

---

## Rollback confidence

| Item | Assessment |
|------|------------|
| Flag flip rollback | **High** — no data migration |
| Code revert | **Medium** — prefer shadow over revert |
| Customer data corruption risk | **None** |

---

## Dependency risks

| Dependency | Status |
|------------|--------|
| PR-1A vocabulary | Satisfied |
| PR-1B CI gate | Satisfied |
| 12-family fixtures | Pending implementation |
| Ops env var access | Required for rollout |

---

## Overall risk posture

| Phase | Posture |
|-------|---------|
| S2 implementation start | **Acceptable** with conditions |
| S2 staging shadow | **Low** customer risk |
| S2 production active | **Medium** — requires G1–G6 + REM verification |

---

## Open items

1. Subline templates — confirm all exist in vocabulary mirror or add to `customer_status_vocabulary.py` during S2 (not hardcoded in projector).
2. Per-tenant pilot flag — optional; env-only sufficient for initial release.
3. `CTA_POLICY_MATRIX.json` — confirm exists or create as S2 task keyed on customer_status_key.
