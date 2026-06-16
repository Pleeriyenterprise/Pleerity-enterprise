# Feature flag strategy (design only)

**Programme:** S2-CUSTOMER-STATUS-PROJECTOR-PLANNING-01  
**Flag name:** `customer_status_projector_v2`  
**Status:** DESIGN ONLY — do not implement in planning phase

---

## 1. States

| State | API behaviour | Customer impact |
|-------|---------------|-----------------|
| `disabled` | Legacy `derive_truth_presentation` only; projector not run | None (pre-S2) |
| `shadow` | Projector runs + divergence logged; API emits legacy fields | None |
| `active` | API emits `customer_status_*`; legacy fields mirrored one release | **Yes** — labels change on enrich surfaces |

---

## 2. Configuration surface

| Layer | Mechanism (proposed) |
|-------|---------------------|
| Server default | `server_feature_flags` / env `CUSTOMER_STATUS_PROJECTOR_V2_MODE` |
| Per-tenant override | Admin pilot flag (optional) — staging tenants first |
| Emergency kill | `disabled` via env without redeploy (if flag registry supports) |

---

## 3. Activation rules

1. PR-1A + PR-1B merged and vocabulary CI gate green
2. S2 code merged to `develop`
3. Staging deploy → `shadow` for ≥5 business days
4. G1–G6 shadow acceptance met (see `SHADOW_MODE_STRATEGY.md`)
5. Production deploy → `shadow` for ≥7 days
6. Product + Platform Architecture written approval
7. Production → `active` during low-traffic window
8. Monitor 48h — rollback trigger ready

**Per-tenant activation (optional):** Pilot cohort only before fleet-wide active.

---

## 4. Rollback rules

| Trigger | Action |
|---------|--------|
| Error rate spike on enrich endpoints | `active` → `shadow` immediately |
| Customer-reported badge contradiction | `active` → `shadow`; investigate |
| P0 modal/list crash | `disabled` if enrich regression (unlikely — additive fields) |
| Shadow divergence regression after active | `active` → `shadow` |

Rollback is **flag flip only** — no data migration.

---

## 5. Observability requirements

| Signal | Required |
|--------|----------|
| Divergence log volume | yes |
| Flag mode in enrich debug header (admin explain API) | yes |
| `customer_status_projector_version` in payload | yes |
| Alert on `retired_phrase_in_projector` > 0 | yes |
| Dashboard: divergence_rate by requirement_code | yes |

---

## 6. Relationship to other flags

| Flag | Interaction |
|------|-------------|
| `evidence_review_v2_enabled` | Queue membership input — do not conflate |
| `customer_status_projector_v2` | Independent — presentation only |

---

## 7. Implementation note

Flag wiring is **S2 task 2.9** per `RECOMMENDED_S1_S5_EXECUTION_PLAN.md` — implement in same PR as projector, default `shadow` on staging.
