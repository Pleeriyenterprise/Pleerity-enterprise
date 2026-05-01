# Stream F — Reconstruction consistency (read-only)

**Purpose:** Tell support and engineering **in what order** to trust stores when rebuilding a story, which joins are **strong** vs **weak**, and when **timeline ordering misleads** — aligned with existing Mongo + `audit_logs` reality (no single timeline collection).

**Companion:** `STREAM_F_FORENSICS_JOIN_RECIPE.md` (query recipes), `STREAM_F_PHASE2_CORRELATION_PROPAGATION.md` (where `correlation_id` lives), `STREAM_C_REMEDIATION_CORRELATION_RUNBOOK.md` (remediation identity), `STREAM_E_MUTATION_FANOUT_MATRIX.md` (Sync vs Enq).

---

## 1. Authoritative reconstruction order

Use **this order** when building a narrative (not necessarily timestamp order):

1. **Applicability truth (operator)** — `applicability_resolution_audit` (append-only) when the story involves override / UNKNOWN / HIUA.
2. **Obligation row** — `requirements` at end of incident window (materialised truth for portal).
3. **Gaps** — `compliance_gaps` by `requirement_id` / `gap_key`; interpret **quiet sync** per join recipe §6.
4. **Evidence** — `documents` + requirement authority fields after document times.
5. **Score persistence** — `properties.compliance_score` + latest **`property_compliance_score_history`** for headline proof.
6. **Score explainability** — `score_ledger_events` (user-facing drivers; **`correlation_id`** when present).
7. **Score deltas** — `score_change_log` for `changed_requirements` (map **`requirement_key`** → `requirement_id` carefully); optional **`correlation_id`** on new rows when `recalculate_and_persist` context supplied it (**F2-A**), same as **`property_compliance_score_history`**.
8. **Audits** — `audit_logs` for actions not fully mirrored in domain collections (`COMPLIANCE_SCORE_UPDATED`, `REQUIREMENT_ACTION_TRIGGERED`, document lifecycle).

**Why not strict timestamp order?** Enqueue-only recalcs, double recalc windows, and quiet gap writes reorder **observable** timestamps vs **causal** intent (matrix + propagation doc).

---

## 2. Trusted joins (strong)

| From | To | Key |
|------|-----|-----|
| `compliance_recalc_queue.correlation_id` | Same value in `COMPLIANCE_SCORE_UPDATED.metadata.correlation_id` and often `score_ledger_events.correlation_id` | Exact string match + `property_id` + time window |
| Outcome `compliance_activity_log.correlation_id` | Same id in synchronous `COMPLIANCE_SCORE_UPDATED` / `score_ledger_events` for that `apply_action_outcome` call | Match `dedupe_key` or printed `correlation_id` on activity row (**F2-B**) |
| `gap_key` | `compliance_gaps` row; `maintenance_issues.operational_root_key` when bridged | Equality |
| `REQUIREMENT_UPDATED:{requirement_id}` | `patch_requirement` audit + enqueue kwargs (tests) | String prefix |
| `TENANT_DELIVERY:{delivery_id}` | Tenant delivery enqueue + downstream score audit/ledger | String prefix |
| `ADMIN_VALIDATOR_REPAIR:{property_id}:{suffix}` | Mismatch / recalc / repaired audit chain | Shared suffix in metadata |
| `property_compliance_score_history.correlation_id` / `score_change_log.correlation_id` | `COMPLIANCE_SCORE_UPDATED.metadata.correlation_id` / `score_ledger_events.correlation_id` | Exact string match + `property_id` when field present on row (**F2-A** + caller context) |

---

## 3. Weak joins (use time + entity scope)

| From | To | Risk |
|------|-----|------|
| `score_change_log.created_at` | `audit_logs` `COMPLIANCE_SCORE_UPDATED` | Rows **without** `correlation_id` (legacy or caller omitted id): match `reason`, score pair, property |
| `property_compliance_score_history` | Document audits | Queue lag — history may appear **after** document audit |
| Gap resolve audit (`resource_id=requirement_id`) | Individual gap row transitions | Bulk resolve metadata lists many `gap_key`s — not 1:1 timeline |
| Outcome-driven `recalculate_and_persist` | Prior WO/document correlation | Resolved **`correlation_id`** in context (**F2-B**); history/change_log carry it when non-empty (**F2-A**) — still validate with activity row / ledger |

---

## 4. Eventual consistency & async delay

- **`enqueue_compliance_recalc`:** Property flagged pending; worker batch processes later — expect **seconds to minutes** unless infra says otherwise.
- **Risk regen** scheduled after enqueue — risk rows may move **after** score persistence.
- **Double scoring:** Matrix notes paths that sync recalc **and** enqueue — expect **two** history rows close in time; **last** headline + ledger alignment wins for “current”.

---

## 5. When support should distrust naive timeline ordering

- **Quiet gap sync** — gap `updated_at` moves without `COMPLIANCE_GAP_*` audit; **do not** infer “no gap activity” from audit silence.
- **Enqueue-only** — document `DOCUMENT_*` audit timestamp **before** `COMPLIANCE_SCORE_UPDATED` — normal; use matrix row to confirm Enq path.
- **Inbox** — `client_task_*` timestamps do **not** order compliance closure (`STREAM_C` runbook).
- **Risk dismiss** before gap resolve — parallel lenses; timeline order is **not** causality.
- **Retention** — missing audits may be policy-bound; absence is **not** proof of non-occurrence.

---

## 6. Escalation

Use **`STREAM_F_FORENSICS_JOIN_RECIPE.md` §10** ladder; add **correlation propagation doc §2** when score moved but ledger lacks expected `correlation_id` for an outcome-driven incident.

---

## Document control

**Owner:** Platform / compliance engineering. **Updates:** F2-A (history/change_log) and F2-B (outcome context + activity log) shipped — revise join recipe when further slices land.
