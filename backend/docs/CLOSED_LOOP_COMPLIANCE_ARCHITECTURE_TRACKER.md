# Closed-loop compliance architecture — implementation tracker

**Purpose:** Coordinate cross-cutting closed-loop work (applicability, score authority, remediation identity, CTAs, events, audit lineage) without ad-hoc scope creep. This file is **governance and planning only**; it does not replace design docs or runbooks.

**Companion:** `CLOSED_LOOP_ARCHITECTURAL_GAP_ANALYSIS.md` (audit / gap framing; normative doctrine **§18**). **Controlled beta (support/admin operations):** `RUNBOOK_CONTROLLED_BETA_OPERATIONS.md`. **Product governance (value, trust, retention, workflow continuity — not a tracker):** `PROPERTY_COMPLIANCE_OS_GAP_AND_RETENTION_AUDIT.md`. **Product value / retention gap tracker (not architecture):** `PRODUCT_VALUE_GAP_TRACKER.md`.

**Last updated:** 2026-05-17 (Launch **F1 DONE**; **G1 IN_PROGRESS** — T1 harness + IMPLEMENTED_PENDING_VERIFICATION review-preparation package; **no** status promotion; surveillance execution pending).

**Launch-gated obligation recovery:** Finishable units **A1–G2** live in `docs/launch/LAUNCH_AUTHORITY_TRACKER.md` § Recovery implementation plan. **No duplicate tracker.** This section maps streams only.

---

## Implementation Order Rules

1. **P0 streams must be completed before P1 streams** unless explicitly approved (document approver and rationale in the stream’s `risks` or `blocked-by` section).
2. **No implementation PR may start** unless it **names the tracker stream** it belongs to (PR title or description: e.g. `Stream A — …`).
3. **Every PR** that ships backend or tracker-affecting behaviour must **update this tracker** after merge (see **Architecture Authority Rules** §5–§7 for required PR fields and duplicate-truth stop rule). **Every Cursor implementation prompt** that ships backend behaviour must likewise update this tracker (`completed work`, `remaining tasks`, `risks`, implementation phases / dates).
4. **No new feature** may bypass **Score Authority**, **CTA Contract**, **Remediation Identity**, **Event Contract**, or **Audit Lineage** rules as defined in acceptance criteria for streams B–F (and applicability separation for Stream A). If a feature cannot comply, it is blocked until criteria are relaxed in writing here.
5. **If implementation discovers a new risk**, **update this tracker before coding further** (add to `risks` and, if needed, `blocked-by` / `depends-on`).

---

## Architecture Authority Rules

1. **Every domain must have one named authority** — Each closed-loop domain (applicability, score, remediation correlation, CTA, event fan-out, audit) names a single module, contract, or document as the source of truth for that concern. See **Named authorities (this programme)** below.
2. **New code must reuse the named authority** instead of creating parallel logic (no second scoring path, second resolver, or second applicability merge semantics for the same concern).
3. **Diagnostic-only exceptions** must be clearly labelled **admin-only** and/or **non-authoritative** in code (docstring/comment) and, if user-visible, in this tracker or linked runbook so they cannot be mistaken for product truth.
4. **Completed streams must not be rewritten** unless this tracker explicitly marks the stream **Reopen** (date, approver, rationale). Partial or in-progress streams remain open to narrow PRs that respect these rules.
5. **Every PR must update this tracker** — At minimum: bump **Last updated**, adjust the relevant stream’s `completed work` / `remaining tasks` / `risks` / implementation phases, and append the **Changelog (tracker edits only)** row for that PR.
6. **Every PR description must state:**
   - **Stream** (A–F, exact label),
   - **Authority reused** (named module/API/doc matrix row),
   - **Files changed** (high-signal list),
   - **Tests run** (commands or CI job names),
   - **Remaining risks** (short, honest).
7. **If duplicate truth is discovered** (two sources diverge for the same obligation, score, CTA, or audit story), **stop implementation** and update this tracker (`risks`, `blocked-by`, or new matrix row) **before** further coding.

### Named authorities (this programme)

| Domain / stream | Named authority |
|-----------------|-----------------|
| **Stream A — Applicability** | `resolve_policy_facts` + `applicability_provenance_pipeline` (pipeline write path); `applicability_effective_resolver` (effective read); `applicability_operator_actions` + `applicability_resolution_audit` (operator path). |
| **Stream B — Score** | `compliance_scoring_service.recalculate_and_persist` (authoritative enterprise write); runtime filter + projection helpers referenced from scoring module docstrings (read alignment with portal). |
| **Stream C — Remediation correlation** | **`STREAM_C_REMEDIATION_CORRELATION_RUNBOOK.md`** (read-only correlation vocabulary + join recipes); code authorities unchanged: **`gap_key`**, `operational_root_key` bridge, `client_priority_stream` → `unified_tasks_service`. |
| **Stream D — CTA (requirements)** | `requirement_action_resolver` (`take_action` / `resolve_take_action_*`). |
| **Stream D — CTA (risk)** | `risk_signal_service` + Command Centre operations URL pattern (intentionally not the requirement resolver). |
| **Stream D — CTA inventory (read-only)** | `STREAM_D_CTA_PRODUCER_CONSUMER_MATRIX.md` — producer/consumer audit; does not replace code authorities above. |
| **Stream D — CTA parity freeze (read-only + BE tests)** | `STREAM_D_CTA_PARITY_ENFORCEMENT.md` + `tests/fixtures/cta_parity_fixtures.py` + `tests/test_cta_parity_contract.py`; frontend mirror remains `requirementTakeActionResolver.js`. |
| **Stream E — Event fan-out** | `STREAM_E_MUTATION_FANOUT_MATRIX.md` (Stream E phase 1) + appendix **Outcome engine** (`compliance_outcome_engine` / `ALL_EVENTS`); code must match matrix rows and contract tests. |
| **Stream F — Audit** | `create_audit_log`; `applicability_resolution_audit` append-only contract; gap lifecycle audit flags as documented in gap sync; **operational joins:** `STREAM_F_FORENSICS_JOIN_RECIPE.md`; **correlation / reconstruction:** `STREAM_F_PHASE2_CORRELATION_PROPAGATION.md`, `STREAM_F_RECONSTRUCTION_CONSISTENCY.md`. |
| **Controlled beta — Support / admin operations** | **`RUNBOOK_CONTROLLED_BETA_OPERATIONS.md`** — recovery discipline, forbidden actions, escalation, monitoring, and beta entry checklist; **does not** waive stream acceptance criteria or replace Streams **B–F** matrices. |

### Stream lifecycle (rule 4)

| Stream | Status for rewrite rule | Notes |
|--------|-------------------------|--------|
| A | **Open** | In progress; narrow PRs allowed. |
| B | **Open (partial)** | Not “complete”; matrix-first, then stragglers. |
| C | **Open (partial)** | **Correlation runbook published** (`STREAM_C_REMEDIATION_CORRELATION_RUNBOOK.md`); internal read-model spike + dedupe policy remain **product-gated**. |
| D | **Open (partial)** | Phase 1 matrix; **Phase 2** B1/B2 + **B3** shipped; **Phase 4** backend parity fixtures + contract tests + enforcement doc **shipped**; phase 3 + optional FE CI gate open. |
| E | **Open (partial)** | Phase 1 matrix; **E2.1–E2.3** gap fixes; **Phase 3** structured fan-out logs; phase 4 (outbox/debounce) deferred. |
| F | **Open (partial)** | Phase 1 join recipe + Phase 2 docs; **F2-A** + **F2-B** correlation **in code**; optional F2-C / F2-D. |

No stream is **Closed** yet. When a stream is closed, add a row here: **Closed** + date + link to PR; reopen only with explicit **Reopen** line in this table.

---

## Recommended cross-stream implementation order

Execute in this order unless a stream’s **blocked-by** requires a pause (document rationale if deviating).

1. **Stream B —** Score authority matrix (**complete** — `STREAM_B_SCORING_AUTHORITY_MATRIX.md`): endpoint → scoring source → persisted vs computed → authority class → consumers.
2. **Stream E —** Event consistency matrix (**phase 1 complete** — `STREAM_E_MUTATION_FANOUT_MATRIX.md`): mutation → gap sync Y/N/quiet → score recalc Y/N → audit types; quiet operator semantics documented.
3. **Stream D —** CTA contract (**phase 1 matrix** published); **phase 2 (B1/B2/B3)** guardrails + tenant_request metadata slice **shipped**; phases 3–4 per tracker.
4. **Stream F —** Audit join recipe (forensics doc: how to reconstruct one story across `audit_logs`, `applicability_resolution_audit`, gap lifecycle, score history).
5. ~~**Stream C —** Remediation correlation runbook~~ — **Done (2026-04-30):** `STREAM_C_REMEDIATION_CORRELATION_RUNBOOK.md` (stable keys, closure vs non-closure, `remediation_key` / `source_system`, MV row shape, dedupe/closure/forbidden rules; companion to `STREAM_F_FORENSICS_JOIN_RECIPE.md`).
6. ~~**Stream C —** Internal read-model spike (v1)~~ — **Shipped (2026-05-01):** `POST /api/admin/support/remediation-correlation-view` behind `FEATURE_REMEDIATION_CORRELATION_VIEW_V1`; `services/remediation_correlation_view.py`; runbook §11; tests `test_remediation_correlation_view_v1.py`. Portfolio-wide / client-wide scans and deferred sources remain out of scope (see runbook §11).
7. **Stream A —** Residual provenance sweeps (grep merge/read paths; reader alignment; operator regression tests) after matrices and runbook reduce blind spots.

**Obligation recovery programme (launch-gated, 2026-05-16):** Execute **only** via `LAUNCH_AUTHORITY_TRACKER.md` units **A1→G2**. **No implementation PR** for streams B–F obligation visibility until **A1** classifies tenant and **A2/A3/B1/B2** complete when triggered.

| Launch unit | Primary stream(s) | Named authority (reuse) | Blocked until |
|-------------|-------------------|---------------------------|---------------|
| **A1** | — (ops proof) | `PUBLISHED_REGISTRY_CLIENT_TRUTH_AUDIT.md` | — |
| **A2, A3** | A (materialisation) | `materialize_requirements_for_property`, `provisioning._generate_requirements` | A1 |
| **B1, B2, B3** | B (read alignment) + registry | `requirement_client_runtime_surface`, `kpi_authority_projection_contract` | A1 (+ A2 if A-only) |
| **C1** | B, E | `recalculate_and_persist`, `enqueue_compliance_recalc`, `compliance_recalc_queue` | **DONE** 2026-05-16 — pilot R1/R2/R3 replay stability, C1-M2 legitimate enqueue, recalc stability, reclaim observability, §9 regression (41 passed); artifacts `backend/docs/audit/c1_*`; watchlist: 11 upsert passes do not cause queue/recalc churn on R2/R3 (`LAUNCH_AUTHORITY_TRACKER.md` § C1 closure) |
| **C2** | B, E, C (remediation read-model) | `compliance_gap_sync`, `client_priority_stream`, `unified_tasks_service`, `kpi_authority_projection_contract`, `recalculate_and_persist` (upstream); correlation via queue/score history/audit | **DONE** 2026-05-16 — pilot normalized staging `c2_pass=true`; C2a root cause `regenerated_ids` + `verification_fingerprint_normalization` (verification-only fix); RC-8/RC-13/RC-14 cleared; no product task-id fix; watchlist: volatile `risk_signal:rs_*` ids non-blocking (`LAUNCH_AUTHORITY_TRACKER.md` § C2 closure; artifacts `backend/docs/audit/c2_*`, `c2a_task_drift_analysis_*`) |
| **D1** | E, F | `authority_mutation_fanout`, `requirement_transition_observability`, `workflow_runtime_activation_registry`; `STREAM_E_MUTATION_FANOUT_MATRIX.md` | **DONE** 2026-05-17 — D1b harness `d1b_harness_rerun_v3` `d1_pass=true`; D1-RC-15 harness baseline cleared; replay lineage stable (split R2/R3 vs M2); no true propagation instability; `d1b_*` authoritative / `d1_*` preserved; **no** product route/fanout/queue/scheduler/notification changes (`LAUNCH_AUTHORITY_TRACKER.md` § D1 closure) |
| **D1b** | E, F | D1 verification harness (`d1_staging_verification.py`, `d1_snapshot.py`) | **DONE** 2026-05-17 — methodology refinement only (parent D1) |
| **D2** | E, F | Legacy bridge inventory | After D1 or parallel when approved |
| **E1** | B, E, F | `requirement_evidence_authority`, `document_operational_state`, `evidence_review_verify`, `AUTHORITY_WRITE_PATH_RECONCILIATION.md`, `COMPLIANCE_CLIENT_STATUS_AUTHORITY.md` | **VERIFIED** 2026-05-17 — `e1b_pass=true`; **E1a**/**E1b DONE**; parent **not DONE** (governance review pause) |
| **F1** | — (notifications) | `NOTIFICATION_GOVERNANCE_INVENTORY.json`, `notification_orchestrator`, `message_logs` | **DONE** 2026-05-17 — governed **F1-M1** replay proof; `f1a_*` authoritative; `f1_*` + **F1-RC-15** preserved (harness history); **F1-M2–M7** unproven; no remediation (`LAUNCH_AUTHORITY_TRACKER.md` § F1 DONE closure) |
| **G1** | Post A–F proof domains | `LAUNCH_AUTHORITY_TRACKER.md` § G1; Tier-0 `audit/*_{slug}.json`; `launch_baseline_manifest_*` | **IN_PROGRESS** (2026-05-17) — **Tranche T1 harness only**; signoff `ANTI_EXPANSION` / `READ_ONLY_SURVEILLANCE_ONLY`; **G1-P1**, **G1-P2**, **G1-P5**, **G1-RC-21**, **G1-RC-27**; staging surveillance **not** authorised |
| **G2** | F, controlled beta | `RUNBOOK_CONTROLLED_BETA_OPERATIONS.md`; admin explain | **NOT_STARTED** — parallel observability hardening (unchanged) |

**PR naming when recovery touches a stream:** `Stream <X> — <launch unit> — <short description>` (e.g. `Stream E — D1 — provisioning fanout trace`).

**Recovery implementation rules (mandatory):** Each launch unit **A1–G2** selected for coding must follow `LAUNCH_AUTHORITY_TRACKER.md` § **Recovery unit implementation contract**:

- No partial implementation; no placeholder wiring; no backend-only if other layers are required.
- Definition of Done written **before** `IN_PROGRESS`.
- Status path: `IN_PROGRESS` → `IMPLEMENTED_PENDING_VERIFICATION` → `READY_FOR_STAGING_VERIFICATION` → `VERIFIED` → **DONE** (ten gates).
- Split into sub-units (e.g. `B2a`) before coding if not safely end-to-end in one train.
- PR must update **both** this tracker (stream row) and launch tracker (unit status + closure evidence).

---

## Stream A — Applicability Governance

| Field | Content |
|--------|---------|
| **status** | In progress — provenance selector, effective resolver, PR4 operator commands, resolution queue, and gap refresh after operator path exist; discipline remains on readers/writers and legacy coexistence. |
| **priority** | P0 |
| **completed work** | Effective vs pipeline read model; append-only `applicability_resolution_audit`; internal resolution queue; operator reason enums; post-operator gap sync (quiet lifecycle where designed); runbook for ops boundaries; materialization/backfill provenance merge uses `pipeline_applicability_state` where wired (see services + tests). |
| **remaining tasks** | Ensure **all** writers/readers that touch applicability use canonical facts (`pipeline_applicability_state` vs effective); eliminate accidental dual-truth in new routes; document any intentional exception in this tracker. |
| **risks** | Long-lived `OPERATOR_OVERRIDE` without pipeline repair forks truth; reporting surfaces that bypass runtime filters disagree with portal KPIs. |
| **blocked-by / depends-on** | **Depends-on:** policy/registry publish semantics (materialization timing). **Execute after** global steps 1–6 so score/event/CTA/audit/remediation inventories exist. **Blocked-by:** none unless Score/Event streams need a shared correlation id (note cross-links when introduced). |

**Acceptance criteria:** (1) Single documented rule for which field is “pipeline truth” vs “effective truth” on requirement rows. (2) No merge path overwrites stored pipeline applicability with operator-influenced effective state. (3) `REVOKE_OVERRIDE` restores effective to true pipeline truth after pipeline correction. (4) Operator actions audited with required keys. (5) Runbook-aligned exception paths documented here if any.

### Architectural authority

- **Pipeline truth** on requirement rows: provenance patches from policy resolution + materialization/backfill paths calling `merge_provenance_into_requirement_patch` / `apply_provenance_and_audit_after_requirement_patch` must use **`pipeline_applicability_state`** from `resolve_policy_facts`, not effective `applicability_state` when provenance exists.
- **Effective truth** for obligation semantics: `applicability_effective_resolver` + legacy dual-write per `APPLICABILITY_PROVENANCE_LEGACY_APPLICABILITY_STATE.md`.
- **Operator mutations:** `applicability_operator_actions` + append-only `applicability_resolution_audit`; ops boundaries in `RUNBOOK_APPLICABILITY_RESOLUTION_OPERATIONS.md`.

### Forbidden patterns

- Passing effective `applicability_state` into provenance merge as pipeline input.
- New routes or aggregations for client KPIs reading raw `requirements` without **`filter_requirement_rows_for_client_runtime_surfaces`** / **`project_requirement_row_client_runtime`** (or documented equivalent).
- Writing applicability while bypassing policy facts normalizer / provenance selector where the rest of the stack does not.

### Affected modules (non-exhaustive)

`policy_field_normalizer.py` (and related policy facts), `applicability_provenance_pipeline.py`, `applicability_effective_resolver.py`, `applicability_operator_actions.py`, `applicability_resolution_audit.py`, `applicability_resolution_queue.py`, `requirement_materialization_service.py`, `compliance_policy_backfill_service.py`, `compliance_registry_*`, `compliance_gap_sync.py` (post-operator quiet paths), tests `test_applicability_*`, `test_requirement_materialization_*`, `test_compliance_policy_backfill_*`.

### Required audit before implementation

- Grep: all call sites of `merge_provenance_into_requirement_patch`, `apply_provenance_and_audit_after_requirement_patch`, direct writes to applicability/provenance on `requirements`.
- Confirm each path’s pipeline vs effective semantics vs `resolve_policy_facts` keys; cross-check runbook (exception vs pipeline truth, revoke).

### Implementation phases

Each numbered phase is an intended **separate PR**; title format `Stream A — <phase>`. PR description must satisfy **Architecture Authority Rules** §6.

1. **Stream A — Applicability write-path inventory** — Doc PR: table writer → fields → pipeline vs effective; link runbook.
2. **Stream A — Residual provenance merge fixes** — Code PR only if grep finds wrong parameters; extend existing provenance/materialization/backfill tests.
3. **Stream A — Reader alignment sweep** — Small vertical PRs (e.g. portfolio/catalog, then reporting/scripts); each uses canonical helpers or documents a tracker exception in the same PR.
4. **Stream A — Operator edge regression pack** — Tests for `OPERATOR_OVERRIDE` / `REVOKE_OVERRIDE` with pipeline correction (reuse operator + gap sync fixtures where present).

### Acceptance tests (stream-specific)

- Unit/integration: pipeline not overwritten by effective in provenance merge; materialization/backfill pass `pipeline_applicability_state`.
- New reader paths: tests for projection vs runtime filter expectations, or doc-only exception with ticket reference.

### Rollout risks

- Wide reader sweeps in one PR — prefer vertical slices per surface.
- Legacy rows without provenance — cover normalizer fallback already defined in code/docs.

---

## Stream B — Score Authority Consolidation

| Field | Content |
|--------|---------|
| **status** | Partial — single writer for property score; admin `validate-compliance-score` `fix=true` **implemented** via `recalculate_and_persist` + `REASON_ADMIN_VALIDATOR_REPAIR`. |
| **priority** | P0 |
| **current phase** | **Phase 4 — Straggler wiring** (matrix: `STREAM_E_MUTATION_FANOUT_MATRIX.md`) or **Digest / Command Centre** hardening. |
| **completed work** | Scoring matrix; legacy labelling; **admin repair refactor:** removed direct `update_one` / `property_compliance_score_history` / `log_score_change` from `routes/admin.py` repair path; `COMPLIANCE_SCORE_MISMATCH_DETECTED` + `correlation_id`; `recalculate_and_persist` → `COMPLIANCE_SCORE_UPDATED`; then `COMPLIANCE_SCORE_REPAIRED` with shared `correlation_id` + `canonical_reason`. Tests: `TestValidateComplianceScoreEndpoint`. Docs: `STREAM_B_SCORING_AUTHORITY_MATRIX.md` §2, §5a, §9. **Straggler (2026-05-01):** after standalone `sync_requirement_evidence_authority` on **admin** document authority routes + **client** guided evidence create/verify, **`enqueue_compliance_recalc`** (`TRIGGER_DOC_STATUS_CHANGED`, stable `AUTHORITY_SYNC:` / `GUIDED_EVIDENCE_*` correlation ids, queue dedupe). Tests: `test_admin_authority_sync_recalc_enqueue.py`, `test_client_compliance_evidence_safety.py`; matrix row 9 updated. **Async honesty slice 1 (2026-05-02, FE only):** client dashboard + compliance score page copy for `score_status` / `score_status_message` / last-calculated + drivers-vs-headline note; `scoreFreshnessUi.js` + Jest tests (no backend/API changes). **Async honesty slice 2 (2026-04-30, FE only):** `ClientCommandCenterPage.js` degraded compliance bundle copy + optional `score_status_message`; `PropertyDetailPage.js` stored-vs-preview note when explainability loads + `score_status_message` / `last_calculated_at`; Command Centre strip shows `score_status_message` whenever set; tests `ClientCommandCenterPage.test.js` (degraded describe), `PropertyDetailPage.asyncHonesty.test.js`, `scoreFreshnessUi.test.js`. **Async honesty slice 3 (2026-04-30):** monthly digest payload `digest_snapshot_framing_line`; `email_service` HTML + plain text snapshot + headline `score_status_message`; `monthly_digest_pdf_service` executive summary snapshot banner + score status / last calculated / headline note rows; `reporting_service` compliance CSV `score_status_message` + `export_snapshot_note`; `routes/reports.py` `score-drivers.csv` legacy `#` snapshot rows + `scoring_metadata` rows `score_status_message` + `export_generated_at`; tests `test_monthly_digest_enterprise.py`, `test_reporting_compliance_export_snapshot.py`. **Score-explanation PDF (2026-04-30):** `pdf_report_builder.build_score_explanation_report` — **Snapshot as of** (same `last_calculated_at` / `portfolio_last_calculated_at` / `score_last_calculated_at` authority as cover), optional **Headline note** from `score_status_message`, **Updates** / bucket-missing / empty-drivers copy aligned with persisted headline vs requirement rows at export time; removed “live calculator” phrasing; tests `test_pdf_report_builder.py`. **Evidence Readiness PDF (2026-04-30):** `build_portfolio_report` / `build_property_report` — **Snapshot generated at** (export UTC), executive **Score status** / **Last score calculation** / **Headline note** from `aggregate_persisted_portfolio_headline` (plus property-doc `score_status_message` on property scope when distinct), portfolio breakdown score column with per-property persisted meta; methodology avoids “live portal” truth wording; tests `test_pdf_report_builder.py`. **Professional compliance summary PDF (2026-04-30):** `professional_reports.generate_compliance_summary_pdf` — **Snapshot generated at**, **Headline note** from `score_status_message`, **Last score calculation (persisted batch)** with plain-language distinction from PDF generation time; executive completion-rate copy avoids implying live portal truth; tests `test_professional_reports_authority_labels.py`. |
| **remaining tasks** | Further stragglers per `STREAM_E_MUTATION_FANOUT_MATRIX.md` (e.g. applicability operator, outcome partial branches); digest/CC tests where claims exist. |
| **risks** | **Triple audit** on repair (mismatch + updated + repaired) may inflate ops volume vs old two-step + partial write; dashboards filtering only `REPAIRED` should include `UPDATED` correlation for full story; `calculate_property_compliance` runs twice per repair (compare + inside recalc). |
| **blocked-by / depends-on** | **Depends-on:** Stream A for obligation truth fed into scoring; **Stream E** phase 1 matrix (**published**) for straggler prioritisation. **Blocked-by:** none unless product freezes scoring API. |

**Acceptance criteria:** (1) Documented list of **authoritative** score write paths and triggers. (2) No new surface computes property compliance score outside that authority without explicit tracker exception. (3) Staleness/repair behaviour documented and test-backed for declared paths. (4) Legacy path either removed, wrapped, or labelled “non-authoritative” in code + here.

### Findings (Stream B — scoring authority matrix audit, 2026-04-30)

- **Authoritative property score writers:** `recalculate_and_persist` (including `job_runner` queue worker), synchronous `recalculate_and_persist` on jurisdiction patch in `routes/properties.py`, `compliance_outcome_engine` outcome handler.
- **Admin repair:** `routes/admin.py` `validate-compliance-score` with `fix=true` calls **`recalculate_and_persist`** with **`REASON_ADMIN_VALIDATOR_REPAIR`**; route emits mismatch + repaired audits with shared **`correlation_id`** (canonical **`COMPLIANCE_SCORE_UPDATED`** from scoring service).
- **No callers found** for `compliance_score._calculate_compliance_score_legacy_from_db` (dead / reference-only risk only).
- **Reads:** Client headline + stats flow through `compliance_score.calculate_compliance_score` and `get_authoritative_property_compliance_for_client`; Command Centre, portfolio, reports, digest, ops summary, score timeline fallback — all mapped in matrix doc.
- **Enqueue-only:** Broad `enqueue_compliance_recalc` surface area (documents, properties, client, admin, jobs, governed rules, provisioning, evidence review, etc.) — does not persist score until worker runs `recalculate_and_persist`.

### Recommended next PR

**Stream B — Straggler wiring** (use `STREAM_E_MUTATION_FANOUT_MATRIX.md` “Recalc today?” / “Missing-wiring risk”) **or** **Stream B — Digest / Command Centre** alignment tests.

### Architectural authority

- **Authoritative enterprise write path:** `compliance_scoring_service.recalculate_and_persist` (history/reasons semantics per module).
- **Read alignment:** scoring module docstring pattern — runtime filter + projection helpers consistent with portal KPIs.

### Forbidden patterns

- New routes/jobs persisting property compliance scores outside `compliance_scoring_service` without tracker exception.
- Client-visible KPIs using `compliance_score` legacy entrypoints without explicit “non-authoritative” boundary in code + this tracker.

### Affected modules (non-exhaustive)

`compliance_scoring_service.py`, `compliance_scoring_v2.py`, `compliance_score.py`, `compliance_recalc_queue.py`, `job_runner.py`, `routes/properties.py`, `routes/admin.py`, `routes/client.py`, `routes/portfolio.py`, `routes/reports.py`, `routes/ops_compliance.py`, `command_center_service.py`, `monthly_digest_assembly_service.py`, `monthly_digest_pdf_service.py`, `email_service.py`, `reporting_service.py`, `compliance_trending.py`, `score_events_service.py`, `compliance_outcome_engine.py`, `score_ledger_service.py`, `risk_signal_service.py`, `catalog_compliance.py` (portfolio lens), `compliance_explain_admin_service.py`, authority tests (`test_compliance_*`, `test_batch*_score_*`).

### Required audit before implementation

- Read-only **route + job grep**: matrix **endpoint → scoring module → persisted fields → consumers** (dashboard, Today, portfolio, digest, PDF/email if applicable); mark authoritative vs legacy vs read-repair-only. **→ Done** for current backend tree; live in `STREAM_B_SCORING_AUTHORITY_MATRIX.md`.

### Implementation phases

Each numbered phase is an intended **separate PR**; title format `Stream B — <phase>`. PR description must satisfy **Architecture Authority Rules** §6.

1. ~~**Stream B — Scoring authority matrix**~~ — **Done:** `STREAM_B_SCORING_AUTHORITY_MATRIX.md`.
2. ~~**Stream B — Legacy path labelling**~~ — **Done.**
3. ~~**Stream B — Admin repair vs authority**~~ — **Done:** `recalculate_and_persist` + `REASON_ADMIN_VALIDATOR_REPAIR`; audits + `correlation_id`.
4. **Stream B — Straggler wiring** — After Stream E matrix (**available**): one micro-PR per proven missing `enqueue_compliance_recalc` / sync recalc.
5. **Stream B — Digest / Command Centre alignment** — Targeted tests / degraded-mode docs once stragglers are known.

### Acceptance tests (stream-specific)

- Tests for persisted score headline vs catalog (`SCORE_AUTHORITY_PERSISTED_HEADLINE`-style patterns where present).
- Regression tests for each newly wired recalculation path.

### Rollout risks

- Over-triggering recalculation (cost/latency) — keep wiring PRs minimal.
- Lazy repair masking missing triggers — matrix must distinguish intentional vs accidental reliance on read-repair.

---

## Stream C — Remediation Architecture Unification

| Field | Content |
|--------|---------|
| **status** | Partial — **correlation runbook + internal read view v1 shipped** (`FEATURE_REMEDIATION_CORRELATION_VIEW_V1`); still no single persisted remediation lifecycle record (by design until product approves broader scope). |
| **priority** | P0 |
| **completed work** | Unified tasks DTO; priority stream → resolver-backed CTAs for requirement-backed actions; optional gap→issue bridge (idempotent per `gap_key`); explicit inbox non-closure semantics documented. **`STREAM_C_REMEDIATION_CORRELATION_RUNBOOK.md`:** per-source stable keys, linked IDs, closure rules, dedupe hazards. **Internal API v1:** `POST /api/admin/support/remediation-correlation-view` + `services/remediation_correlation_view.py` (property-scoped, read-only, caps, `non_authoritative` + disclaimer, tightened score-change mapping advisory); runbook §11; support note `SUPPORT_REMEDIATION_CORRELATION_VIEW_V1.md`. |
| **remaining tasks** | Dedupe policy (risk vs gap) after product rules; bridge/quiet-sync doc slice (Next PRs item 4); optional v2+ scope (documents, requirements anchor, portfolio) only with tracker approval. |
| **risks** | Duplicate surfacing of same obligation; operators treating dismiss/snooze as compliance closure; optional bridge off on operator sync path; internal view misread as SSOT — mitigated by fixed disclaimer + admin-only flag. |
| **blocked-by / depends-on** | **Depends-on:** Stream D for stable requirement CTAs; Stream B for “done means score/gap reflects reality”; Stream F for audit linkage (`STREAM_F_FORENSICS_JOIN_RECIPE.md`). **Blocked-by:** product decision on dedupe collapse rules and any v2 read-model scope beyond v1 caps/sources. |

**Acceptance criteria:** (1) Documented **one** remediation correlation key or lifecycle model for in-scope entities. (2) No new remediation source added without mapping into that model or documented exception. (3) Inbox actions remain non-authoritative for compliance closure unless explicitly redesigned and recorded here.

### Architectural authority

- **Stable keys today:** `gap_key` on `compliance_gaps`; `operational_root_key` = `gap_key` when bridge creates issues; priority stream → `unified_tasks_service` as client aggregation.
- **Conceptual contract** (gap analysis §4, design-only): correlation via `remediation_key` / `(client_id, remediation_key, source_system)` — **documented** in `STREAM_C_REMEDIATION_CORRELATION_RUNBOOK.md` §3–5; no new persisted lifecycle entity without product approval.

### Forbidden patterns

- New persisted “single remediation lifecycle” store without explicit product approval and tracker update.
- Dedupe by **`requirement_id` alone** when multiple gaps per requirement.
- Treating Today snooze/dismiss/reviewed or risk dismiss as compliance closure.

### Affected modules (non-exhaustive)

`compliance_gap_engine.py`, `compliance_gap_sync.py`, `compliance_gap_operational_bridge.py`, `client_priority_stream.py`, `unified_tasks_service.py`, `client_task_state_service.py`, `command_center_service.py`, `maintenance_issues_service.py` (bridge path), work order routes/models, `risk_signal_service.py`.

### Required audit before implementation

- Map **source_system** → stable key: gap (`gap_key`), risk (signal id / command centre URL pattern), WO/issue linkage fields per gap analysis §3.
- Record product gate: correlation-only MVP vs internal read-model spike before coding beyond docs/runbook.

### Next PRs (concrete)

1. ~~**Stream C — Remediation correlation runbook**~~ — **Done (2026-04-30):** `STREAM_C_REMEDIATION_CORRELATION_RUNBOOK.md` (**global step 5**).
2. ~~**Stream C — Internal read-model spike (v1)**~~ — **Done (2026-05-01):** correlation view endpoint + runbook §11; extend or add script-backed joins only with tracker update (**global step 6** follow-ups).
3. **Stream C — Dedupe policy (risk vs gap)** — **After product rules:** narrow change in `unified_tasks_service` or priority stream.
4. **Stream C — Bridge / quiet-sync documentation** — Doc PR: operator gap sync disables bridge by design; link from runbook.

### Acceptance tests (stream-specific)

- Existing unified-task / CTA tests stay green; add tests only for documented dedupe or key exposure changes.
- If internal read-model: contract tests on shape + stable keys; no external client exposure unless explicitly routed.

### Rollout risks

- Dedupe collapses user-visible items incorrectly — product-owned rules first.
- Internal endpoint misuse — match existing admin-only / feature-flag patterns.

---

## Stream D — CTA Contract Integrity

| Field | Content |
|--------|---------|
| **status** | Partial — phase **1** matrix + **Phase 2** B1/B2/B3 **shipped**; phases 3–4 open. |
| **priority** | P1 |
| **current phase** | **Phase 3 — Resolver validation hardening** (non-empty navigable URL where contract expects) **or** **Phase 4** cross-repo parity CI. |
| **completed work** | **Phase 1:** `STREAM_D_CTA_PRODUCER_CONSUMER_MATRIX.md` (producer/consumer audit + §3 exceptions). **Phase 2 (2026-04-30):** **B1/B2** — `gaps_to_priority_actions` + `_primary_action_fields` gap/canonical alignment (`test_compliance_gap_engine_governed`, `test_today_requirement_cta_authority`). **B3** — `_tenant_request_tasks` attaches **`metadata.take_action`** when `property_id`+`requirement_id` resolve a requirement row (`primary_action_*` unchanged); **`logger.warning`** + `compliance_fanout_extra(op="tenant_request_cta", stage="partial")` when canonical primary is not standard `/documents` navigate for that pair (`test_unified_tasks_tenant_request_cta`). **D-C07 (2026-05-01):** `ComplianceScorePage.js` — score-driver remediation gated on **`requirementUsesServerTakeActionPrimary`** + **`resolveRequirementAction`**; removed synthetic `navigateDriverAction` / `resolveTaskCta` path; tests `ComplianceScorePage.scoreDrivers.test.js`, `ComplianceScorePage.driverRemediation.test.js`. |
| **remaining tasks** | Phase 3: resolver/API URL validation; phase 4: golden parity JS ↔ Python; optional Command Centre degraded-mode banner; optional future **tenant_request** primary CTA alignment **with** frontend guided `source_type` handling. |
| **risks** | Dead or misleading CTAs; silent fallback URLs; partial Command Centre bundles on submodule errors. |
| **blocked-by / depends-on** | **Depends-on:** Stream C for which entity types expose `take_action`. Matrix inventory **done**; guardrails run per Stream D phases 2–4 (**before** Stream A sweep where CTA-sensitive); **applicability-edge** CTA expansions defer to **Stream A** (global step 7) unless explicitly approved. |

**Acceptance criteria:** (1) Requirement-backed CTAs go through resolver contract. (2) New action types include contract test or documented cross-repo check. (3) No shipped CTA that cannot be traced to an obligation/signal row + policy. (4) Documented list of intentional non-resolver URLs (if any) with owner.

### Architectural authority

- **Requirement-backed CTAs:** `requirement_action_resolver` (`resolve_take_action_*`, `take_action`); enrichment via `unified_tasks_service` / priority mapping.
- **Risk CTAs:** dedicated operations URL pattern (`command_center_service` / `risk_signal_service`) — intentionally separate from resolver.

### Forbidden patterns

- **Rule R2 (gap analysis):** New surfaces using `compliance_gaps.recommended_url` for requirement-primary CTAs when resolver should win.
- Frontend rebuilding requirement intent URLs outside parity with backend resolver.
- Shipping intents without URL where contract expects both.

### Affected modules (non-exhaustive)

`requirement_action_resolver.py`, `requirement_action_links.py`, `client_priority_stream.py`, `unified_tasks_service.py`, `command_center_service.py`, `compliance_gap_engine.py` (`gaps_to_priority_actions`), gap → priority mapping modules, `today_projection_service.py`, `risk_signal_service.py`, `requirement_truth.py`, `requirement_client_runtime_surface.py`, `catalog_compliance.py`, `monthly_digest_assembly_service.py`, `priority_actions.py`, frontend `requirementTakeActionResolver.js`, `ctaRegistry.js`, Today / Command Centre / Property Detail / Requirement Intelligence Modal / **Compliance score** (`ComplianceScorePage.js`); **inventory:** `STREAM_D_CTA_PRODUCER_CONSUMER_MATRIX.md`; Today / authority alignment tests.

### Required audit before implementation

- ~~Inventory producers of `primary_action_url` / `take_action` for requirements; list gap `recommended_*` consumers (backend + frontend repo if applicable).~~ **Done** — see `STREAM_D_CTA_PRODUCER_CONSUMER_MATRIX.md`.
- ~~Exception table for intentional non-resolver URLs (e.g. risk slim path).~~ **Done** — matrix §3.

### Findings (Stream D — CTA matrix, 2026-04-30)

- **Requirement CTAs** are contractually **`take_action`** / `requirement_action_resolver` on the backend, with **mandatory parity** to `frontend/src/utils/requirementTakeActionResolver.js`; Today and unified tasks enforce resolver over misaligned gap `recommended_*` when `canonical_take_action` is present (`test_today_requirement_cta_authority.py`).
- **Risk CTAs** intentionally **bypass** the requirement resolver: copy from `risk_signal_service` (`RECOMMENDED_ACTIONS`, etc.); URL from **constructed** `/operations/risk-signals?signal_id=…` in `client_priority_stream` and `command_center_service._slim_risk` — duplicate pattern, medium drift risk if one path changes.
- **Compliance score page** (`ComplianceScorePage.js`) — driver **remediation** column now uses **`requirementUsesServerTakeActionPrimary`** + **`resolveRequirementAction`** (same authority pattern as Property Detail); heuristic `actions` no longer produce clickable remediation. **Residual:** score **recommendations** card is still narrative-only text from the score API (not resolver-backed CTAs); structural **Open property** link when canonical is absent.
- **Admin** priority stream (`priority_actions.py` + `AdminDashboard.js`) is a **separate** system (`/admin/…` URLs); low risk to **client** CTA contract but must not be mistaken for tenant-facing authority.
- **`complianceObligationPresent.js`** synthesises explanatory `recommended_action_text` — informational, not navigation authority.

### Implementation phases

Each numbered phase is an intended **separate PR**; title format `Stream D — <phase>`. PR description must satisfy **Architecture Authority Rules** §6.

1. ~~**Stream D — CTA producer/consumer matrix**~~ — **Done (2026-04-30):** `STREAM_D_CTA_PRODUCER_CONSUMER_MATRIX.md` — surface → module → label/URL authority → workflow → `take_action` bypass → audience → risk (**global step 3** inventory).
2. **Stream D — Backend gap field guardrails** — **Done (2026-04-30):** B1 `gaps_to_priority_actions` + B2 `_primary_action_fields` + **B3** `_tenant_request_tasks` metadata + mismatch log (`test_unified_tasks_tenant_request_cta`). Phases 3–4 next.
3. **Stream D — Resolver validation hardening** — Narrow PR: non-empty URL for shipped intents at resolver or API boundary.
4. ~~**Stream D — Cross-repo parity CI**~~ — **Partial (2026-05-01):** Backend parity freeze — `STREAM_D_CTA_PARITY_ENFORCEMENT.md`, `tests/fixtures/cta_parity_fixtures.py`, `tests/test_cta_parity_contract.py`. **Defer:** optional FE golden export / CI job in frontend pipeline (enforcement doc §6).

### Acceptance tests (stream-specific)

- Extend `test_compliance_authority_alignment` / take-action matrix tests for touched intents or surfaces.
- Command Centre: document or test degraded behaviour when subgraph errors (align with P2 “banner” scope if out of scope).

### Rollout risks

- Parity CI blocks on copy drift — scope golden files to **intent + URL** if agreed.
- Hardening too strict for JOB envelope — align with existing resolver comments.

### Recommended next PR (Stream D)

**Stream D — Phase 3:** Resolver / API boundary validation for non-empty navigable URL where contract expects one **or** optional **Phase 4** frontend CI wiring against `STREAM_D_CTA_PARITY_ENFORCEMENT.md` §6. **Optional Phase 2 follow-up:** grep-only inventory for any remaining raw gap-field readers on client requirement-primary paths (no behaviour change unless findings warrant a new slice).

---

## Stream E — Event Consistency Contracts

| Field | Content |
|--------|---------|
| **status** | Partial — phase **1** matrix + **E2.1–E2.3** + **Phase 3** structured logging **shipped**; optional matrix rows / phase 4 deferred. |
| **priority** | P0 |
| **current phase** | **Phase 4 — Optional outbox/debounce** (or further narrow matrix rows if product prioritises). |
| **completed work** | **Launch D1 (2026-05-17):** pilot propagation fanout verification **DONE** — governed `enqueue_compliance_recalc_with_fanout` driver; R1/R2/R3 replay collapse + suppression determinism; delegated lineage; bounded growth; unrelated-surface integrity **0**; artifacts `d1b_*` (authoritative). **Open governance:** production `POST …/requirements/sync` still direct `enqueue_compliance_recalc` — not fixed in D1 (separate unit if aligned). Idempotent gap upserts; applicability queue; **`STREAM_E_MUTATION_FANOUT_MATRIX.md`** (incl. **appendix — Outcome engine**; rows 13–14 **tenant delivery → `Enq`**; **row 10** client `patch_requirement` → `REQUIREMENT_ACTION_TRIGGERED`). **E-patch-requirement-audit (2026-04-30):** `routes/properties.py` `patch_requirement` — audit after `sync_requirement_evidence_authority`, before `enqueue_compliance_recalc`; `tests/test_patch_requirement_audit_http.py`. **E2.1** `compliance_outcome_engine` — after `_set_requirement_compliant`, `sync_requirement_evidence_authority` per affected requirement **before** `recalculate_and_persist` (`tests/test_compliance_outcome_engine.py`); **E-outcome-coverage:** `tests/test_compliance_outcome_engine_event_coverage.py`. **E-tenant-delivery-recalc:** `tenant_delivery_proof_service` + `tenant_delivery_reconciliation`; tests in `test_tenant_delivery_and_audit_pack.py`. **E2.2** `api_compliance_workflow` mark-not-applicable + reopen — `sync_requirement_evidence_authority` after update (`test_compliance_workflow_mark_not_applicable_http.py`); **E2.3** `routes/properties.py` `patch_property` — post-success materialisation gap sweep via `sync_compliance_gaps_for_requirement` (cap 500, default lifecycle/bridge) (`test_properties_requirement_materialisation_http.py`). **Phase 3:** `utils/compliance_fanout_log.compliance_fanout_extra` — structured `event=compliance_fanout` on authority/gap partial-fail, recalc enqueue dedupe (`stage=dedupe`), `apply_action_outcome` swallow paths (`routes/documents.py`, `maintenance_service.py`, `evidence_review_verify.py`), tenant delivery + property sweep warnings, outcome-engine authority sync exception (`tests/test_compliance_fanout_log.py`). |
| **remaining tasks** | Optional matrix follow-ups; deeper observability (e.g. `recalculate_and_persist` inner warnings, other DEBUG-only skips); defer outbox/debounce unless product/infra approve. |
| **risks** | Transient queue lag on `Enq`-only paths unchanged; double recalc on some verify paths unchanged; gap sweep skips when materialisation throws (logged). |
| **blocked-by / depends-on** | **Depends-on:** Streams A, B for payloads; Stream F for correlation on new milestones. **Blocked-by:** infra if adopting outbox/debounce later. |

**Acceptance criteria:** (1) For each **classified** mutation path, documented outcome: gap sync (Y/N), score (Y/N), audit event types. (2) New paths add a matrix row before merge. (3) Ordering/eventual consistency boundaries documented for client-facing surfaces.

### Architectural authority

- **Documented fan-out** today: **`STREAM_E_MUTATION_FANOUT_MATRIX.md`** + hand-written triggers (`requirement_evidence_authority`, operator applicability + `sync_compliance_gaps_for_requirement`, tenant delivery reconciliation, backfills) per gap analysis — **no central saga** unless product approves deferred scope.

### Forbidden patterns

- New mutation paths that change obligation/gap/score without updating the **mutation matrix** (this stream’s acceptance criteria).
- Swallowing gap sync failures without structured logs where today only warnings exist.

### Affected modules (non-exhaustive)

`requirement_evidence_authority.py`, `compliance_gap_sync.py`, tenant delivery reconciliation modules, `tenant_delivery_proof_service.py`, `applicability_operator_actions.py`, `compliance_policy_backfill_service.py`, gap backfill services, `compliance_scoring_service.py`, `compliance_outcome_engine.py`, `routes/api_compliance_workflow.py`, `applicability_resolution_queue.py`, `risk_signal_regen_queue.py`.

### Findings (Stream E — mutation matrix, 2026-04-30)

- **Single matrix:** `STREAM_E_MUTATION_FANOUT_MATRIX.md` — **22** classified rows covering document upload/delete/verify/reject (client + admin), evidence authority sync, requirement PATCH, workflow API mark-not-applicable / reopen, property PATCH (jurisdiction / applicability), applicability operator (**quiet** gap sync), tenant delivery initiate + reconciliation, gap backfill vs policy gap reconciliation job, WO completion, issue resolution, admin score validate/repair, admin bulk recalc enqueue.
- **Quiet sync:** `applicability_operator_actions` → `sync_compliance_gaps_for_requirement(..., audit_lifecycle=False, run_operational_bridge=False)` — intentional; see matrix §Cross-cutting notes.
- **E2.1–E2.3 shipped (2026-05-01):** Outcome engine compliant-set branch + workflow API requirement mutations + property post-materialisation gap sweep — see matrix rows 17–18, 21–22, 11.
- **`patch_requirement` audit (2026-04-30):** `REQUIREMENT_ACTION_TRIGGERED` / `client_patch_requirement` after authority sync, before enqueue; `REQUIREMENT_UPDATED:{requirement_id}` in metadata for queue join — matrix row 10; `STREAM_F_FORENSICS_JOIN_RECIPE.md` §5.
- **Tenant delivery → score (2026-04-30):** After **≥1** successful gap sync in proof send / reconcile `_sync_requirements_for_proof` / tenant acknowledge, **`enqueue_compliance_recalc`** once per property with `TENANT_DELIVERY:{delivery_id}`; **no** sync recalc on the hot path. Partial gap-sync failure still enqueues if **any** requirement sync succeeded.
- **Outcome engine:** WO / issue events that **do not** use `_set_requirement_compliant` still have **no** authority refresh on that path (by design of this slice).

### Required audit before implementation

- ~~Build mutation → gap sync (Y/N/quiet) → score recalc (Y/N) → audit types from code~~ **Done** — see matrix doc; keep matrix updated when adding paths.
- Record intentional quiet operator sync (`audit_lifecycle=False`, `run_operational_bridge=False`).

### Implementation phases

Each numbered phase is an intended **separate PR**; title format `Stream E — <phase>`. PR description must satisfy **Architecture Authority Rules** §6.

1. ~~**Stream E — Mutation fan-out matrix**~~ — **Done:** `STREAM_E_MUTATION_FANOUT_MATRIX.md` + tracker (**global step 2**).
2. **Stream E — Matrix gap fixes** — **Done (approved slice 2026-05-01):** micro-PRs **E2.1** (outcome engine), **E2.2** (workflow API), **E2.3** (property PATCH post-materialisation); further rows optional.
3. ~~**Stream E — Logging / observability**~~ — **Done (2026-04-30):** `compliance_fanout_extra` + WARNING/INFO on high-risk paths (authority gap partial, recalc dedupe, `apply_action_outcome` failures, tenant delivery / property sweep, outcome-engine authority sync); `tests/test_compliance_fanout_log.py`; matrix cross-cutting note §2 aligned with E2.1.
4. **Stream E — Optional outbox/debounce** — **Defer** unless product + infra approve; separate PR + tracker update if pursued.

### Recommended next PR

**Stream B — Straggler wiring** (remaining matrix “Recalc today?” gaps) **or** **Stream E — Phase 4** (outbox/debounce — product/infra gate).

### Acceptance tests (stream-specific)

- Per fixed path: integration or service tests for gap sync and/or score hooks.
- Regression: quiet operator path does **not** emit gap lifecycle audit.

### Rollout risks

- Synchronous recalculation everywhere — prefer existing async/job patterns.
- Accidentally auditing quiet operator gap sync — operator noise.

---

## Stream F — Audit Correlation & Traceability

| Field | Content |
|--------|---------|
| **status** | Partial — phase **1** + **phase 2** **shipped** (read-side docs + **F2-A** / **F2-B** code); optional **F2-C** / **F2-D** still open. |
| **priority** | P1 |
| **current phase** | **Phase 2b — Narrow propagation PRs** (enqueue/worker/outcome/metadata only; no new bus) **or** Phase 3 audit key standardisation. |
| **completed work** | Append-only applicability audit; gap lifecycle events where enabled; patterns in `risk_signal_service` and client navigation audit. **Phase 1 (2026-04-30):** `STREAM_F_FORENSICS_JOIN_RECIPE.md`. **Phase 2 (2026-04-30–2026-05-01):** `STREAM_F_PHASE2_CORRELATION_PROPAGATION.md`; `STREAM_F_RECONSTRUCTION_CONSISTENCY.md`; **F2-A** — optional `correlation_id` on `property_compliance_score_history` + `score_change_log` when `recalculate_and_persist` context supplies non-empty id (`compliance_scoring_service.py`); **F2-B** — outcome engine + `compliance_activity_log.correlation_id`. **Contract tests:** `tests/test_stream_f_correlation_propagation_contract.py` (ledger + audit + history + change_log + absent/blank cases); `tests/test_compliance_outcome_engine.py` (F2-B). Cross-links: `STREAM_E_MUTATION_FANOUT_MATRIX.md` §6, `STREAM_F_FORENSICS_JOIN_RECIPE.md` §5/§8, `STREAM_C_REMEDIATION_CORRELATION_RUNBOOK.md` companion. |
| **remaining tasks** | Optional slices **F2-C** / **F2-D** from propagation doc (product-approved); Phase 3 — consistent id keys on new `create_audit_log` payloads (no broad migration); incremental optional `audit_correlation_id` on new transitions only if product wants cross-surface UUID. |
| **risks** | Forensics requires multiple stores; operator support misinterprets volume as noise. |
| **blocked-by / depends-on** | **Depends-on:** Streams A–E for auditable transitions. **Blocked-by:** retention/compliance policy for new audit fields. |

**Acceptance criteria:** (1) New compliance-posture transitions emit auditable records with tenant/entity ids. (2) Correlation key scheme documented (addendum or linked doc). (3) Applicability and gap critical transitions remain append-only / idempotent per existing contracts.

### Architectural authority

- **Stores:** `audit_logs` (`create_audit_log`), `applicability_resolution_audit`, gap lifecycle when enabled, risk / Today navigation audits.
- **Operational reconstruction:** `STREAM_F_FORENSICS_JOIN_RECIPE.md` (read-only; Mongo + audit join order; does not imply single-collection timeline).
- **Correlation propagation & reconstruction:** `STREAM_F_PHASE2_CORRELATION_PROPAGATION.md`, `STREAM_F_RECONSTRUCTION_CONSISTENCY.md` — where `correlation_id` survives async boundaries; **`score_change_log` / `property_compliance_score_history`** may carry optional **`correlation_id`** on new rows (**F2-A**); legacy rows and callers without id still rely on weak joins.
- **Incremental correlation:** optional shared id on **new** milestones only — no big-bang rewrite of historical rows.

### Forbidden patterns

- Breaking append-only / required-key contracts on `applicability_resolution_audit`.
- Assuming a single-collection timeline without documented joins (quiet gap sync requires applicability audit + row diffs per gap analysis).

### Affected modules (non-exhaustive)

`create_audit_log` call sites, `applicability_resolution_audit.py`, `compliance_gap_sync.py` (audit flags), `risk_signal_service.py`, `routes/client.py` (Today), score history writers in `compliance_scoring_service.py`.

### Required audit before implementation

- Event types per store: applicability command, gap open/resolve/issue-created, score recalc reasons, risk dismiss.
- Legal/retention review before new PII-bearing audit fields.

### Implementation phases

Each numbered phase is an intended **separate PR**; title format `Stream F — <phase>`. PR description must satisfy **Architecture Authority Rules** §6.

1. ~~**Stream F — Forensics join recipe**~~ — **Done (2026-04-30):** `STREAM_F_FORENSICS_JOIN_RECIPE.md` (**global step 4**).
2. ~~**Stream F — Phase 2 correlation (read-side + F2-B outcome engine)**~~ — **Done (2026-05-01):** propagation + reconstruction docs; matrix §6; `test_stream_f_correlation_propagation_contract.py`; **F2-B** — `compliance_outcome_engine._resolve_outcome_correlation_id`, `compliance_activity_log.correlation_id`, `test_compliance_outcome_engine.py` correlation assertions. **Next:** optional **F2-A / F2-C / F2-D**.
3. **Stream F — Correlation id on new milestones** — Narrow PR: optional UUID on new closure-style business audits, propagated to related `audit_logs` only for that path (may merge with F2-A scoping).
4. **Stream F — Standardise id keys on new audits** — Ensure new `create_audit_log` calls include `client_id`, `property_id`, `requirement_id` / `gap_key` consistently (no broad schema migration unless already planned).
5. **Stream F — Score milestone audit** — Pair with Stream B straggler wiring: structured audit using existing reason constants (no new scoring formula).

### Acceptance tests (stream-specific)

- Tests for audit payloads including required linkage fields for new event types.
- Applicability audit immutability tests unchanged or extended, not weakened.

### Rollout risks

- Correlation UUID without query guidance — document query patterns in join recipe.
- Over-auditing operator paths — do not add gap lifecycle noise where quiet sync is intentional.

---

## Changelog (tracker edits only)

| Date | Change |
|------|--------|
| 2026-04-30 | Initial tracker created with six streams and implementation order rules. |
| 2026-04-30 | Cross-stream sequencing (B→E→D→F→C runbook→C spike→A); concrete implementation phases per stream; gap-analysis draft sections; **Architecture Authority Rules** §1–7; named-authorities + stream lifecycle tables; Implementation Order Rule 3 extended to every PR; stream sections use **Implementation phases** (PR checklist → §6). |
| 2026-04-30 | **Stream B — Scoring authority matrix** phase: added `STREAM_B_SCORING_AUTHORITY_MATRIX.md`; updated Stream B (current phase → 2, findings, risks, admin-exception, recommended next PR, expanded affected modules, phased checklist). |
| 2026-04-30 | **Stream B — Legacy labelling + admin repair decision:** docstrings (`compliance_score`, `compliance_scoring`, `compliance_scoring_service`, `admin.validate_compliance_score`); matrix §5a (recommend **B** now, **A** later); contract test; Stream B phase → 3; enterprise test mocks for gap aggregate + portfolio override. |
| 2026-04-30 | **Stream B — Admin repair refactor:** `fix=true` → `recalculate_and_persist` + `REASON_ADMIN_VALIDATOR_REPAIR`; removed second writer; tracker/matrix/tests updated. |
| 2026-04-30 | **Stream E — Mutation fan-out matrix:** added `STREAM_E_MUTATION_FANOUT_MATRIX.md`; Stream E phase 1 marked **Done**; findings + **current phase → 2**; cross-links Stream B straggler wiring; named-authorities + lifecycle + global step 2 updated. |
| 2026-04-30 | **Stream E — Phase 3 (logging):** `compliance_fanout_log.compliance_fanout_extra`; structured WARNING/INFO on authority gap partial, compliance recalc enqueue dedupe, `apply_action_outcome` exception paths (documents, maintenance, evidence review verify v2), tenant delivery + reconciliation + `patch_property` sweep, outcome-engine post-compliant authority sync failures; `test_compliance_fanout_log.py`; matrix §2 cross-cutting note; tracker Stream E → phase **4** next. |
| 2026-05-01 | **Stream E — Phase 2 (E2.1–E2.3):** outcome engine authority refresh after compliant-set; workflow API `sync_requirement_evidence_authority` on mark-not-applicable + reopen; property `patch_property` post-materialisation `sync_compliance_gaps_for_requirement` sweep (500 cap); tests + matrix rows 11/17/18/21/22 + tracker Stream E (phase **3** next). |
| 2026-04-30 | **Stream D — Phase 1 (CTA matrix):** added `STREAM_D_CTA_PRODUCER_CONSUMER_MATRIX.md`; named-authorities row; global step 3 wording; Stream D status/completed/remaining/current phase + findings + recommended next PR (phase 2); required-audit items marked done. |
| 2026-04-30 | **Stream D — Phase 2 (first slice, B1/B2):** `gaps_to_priority_actions` suppresses raw gap `recommended_url` when canonical `take_action.primary` has no navigable route; `_primary_action_fields` prefers `canonical_take_action` label/route and blocks gap URL fallback on empty canonical route; tests in `test_compliance_gap_engine_governed.py` + `test_today_requirement_cta_authority.py`; tracker Stream D updated. |
| 2026-04-30 | **Stream D — Phase 2 (B3 slice):** `_tenant_request_tasks` attaches `metadata.take_action` when requirement resolves; `logger.warning` + `compliance_fanout_extra(op="tenant_request_cta")` on non-standard-document canonical vs hardcoded upload CTA; `test_unified_tasks_tenant_request_cta.py`. |
| 2026-04-30 | **Stream F — Phase 1 (forensics join recipe):** added `STREAM_F_FORENSICS_JOIN_RECIPE.md`; named-authorities row + Stream F status/current phase/completed/remaining/architectural authority; global step 4 marked done; lifecycle table updated. |
| 2026-04-30 | **Stream E — Outcome engine coverage freeze (doc + tests, no runtime change):** `STREAM_E_MUTATION_FANOUT_MATRIX.md` appendix (`compliance_outcome_engine` / `ALL_EVENTS`); `tests/test_compliance_outcome_engine_event_coverage.py`; named-authorities Stream E row; Stream E completed work + findings; **Last updated**. |
| 2026-04-30 | **Stream E — Tenant delivery score convergence:** `enqueue_property_recalc_after_tenant_delivery_gap_batch` in `tenant_delivery_reconciliation.py`; calls from `tenant_delivery_proof_service` + `_sync_requirements_for_proof` / tenant acknowledge; matrix rows 13–14 + cross-cutting §5; tests in `test_tenant_delivery_and_audit_pack.py`; tracker Stream E completed/remaining/findings/next PR + **Last updated**. |
| 2026-04-30 | **Stream E — `patch_requirement` audit (row 10):** `REQUIREMENT_ACTION_TRIGGERED` in `routes/properties.py`; `test_patch_requirement_audit_http.py`; matrix row 10; `STREAM_F_FORENSICS_JOIN_RECIPE.md` §5; tracker Stream E completed/remaining/findings/next PR + **Last updated**. |
| 2026-04-30 | **Stream C — Remediation correlation runbook:** added `STREAM_C_REMEDIATION_CORRELATION_RUNBOOK.md`; named-authorities Stream C row; lifecycle **Open (partial)**; global step 5 marked done; Stream C status/completed/remaining/required-audit/Next PRs item 1; **Last updated**. |
| 2026-05-01 | **Stream D — Phase 4 (backend parity):** `STREAM_D_CTA_PARITY_ENFORCEMENT.md`; `tests/fixtures/cta_parity_fixtures.py` + `tests/test_cta_parity_contract.py`; `tests/__init__.py` + `tests/fixtures/__init__.py`; matrix §6 + parity authority row; tracker Stream D (status, current phase, completed, remaining, Next PRs phase 4, lifecycle, named authorities, recommended next PR); **Last updated**. |
| 2026-05-01 | **Stream F — Phase 2 (read-side correlation):** `STREAM_F_PHASE2_CORRELATION_PROPAGATION.md`; `STREAM_F_RECONSTRUCTION_CONSISTENCY.md`; `tests/test_stream_f_correlation_propagation_contract.py`; `STREAM_F_FORENSICS_JOIN_RECIPE.md` + `STREAM_E_MUTATION_FANOUT_MATRIX.md` §6 + `STREAM_C_REMEDIATION_CORRELATION_RUNBOOK.md` companion links; tracker Stream F (status, current phase, completed, remaining, architectural authority, implementation phases 2/3–5 renumber, lifecycle, named authorities); **Last updated**. |
| 2026-05-01 | **Stream F — F2-B outcome engine correlation:** `compliance_outcome_engine._resolve_outcome_correlation_id` + `compliance_activity_log.correlation_id`; `test_compliance_outcome_engine.py`; `STREAM_F_PHASE2_CORRELATION_PROPAGATION.md` / `STREAM_F_RECONSTRUCTION_CONSISTENCY.md` / `STREAM_E_MUTATION_FANOUT_MATRIX.md` §6; tracker Stream F phase 2 item merged with F2-B; **Last updated**. |
| 2026-04-30 | **Stream F — F2-A score history / change log correlation:** `compliance_scoring_service.recalculate_and_persist` persists optional `correlation_id` on `property_compliance_score_history` + `score_change_log` when context supplies non-empty string; `test_stream_f_correlation_propagation_contract.py`; propagation + reconstruction + matrix §6; tracker Stream F (status, completed, remaining, lifecycle, phase 2, architectural authority); **Last updated**. |
| 2026-05-01 | **Stream B — Standalone authority-sync enqueue:** `routes/admin.py` (`_enqueue_recalc_after_standalone_authority_sync` + document scope / link / unlink / reject-unresolved / evidence-match / backfill paths), `routes/client_compliance_evidence.py` (post evidence + verification); `STREAM_E_MUTATION_FANOUT_MATRIX.md` row 9; tests `test_admin_authority_sync_recalc_enqueue.py`, `test_client_compliance_evidence_safety.py`, `test_evidence_match_operations_http.py` patch; tracker Stream B completed/remaining/changelog; **Last updated**. |
| 2026-05-01 | **Stream C — Internal remediation correlation view v1:** `POST /api/admin/support/remediation-correlation-view` (`FEATURE_REMEDIATION_CORRELATION_VIEW_V1`), `services/remediation_correlation_view.py`, `routes/support.py`, `tests/test_remediation_correlation_view_v1.py`, `STREAM_C_REMEDIATION_CORRELATION_RUNBOOK.md` §11; tracker global step 6 + Stream C Next PRs item 2 + recommended order item 6; **Last updated**. |
| 2026-05-01 | **Stream C — Correlation view v1 safety refinements:** response `non_authoritative: true`; `score_change_log_present_mapping_advisory` only when `score_change_log` rows imply requirement-level mapping (`changed_requirements` / malformed / empty `requirement_key` on entries); runbook §11 + tests updated; **Last updated**. |
| 2026-05-01 | **Stream C — Internal support note:** `SUPPORT_REMEDIATION_CORRELATION_VIEW_V1.md` (purpose, RBAC, flag, examples, interpretation, limitations, escalation); runbook §11 link; **Last updated**. |
| 2026-05-01 | **Stream D — D-C07 (Compliance score driver CTAs):** `frontend/src/pages/ComplianceScorePage.js` + `ComplianceScorePage.driverRemediation.js`; matrix D-C07 + §5; `STREAM_D_CTA_PARITY_ENFORCEMENT.md` §4/§5.3; tests `ComplianceScorePage.scoreDrivers.test.js`, `ComplianceScorePage.driverRemediation.test.js`; tracker Stream D completed work + findings; **Last updated**. |
| 2026-05-02 | **Stream B — Async honesty (FE slice 1):** `ClientDashboard.js`, `ComplianceScorePage.js`, `frontend/src/utils/scoreFreshnessUi.js`; tests `ClientDashboard.scoreFreshness.test.js`, `ComplianceScorePage.asyncHonesty.test.js`, `scoreFreshnessUi.test.js`; `STREAM_B_SCORING_AUTHORITY_MATRIX.md` §6–§7; tracker Stream B completed work; **Last updated**. |
| 2026-04-30 | **Stream B — Async honesty (FE slice 2):** `ClientCommandCenterPage.js`, `PropertyDetailPage.js`, `frontend/src/utils/scoreFreshnessUi.js` (shared copy); tests `ClientCommandCenterPage.test.js`, `PropertyDetailPage.asyncHonesty.test.js`, `scoreFreshnessUi.test.js`; `STREAM_B_SCORING_AUTHORITY_MATRIX.md` §6–§7; tracker Stream B completed work + **Last updated**. |
| 2026-04-30 | **Stream B — Async honesty (slice 3, digest + exports):** `monthly_digest_assembly_service.py`, `email_service.py`, `monthly_digest_pdf_service.py`, `reporting_service.py`, `routes/reports.py`; tests `test_monthly_digest_enterprise.py`, `test_reporting_compliance_export_snapshot.py`; `STREAM_B_SCORING_AUTHORITY_MATRIX.md` §7; tracker Stream B completed work + **Last updated**. |
| 2026-04-30 | **Stream B — Score-explanation PDF snapshot honesty:** `services/pdf_report_builder.py` (`build_score_explanation_report`); tests `test_pdf_report_builder.py`; `STREAM_B_SCORING_AUTHORITY_MATRIX.md` §7; tracker Stream B completed work + **Last updated**. |
| 2026-04-30 | **Stream B — Evidence Readiness PDF snapshot honesty:** `services/pdf_report_builder.py` (`build_portfolio_report`, `build_property_report`); tests `test_pdf_report_builder.py`; `STREAM_B_SCORING_AUTHORITY_MATRIX.md` §7; tracker Stream B completed work + **Last updated**. |
| 2026-04-30 | **Stream B — Professional compliance summary PDF snapshot honesty:** `services/professional_reports.py` (`generate_compliance_summary_pdf`); tests `test_professional_reports_authority_labels.py`; `STREAM_B_SCORING_AUTHORITY_MATRIX.md` §7; tracker Stream B completed work + **Last updated**. |
| 2026-04-30 | **Controlled beta operations runbook:** `RUNBOOK_CONTROLLED_BETA_OPERATIONS.md` (support/admin recovery, escalation, monitoring, beta entry checklist); tracker **Companion**, **Named authorities** row, **Last updated**. |
| 2026-05-17 | **Launch D1 DONE (+ D1b harness):** propagation fanout verification on pilot `6fd5ac4c…`/`d35a58ae…`; authoritative `d1b_harness_rerun_v3` `d1_pass=true`; D1-RC-15 harness baseline cleared; replay lineage stable; no product propagation changes; production HTTP sync path observation documented; E1 DoD drafting unlocked — `LAUNCH_AUTHORITY_TRACKER.md` § D1 closure; RUNBOOK §12.7 D1. |
| 2026-05-17 | **Launch E1 VERIFIED (+ E1a/E1b):** evidence authority semantic replay proof on authority-capable seeded fixture (`e1b_pass=true`); original `e1_*` E1-RC-2 preserved as fixture-insufficiency history; no product authority remediation; parent **not DONE**; **F1** DoD drafting unlocked — `LAUNCH_AUTHORITY_TRACKER.md` § E1 closure; RUNBOOK §12.7 E1. |
| 2026-05-17 | **Launch F1 DoD rev 1 draft:** notification/delivery governance verification spec — truthful operational communication under replay; **F1-RC-1**–**13**; `f1_*` artifacts — `LAUNCH_AUTHORITY_TRACKER.md` § F1; **not** implementation. |
| 2026-05-17 | **Launch F1 DoD rev 2 draft:** + delivery authority precedence (§4a), acknowledgement ambiguity (§4b), replay-visible impact (§3k), lineage boundedness (§3l); **F1-RC-14**–**17**; tightened DONE gates. |
| 2026-05-17 | **Launch F1 VERIFIED (+ F1a DONE):** governed **F1-M1** replay proof on pilot (`f1a_harness_refinement_rerun_v1`); original `f1_*` **F1-RC-15** preserved + reclassified harness methodology; replay-pair ack semantics; no notification remediation — `LAUNCH_AUTHORITY_TRACKER.md` § F1 closure; RUNBOOK §12.7 F1. |
| 2026-05-17 | **Launch F1 DONE:** F-layer replay-governance proof operationally complete for approved **F1-M1** scope; historical RC chain preserved; watchlists explicit; future notification work requires separate units — `LAUNCH_AUTHORITY_TRACKER.md` § F1 DONE closure. |
| 2026-05-17 | **Launch G1 DoD rev 1 draft:** programme-governance integrity layer above B–F; replay-confidence decay; artifact/RC preservation; **G1-RC-1**–**10**; `g1_*` artifacts — **not** implementation. |
| 2026-05-17 | **Launch G1 DoD rev 2 draft:** + proof-context preservation (§3A.1, **G1-RC-11**); deferred-risk integrity (§3A.2, **G1-RC-12**); governance replayability (§3A.3, **G1-RC-13**); surveillance boundedness (§3A.4, **G1-RC-14**); tightened DONE gates — **not** implementation. |
| 2026-05-17 | **Launch G1 DoD rev 3 draft:** + governance authority integrity (§3B.1, **G1-RC-15**); interpretation drift containment (§3B.2, **G1-RC-16**); historical contradiction accountability (§3B.3, **G1-RC-17**); tightened DONE gates — **not** implementation. |
| 2026-05-17 | **Launch G1 DoD rev 4 draft:** + governance succession integrity (§3C.1, **G1-RC-18**); institutional-memory anti-fragility (§3C.2, **G1-RC-19**); partial-knowledge survivability (§3C.3, **G1-RC-20**); tightened DONE gates — **not** implementation. |
| 2026-05-17 | **Launch G1 DoD rev 5 draft:** + governance legitimacy preservation (§3D.1, **G1-RC-21**); bounded reinterpretation power (§3D.2, **G1-RC-22**); anti-authoritarian governance drift (§3D.3, **G1-RC-23**); tightened DONE gates — **not** implementation. |
| 2026-05-17 | **Launch G1 DoD recovery (simplified LGS):** constitutional mass reduction — **G1-P1**–**P10**; 6 artefacts; tier model T0–T3; anti-recursion breakers; degraded surveillance mode; rev 5 constitutional artefacts/RCs **retired** (`historical_only`); ≤12 DONE gates — `LAUNCH_AUTHORITY_TRACKER.md` § G1. |
| 2026-05-17 | **Launch G1 DoD pre-signoff hardening:** DONE gate consistency; degraded `g1_pass` prohibition; manifest T1-only + **G1-RC-21**; field+element mass + **G1-RC-22**; retired read ban + **G1-RC-23**; tracker binding + **G1-RC-24**; tag anti-elevation + **G1-RC-25**; predicate binding + **G1-RC-26**; critical-path degraded + **G1-RC-27**; Pillar vs G1-P namespace — ready for sign-off. |
| 2026-05-17 | **Launch G1 formal sign-off:** LGS recovery approved; **NOT_STARTED → IN_PROGRESS** (Tranche **T1** harness only); `ANTI_EXPANSION`; surveillance execution pending; T2/T3 blocked — `LAUNCH_AUTHORITY_TRACKER.md` § G1 sign-off; RUNBOOK §12.7 G1 stub. |
| 2026-05-16 | **TRUST-01 (client evidence inspectability):** read-only CER panel in requirement details; truthful guided upload vs submit semantics; existing list route only — no authority/fanout change — `LAUNCH_AUTHORITY_TRACKER.md` TRUST-01; RUNBOOK §4.8. |
| 2026-05-16 | **OPS-VERIFY-01 defined:** operational client evidence journey verification unit; replay/fixture proof explicitly insufficient for user closure — see `LAUNCH_AUTHORITY_TRACKER.md` OPS-VERIFY-01; harness `scripts/ops_verify_01_*`. |
| 2026-05-18 | **TRUST-01 frontend remediation:** CORS dev-origin parity, requirements load-error visibility, submission-aware presentation; verified via OPS-VERIFY-01 Journey A browser re-submit — `LAUNCH_AUTHORITY_TRACKER.md` TRUST-01 / OPS-VERIFY-01. |
| 2026-05-18 | **OPS-VERIFY-01 Journey A:** `VERIFIED_OPERATIONALLY` for pilot `occupation_contract` existing-CER re-submit (`6fd5ac4c…` / `d35a58ae…`); unit **IN_PROGRESS / PARTIAL** (B/C not started; clean first-submit watchlist). |
| 2026-05-21 | **OPS-VERIFY-01 complete (A/B/C/D):** pilot evidence journeys closed — document-primary verify CER review alignment + `VERIFIED_CURRENT`/`COMPLIANT` presentation fix; Journey D browser attestation; reject/resubmit and structured CER review path remain watchlist — `LAUNCH_AUTHORITY_TRACKER.md` OPS-VERIFY-01. |
| 2026-05-20 | **CONDITION_STANDARD_ACTIVE_STANDARD Phase 1:** operational convergence foundation for FFHH/RS — pilot materialisation service, enriched `active_standard_status_summary`, authority/lifecycle guards, inspect panel, OPS readiness helpers; **not** fleet rollout — `CONDITION_STANDARD_ACTIVE_STANDARD_OPS.md`; `LAUNCH_AUTHORITY_TRACKER.md`. |
| 2026-05-22 | **`repairing_standard` OPS closure:** bounded runtime-legitimacy + `?open=resolve` operational routing; **`VERIFIED_OPERATIONALLY`** (Scotland pilot `ec0b091b`/`def23b30`); FFHH/rollout/launch **not** authorized — `ops_verify_01_ec0b091b_def23b30_repairing_standard/`. |
| 2026-05-23 | **FFHH OPS closure:** staging publish `FITNESS_FOR_HUMAN_HABITATION\|ENGLAND` (v24); runtime legitimacy restored; **`VERIFIED_OPERATIONALLY`** — bundle `ops_verify_01_6bcc43c0_3a69dcbd_fitness_for_human_habitation/`. |
| 2026-05-23 | **PRELAUNCH-OPS-RUNTIME-VERIFY-01 (hardened charter):** operational domain runtime verification programme defined — ownership model, G9 idempotency, G10 authority integrity, Family 8 anti-duplication, `TRUST_RISK_PRESENT`, tenant trust-risk hardening, rent browser/runtime rule; **separate from** OPS-VERIFY-01 / compliance journeys — `docs/PRELAUNCH_OPS_RUNTIME_VERIFICATION.md`; `LAUNCH_AUTHORITY_TRACKER.md` § PRELAUNCH-OPS-RUNTIME-VERIFY-01. |
| 2026-05-23 | **PRELAUNCH-OPS-RUNTIME-VERIFY-01 F1 (issues):** first bounded family run on Wales HMO pilot (`6fd5ac4c` / `d35a58ae`) — browser+API lifecycle PASS; **G9 FAIL** (duplicate POST creates twin visible issues) → `FAIL_SYSTEM` + `TRUST_RISK_PRESENT`; bundle `backend/docs/audit/ops_runtime_01_issues_6fd5ac4c_d35a58ae/`. F2 blocked until G9 remediated + rerun. |
| 2026-05-23 | **PRELAUNCH-OPS-RUNTIME-VERIFY-01 F1 G9 remediation + rerun:** bounded idempotent issue create (client submit guard + backend fingerprint/window dedupe); rerun `20260523T113129Z` → **`VERIFIED_OPERATIONALLY`**; F2 (`ops_runtime_02_work_orders`) may proceed. |
| 2026-05-23 | **PRELAUNCH-OPS-RUNTIME-VERIFY-01 F2 (work orders):** Wales HMO pilot (`6fd5ac4c` / `d35a58ae`) — issue→WO create + browser surfaces PASS; **G9 FAIL** (duplicate `create-work-order` creates twin WOs, 3 visible marker rows); lifecycle **incomplete** (no assignable contractors → approved-quote gate blocks start/complete); convergence partial (WO stuck OPEN); → **`FAIL_SYSTEM` + `TRUST_RISK_PRESENT`**; bundle `backend/docs/audit/ops_runtime_02_work_orders_6fd5ac4c_d35a58ae/`. F3 blocked until F2 G9 remediated + full lifecycle rerun. |
| 2026-05-23 | **PRELAUNCH-OPS-RUNTIME-VERIFY-01 F2 remediation:** G9 bounded idempotency (`maintenance_wo_from_issue_idempotency.py` + frontend guards); lifecycle fixture (`f2_ops_runtime_pilot_contractor_fixture.py`); G10 terminal reopen guard; post-remediation staging rerun `20260523T144750Z` — full API lifecycle + browser PASS; G9/G10 staging probes still FAIL (code not deployed); classification remains **`FAIL_SYSTEM`** pending deploy + same-run rerun. |
| 2026-05-23 | **PRELAUNCH-OPS-RUNTIME-VERIFY-01 F2 post-deploy:** commit `b921cbe7` pushed to main; Render deploy verified via smoke (G9 replay + G10 400); same-run OPS `20260523T152330Z` → **`VERIFIED_OPERATIONALLY`**; F3 may proceed. |
| 2026-05-23 | **PRELAUNCH-OPS-RUNTIME-VERIFY-01 F3 (contractor):** Wales HMO pilot — client assign + contractor portal quote/accept/complete + cross-role browser proof; G9/G10/visibility/convergence PASS → **`VERIFIED_OPERATIONALLY`**; bundle `backend/docs/audit/ops_runtime_03_contractor_6fd5ac4c_d35a58ae/`. F4 may proceed. |
| 2026-05-23 | **PRELAUNCH-OPS-RUNTIME-VERIFY-01 F4 (risk signals):** Wales HMO pilot — signal→issue→WO propagation + contractor remediation + client browser PASS; **signal lifecycle FAIL** (heuristic regen deletes active signals during run; lifecycle signal 404 before acknowledge/resolve); G9/G10 partial; convergence incomplete → **`FAIL_OPERATIONAL`**; bundle `backend/docs/audit/ops_runtime_04_risk_signals_6fd5ac4c_d35a58ae/`. F5 blocked. |
| 2026-05-23 | **PRELAUNCH-OPS-RUNTIME-VERIFY-01 F4 post-deploy:** commit `a4b23caa` pushed; behavioural smoke PASS; same-run OPS `20260523T174844Z` on deployed staging → **`VERIFIED_OPERATIONALLY`** (signal stable through regen, G9/G10/convergence/browser PASS); bundle `backend/docs/audit/ops_runtime_04_risk_signals_6fd5ac4c_d35a58ae/`. F5 may proceed. |
| 2026-05-23 | **PRELAUNCH-OPS-RUNTIME-VERIFY-01 F5 (client sync):** Wales HMO pilot — issue→WO→contractor complete with dashboard/protection-snapshot/open-count/command-center projection coherence; G9/G10/convergence/browser PASS → **`VERIFIED_OPERATIONALLY`**; bundle `backend/docs/audit/ops_runtime_05_client_sync_6fd5ac4c_d35a58ae/`. F6 may proceed. |
| 2026-05-23 | **PRELAUNCH-OPS-RUNTIME-VERIFY-01 F6 (rent ops):** Wales HMO pilot — partial+full payment on ledger `rlp_e444e72a552c`, summary/ledger coherence, duplicate payment rejected, G9/G10/convergence/landlord browser PASS → **`VERIFIED_OPERATIONALLY`**; bundle `backend/docs/audit/ops_runtime_06_rent_ops_6fd5ac4c_d35a58ae/`. F7 may proceed. |
| 2026-05-23 | **PRELAUNCH-OPS-RUNTIME-VERIFY-01 F6 refinement:** payment-date authority, partial-overdue urgency, mobile clarity, monotonic truth, reminder idempotency — same-run OPS `20260523T204027Z` → **`VERIFIED_OPERATIONALLY`** (R1–R5 PASS); bundle updated. F7 may proceed. |
| 2026-05-23 | **PRELAUNCH-OPS-RUNTIME-VERIFY-01 F7 (tenant portal):** Wales HMO — cross-role maintenance sync PASS; **G10 FAIL** — `ROLE_TENANT` accessed `/api/client/*` → **`FAIL_SYSTEM`**; run `20260523T211806Z`. |
| 2026-05-23 | **PRELAUNCH-OPS-RUNTIME-VERIFY-01 F7 deploy verify:** F7 remediation **not on origin/main** (`a4b23caa`); staging smoke — tenant rent summary **200**, maintenance POST **200** → precheck **FAIL**; full OPS rerun **not executed**; classification unchanged **`FAIL_SYSTEM`**. |
| 2026-05-23 | **PRELAUNCH-OPS-RUNTIME-VERIFY-01 verification-chain remediation:** commit `128736db` — decouple `tenant_route_guard` from landlord `client_route_guard`; staging smoke — tenant `/api/tenant/*` **200**, `/api/client/*` **403**; F3 contractor continuity reproved (`contractor-login` + WO list **200**); F3/F5/F6 audit bundles committed to origin; F7 classification unchanged **`FAIL_SYSTEM`** until full same-run OPS rerun. |
| 2026-05-24 | **PRELAUNCH-OPS-RUNTIME-VERIFY-01 F8 (cross-domain):** Wales HMO — single same-run chain tenant→landlord→WO→contractor→risk→projections→rent→tenant visibility; G9/G10/convergence/browser PASS → **`VERIFIED_OPERATIONALLY`**; bundle `backend/docs/audit/ops_runtime_08_cross_domain_6fd5ac4c_d35a58ae/`. Programme F1–F8 operational closure complete (not launch authorization). |
| 2026-05-20 | **PRELAUNCH-OPS-RUNTIME-VERIFY-02 (hardened charter):** client operational-control surface verification programme defined — operational cognition model, G0 programme precheck owner, G2/G7 projection authority boundary, G5 documents surface boundary, G6 calendar scope boundary, G-CTA-NOOP (`FAIL_OPERATIONAL_NOOP`), extended classifications (`COGNITIVE_TRUST_RISK`, `PROJECTION_AUTHORITY_DRIFT`, `SURFACE_SCOPE_DRIFT`); **separate from** VERIFY-01 domain proof; execution not started — `docs/PRELAUNCH_OPS_RUNTIME_VERIFICATION_02.md`; `LAUNCH_AUTHORITY_TRACKER.md` § PRELAUNCH-OPS-RUNTIME-VERIFY-02. |
| 2026-05-24 | **PRELAUNCH-OPS-RUNTIME-VERIFY-02 G0:** first runtime execution Wales HMO pilot — lineage F1–F8 intact; all 7 surfaces reachable (browser+API); route authority coherent; **CONTROL_PLANE_CIRCULARITY** (7 static-graph cycles `resolution_reachable=false`, 4 unresolved escalation chains); deploy_sha ambiguous; bundle `ops_control_g0_programme_precheck_6fd5ac4c_d35a58ae` — G1 blocked. |
| 2026-05-20 | **PRELAUNCH-OPS-RUNTIME-VERIFY-02 (framework IMPLEMENTATION_READY):** `backend/services/ops_runtime_verify_02/` shared control-plane verification primitives; G0 harness `tmp_ops_control_g0_programme_precheck_execute.py` (scaffold-only default); audit scaffolds `ops_control_verify_02/` + `ops_runtime_g1..g7` STATUS `NOT_EXECUTED`; tests `test_ops_runtime_verify_02_framework.py` — no G0/G1–G7 runtime execution. |
| 2026-05-20 | **PRELAUNCH-OPS-RUNTIME-VERIFY-02 (control-plane rev 4):** `CONTROL_PLANE_CIRCULARITY` + `PROJECTION_RESOLUTION_ORDER` models — navigation loop detection, canonical projection hierarchy (live→attention→property→derived→exported), classifications `PROJECTION_RESOLUTION_FAILURE` / `PROJECTION_LAG_UNDISCLOSED`, G0 extended `route_authority_map.json`, checkpoints G-CYCLE / G-RESOLVE; execution not started — `docs/PRELAUNCH_OPS_RUNTIME_VERIFICATION_02.md`. |
| 2026-05-20 | **PRELAUNCH-OPS-RUNTIME-VERIFY-02 (control-plane rev 3):** programme reclassified as **OPERATIONAL_CONTROL_PLANE_VERIFICATION** — G1 attention authority (`ATTENTION_PRIORITY_DRIFT`, `OPERATIONAL_ATTENTION_CONTRADICTION`), G2 widget-island model (`WIDGET_ISLAND_FAILURE`), G7 report freshness authority (`REPORT_FRESHNESS_DECEPTION`), operational orphan state model, G0 `route_authority_map.json`, checkpoints G-ATTN/G-WIDGET/G-FRESH/G-ORPHAN; execution not started — `docs/PRELAUNCH_OPS_RUNTIME_VERIFICATION_02.md`. |
