# Stream F — Operational forensics join recipe (read-only)

**Purpose:** Help support, admin, and engineering **reconstruct one compliance/remediation story** from MongoDB and general `audit_logs` without assuming a single timeline or shared correlation id. This document is **operational guidance only**; it does not change product behaviour.

**Companion:** `CLOSED_LOOP_COMPLIANCE_ARCHITECTURE_TRACKER.md` (Stream F), `CLOSED_LOOP_ARCHITECTURAL_GAP_ANALYSIS.md`, `STREAM_E_MUTATION_FANOUT_MATRIX.md` (mutation → gap sync / recalc / audit patterns).

**Authority (facts in this doc):** Collection names and key fields are aligned with `database.py` index definitions and the services named below. When behaviour is **intentional but non-obvious** (quiet gap sync, inbox non-closure), this doc cites the same sources as the tracker.

---

## 1. Key collections

| Collection | Role in the story |
|------------|-------------------|
| **`requirements`** | Obligation truth as materialised for the property: applicability provenance, evidence authority mirrors, status fields that scoring and gap inference read. |
| **`compliance_gaps`** | Persisted gap rows: `gap_key` (unique), `gap_kind`, policy snapshots, linkage to `requirement_id` / `property_id` / `client_id`, `status` (`open` / `resolved`), timestamps. |
| **`documents`** | Evidence artefacts; link to `requirement_id` when attached; status drives authority sync on wired paths. |
| **`audit_logs`** | Broad business/security audit via `create_audit_log` (`AuditLog`): `action`, `client_id`, `resource_type`, `resource_id`, `metadata`, `timestamp`. Includes gap lifecycle, score updates, documents, tenant delivery, many admin/client actions. |
| **`applicability_resolution_audit`** | **Append-only** operator applicability commands: `event_id`, `client_id`, `property_id`, `requirement_id`, pipeline vs effective applicability, resolution source, reason codes, `created_at`. |
| **`property_compliance_score_history`** | Point-in-time property score snapshots written by `compliance_scoring_service.recalculate_and_persist`: `property_id`, `client_id`, `score`, `breakdown_summary`, `reason`, `created_at`, `actor`. |
| **`score_change_log`** | Per-recalc row with `changed_requirements` (requirement_key level deltas), `reason`, `previous_score` / `new_score`, `created_at`. Written beside history in `recalculate_and_persist`. |
| **`score_ledger_events`** | User-facing ledger lines from `score_ledger_service.log_score_change`: trigger labels/types, driver deltas, optional `requirement_id`, `document_id`, **`correlation_id`** (when caller supplied — e.g. admin repair). |
| **`risk_signals`** | Stored risk rows: `signal_id`, `client_id`, `property_id`, category/type/level, status, timestamps. Regenerated/replaced on property regen (`delete_many` + `insert_one` pattern). |
| **`maintenance_issues`** | Operational issues; **`operational_root_key`** may equal **`gap_key`** when created from gap bridge. |
| **`work_orders`** | Contractor workflow: `work_order_id`, `client_id`, `property_id`, optional `issue_id`, optional `risk_signal_id` / linkage fields per product usage. |
| **`client_task_overrides`** | Per-user inbox suppression/snooze/done overlay — **presentation only**. |
| **`client_task_activity_log`** | Append-only inbox actions (snooze, dismiss, reviewed, restore). |
| **`properties`** | Current persisted headline: `compliance_score`, breakdown fields, `compliance_last_calculated_at`, etc. |
| **`compliance_score_history`** | **Client-level** daily/trend snapshots (`compliance_trending`) — portfolio trend card; not the same as `property_compliance_score_history`. |

---

## 2. Join keys (logical, not always indexed)

| Starting id | Join to | Typical key |
|-------------|---------|-------------|
| **`requirement_id`** | Gaps | `compliance_gaps.requirement_id` + `client_id` |
| | Requirement row | `requirements.requirement_id` (and `client_id` / `property_id` for scoping) |
| | Applicability audit | `applicability_resolution_audit.requirement_id` |
| | Documents | `documents.requirement_id` (when set) |
| | Score delta detail | `score_change_log.changed_requirements[].requirement_key` (code/key, not always same string as UUID — **verify mapping**) |
| **`property_id`** | All property-scoped rows | `property_id` + `client_id` where collections store both |
| | Current score | `properties.property_id` |
| | History / ledger | `property_compliance_score_history`, `score_ledger_events`, `score_change_log` |
| **`gap_key`** | Gap row | `compliance_gaps.gap_key` (unique) |
| | Maintenance issue | `maintenance_issues.operational_root_key` **when** bridge created issue with `operational_root_key = gap_key` |
| | Audit (opened) | `audit_logs` where `action = COMPLIANCE_GAP_OPENED` and `resource_id = gap_key` |
| **`document_id`** | Document | `documents` primary key field as stored (often `document_id`) |
| | Score ledger | `score_ledger_events.document_id` when recalc passed context |
| | Document audits | `audit_logs` with document-related actions; inspect `metadata` / `resource_id` |
| **`work_order_id`** | Work order | `work_orders.work_order_id` |
| | Issue | `work_orders.issue_id` → `maintenance_issues.issue_id` |
| **`issue_id`** | Issue | `maintenance_issues.issue_id` |
| | Work orders | `work_orders.issue_id` |
| | Gap bridge | Issue may carry `operational_root_key` → `gap_key` |
| **`risk_signal_id`** | Risk row | `risk_signals.signal_id` + `client_id` |
| | Downstream | WO/issue creation helpers may store `risk_signal_id` on operational rows |
| **Audit / score** | Correlation (partial) | `score_ledger_events.correlation_id`; `audit_logs.metadata.correlation_id` on some paths (e.g. admin score repair) — **not universal** |

Always constrain by **`client_id`** when the collection has it: IDs are only unique in tenant scope.

---

## 3. Recommended query order

Pick the **entry point** you actually have; then widen the net in this order.

### A. You have `requirement_id` (+ `client_id`)

1. **`requirements`** — Current obligation row: applicability fields (`pipeline_applicability_state`, `effective_applicability_state`, `applicability_resolution_source`, provenance blobs), evidence authority, compliance status mirrors.
2. **`compliance_gaps`** — `requirement_id` + `client_id`, `status: open` first; then historical resolved rows if needed (`updated_at`, `resolved_at`, `resolved_reason`).
3. **`applicability_resolution_audit`** — Same `requirement_id`, sort `created_at` ascending — operator narrative.
4. **`documents`** — Linked evidence for that requirement.
5. **`audit_logs`** — Filter `client_id`, then narrow by `metadata.requirement_id` or requirement-adjacent actions (documents, workflow). **Broad text/index scan may be heavy** — use time bounds.
6. **Score artefacts** — `property_id` from requirement → `property_compliance_score_history`, `score_change_log`, `score_ledger_events` in the incident window.

### B. You have `gap_key` (+ `client_id`)

1. **`compliance_gaps`** — Authoritative row: `requirement_id`, `property_id`, `gap_kind`, snapshot fields, lifecycle timestamps.
2. **`requirements`** — Row for `requirement_id`.
3. **`audit_logs`** — `COMPLIANCE_GAP_OPENED` / `COMPLIANCE_GAP_RESOLVED` / `COMPLIANCE_GAP_ISSUE_CREATED` with metadata containing `gap_key` or `resource_id` = gap_key (pattern depends on action).
4. **`maintenance_issues`** — `operational_root_key == gap_key` (when bridge ran).
5. **Score** — Property-level only unless gap maps to a specific requirement_key delta in `score_change_log`.

### C. You have `document_id` (+ `client_id`)

1. **`documents`** — `requirement_id`, `property_id`, status, verification timestamps.
2. **`requirements`** / **`sync_requirement_evidence_authority`** outcomes are implicit in row state — re-fetch requirement **after** the document event time.
3. **`compliance_gaps`** — For that `requirement_id` after the event.
4. **`audit_logs`** — `DOCUMENT_*` actions; `score_ledger_events` / history around `created_at` for uploads/verify (often **enqueue**, so allow lag — see §8).

### D. You have `work_order_id` or `issue_id`

1. **`work_orders`** / **`maintenance_issues`** — Full operational row; note `operational_root_key`, `requirement_code`, any compliance linkage.
2. If `operational_root_key` looks like a **`gap_key`**, resolve **`compliance_gaps`** and upstream **`requirements`**.
3. **`compliance_outcome_engine`** / maintenance paths may call **`recalculate_and_persist`** — check **`score_change_log`** and **`COMPLIANCE_SCORE_UPDATED`** near WO/issue closure time (see matrix row 17–18).

### E. You have `risk_signal_id` (+ `client_id`)

1. **`risk_signals`** — Signal payload and status (`active` / `acknowledged` / `resolved`).
2. **`audit_logs`** — Risk dismiss / acknowledge patterns from `risk_signal_service` (if present for that id).
3. **Do not assume** gap closure — risk is a **parallel** lens (`CLOSED_LOOP_ARCHITECTURAL_GAP_ANALYSIS.md` §3.2). Cross-check **`compliance_gaps`** for the same property/requirement if the signal is compliance-category.

---

## 4. What each collection proves

| Collection | Proves (when row exists and is consistent) |
|------------|--------------------------------------------|
| **`requirements`** | What the engine and portal **should** treat as obligation truth at read time (subject to eventual consistency). |
| **`compliance_gaps`** | Structured non-compliance or exposure **inference** persisted for prioritisation; open/resolved transitions when sync succeeded. |
| **`audit_logs` (`COMPLIANCE_GAP_*`)** | **Observable** open/resolve milestones **only when** `audit_lifecycle=True` on sync. |
| **`applicability_resolution_audit`** | **Who changed applicability interpretation** (operator vs pipeline), with before/after semantics — authoritative for override narrative. |
| **`audit_logs` (`COMPLIANCE_SCORE_UPDATED`, repair pair)** | That enterprise score **persist** ran and with what headline delta; repair flows may chain **mismatch → updated → repaired** with shared `correlation_id` in metadata. |
| **`property_compliance_score_history` + `score_change_log`** | **Numerical** history and **which requirement_keys** moved in that recalculation. |
| **`score_ledger_events`** | Operator/user-facing explanation of the same recalculation (trigger label, drivers). |
| **`documents`** | Evidence state transitions (upload, verify, reject). |
| **`risk_signals`** | Risk engine output — explainable, **not** legal compliance verdict. |
| **`maintenance_issues` / `work_orders`** | Operational execution state; closure **does not** automatically prove compliance closure. |
| **`client_task_*`** | **Inbox** preference only (§7). |

---

## 5. Known gaps where lineage is weak

- **No universal `audit_correlation_id`** across gap + issue + WO + score + risk for one story (tracker Stream F — future incremental work).
- **Quiet gap sync** (§6): gap rows and `updated_at` may change **without** `COMPLIANCE_GAP_OPENED` / `COMPLIANCE_GAP_RESOLVED`.
- **Client `patch_requirement`:** **`REQUIREMENT_ACTION_TRIGGERED`** with `metadata.event=client_patch_requirement` and `correlation_id=REQUIREMENT_UPDATED:{requirement_id}` (after authority sync; Stream E row 10). Join to score queue/history via that correlation where present.
- **Enqueue-only recalc**: `audit_logs` / history may trail the triggering document audit by **queue latency**.
- **Risk regen** replaces signals — historical risk rows for a property may **not** be retained in `risk_signals` after regen; rely on audits or external reporting if required.
- **`score_change_log.changed_requirements`** uses **requirement_key** — map to `requirement_id` via requirement row or catalog conventions; mismapping is a common forensics mistake.
- **Operational bridge off** on operator path: **no** `COMPLIANCE_GAP_ISSUE_CREATED` from that sync — issues won’t appear “because of” quiet sync.

---

## 6. Quiet sync paths (how to interpret)

**Definition:** `sync_compliance_gaps_for_requirement(..., audit_lifecycle=False, run_operational_bridge=False)` — see `compliance_gap_sync.py` and Stream E matrix row 12.

**What still happens:** Gap documents are **upserted** or **resolved**; policy snapshots on gaps can move; HIUA-relevant fields on gap rows can change.

**What does not happen:** No **`COMPLIANCE_GAP_OPENED` / `COMPLIANCE_GAP_RESOLVED`** in `audit_logs` for that sync; **no** idempotent **gap → issue** bridge side effects.

**Forensics recipe:**

1. Read **`applicability_resolution_audit`** for the `requirement_id` around the incident.
2. Compare **`compliance_gaps`** versions using `updated_at` / field diff vs **`requirements`** applicability fields.
3. Do **not** infer “no gap activity” from silence in `audit_logs` gap actions.

---

## 7. Inbox visibility vs compliance closure

**Inbox (Today / Command Centre task list):**

- Collections: **`client_task_overrides`**, **`client_task_activity_log`** (`client_task_state_service`).
- Actions: snooze, dismiss, reviewed, done (legacy), restore — **documented as non-authoritative** for compliance (`client_task_state_service` module docstring; `routes/client.py` task endpoints).

**What they prove:** User **saw** or **hid** a task; habit/analytics; optional **`audit_logs`** on navigation intent / overrides.

**What they do not prove:** Evidence uploaded, gap resolved, obligation satisfied, or score recalculated.

**Compliance closure signals (inferential, multi-store):**

- Gap **`status: resolved`** with plausible `resolved_reason` / inference change.
- Requirement **evidence authority** and compliance mirrors align with “met”.
- **`COMPLIANCE_SCORE_UPDATED`** (or history/ledger) after the evidence path with consistent `reason`.
- Applicability **not** stuck in `UNKNOWN` when HIUA depends on resolution (§9).

Train support: **dismiss ≠ fixed**.

---

## 8. Tracing score recalculation after evidence or requirement changes

**Authoritative write:** `compliance_scoring_service.recalculate_and_persist` persists `properties`, inserts **`property_compliance_score_history`** and **`score_change_log`**, writes **`score_ledger_events`**, emits **`COMPLIANCE_SCORE_UPDATED`** (`create_audit_log`).

**Practical sequence:**

1. Anchor **time window** from the document or requirement event (`audit_logs` or application timestamps).
2. Query **`property_compliance_score_history`** for `property_id` (+ `client_id`), sort `created_at` descending — each doc has **`reason`** (trigger reason string).
3. Match **`score_change_log`** entries on `created_at` / score pair; inspect **`changed_requirements`** for obligation-level movement.
4. Query **`score_ledger_events`** for human-readable **`trigger_label`** / **`trigger_type`**; check **`document_id`** / **`requirement_id`** / **`correlation_id`** when populated.
5. Check **`audit_logs`** for `COMPLIANCE_SCORE_UPDATED` and **`metadata.reason`**, **`metadata.correlation_id`** (admin repair).
6. **Enqueue path:** If only **`enqueue_compliance_recalc`** ran, score rows may appear **later** than document audit — consult **`STREAM_E_MUTATION_FANOUT_MATRIX.md`** for the mutation row (Sync vs Enq).

**Double-score windows:** Some paths enqueue **and** call synchronous recalc (matrix notes on verify/outcome) — expect **tight pairs** of history rows; interpret the **last** consistent state as authoritative for “current”.

---

## 9. Applicability overrides and HIUA

**Applicability operator narrative:** Only **`applicability_resolution_audit`** captures the command with **`applicability_resolution_source`** (e.g. operator override vs pipeline), **`pipeline_applicability_state`** vs **`effective_applicability_state`**, and **`resolution_reason_code`**. Cross-reference **`RUNBOOK_APPLICABILITY_RESOLUTION_OPERATIONS.md`** for process boundaries.

**Requirement row:** After commands, **`requirements`** carries provenance and effective fields used by runtime surfaces — diff requirement document around `created_at` of audit events.

**HIUA (HIGH_IMPACT_UNRESOLVED_APPLICABILITY):** Derived **read-time** from open gap shape + policy facts (`hiua_operational_uncertainty.derive_hiua_signal_for_open_gap`), not a separate collection. **Queue / prioritisation** uses HIUA counts over capped gap scans (`applicability_resolution_queue`).

**Forensics:**

1. If HIUA flags disagree with expectations, inspect **open `compliance_gaps`** for `UNKNOWN` applicability + material gap kinds on **HIUA-eligible** codes (see `HIUA_ELIGIBLE_REQUIREMENT_CODES` / `HIUA_MATERIAL_GAP_KINDS` in `hiua_operational_uncertainty.py`).
2. Confirm whether a **quiet sync** refreshed gap snapshots after operator action (§6).
3. **Standing `OPERATOR_OVERRIDE`** without pipeline repair creates **intentional fork** between pipeline truth and effective truth until revoke — see gap analysis §4–5.

---

## 10. Escalation when lineage is incomplete

Use this ladder **before** assuming data loss:

1. **Widen time window** — queue lag, batch jobs, tenant delivery reconciliation.
2. **Check quiet sync** — absence of `COMPLIANCE_GAP_*` does not mean absence of gap changes (§6).
3. **Check `sync_errors`** — not stored in Mongo by default; engineering may need app logs / `compliance_fanout` structured logs for failed gap sync stages.
4. **Check matrix row** for the mutation — `STREAM_E_MUTATION_FANOUT_MATRIX.md` states whether recalc is **Enq**, **Sync**, or **missing**.
5. **Compare three score artefacts** — `properties.compliance_score` vs latest `property_compliance_score_history` vs `score_ledger_events`; if divergent, stale read or failed persist — escalate with property id + timestamps.
6. **Risk vs gap** — User may have “resolved” a **risk signal** while gaps remain open — verify **`compliance_gaps`**.
7. **WO/issue closure** — Confirm whether **`compliance_outcome_engine`** ran **`_set_requirement_compliant`** branch (authority + gap sync before score) for that event type (matrix §2 outcome engine note).
8. **Legal / retention** — If audit is missing due to retention policy, note **policy** limitation; do not infer compliance from absence.

**Ticket template (suggested):** `client_id`, `property_id`, `requirement_id?`, `gap_key?`, `document_id?`, incident window (UTC), expected vs observed gap/score/applicability state, queries already run, screenshots/IDs from portal.

---

## Document control

**Owner:** Platform / compliance engineering. **Change rule:** Update this doc when collections, audit actions, or intentional quiet paths change; mirror updates in `CLOSED_LOOP_COMPLIANCE_ARCHITECTURE_TRACKER.md` Stream F changelog.
