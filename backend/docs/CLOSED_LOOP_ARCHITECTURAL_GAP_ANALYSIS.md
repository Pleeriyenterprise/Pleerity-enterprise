# Closed-loop compliance platform — architectural gap analysis

**Purpose:** Compare the **current implemented state** of the Pleerity Enterprise backend (and its implied client surfaces) against an **intended closed-loop compliance architecture**: policy truth → obligations → risk/remediation signals → operational work → evidence → verification → recalculated compliance → audit → reporting.

**Scope:** This document is an **audit and gap analysis only**. It does **not** implement code, redesign unrelated systems, or propose speculative marketplace features. Claims are grounded in **observable module boundaries** (`services/*`, `routes/*`, `scripts/*`, `docs/*`) unless explicitly labelled as **inference**.

**Last reviewed:** Backend tree as of applicability resolution runbook / PR4 operator gap sync era (see `RUNBOOK_APPLICABILITY_RESOLUTION_OPERATIONS.md`, `applicability_operator_actions.py`, `compliance_gap_sync.py`).

---

## 1. Executive summary

### Current strengths

- **Persisted compliance gaps** — `compliance_gap_engine` infers structured gaps; `compliance_gap_sync` upserts **`compliance_gaps`** with policy snapshot fields and optional lifecycle audit (`COMPLIANCE_GAP_OPENED` / `RESOLVED`) when `audit_lifecycle` is enabled; gap rows carry **`gap_key`** for idempotent operational linkage.
- **Applicability governance spine (recent)** — Provenance selector + **effective** read model (`applicability_effective_resolver`), **PR4** operator commands (`applicability_operator_actions`), **append-only** `applicability_resolution_audit`, **internal** applicability resolution **queue** (`applicability_resolution_queue`), and **post-operator** gap snapshot refresh via `sync_compliance_gaps_for_requirement` with **quiet** gap lifecycle (`audit_lifecycle=False`, `run_operational_bridge=False`) reduce HIUA / gap drift after operator intervention.
- **Client “Today” / Command Centre composition** — `unified_tasks_service` aggregates multiple sources with **server-side** prioritisation; `command_center_service` composes digest + risk + compliance summary; explicit intent to avoid client-side duplication of business rules (see module docstrings).
- **Canonical requirement CTAs (partial)** — `requirement_action_resolver` defines **`take_action`** contract and documents parity with frontend resolver; tests exist for Today CTA authority alignment.
- **Risk signal layer** — `risk_signal_service` stores explainable **risk signals** with audit hooks and dismiss reasons; separate from gap persistence but can surface as priority actions (`ACTION_RISK_SIGNAL` in `client_priority_stream`).
- **Compliance scoring v2 path** — `compliance_scoring_service` documents a **single** recalculation entrypoint (`recalculate_and_persist`) for property-level enterprise scoring with history and semantics attachment.

### Current architectural risks

- **Multiple “truth” surfaces** — Obligation truth can be read from **materialised requirements**, **persisted gaps**, **catalog-derived** portfolio views (`catalog_compliance`), **legacy** score paths (`compliance_score` module still carries legacy calculation naming), and **operator overrides** on applicability. Not all consumers use the same filter or projection pipeline.
- **Remediation multiplicity** — Signals can originate from **gaps**, **risk signals**, **work orders**, **maintenance issues**, **invoices**, and **requirement overdue/legacy** paths in `client_priority_stream`. Each has different DTO shapes and closure semantics; **no single canonical remediation aggregate** exists at the persistence layer.
- **Operational closure vs inbox closure** — Today / Command Centre **snooze, dismiss, reviewed** actions are explicitly **not** domain completion (see `routes/client.py` docstrings). Risk dismiss is **informational** (`risk_signal_service`). This is correct product intent but **easy to misread** as “compliance fixed” without a closed-loop narrative.
- **Eventual consistency and ordering** — Requirement writes can succeed while **gap sync** logs warnings or skips (e.g. missing post-update `find_one`, `sync_compliance_gaps_for_requirement` errors, runtime surface exclusion). **Dashboard / HIUA / queue** can temporarily disagree until downstream sync completes or retries.

### Launch-critical unresolved gaps (architecture-level)

- **No unified remediation lifecycle record** — There is **no** single persisted entity that tracks “opened → assigned → evidence submitted → verified → score recalculated → archived” across gaps, issues, and work orders. Closure is **inferred** from multiple collections and logs.
- **Authoritative “compliance changed” fan-out** is **not** centrally orchestrated — Different writers trigger gap sync (`requirement_evidence_authority`, `tenant_delivery_reconciliation`, operator command, backfills). **Recalculation** is triggered from specific domains (`compliance_scoring_service` contract) but is **not** proven here to fire on **every** meaningful mutation path uniformly.
- **Cross-surface CTA integrity** depends on **discipline** — Backend resolver + frontend resolver must stay aligned; drift creates **dead or misleading CTAs** without compile-time enforcement across repos.

### Governance strengths already implemented

- **Structured operator reason codes** — Closed enum for PR4 commands (`applicability_operator_resolution_reasons.py`).
- **Append-only applicability audit** — `applicability_resolution_audit` with required keys (`applicability_resolution_audit.py`).
- **Internal ops queue** — Applicability resolution queue is **admin-only**, tenant-scoped, with deterministic root-cause codes and operational prioritisation fields.
- **Runbook governance** — `RUNBOOK_APPLICABILITY_RESOLUTION_OPERATIONS.md` encodes decision boundaries (exceptions vs pipeline truth, no bulk override without root cause, revoke when pipeline corrected).

### Remaining coherence risks

- **Override and provenance drift** — Standing `OPERATOR_OVERRIDE` without pipeline repair creates a **permanent fork** between pipeline and effective truth until revoked.
- **Support interpretation risk** — Operators may treat **queue volume** or **HIUA** as targets to silence rather than signals to remediate (mitigated by governance text, not by hard architecture).
- **Reporting vs runtime universe** — Anything not using **`filter_requirement_rows_for_client_runtime_surfaces`** + **`project_requirement_row_client_runtime`** (or equivalent) can **disagree** with portal KPIs (`compliance_scoring_service` docstring warns of this alignment pattern).

---

## 2. Closed-loop integrity review

Intended loop:

**Policy Registry → Compliance Engine → Risk Detection → Remediation Signal → Operations Workflow → Evidence Collection → Verification → Compliance Recalculation → Audit Trail → Dashboard / Reports / Alerts**

| Stage | Implemented | Partial / fragmented | Disconnected / legacy | Notes |
|-------|-------------|------------------------|------------------------|-------|
| **Policy Registry** | Published registry snapshot services (`compliance_registry_publish_service`, `compliance_registry_admin_service`); `materialize_requirements_for_property` merges snapshot into requirements. | **Partial:** registry metadata on requirements varies by publish/materialization timing; legacy fields still exist on rows. | Older obligation rows may predate provenance; **legacy applicability** paths documented in `APPLICABILITY_PROVENANCE_LEGACY_APPLICABILITY_STATE.md`. | Registry is not the only writer of obligation truth—**operator override** can supersede effective read without changing pipeline snapshot. |
| **Compliance Engine** | **Gap inference** (`infer_compliance_gaps_for_requirement`), **policy facts** (`policy_field_normalizer` / related), **materialization** of requirements, **HIUA** read-time (`hiua_operational_uncertainty`). | **Partial:** engine outputs are **persisted** via sync jobs, not always synchronously on every requirement mutation path historically; operator path now triggers sync. | **Legacy** gap derivation bridge (`derive_gaps_from_legacy_requirement_row` in gap engine) for migration windows. | “Engine” is really **multiple engines** (gaps, scoring v2, risk heuristics). |
| **Risk Detection** | **Risk signals** persisted with categories/types (`risk_signal_service`); can feed priority stream (`ACTION_RISK_SIGNAL`). | **Partial:** overlap conceptually with **compliance gaps** and **maintenance frequency** heuristics—two lenses on similar distress. | Risk dismiss does **not** close compliance gaps or obligations. | Explicitly **not ML**; transparency is a strength but rules can diverge from gap severity. |
| **Remediation Signal** | **Priority actions** from `client_priority_stream` (gaps, requirements, work orders, invoices, issues, risk); mapped into **unified tasks** (`unified_tasks_service`). | **Fragmented:** each source has different **metadata**, IDs, and URLs; dedupe is **not** a first-class global key across sources. | Some URLs are **constructed** (e.g. risk CTA in `command_center_service._slim_risk`) vs resolver-derived requirement CTAs. | Signals can exist **without** a guaranteed operational workflow (e.g. dismiss-only risk). |
| **Operations Workflow** | **Work orders** collection and contractor assignment indexes (`database.py`); **maintenance issues** (`maintenance_issues_service`); **gap → issue** bridge when enabled (`apply_gap_operational_bridge` — **idempotent** per `gap_key`). | **Partial:** bridge is **optional** (`run_operational_bridge`); operator-triggered sync **disables** it to avoid noise—**no automatic issue** from that path. | **Work order creation** is described as **client-led** in gap bridge docstring—not auto-created from every gap. | True “workflow state machine” across WO/issue/gap is **not** centralised. |
| **Evidence Collection** | Document and evidence authority flows (`requirement_evidence_authority` triggers gap sync); evidence modes in `requirement_action_resolver`. | **Partial:** JOB vs DOCUMENT vs OBLIGATION paths have different UX promises; guided evidence may be limited for JOB per resolver comments. | Legacy status mirrors until authority fully synced. | Collection does **not** automatically imply **verification** or **score** update unless wired paths run. |
| **Verification** | Evidence authority / extraction pipeline (referenced across services); policy predicates on gaps (`classify_gap_policy_predicates`). | **Partial:** “verification” is distributed (document verification, authority sync), not one service name. | | |
| **Compliance Recalculation** | `compliance_scoring_service.recalculate_and_persist` contract; property score persistence + history reasons. | **Partial:** other modules (`compliance_score.calculate_compliance_score` naming) suggest **legacy** client score path still present—risk of **dual mental models** “enterprise vs legacy”. | Not every mutation is proven here to enqueue **deterministic** recalculation (depends on route/service wiring). | **Lazy repair** path (`REASON_SCORE_READ_REPAIR`) indicates **staleness** is anticipated. |
| **Audit Trail** | `audit_logs` via `create_audit_log`; gap lifecycle; applicability resolution audit collection; some job/digest audit verbs. | **Fragmented:** multiple stores (`audit_logs`, `applicability_resolution_audit`, collection-specific logs). | Not all transitions may be reconstructable from a **single** timeline without correlation keys. | |
| **Dashboard / Reports / Alerts** | Command centre bundle; digest assembly (`monthly_digest_assembly_service`, `jobs`); portfolio routes use catalog/score modules. | **Partial:** “same truth as dashboard / score / Today” is **claimed** in digest code comments—**must be validated** whenever a new reader bypasses canonical services. | PDF/email templates may embed fields **duplicated** from models (email_service work order strings). | **Frontend** calculations (outside this repo) are a known divergence class if not guarded. |

**Loop verdict:** The platform implements **strong segments** (registry → requirements → gaps → client priority → unified tasks → scoring v2 path → multiple audits) but the **full closed loop is not a single orchestrated pipeline**. It is a **mesh of services** with **explicit** hand-written triggers. Coherence depends on **continued wiring discipline** and **tests**, not on a unified saga or remediation DTO.

---

## 3. Remediation architecture fragmentation audit

### 3.1 Compliance gaps (`compliance_gaps`)

| Aspect | Current state |
|--------|----------------|
| **Object shape** | Rich Mongo document from `ComplianceGap.to_mongo` — `gap_key`, `gap_kind`, `severity`, policy snapshot fields (`effective_applicability_state`, etc.), URLs/labels, `policy` flags including `create_issue_if_open`. |
| **Routing / action** | Priority stream maps to actions (`gaps_to_priority_actions`); unified tasks attach **`take_action`** via `resolve_take_action_for_priority_action`. |
| **Duplication** | Same obligation can theoretically surface as **gap** + **overdue requirement** + **risk** depending on rules. |
| **Real workflow** | **Persistence + optional maintenance issue** when bridge runs; **no** auto work order. |
| **Signals without valid actions** | Possible if URL/label empty or resolver returns fallback; mitigated by tests for Today CTAs but not universally proven. |
| **Audit linkage** | `COMPLIANCE_GAP_*` and `COMPLIANCE_GAP_ISSUE_CREATED` when bridge creates issue; operator gap sync **suppresses** gap lifecycle audit by design. |
| **Evidence / recalc closure** | **Not guaranteed** by gap alone—closure depends on **evidence sync**, **gap resolve** when inference drops gap, and **scoring** triggers elsewhere. |

### 3.2 Risk signals (`risk_signal_service`)

| Aspect | Current state |
|--------|----------------|
| **Object shape** | Stored signals with type, level, metadata, suggested actions (`SUGGESTED_ACTION_*` constants). |
| **Routing** | Command centre slim risk → CTA URL to `/operations/risk-signals?signal_id=…`. |
| **Duplication** | Overlaps **compliance churn** heuristics with gap/score reality. |
| **Workflow** | **Dismiss / acknowledge** style lifecycle; **not** obligation completion. |
| **Audit** | `create_audit_log` usage in service (pattern present). |
| **Closure to evidence/recalc** | **Not guaranteed** — informational layer unless user acts outside signal record. |

### 3.3 Today tasks (`unified_tasks_service` + `client_task_state_service`)

| Aspect | Current state |
|--------|----------------|
| **Object shape** | Normalised task DTO with `source_type`, `primary_action_url`, overrides, activity. |
| **Routing** | Resolver-based `take_action` for requirement-backed actions. |
| **Duplication** | Same underlying requirement may appear through multiple priority `action_type`s if not deduped upstream. |
| **Workflow** | **Inbox** semantics — snooze/dismiss/reviewed **do not** satisfy compliance. |
| **Audit** | Activity / navigation audit routes exist (`routes/client.py` Today navigation audit). |
| **Closure** | **Explicit non-closure** — strong integrity statement, weak **closed-loop** unless user follows deep link and completes evidence/job. |

### 3.4 Command Centre items (`command_center_service`)

| Aspect | Current state |
|--------|----------------|
| **Composition** | Wraps unified digest + risk signals + compliance summary; **defensive** try/except per submodule. |
| **Duplication** | If digest vs full tasks diverge on errors, **partial bundles** possible (logged warnings). |
| **Workflow** | Read-model aggregation; **no** transactional guarantee across sources. |

### 3.5 Maintenance issues (`maintenance_issues`)

| Aspect | Current state |
|--------|----------------|
| **Creation** | From gap bridge (`operational_root_key` = `gap_key`) when policy requests; general human-created issues elsewhere. |
| **Closure** | Issue status workflows exist (labels in `client_priority_stream`); **link back to gap resolve** is **not automatic** from issue closure alone (operational discipline). |
| **Audit** | `COMPLIANCE_GAP_ISSUE_CREATED` when created from bridge. |

### 3.6 Work orders (`work_orders`)

| Aspect | Current state |
|--------|----------------|
| **Shape** | Distinct collection with `work_order_id`, optional `issue_id`, `requirement_code`, `work_order_kind`. |
| **Priority stream** | SLA near/breach + open WO actions. |
| **Closure loop** | Completion should update obligation/evidence **only if** business rules and integrations wire it—**not** proven as a single saga here. |
| **Contractor** | Indexes and assignment collections exist; **contractor management** is parallel to compliance engine, not derived from it. |

### 3.7 Evidence rejection flows

| Aspect | Current state |
|--------|----------------|
| **Distribution** | Evidence authority, gap kinds (`MISMATCHED_EVIDENCE`, etc.), policy predicates. |
| **Risk** | Rejection can open/change gaps; **recalculation** depends on which service handles the mutation. |

### 3.8 Operational automations / reminders / escalations

| Aspect | Current state |
|--------|----------------|
| **Examples** | `operational_automation_service` (referenced in tests), digest/email (`email_service`), `risk_signal_regen_queue` / alert monitor filenames. |
| **Fragmentation** | Multiple channels can alert on related facts (email, in-app Today, risk). **Dedupe** across channels is **not** architecturally centralised in one module from this audit. |

---

## 4. Unified remediation DTO gap analysis

### What could become canonical (existing building blocks)

- **`gap_key`** — Stable idempotent key for gap persistence and operational bridge.
- **`take_action` envelope** (`requirement_action_resolver`) — Strong **client contract** for requirement-backed CTAs.
- **Priority action tuple** from `client_priority_stream._action` — Already a partial normalisation layer before unified tasks.

### Overlaps / conflicts

- **Gap vs risk vs overdue requirement** can surface **redundant** user actions for the same underlying statutory item.
- **`recommended_url` / `recommended_action_label`** on gap rows vs resolver outputs — potential **duplicate CTAs** if UI uses gap fields where resolver should win (tests mitigate for Today).

### Missing fields (for a canonical remediation DTO)

- **Unified `remediation_id`** spanning issue/WO/gap/risk.
- **Explicit `closure_criteria`** (what evidence state / gap absence / score event closes the item).
- **`opened_by` / `trigger_source`** (engine vs human vs operator vs import).
- **`blocking_score`** boolean — today implied by several paths but not one field.

### Dedupe risks

- Dedupe by `requirement_id` alone is **wrong** when multiple gaps exist per requirement.
- Dedupe by `gap_key` does not cover **risk signals** or **work orders**.

### Ownership ambiguity

- **Who owns closure?** Issue assignee vs property manager vs automated gap resolve—no universal owner field across types.

### Action resolution inconsistency

- Resolver path vs **hard-coded** risk CTA URL vs gap `recommended_url`.

### Proposal (design only — not implemented)

**Minimum viable canonical remediation contract (conceptual):**

| Field | Purpose |
|-------|---------|
| `remediation_key` | Stable string; default `gap_key` when source is gap; prefixed IDs for `risk:`, `wo:`, `issue:` when not. |
| `source_system` | `gap \| risk_signal \| work_order \| maintenance_issue \| requirement` |
| `client_id`, `property_id`, `requirement_id?` | Tenant scope + linkage |
| `severity`, `priority_score` | For ordering only; not legal verdict |
| `primary_action` | **Subset** of `take_action` v1 or explicit `{intent, url, label}` |
| `closure_signals` | Enum list: `gap_resolved`, `evidence_verified`, `score_recalculated`, `issue_closed`, `risk_resolved` |
| `audit_correlation_id` | UUID written to each related audit row |

**Gating rules (conceptual):**

- No persisted “user dismissed” state may imply **compliance closure** without a `closure_signal`.
- Operator applicability commands must **never** synthesise `closure_signals` without pipeline/evidence truth movement (governance).

**Audit linkage:** every transition on `remediation_key` appends to **`audit_logs`** with shared `audit_correlation_id` (future); today partially satisfied by separate audits.

**Dedupe identity:** **`(client_id, remediation_key, source_system)`** as a logical unique key for UI aggregation (future).

---

## 5. Workflow routing and CTA integrity audit

### Observed risks

- **Misleading booking language** — Resolver explicitly aliases `INTENT_BOOK_INSPECTION` to coordinated inspection evidence; product copy can still read as “book” generic trade if not curated (`requirement_action_resolver.py` comments acknowledge JOB envelope limits).
- **Generic “fix issue”** — Maintenance issues created from gaps use templated title/description; without tight UX, users may treat as **generic housekeeping** rather than statutory gap.
- **Dead CTAs** — Any divergence between **`requirementTakeActionResolver.js`** and `requirement_action_resolver.py` produces **dead or wrong routes** (backend file mandates parity).
- **Duplicate action resolvers** — Gap `recommended_*` vs resolver `take_action` — mitigated by tests for Today but **not eliminated at type level**.
- **Frontend/backend divergence** — Any new client surface that rebuilds URLs bypassing resolver breaks the contract.
- **Actions without workflows** — Risk dismiss, Today “reviewed”, snooze — **intentionally non-closing**; dangerous if product implies otherwise.

### Required authoritative path (as implemented today)

1. **Requirement-backed actions:** `requirement_action_resolver.resolve_take_action_*` → persisted/enriched on API payloads used by Today/unified tasks.
2. **Priority actions:** `client_priority_stream` → `unified_tasks_service` mapping → resolver enrichment.
3. **Risk signals:** `risk_signal_service` store + **dedicated** operations route (`command_center_service` CTA pattern).

### Routing integrity rules (recommended policy)

- **Rule R1:** Client-visible requirement CTAs **must** come from **`take_action`** when present.
- **Rule R2:** New surfaces **must not** read `compliance_gaps.recommended_url` for requirement-primary CTAs unless resolver explicitly delegates.
- **Rule R3:** Any new automation that opens human tasks **must** set **`operational_root_key`** (or successor) to a **stable** key and log **`create_audit_log`** with recoverable metadata.

### Action validation requirements

- Resolver should validate **intent + URL** presence before shipping; **integration tests** per surface (Today, exports, PDFs if they embed links).

---

## 6. Operations layer audit

### Tied to compliance closure?

| Path | Tied? | Orphan risk |
|------|-------|-------------|
| Gap resolve when inference removes gap | **Strong** | Low when sync runs successfully |
| Evidence authority sync → gap sync | **Medium–strong** | Medium on partial errors |
| Maintenance issue from gap | **Weak** | Issue can linger **after** gap resolved if not manually managed |
| Work order | **Variable** | WO can complete **without** evidence upload if process allows |
| Contractor assignment | **Parallel** | Operational **supply chain** state, not automatically compliance-closed |

### Weak-value / duplicated / noisy

- **Multiple “attention” channels** (Today, risk, digest email) for overlapping facts — value if curated; **noise** if uncorrelated.
- **Operational bridge disabled** on operator gap sync — **reduces noise** but means **no auto-issue** from that path (trade-off).
- **Contractor management** — Indexed and integrated financially (`work_orders`, `contractor_assignments`) but **not** inherently tied to **compliance recalculation** without explicit product rules.

---

## 7. Audit trail completeness analysis

### What is audited (examples)

- **General** `audit_logs` — broad actions (`create_audit_log`).
- **Gap lifecycle** — `COMPLIANCE_GAP_OPENED`, `COMPLIANCE_GAP_RESOLVED`, `COMPLIANCE_GAP_ISSUE_CREATED` (when paths enabled).
- **Applicability resolution** — `applicability_resolution_audit` append-only for operator commands.
- **Gap backfill** — aggregate audit pattern (`compliance_gap_backfill`).
- **Today inbox** — visibility actions and navigation intent (routes in `client.py`).

### Likely gaps / lineage breaks

- **No single correlation ID** across gap + issue + WO + score history for one “remediation story”.
- **Operator gap sync** intentionally **skips** gap lifecycle audit — correct to avoid noise, but **auditors must know** to consult applicability audit + gap document diffs (`updated_at`) for reconstruction.
- **Recalculation lifecycle** — score history reasons exist in scoring service, but **not every downstream consumer** may log a paired business event.
- **Notification lifecycle** — email/message logs are separate (`MessageLog` model exists); alignment with compliance events is **not** unified in this audit’s code reading.

### Reconstructability

- **Strong** for PR4 applicability (dedicated collection + immutable append).
- **Medium** for gaps when lifecycle audit enabled; **weaker** when quiet sync paths run.
- **Variable** for operational work unless staff consistently link WO/issue to `gap_key` / `requirement_id`.

---

## 8. Compliance recalculation integrity audit

### Meaningful compliance-changing events (non-exhaustive)

- Document upload/delete (reason constants in `compliance_scoring_service`).
- Requirement / evidence authority mutations (implied by scoring service filters).
- Property creation / lazy backfill / reconciliation-required semantics (`SCORE_STATUS_RECONCILIATION_REQUIRED` pattern in scoring semantics module references).

### Guaranteed recalculation?

- **Enterprise path:** `compliance_scoring_service` **claims** centralisation (“no route implements its own scoring”) — **must be enforced by code review** of routes; this document does not exhaustively grep every route.
- **Legacy path:** `compliance_score` module still exposes **legacy calculation** naming — **stale-state risk** if any client still reads legacy endpoints.

### Stale-state and eventual consistency

- **Gap sync warnings** after requirement writes → HIUA / dashboards can lag until resolved.
- **Queue operational scan truncation** → bounded HIUA enumeration on queue page.
- **Digest “same truth” claims** — depend on subgraph not throwing; partial failure → **silent partial bundle** in command centre.

### Queue / retry

- Background queues exist for risk regen (`risk_signal_regen_queue.py` filename) — retry semantics not fully audited here.

---

## 9. Dashboard / report consistency audit

### Surfaces

- **Dashboard / Command Centre** — `command_center_service` + `unified_tasks_service` + scoring summary hooks.
- **Today** — same unified tasks canonical per `routes/client.py`.
- **Portfolio** — `routes/portfolio.py` uses `catalog_compliance` helpers.
- **Compliance score** — `compliance_scoring_service` vs legacy `compliance_score` naming collision risk.
- **PDFs / digests / emails** — `email_service`, `monthly_digest_assembly_service`, `jobs` — template-driven; **risk of duplicated literals** vs live resolver strings.

### Conflicts to watch

- **Catalog portfolio** interpretation vs **persisted score headline** semantics (`SCORE_AUTHORITY_PERSISTED_HEADLINE` patterns in scoring service imports).
- **Risk level** vs **gap severity** vs **task urgency** — three scales.

### Mitigations already present

- **Runtime projection** helpers reused in scoring service docstring (`filter_requirement_rows…`, `project_requirement_row…`).
- **Tests** for authority alignment and take-action matrix (`test_compliance_authority_alignment.py`, `test_catalog_compliance_take_action_matrix.py` filenames).

---

## 10. Governance and operational debt risks

| Risk | Description |
|------|-------------|
| **Override accumulation** | Long-lived `OPERATOR_OVERRIDE` masks pipeline UNKNOWN backlog; governance runbook mitigates **process** not **schema**. |
| **Provenance drift** | Flat vs nested provenance mirrors can drift if non-selector writers exist—partially addressed by applicability stack but **not impossible**. |
| **Operational misuse** | Today dismiss / risk dismiss / snooze interpreted as compliance work done. |
| **Silent divergence** | Quiet gap sync + skipped bridge + partial command centre try/except → **silent** partial truth in UI. |
| **Reconciliation dependency** | Tenant delivery / policy backfill jobs repair snapshots—**operational dependency** on job schedules. |
| **Support burden** | Multiple audits + multiple DTOs + override semantics increase **training** cost for support/engineering. |

---

## 11. Priority-ranked unresolved items

### P0 — launch blockers (architecture / integrity)

- **Prove single scoring authority end-to-end** — Eliminate or isolate **legacy** `compliance_score` paths from client-visible KPIs; document which endpoints are authoritative.
- **CTA parity enforcement** — CI contract: backend resolver + frontend resolver **must** ship together; block releases on drift.
- **Remediation correlation** — Minimum **correlation strategy** (even documentation + ops query recipes) until a DTO exists.

### P1 — integrity gaps

- **Unified remediation read model** — Read-side aggregator API that joins gap/issue/WO/risk by keys (even before write-side DTO).
- **Explicit closure events** — When score recalculates, emit auditable **business milestone** tied to `property_id` / `requirement_id`.
- **Risk vs gap dedupe policy** — Product rules for when to show both vs collapse.

### P2 — operational improvements

- **Command centre hardening** — Fail-fast or degraded-mode banner when a subgraph errors (instead of silent subset).
- **Contractor loop closure** — Explicit mapping rules from WO completion → evidence expectation → score.

### DEFERRED — acceptable or product-dependent

- **Full saga orchestration** — Large investment; current mesh may remain if governance + observability improve.
- **ML risk scoring** — Explicitly out of scope in `risk_signal_service` docstring.

---

## 12. Recommended next implementation order

1. **Scoring authority audit (read-only code + route grep)** — Publish internal matrix: endpoint → scoring module → persisted fields consumed by dashboard/Today/portfolio.
2. **CTA contract CI** — Cross-repo check or golden tests for resolver parity; block on mismatch.
3. **Remediation correlation MVP** — Ops runbook queries: given `requirement_id`, list gaps (`gap_key`), issues (`operational_root_key`), WO (`issue_id` / codes), risk ids; store recipe in docs until automated.
4. **Read-model aggregator spike** — Single internal endpoint returning unified remediation rows (no new client product until validated).
5. **Closure audit events** — When score recalculates, append structured audit with reason + linkage ids.
6. **Dedupe policy for risk+gap** — Product decision then backend filtering in `unified_tasks_service` if approved.
7. **Contractor completion → evidence checklist** — Optional workflow hooks after WO terminal states.

---

## Appendix — key modules referenced

| Concern | Modules |
|---------|---------|
| Gaps | `compliance_gap_engine.py`, `compliance_gap_sync.py`, `compliance_gap_operational_bridge.py`, `compliance_gap_policy_aggregate.py` |
| Priority / Today | `client_priority_stream.py`, `unified_tasks_service.py`, `command_center_service.py` |
| CTAs | `requirement_action_resolver.py`, `requirement_action_links.py` |
| Risk | `risk_signal_service.py`, `risk_signal_regen_*.py` |
| Scoring | `compliance_scoring_service.py`, `compliance_score.py`, `catalog_compliance.py` |
| Applicability governance | `applicability_*`, `applicability_resolution_queue.py`, `applicability_resolution_audit.py` |
| Evidence | `requirement_evidence_authority.py` |
| Ops runbook | `docs/RUNBOOK_APPLICABILITY_RESOLUTION_OPERATIONS.md` |

---

*This document is descriptive. Update it when major architectural seams change (new DTOs, new audit collections, or scoring authority moves).*
