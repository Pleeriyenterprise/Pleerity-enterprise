# Rollout plan — S2 customer status projector

**Programme:** S2-CUSTOMER-STATUS-PROJECTOR-IMPLEMENTATION-PLAN-01

---

## Phase diagram

```
Local dev → CI → Staging disabled → Staging shadow → [G1–G6] → Production shadow → [G1–G6 prod] → Staging active pilot → Production active
                                                                                                                              ↑
                                                                                              NOT RECOMMENDED until shadow acceptance
```

---

## 1. Local implementation

| Step | Action |
|------|--------|
| L-1 | Implement projector module + config + shadow |
| L-2 | Wire enrich integration + 5 remediations |
| L-3 | `CUSTOMER_STATUS_PROJECTOR_V2_MODE=shadow` locally |
| L-4 | Run fixture pack + full pytest |
| L-5 | Manual spot-check enrich JSON for 2–3 families |

**Default local:** `disabled` until developer opts in.

---

## 2. CI

| Step | Action |
|------|--------|
| CI-1 | Merge S2 PR to develop |
| CI-2 | CI runs with `CUSTOMER_STATUS_PROJECTOR_V2_MODE=shadow` |
| CI-3 | vocabulary_governance_ci_gate.py must pass |
| CI-4 | All new tests green |

---

## 3. Staging — disabled mode

| Step | Action | Duration |
|------|--------|----------|
| ST-D1 | Deploy S2 build | Day 0 |
| ST-D2 | `CUSTOMER_STATUS_PROJECTOR_V2_MODE=disabled` | 24h |
| ST-D3 | Smoke enrich endpoints — identical to pre-S2 | 24h |
| ST-D4 | Verify no latency regression | 24h |

**Gate:** Zero enrich errors vs baseline.

---

## 4. Staging — shadow mode

| Step | Action | Duration |
|------|--------|----------|
| ST-S1 | Set `shadow` | Day 1 |
| ST-S2 | 100% divergence logging | ≥5 business days |
| ST-S3 | Run 12-family fixture cohort manually | Within soak |
| ST-S4 | Admin explain projector debug | Within soak |
| ST-S5 | Measure G1, G2, G4, G5 | End of soak |

**Gate:** G1–G2, G4–G5 pass on staging.

---

## 5. Staging — active mode (pilot only)

| Step | Action | Notes |
|------|--------|-------|
| ST-A1 | Set `active` on **pilot tenant only** OR full staging if no per-tenant flag | Requires G1–G6 staging |
| ST-A2 | Verify customer_status_* authoritative | |
| ST-A3 | Verify legacy mirror matches projector | |
| ST-A4 | FE still on legacy reads — document expected partial drift | |
| ST-A5 | Product sign-off G6 | |

**Do not proceed to production active without ST-A success.**

---

## 6. Production — disabled mode

| Step | Action |
|------|--------|
| PR-D1 | Deploy S2 release to production |
| PR-D2 | `CUSTOMER_STATUS_PROJECTOR_V2_MODE=disabled` |
| PR-D3 | 24h soak — zero customer impact |

---

## 7. Production — shadow mode

| Step | Action | Duration |
|------|--------|----------|
| PR-S1 | Set `shadow` | Day 0 |
| PR-S2 | 100% divergence logging 72h → 10% sample | ≥7 calendar days |
| PR-S3 | Monitor G2, G3, G4 | Continuous |
| PR-S4 | Shadow report to Product | End of soak |

---

## 8. Active promotion gate

**Do not recommend production `active` until:**

| Gate | Requirement |
|------|-------------|
| G1 | D1–D12 = 0 staging cohort |
| G2 | class_a_review_leaks = 0 for 7 days |
| G3 | divergence_rate < 2% production shadow |
| G4 | enrich p95 ≤ +15% |
| G5 | CI green |
| G6 | Product written sign-off |
| REM | All 5 backend remediations verified on staging active pilot |

### Production active (when approved)

| Step | Action |
|------|--------|
| PR-A1 | Low-traffic window |
| PR-A2 | `active` fleet-wide OR pilot cohort first |
| PR-A3 | Monitor 48h — rollback trigger ready |
| PR-A4 | Open S3 frontend migration track |

### Rollback triggers

- Enrich error rate > baseline + threshold
- Customer badge contradiction P0
- retired_phrase_in_projector > 0
- Product hold

**Rollback action:** `active` → `shadow` → `disabled` as needed.

---

## Environment summary

| Environment | Initial | After soak | Customer impact |
|-------------|---------|------------|-----------------|
| Local | disabled | shadow | Dev only |
| CI | shadow | shadow | None |
| Staging | disabled → shadow | active pilot | None until active pilot |
| Production | disabled → shadow | **active only after gates** | shadow=none; active=API semantic change |

---

## S3/S4/S5 triggers

| Phase | Trigger |
|-------|---------|
| S3 | S2 active stable on staging ≥1 week |
| S4 | S3 portal alignment complete |
| S5 | S4 reports/emails complete |
