# GO / NO-GO — S2 implementation

**Programme:** S2-CUSTOMER-STATUS-PROJECTOR-PLANNING-01  
**Date:** 2026-06-02

---

## Decision: **GO** for S2 **implementation planning complete** → **GO with conditions** to begin S2 **code**

---

## Rationale

| Criterion | Assessment |
|-----------|------------|
| PR-1A/1B prerequisites | Satisfied |
| Single projector architecture defined | Yes |
| Shadow mode before customer cutover | Yes |
| No data migration | Yes |
| Blast radius bounded to enrich path | Yes |
| Rollback via flag | Yes |
| Test strategy covers D1–D12 | Yes |

---

## Conditions before writing S2 code

1. **Approve** `CUSTOMER_STATUS_PROJECTOR_ARCHITECTURE.md` + mapping matrix (Product + Platform Architecture)
2. **Create** shadow fixture pack (12 families) in same PR as projector or immediately prior
3. **Confirm** feature flag host (`server_feature_flags` pattern) with ops
4. **Assign** S2 PR owner and QA staging window

---

## NO-GO triggers (do not start implementation)

| Trigger | Action |
|---------|--------|
| PR-1B vocabulary CI gate failing | Fix first |
| Attempt to change frontend in S2 PR | Reject — S3 scope |
| Attempt to add Mongo migration | Reject — policy violation |
| Skip shadow mode | Reject |
| Active flag without staging G1–G6 | Reject |

---

## S2 vs S3 boundary

| Phase | Customer-visible change |
|-------|-------------------------|
| S2 shadow | **No** |
| S2 active (API only, legacy FE) | **Partial** — API fields change; UI may still fallback until S3 |
| S3 | **Full** portal alignment |

---

## Recommendation summary

| Scope | Verdict |
|-------|---------|
| **S2 planning** | **GO** — complete |
| **S2 implementation start** | **GO with conditions** above |
| **S2 production active** | **NO-GO** until shadow acceptance |
