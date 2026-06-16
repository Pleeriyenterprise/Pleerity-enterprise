# S2 rollback strategy

**Programme:** S2-CUSTOMER-STATUS-PROJECTOR-PLANNING-01  
**Principle:** No data migration — rollback is configuration + code revert only

---

## 1. Rollback levels

| Level | Action | Recovery time | Data impact |
|-------|--------|---------------|-------------|
| **L1 — Flag rollback** | Set `customer_status_projector_v2` → `shadow` or `disabled` | Minutes | None |
| **L2 — Deploy revert** | Revert S2 release commit on server | 15–30 min | None |
| **L3 — Hotfix forward** | Patch projector gate bug; keep flag active | Hours | None |

**Preferred:** L1 for customer-visible issues after `active`.

---

## 2. L1 procedure

1. Set env / feature flag `customer_status_projector_v2=disabled` (or `shadow`)
2. Verify enrich responses return legacy `truth_presentation_*` only
3. Confirm divergence logging stops (if disabled)
4. Notify support — "status wording may match pre-release behaviour"
5. Post-mortem before re-activating

---

## 3. Observability preserved during rollback

| Signal | Keep running? |
|--------|---------------|
| Divergence logs | Optional off when disabled |
| Flag mode in admin explain | yes — shows disabled |
| `vocabulary_governance_ci_gate` | yes — unaffected |

---

## 4. What rollback does NOT do

- Does not revert Mongo evidence authority state
- Does not undo admin verify/reject actions
- Does not change queue membership
- Does not roll back PR-1A/1B vocabulary docs

---

## 5. Re-activation criteria

Same as `FEATURE_FLAG_STRATEGY.md` activation rules — must re-pass G1–G6 after fix.

---

## 6. Code revert scope (L2)

If flag mechanism insufficient, revert files:

- `customer_status_projector_v2.py` (delete)
- `requirement_truth.py` integration block
- `operational_cognition_service.py` consumer changes
- Flag registry entries

Legacy `derive_truth_presentation` remains in codebase — full behavioural restore.
