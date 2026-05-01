# Stream C — Remediation correlation runbook (read-only)

**Purpose:** Give support, ops, and engineering a **single correlation vocabulary** and **join recipes** across persisted remediation *signals* (gaps, risk, issues, work orders) and *presentation* layers (Today / unified tasks), without implying a unified lifecycle store exists today.

**Companion:** `CLOSED_LOOP_COMPLIANCE_ARCHITECTURE_TRACKER.md` (Stream C), `CLOSED_LOOP_ARCHITECTURAL_GAP_ANALYSIS.md` §3–4, `STREAM_F_FORENSICS_JOIN_RECIPE.md` (Mongo + `audit_logs` query order).

**Authority:** This document is **governance and read-side correlation only** — no runtime behaviour. Product may later adopt a persisted remediation aggregate; until then, use **`remediation_key` + `source_system`** as *logical* keys for scripts, dashboards, and internal APIs (see §8–12).

---

## 1. Scope and non-goals

**In scope:** How each signal type maps to stable keys, which IDs join to `requirements` / `compliance_gaps` / score artefacts, what counts as **compliance closure** vs **inbox or risk closure**, and dedupe hazards.

**Out of scope:** New collections, new queues, frontend behaviour, dedupe implementation in `unified_tasks_service` (product-gated per tracker).

---

## 2. Source-by-source correlation reference

Columns: **stable key** · **linked entity IDs** · **owner / status fields** · **closure semantics** · **does NOT count as compliance closure** · **evidence / recalc** · **audit linkage** · **dedupe risk** · **audience**

### 2.1 `compliance_gaps` (persistence)

| Dimension | Detail |
|------------|--------|
| **Stable key** | **`gap_key`** — unique in Mongo; idempotent upsert key for gap sync (`compliance_gap_sync`). |
| **Linked entity IDs** | `client_id`, `property_id`, `requirement_id`; policy snapshot fields mirror obligation/gap engine at sync time. |
| **Owner / status** | `status`: `open` \| `resolved`; `resolved_at`, `resolved_reason`; severity / `gap_kind` for prioritisation (not legal verdict alone). |
| **Closure semantics** | **Compliance-relevant** when gap **resolves** because inference + evidence truth no longer emit that gap (often after `sync_requirement_evidence_authority` + engine). Optional **`COMPLIANCE_GAP_RESOLVED`** in `audit_logs` when `audit_lifecycle=True`. |
| **Does NOT count as closure** | Row still `open` while user dismisses Today task; operator **quiet** gap sync (no lifecycle audit) still changes gap rows — use applicability audit + row diff (`STREAM_F_FORENSICS_JOIN_RECIPE.md` §6). |
| **Evidence / recalc** | Gap persistence follows evidence authority sync on wired paths; **score** updates via `enqueue_compliance_recalc` / `recalculate_and_persist` on **separate** triggers (`STREAM_E_MUTATION_FANOUT_MATRIX.md`). |
| **Audit linkage** | `COMPLIANCE_GAP_OPENED`, `COMPLIANCE_GAP_RESOLVED`, `COMPLIANCE_GAP_ISSUE_CREATED` (when operational bridge creates an issue) when lifecycle audit enabled. |
| **Dedupe risk** | **Multiple `gap_key`s per `requirement_id`** — dedupe by `requirement_id` alone is **forbidden** (tracker Stream C). |
| **Audience** | **Client-facing** via Today / Command Centre (through priority stream); **admin** gap tools / backfills. |

---

### 2.2 `risk_signals` (`risk_signal_service`)

| Dimension | Detail |
|------------|--------|
| **Stable key** | **`signal_id`** (+ `client_id` scope). Signals are **regenerated** per property (`delete_many` + insert pattern) — treat as **current snapshot**, not immutable history. |
| **Linked entity IDs** | `property_id`, `client_id`; optional `asset_id`; metadata may reference categories / types; **not** the same row shape as `compliance_gaps`. |
| **Owner / status** | `status`: e.g. `active`, `acknowledged`, `resolved` (service constants); dismiss reasons are **informational** (`RISK_DISMISS_REASONS`). |
| **Closure semantics** | **Risk-layer closure** only — reduces Command Centre / digest noise when acknowledged or resolved. |
| **Does NOT count as compliance closure** | **Risk dismiss / resolve does not close gaps or obligations** (`CLOSED_LOOP_ARCHITECTURAL_GAP_ANALYSIS.md` §3.2). |
| **Evidence / recalc** | **Not guaranteed** — user must still complete evidence / obligation paths; score may move from **other** mutations. |
| **Audit linkage** | `create_audit_log` patterns in `risk_signal_service` (dismiss / transitions — verify action names in code when forensics). |
| **Dedupe risk** | Same property may show **compliance churn risk** alongside **concrete gaps** for similar facts — product rule for collapse not centralised in one module. |
| **Audience** | **Client-facing** Command Centre / priority `ACTION_RISK_SIGNAL`; operations URL pattern **`/operations/risk-signals?signal_id=…`** (Stream D risk CTA authority). |

---

### 2.3 `maintenance_issues`

| Dimension | Detail |
|------------|--------|
| **Stable key** | **`issue_id`** (+ `client_id`). When created from gap bridge: **`operational_root_key` = `gap_key`** (idempotent bridge per `gap_key`). |
| **Linked entity IDs** | `property_id`, `client_id`; optional linkage to WO; may carry `requirement_code` / narrative from bridge template. |
| **Owner / status** | Human workflow status (labels in `client_priority_stream` for open issues); assignee fields per product. |
| **Closure semantics** | **Operational closure** — issue resolved/closed in maintenance domain. **Does not automatically resolve** `compliance_gaps` or recalc score unless outcome engine / evidence paths fire (`gap analysis` §3.5). |
| **Does NOT count as compliance closure** | Issue closed while gap still `open`; bridge-created issue without subsequent evidence sync. |
| **Evidence / recalc** | May trigger **`compliance_outcome_engine`** paths on some resolutions (see `STREAM_E` matrix rows 17–18); **partial** — not all event types refresh authority before score. |
| **Audit linkage** | **`COMPLIANCE_GAP_ISSUE_CREATED`** when bridge creates issue; other issue transitions may have maintenance audits — check `maintenance_issues_service` / routes. |
| **Dedupe risk** | Same `gap_key` should not create duplicate bridge issues (idempotent bridge); **separate** human issues may overlap same obligation by narrative. |
| **Audience** | **Client-facing** open-issue priority actions; **admin** maintenance surfaces. |

---

### 2.4 `work_orders`

| Dimension | Detail |
|------------|--------|
| **Stable key** | **`work_order_id`** (+ `client_id`). |
| **Linked entity IDs** | `property_id`, optional **`issue_id`**, optional **`risk_signal_id`** / `requirement_code` / `work_order_kind` per product usage (`database.py` indexes). |
| **Owner / status** | Contractor / SLA state; `status` drives near-breach / breached priority actions. |
| **Closure semantics** | **Operational** completion; compliance posture may update **only if** wired paths run (outcome engine, evidence append — `STREAM_E` matrix). |
| **Does NOT count as compliance closure** | WO completed without compliant-set / authority refresh on that outcome branch. |
| **Evidence / recalc** | Evidence may be appended on some flows; property score via **`recalculate_and_persist`** on wired paths; **enqueue** on others. |
| **Audit linkage** | WO-specific audits vary by route; **not** a single `COMPLIANCE_GAP_*` story. |
| **Dedupe risk** | Multiple WOs per property / issue; **no** universal `(WO ↔ gap_key)` unless fields populated by integration discipline. |
| **Audience** | **Client-facing** SLA / open WO tasks; **admin** contractor tooling. |

---

### 2.5 Today / unified tasks (`client_priority_stream` → `unified_tasks_service`)

| Dimension | Detail |
|------------|--------|
| **Stable key** | **`task_id`** = `{source_type}:{source_id}` where `source_type` ∈ `requirement`, `risk_signal`, `work_order`, `issue`, `approval`, or `priority_action` / other synthetic; `source_id` from `_stable_source_id` (`unified_tasks_service`). |
| **Linked entity IDs** | Embedded in task DTO / `task_metadata`: `related_requirement_id`, `related_risk_signal_id`, `related_work_order_id`, `related_issue_id`, `related_invoice_id`, `requirement_code`, `related_property_id`. |
| **Owner / status** | **No persisted obligation owner** on the task row — **aggregated read model**; urgency from action_type + severity + overdue. |
| **Closure semantics** | **None for compliance** — task list is **prioritisation + navigation**; resolver-backed **`take_action`** for requirement-backed CTAs (Stream D). |
| **Does NOT count as compliance closure** | **Snooze, dismiss, reviewed, done (legacy), restore** — `client_task_state_service` / `client_task_*` overlays only (`STREAM_F` §7). |
| **Evidence / recalc** | Completing evidence is **downstream** of following CTAs / documents routes, not the inbox row itself. |
| **Audit linkage** | Today **navigation intent** and **task overrides** audited via `routes/client.py` patterns — **visibility**, not gap resolve. |
| **Dedupe risk** | Same `requirement_id` may appear as **missing doc**, **overdue**, **cert expiring** if upstream does not collapse; **different `task_id`s**. |
| **Audience** | **Client-facing** Today + Command Centre bundle (defensive partial failures possible per gap analysis §3.4). |

**`tenant_request` / `tenant_message`:** Additional `source_type` values from `unified_tasks_service` for non-priority streams — correlate via `requirement_id` / property in metadata; same **non-closure** inbox rules unless evidence path completes.

---

### 2.6 Evidence rejection flows

| Dimension | Detail |
|------------|--------|
| **Stable key** | **`document_id`** (+ `client_id`); rejection ties to **`requirement_id`** when document was linked. |
| **Linked entity IDs** | `documents.status` → `REJECTED` (or equivalent); `requirement_id` when set; drives **`sync_requirement_evidence_authority`** on wired paths (`STREAM_E`). |
| **Owner / status** | Document lifecycle + admin verifier; requirement `evidence_authority` / gap kinds (`MISMATCHED_EVIDENCE`, etc.). |
| **Closure semantics** | **Compliance** may **worsen** (new / reopened gaps) or improve after replacement evidence — **not** “reject = done”. |
| **Does NOT count as compliance closure** | Rejection alone; user must upload acceptable evidence. |
| **Evidence / recalc** | Rejection path triggers authority + gap sync when linked; **Enq** recalc on typical document routes. |
| **Audit linkage** | `DOCUMENT_REJECTED` / related `audit_logs`; join `STREAM_F` §3C from `document_id`. |
| **Dedupe risk** | Multiple documents per requirement — correlate each `document_id` separately. |
| **Audience** | **Client + admin** document surfaces; **diagnostic** read-repair / admin bulk tools must be labelled non-authoritative if applicable (tracker rule). |

---

### 2.7 Score / recalc history

| Dimension | Detail |
|------------|--------|
| **Stable key** | **Property-level:** `property_id` + time ordering; **`property_compliance_score_history`**, **`score_change_log`**, **`score_ledger_events`**. |
| **Linked entity IDs** | `score_ledger_events` / `recalculate_and_persist` **context** may carry `requirement_id`, `document_id`, `correlation_id` (when supplied — e.g. `REQUIREMENT_UPDATED:{rid}`, `TENANT_DELIVERY:{delivery_id}`, admin repair). |
| **Owner / status** | **Authoritative writer:** `compliance_scoring_service.recalculate_and_persist` (Stream B); `reason` / trigger strings on history rows. |
| **Closure semantics** | Score move reflects **aggregate** obligation state — **indirect** evidence of compliance movement, not a single remediation item closing. |
| **Does NOT count as compliance closure** | Score unchanged while gaps still open (staleness, queue lag); lazy repair / read paths. |
| **Evidence / recalc** | Recalc **follows** evidence mutations on matrix-classified paths; **may lag** on `Enq`-only. |
| **Audit linkage** | `COMPLIANCE_SCORE_UPDATED`, repair pair audits; join `STREAM_F` §8. |
| **Dedupe risk** | **`score_change_log.changed_requirements`** uses **`requirement_key`** — map to `requirement_id` carefully (`STREAM_F` §5). |
| **Audience** | **Client** headline + ledger; **admin** validate/repair; **diagnostic** compare-only admin paths per matrix. |

---

### 2.8 Audit events (`audit_logs` + specialised collections)

| Dimension | Detail |
|------------|--------|
| **Stable key** | No single key — filter by **`action`**, **`client_id`**, **`resource_type` / `resource_id`**, **`metadata.requirement_id`**, **`metadata.correlation_id`**, **`timestamp`**. |
| **Linked entity IDs** | Varies by action: gap (`resource_id` may be `gap_key`), requirement PATCH (`REQUIREMENT_ACTION_TRIGGERED` + `event`), documents, tenant delivery, score. |
| **Owner / status** | `actor_id` / `actor_role`; optional `reason_code`. |
| **Closure semantics** | **Evidence of who did what when** — reconstruct narrative with `STREAM_F` join order; **not** a second score truth. |
| **Does NOT count as compliance closure** | Any audit without matching persistence change (failed downstream, eventual consistency). |
| **Evidence / recalc** | Audits **trail or parallel** persistence; use correlation_id to chain score enqueue → worker when present. |
| **Audit linkage** | Self; plus **`applicability_resolution_audit`** for operator applicability (append-only, separate collection). |
| **Dedupe risk** | High volume + similar actions — **always** narrow by time window + `client_id` + entity id. |
| **Audience** | **Admin / security** primary; **support** forensics; some rows **client-impacting** (document viewed, etc.). |

---

## 3. `remediation_key` convention (logical — not persisted today)

Use a **single string** per “attention item” for scripts and future read models:

| `source_system` | `remediation_key` format | Example |
|-----------------|-------------------------|---------|
| **`gap`** | `gap_key` as stored | `gap:abc123...` optional prefix `gap:` only if disambiguation needed; **default raw `gap_key`** matches bridge. |
| **`risk_signal`** | `risk:{signal_id}` | Stable until regen replaces row — document **regen** when correlating long windows. |
| **`work_order`** | `wo:{work_order_id}` | |
| **`maintenance_issue`** | `issue:{issue_id}` | If bridge-linked, **also** store logical `gap:{gap_key}` in join tables **future** — today correlate via `operational_root_key`. |
| **`requirement`** | `req:{requirement_id}` | Use **only** for overdue / cert-expiring **priority** rows that lack a single gap_key (dedupe **weak** — multiple gaps per req). |
| **`approval`** (invoice) | `inv:{invoice_id}` | Billing / compliance-adjacent; not statutory gap closure. |
| **`tenant_request`** / **`tenant_message`** | `task:{task_id}` or dedicated prefix if product assigns — **inbox** semantics dominate. |

**Rule:** Prefer **`gap_key`** whenever a persisted gap row exists for the story — it is the strongest operational correlation (`operational_root_key`).

---

## 4. `source_system` values (enumeration for future APIs)

Suggested **closed vocabulary** for correlation-only MVPs:

`gap` · `risk_signal` · `work_order` · `maintenance_issue` · `requirement` · `approval` · `tenant_inbox` · `audit_only`

**`audit_only`:** Reconstruct from `audit_logs` alone when persistence row missing or regen dropped risk — **diagnostic**, not client KPI authority.

---

## 5. Minimum viable remediation row (read model — design only)

Shape for **internal** dashboards / exports (not implemented in this PR):

| Field | Description |
|-------|-------------|
| `client_id` | Tenant scope |
| `property_id` | Property scope |
| `remediation_key` | §3 |
| `source_system` | §4 |
| `display_title` | From gap label, risk type, WO title, issue title, or task title |
| `severity_or_priority` | Normalised for sorting only |
| `requirement_id` | Nullable — many WOs/issues may be weakly tied |
| `gap_key` | Nullable |
| `signal_id` / `issue_id` / `work_order_id` | Nullable foreigns |
| `compliance_closure_signals` | Set of **achieved** signals from §9 (empty until inferred from joins) |
| `last_seen_at` | Max of source `updated_at` / task freshness |

---

## 6. Dedupe rules (product + engineering)

1. **Never dedupe by `requirement_id` alone** when multiple **`gap_key`**s can exist on one requirement.  
2. **Risk vs gap:** Treat as **distinct `source_system`** unless product defines collapse rules (Stream C tracker: product-gated).  
3. **Unified tasks:** Dedupe by **`task_id`** for inbox overlays; **do not** merge distinct `task_id`s without explicit rule.  
4. **Bridge issues:** Match **`operational_root_key` == `gap_key`** before inventing a second issue for the same gap.  
5. **Risk regen:** Do not assume **`signal_id`** from six months ago still exists — correlate via **time-bounded** `audit_logs` if needed.

---

## 7. Closure rules (compliance vs operational vs inbox)

| Signal | Compliance closure (strict) | Operational / UX closure |
|--------|------------------------------|----------------------------|
| **Gap** | `status=resolved` with inference aligned to evidence + applicability | — |
| **Risk** | — | `resolved` / dismiss on risk layer |
| **Issue** | Only if evidence + gap + score paths prove obligation met | Issue status terminal |
| **WO** | Only if wired compliance outcomes + evidence | WO completed |
| **Today task** | — | Snooze / dismiss / reviewed |
| **Score** | Supports **narrative** “headline moved” | Not a substitute for gap `resolved` |

**Gating (conceptual):** No **`closure_signal=compliance_met`** without at least one of: gap resolved for the obligation family, evidence authority satisfied per policy, or score recalc reflecting change **and** gap story consistent (`gap analysis` §4).

---

## 8. Forbidden interpretations

1. **“User cleared Today” ⇒ compliant** — **False** (`client_task_*` non-authoritative).  
2. **“Risk gone” ⇒ gap gone”** — **False** (independent layers).  
3. **“WO done ⇒ score correct”** — **Not guaranteed** without path-specific proof (`STREAM_E` outcome matrix).  
4. **`requirement_id` dedupe across gaps** — **Forbidden** for remediation identity.  
5. **Treating quiet operator gap row changes as “no activity”** because no `COMPLIANCE_GAP_*` audit — **False** (`STREAM_F` §6).  
6. **Using risk Command Centre URL as requirement resolver authority** — **False** (Stream D: separate CTA authority).  
7. **Single `audit_logs` row as entire compliance verdict** — Audits support narrative; **persistence** on `requirements` / `compliance_gaps` / score history remains authoritative for posture.

---

## 9. Crosswalk: priority `action_type` → `source_system` / stable id

| `action_type` (from `client_priority_stream`) | `source_type` (`ACTION_TO_SOURCE`) | Stable `source_id` field on action |
|-----------------------------------------------|--------------------------------------|-----------------------------------|
| `overdue_compliance`, `certificate_expiring_soon`, `missing_document` | `requirement` | `related_requirement_id` |
| `risk_signal` | `risk_signal` | `related_risk_signal_id` |
| `work_order_*` / `open_work_order` | `work_order` | `related_work_order_id` |
| `open_operational_issue` | `issue` | `related_issue_id` |
| `pending_invoice_approval` | `approval` | `related_invoice_id` |
| Other | `priority_action` | Hash fallback — **weak** key for dedupe |

---

## 10. Query recipes (high level)

- **From `gap_key`:** `compliance_gaps` → `requirements` → issues with `operational_root_key` → `audit_logs` gap lifecycle (if not quiet) → score history for `property_id` (`STREAM_F` §B).  
- **From `signal_id`:** `risk_signals` → property → related gaps by property + time (heuristic) → risk audits.  
- **From `task_id`:** Parse `source_type:source_id` → underlying collection → re-run §10 row for that system.  
- **From `document_id`:** `STREAM_F` §C + gap list for linked `requirement_id`.

---

## Document control

**Owner:** Platform / compliance product. **Updates:** When bridge semantics, priority stream `action_type`s, or risk regen behaviour change, update this runbook and **Stream C** tracker row in the same PR.
