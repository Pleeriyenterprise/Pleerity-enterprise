# Design decision record: multi-gap task identity

| Field | Value |
|-------|--------|
| **ID** | DDR — multi-gap task identity |
| **Related** | PVG-001 (Unified Compliance Work Queue), `unified_tasks_service`, Stream C / D (remediation identity, CTAs) |
| **Status** | **Proposed — not implemented** |
| **Date** | 2026-05-02 |

This document records a **product/architecture decision point** only. It does **not** change runtime behaviour or introduce a new source of truth.

---

## 1. Problem statement

`fetch_client_priority_actions` can emit **multiple** priority-action rows for the **same** `related_requirement_id` when `infer_compliance_gaps_for_requirement` returns more than one gap (each row is produced via `gaps_to_priority_actions` and includes a distinct `gap_key`).

`get_unified_tasks_for_client` then builds unified tasks with:

- `task_id` = `requirement:{related_requirement_id}` for all requirement-shaped compliance actions (see `_stable_source_id`), **without** encoding gap identity in the id.
- A **`seen`** set that skips any subsequent task whose `id` was already appended.

**Result:** only **one** unified task per requirement survives for gap-backed compliance work, even when multiple gaps exist. Which gap “wins” depends on **iteration order** of the priority `actions` list, not on an explicit product rule surfaced to users.

---

## 2. Current behaviour

- **Priority stream:** One Mongo requirement row per `requirement_id` in the gap pass; **multiple gaps** → **multiple** action dicts extended onto `actions`.
- **Unified tasks:** For each action `a`, `t = _action_to_task(a, …)`; if `t["id"]` is already in `seen`, the task is **not** appended. `metadata.gap_key` is set from `a.get("gap_key")` when present on the **winning** row only (losers never appear in `tasks`).
- **UCWQ:** Read-only projection over `get_unified_tasks_for_client` only — it **inherits** the same single row per requirement for gap-backed compliance.

---

## 3. Why it matters for PVG-001

- PVG-001 and Stream C emphasise **stable remediation identity** (`remediation_key`, `gap_key` where applicable) and **no** `requirement_id`-only dedupe for user-visible queues.
- Today’s UCWQ correctly **does not** add requirement-only dedupe, but **upstream** collapse means tenants may still see **at most one** row per requirement from the unified pipeline, which can **under-represent** distinct gap kinds for the same obligation.
- Validation: **UCWQ does not incorrectly merge by requirement_id in its own layer**; the limitation is **unified task identity + dedupe** before the queue.

---

## 4. Affected systems

| System | Role |
|--------|------|
| **`unified_tasks_service`** | Defines `_stable_source_id`, `task_id`, and the `seen` dedupe loop in `get_unified_tasks_for_client`. |
| **`client_task_overrides`** | Persists snooze / dismiss / reviewed / done by **`task_id`** (`client_task_state_service`; `is_valid_task_id` regex: `^[a-z_]+:[A-Za-z0-9_-]{1,128}$`). Changing id format affects stored overrides and validation. |
| **Today (client inbox)** | Consumes unified tasks; overrides and visibility are keyed by `task_id`. |
| **Command Centre** | Uses the same unified / priority bundle patterns; same cardinality as Today for compliance rows. |
| **UCWQ** | Projection only; inherits unified list cardinality. |
| **Analytics / navigation logs** | Events and `recordTaskNavigationIntent`-style payloads reference `task_id` / unified task identity. |

---

## 5. Options

### A. Keep current collapse and document limitation

- Accept **one** unified task per requirement for gap-backed rows; document ordering / “first gap wins” for engineering and support.

### B. Change `task_id` for gap-backed rows to include a safe gap token

- Derive `source_id` from `(related_requirement_id, gap_kind)` or a **single-segment** encoding (e.g. hash) so `task_id` stays valid under `is_valid_task_id` **without** embedding raw `stable_gap_key` strings (which contain colons and break the current regex).

### C. Add separate `remediation_key` (or equivalent) while **preserving** `task_id`

- **Does not** increase row count in unified tasks by itself; useful for **correlation** and API DTOs but **does not** fix multiple visible rows if dedupe remains on unchanged `task_id`.

### D. UCWQ-specific alternate projection

- Assemble UCWQ from a **second** pass (e.g. re-call priority assembly or duplicate logic). **Conflicts** with PVG-001 rule “built only from `get_unified_tasks_for_client`” unless scope is explicitly relaxed; risks duplicate truth and drift.

---

## 6. Pros / cons

| Option | Pros | Cons |
|--------|------|------|
| **A — Keep + document** | No migration; Today/CC/UCWQ stay stable; no override invalidation. | Multi-gap reality hidden; may conflict with Stream C “no requirement-only dedupe” **intent** for user-visible lists. |
| **B — Safe gap token in `task_id`** | Multiple rows possible; aligns inbox identity with gap-level work; UCWQ inherits. | **Breaking** for stored overrides and analytics unless migrated; needs strict id contract and rollout; must preserve regex or update validation consistently. |
| **C — remediation_key only, same task_id** | Lower surface change for ids. | **Does not** surface multiple rows in unified/UCWQ; only metadata richness. |
| **D — UCWQ-only projection** | Could list gaps without touching Today. | Second pipeline / drift risk; violates current UCWQ authority boundary unless explicitly approved. |

---

## 7. Recommended approach (proposal)

1. **Short term (no code change):** Treat **Option A** as the **default** until product explicitly needs multi-row gap visibility — document the limitation in PVG-001 / runbooks and in support-facing notes.
2. **If** multi-gap rows are **required** in tenant UIs: prefer **Option B** with a **flagged rollout**, migration plan for `client_task_overrides`, and explicit sign-off on Today/CC behaviour — **not** Option D unless the product **explicitly** splits UCWQ from the unified read model (architecture tracker update would then be needed).

*This recommendation is **proposed** only; final authority is product + architecture.*

---

## 8. Migration / compatibility risks (if Option B or similar is implemented)

- **Overrides:** Existing documents keyed by `requirement:<uuid>` may no longer match new ids → snooze/dismiss appear “lost” or duplicated without migration or dual-key lookup.
- **Analytics:** Time series by old `task_id` break comparability.
- **Frontend:** Any hard-coded assumption of `requirement:` + UUID-only suffix.
- **Contract:** `is_valid_task_id` and max length (180 / 128 segment) must be satisfied for any new format.

---

## 9. Required tests if implemented

- **Unit:** Multiple mocked priority actions, same `related_requirement_id`, different `gap_key` → expected number of unified tasks and stable ids.
- **Override service:** `is_valid_task_id` for new ids; optional migration tests.
- **Integration:** Today sections, digest, Command Centre bundle, UCWQ API row count and `remediation_key` / `queue_item_id`.
- **Regression:** Snooze/dismiss round-trip, navigation intent logging.

---

## 10. Decision status

| | |
|--|--|
| **Status** | **Proposed — not implemented** |
| **Next** | Product/architecture review; link outcome back to `PRODUCT_VALUE_GAP_TRACKER.md` (PVG-001) when decided. |

---

## References (code)

- `services/unified_tasks_service.py` — `get_unified_tasks_for_client`, `_stable_source_id`, `_action_to_task`, `seen` dedupe.
- `services/client_priority_stream.py` — gap loop, `gaps_to_priority_actions`.
- `services/compliance_gap_engine.py` — `stable_gap_key`, `gaps_to_priority_actions`.
- `services/client_task_state_service.py` — `is_valid_task_id`, `_TASK_ID_RE`.
