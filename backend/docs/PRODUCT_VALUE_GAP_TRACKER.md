# Product value gap tracker

**Purpose:** Track **product-value** and **retention** gaps (trust, continuity, cognitive load, completeness) identified in `PROPERTY_COMPLIANCE_OS_GAP_AND_RETENTION_AUDIT.md` and related product governance — **without** duplicating the closed-loop **architecture** tracker, stream matrices, or operational runbooks.

**Does not replace:** `CLOSED_LOOP_COMPLIANCE_ARCHITECTURE_TRACKER.md`, Streams **A–F** matrices, or `RUNBOOK_CONTROLLED_BETA_OPERATIONS.md`.

**Aligns with:** `PROPERTY_COMPLIANCE_OS_GAP_AND_RETENTION_AUDIT.md` (strategic audit); architecture authority remains in the architecture tracker and stream docs.

---

## 1. Purpose and rules

### Why this tracker exists

Architecture streams and matrices govern **correctness** and **single writers**. This tracker governs whether work **improves user-perceived value**: trust, retention, workflow continuity, and cognitive simplicity. Items here may **span** streams; they must still **respect** named authorities and not invent parallel truth.

### Rules for every value-gap item

Each gap (existing or future) must be describable in terms of:

| Dimension | What to record |
|-----------|----------------|
| **User question improved** | Which of the core user questions (from the audit) get a clearer answer. |
| **Fragmentation reduced** | Which disconnected surfaces or mental stitches become fewer. |
| **Trust risk reduced** | What misunderstanding or “two truths” risk is lowered. |
| **Retention risk reduced** | What abandonment or support-dependence driver is addressed. |
| **Existing authorities reused** | Named modules, resolvers, services, or docs (per architecture tracker) — **no** second scoring path, second resolver, or second remediation truth without explicit programme sign-off. |
| **Streams affected** | Stream(s) A–F touched (for coordination only — stream acceptance still governs implementation). |

This tracker **does not** approve bypassing stream rules. It **prioritises product outcomes** within those rules.

---

## 2. Product value gap statuses

| Status | Meaning |
|--------|---------|
| **Identified** | Gap named; problem and target outcome understood at product level. |
| **In Design** | UX/product design in progress; authorities and boundaries chosen. |
| **In Implementation** | Engineering work underway against design + stream PR rules. |
| **Partial** | Some user value delivered; continuity or trust not yet at target. |
| **Stabilized** | Behaviour and copy stable; edge cases documented for users/support. |
| **Verified** | Validated against retention/trust goals (e.g. research, beta criteria, support metrics — as defined by product). |
| **Deferred** | Explicitly parked with reason (capacity, dependency on stream closure, product decision). |

---

## 3. Initial value gaps

### PVG-001 — Unified Compliance Work Queue

| Field | Content |
|-------|---------|
| **ID** | PVG-001 |
| **Priority** | P0 |
| **Related audit sections** | §3.2, §3.3, §3.4, §3.5, §4, §7, §9, §10 (`PROPERTY_COMPLIANCE_OS_GAP_AND_RETENTION_AUDIT.md`) |
| **User questions affected** | What exactly is wrong? What should I do next? How urgent is it? Can I act directly? Can I track remediation? |
| **Current fragmentation** | Dashboard summary; `unified_tasks_service`; Today; priority actions; `compliance_gaps`; risk signals; `maintenance_issues`; `work_orders`. |
| **Target continuity outcome** | One **tenant-facing** operational queue where each row has: issue, affected property, urgency, reason, compliance impact, **valid** action, owner/status, proof state, completion state — without inventing a second source of truth. |
| **Linked streams** | Stream C, Stream D, Stream E, Stream F |
| **Authorities to reuse (non-exhaustive)** | `unified_tasks_service` / priority stream patterns; `requirement_action_resolver` (Stream D); gap and outcome semantics (Stream C/E); audit/read models (Stream F). |
| **Design document** | `UNIFIED_COMPLIANCE_WORK_QUEUE_DESIGN.md` |
| **Wireframe & copy spec (v1)** | `UNIFIED_COMPLIANCE_WORK_QUEUE_WIREFRAME_V1.md` |
| **Status** | **Controlled beta stabilization** — thin vertical slice shipped; scope expansion gated (see § below). |
| **Completed work** | **Backend:** read-only assembler `get_unified_compliance_work_queue_v1` in `services/unified_compliance_work_queue_service.py` (calls `get_unified_tasks_for_client` only; excludes `tenant_message` / `tenant_request`; v1 DTO with `urgency_band`, `primary_action` + optional nested `take_action`, `closure_summary_user`, `related_ids`; sorts by unified `impact_score` + id + property). `GET /api/client/work-queue` in `routes/client.py`. `gap_key` copied onto unified task `metadata` in `unified_tasks_service.py` when present on priority actions (for `remediation_key` / related ids). **Frontend:** `clientAPI.getWorkQueue`, `/work-queue` route in `App.js`, `ClientWorkQueuePage.js` (empty state, urgency badge, closure line, primary action via `resolveTaskCta` + `workQueueRowToTask`), dashboard entry button in `ClientDashboard.js` (Inbox snapshot card). **Tests:** `tests/test_unified_compliance_work_queue.py`; `ClientWorkQueuePage.test.js`; `ClientDashboard.workQueueEntry.test.js`. **Stream D / trust (client):** Shared `requirementIntelligenceLabels` humanises workflow/compliance/evidence copy; **RequirementIntelligenceModal** removes audit/registry debug rows, orphan “Request help”, and misleading “Book inspection” secondary; shows **Accepted evidence** from `registry_metadata.evidence_resolution.allowed_evidence_modes`; tenant-safe applicability and active-job summary; **PropertyDetailPage** compliance row removes per-row “Request help”. **Resolver fallbacks** (`requirementTakeActionResolver`): clearer document labels (e.g. legionella, gas, EICR) when API `take_action` absent — still no second SSOT when `take_action.primary` is present. |
| **Files changed (implementation)** | `backend/services/unified_compliance_work_queue_service.py` (new), `backend/services/unified_tasks_service.py`, `backend/routes/client.py`, `backend/tests/test_unified_compliance_work_queue.py` (new); `frontend/src/api/client.js`, `frontend/src/App.js`, `frontend/src/pages/ClientWorkQueuePage.js` (new), `frontend/src/pages/ClientWorkQueuePage.test.js` (new), `frontend/src/pages/ClientDashboard.js`, `frontend/src/pages/ClientDashboard.workQueueEntry.test.js` (new). Design docs unchanged in this slice except this tracker row. |
| **Tests run** | `python -m pytest tests/test_unified_compliance_work_queue.py` (11 passed). `npx craco test --watchAll=false --testPathPattern=ClientWorkQueuePage.test` and `--testPathPattern=ClientDashboard.workQueueEntry` (all passed). |
| **Narrowed v1 scope decision** | Unchanged from design: projection-only, unified pipeline only, no tenant_request rows in UCWQ, three urgency bands, no raw gap primary CTA. **Not shipped in this slice:** `show_inbox_overlay_note`, advanced filters/sort UX, search, snoozed rows in the list. |
| **Remaining blockers before implementation** | During **controlled beta stabilization**, treat **non–bug / non–trust** enhancements as **deferred** unless they meet the expansion gates in the § below. |
| **Remaining risks** | Same as design: projection must never become a ledger; Rule R2 and dedupe-by-requirement-only remain regression targets as the queue gains features; guided-evidence rows depend on `take_action` remaining available inside `primary_action` for resolver parity. **Upstream task identity:** `get_unified_tasks_for_client` uses `task_id` = `requirement:{related_requirement_id}`, so **multiple gap-backed priority actions for the same requirement collapse to one unified task** before UCWQ — affecting Today and Command Centre the same way. See `DECISION_MULTI_GAP_TASK_IDENTITY.md`. |
| **Next recommended step** | **Observation-first stabilization** per `BETA_OBSERVATION_AND_TRUST_REVIEW.md`: production/beta monitoring, trust and copy alignment with design docs, bugs and beta feedback triage; **no** scope expansion beyond this row’s gates without evidenced pattern. **Multi-gap task identity** remains an explicit architecture/product decision (`DECISION_MULTI_GAP_TASK_IDENTITY.md`) — not a default trigger for UCWQ-only feature work. Deferred enhancements (filters, search, `show_inbox_overlay_note`, etc.) only after stabilization exit criteria or explicit scope change. |

#### PVG-001 — Controlled beta stabilization mode (governance)

**Scope expansion is not allowed unless** one of: **bug**; **trust issue**; **architectural drift issue**; **beta feedback pattern** (recurring, evidenced); **documented blocker** (named in this tracker or linked decision record).

**Do not add** (until explicitly out of stabilization and product re-scopes): new remediation workflow states; comments/notes system; assignment systems; search; custom sorting persistence; separate queue persistence; new urgency engine; `tenant_request` integration; per-row scoring overlays.

**Authoritative references for all PVG-001 work:** `PRODUCT_VALUE_GAP_TRACKER.md` (this row), `UNIFIED_COMPLIANCE_WORK_QUEUE_DESIGN.md`, `DECISION_MULTI_GAP_TASK_IDENTITY.md`. Wireframe copy remains `UNIFIED_COMPLIANCE_WORK_QUEUE_WIREFRAME_V1.md` for UX wording.

**Classify every change** as one of: **stabilization** (fixes, monitoring, small regressions); **UX clarification** (copy, a11y, layout honesty); **trust improvement** (disclosure, alignment with authorities, no new SSOT); **architecture fix** (authority alignment, drift); or **deferred** (record here or in design deferrals — not shipped in stabilization).

---

### PVG-002 — Resolution Continuity

| Field | Content |
|-------|---------|
| **ID** | PVG-002 |
| **Priority** | P0 |
| **Related audit sections** | §3.6, §4, §5, §7, §9 |
| **User questions affected** | Can I track remediation start to finish? Did my action work? Is the issue actually resolved? |
| **Current fragmentation** | Evidence upload; verification; jobs/work orders; gaps; score recalculation; audit trail. |
| **Target continuity outcome** | Users can see the **chain**: problem detected → action started → evidence submitted → verified → score updated → resolved — within honest async and closure semantics (Stream C). |
| **Linked streams** | Stream C, Stream E, Stream F |
| **Authorities to reuse (non-exhaustive)** | Remediation correlation vocabulary; `create_audit_log`; fan-out / recalc outcomes (Stream E); reconstruction order (Stream F). |
| **Status** | Identified |

---

### PVG-003 — Applicability Confidence

| Field | Content |
|-------|---------|
| **ID** | PVG-003 |
| **Priority** | P1 |
| **Related audit sections** | §3.1, §3.9, §7, §12 |
| **User questions affected** | Why does this requirement apply to me? Can I trust this obligation? |
| **Current fragmentation** | Policy registry; materialised requirements; applicability provenance; operator overrides; dashboard/report projections. |
| **Target continuity outcome** | Every **client-visible** requirement can explain why it applies, what rule/jurisdiction triggered it, and whether posture is **pipeline-derived** or **operator-adjusted** (transparently). |
| **Linked streams** | Stream A, Stream B, Stream F |
| **Authorities to reuse (non-exhaustive)** | `resolve_policy_facts`, effective resolver, provenance pipeline, client projection helpers (per architecture tracker Stream A); scoring exposure (Stream B); audit for overrides (Stream F). |
| **Status** | Identified |

---

### PVG-004 — Self-Explaining Async States

| Field | Content |
|-------|---------|
| **ID** | PVG-004 |
| **Priority** | P1 |
| **Related audit sections** | §3.1, §3.7, §5, §6, §7 |
| **User questions affected** | Why has my score not changed yet? Is the platform stuck or still calculating? |
| **Current fragmentation** | Recalc queue; stale score states; `score_status` / `score_status_message`; dashboards; exports; command centre. |
| **Target continuity outcome** | Users understand **pending**, **calculating**, **stale**, **partial**, and **snapshot** states **without** defaulting to support interpretation — copy and layout aligned to Stream B honesty. |
| **Linked streams** | Stream B, Stream E, Stream F |
| **Authorities to reuse (non-exhaustive)** | `compliance_scoring_service` / score status semantics; queue observability patterns (tenant-safe subset); export snapshot doctrine. |
| **Status** | Partial |
| **Completed work** | **Work queue async-honesty slice (frontend):** `ClientWorkQueuePage` loads portfolio headline via **`GET /api/client/compliance-score`** (`clientAPI.getComplianceScore`) — same authority as dashboard, no parallel scoring contract. Copy and non-ok detection reuse **`scoreFreshnessUi`** (`resolveDashboardFreshnessExplanation`, shared fallbacks; `isWorkQueueScoreHeadlineDegradedStatus` + `WORK_QUEUE_SCORE_SNAPSHOT_LOAD_FAILED` for classification). **UX:** healthy `score_status` → **no** headline strip (quiet); non-ok → short explanation only. **Three UI lanes:** processing-style non-ok (e.g. calculating / partial / stale) vs **degraded** statuses (unavailable / unknown / reconciliation_required) vs **compliance-score fetch failure** (safe fallback copy, not “calculating”). **`visibilitychange`** refetches headline only when the tab becomes visible so resolved backend states can replace pending copy without implying instant or real-time guarantees. Initial page load uses `allSettled` so work-queue list errors and headline fetch failures stay separable. **Phase 2 — `risk_signal_regen_worker` job_runs outcome honesty (backend):** `run_risk_signal_regen_worker` now returns `outcome_status` / `outcome_metrics` that distinguish **queue empty** (`NO_WORK_ELIGIBLE`, `conditional_no_output`), **regenerations** (`WORK_PERFORMED` / `success`), **feature-flag skips** (`BLOCKED`, not counted as `regenerated_count`), **all failures** (`FAILED` / `failed`), and **partial batch** (`DEGRADED`). `count` aligns with **`regenerated_count`** only (not flag skips). `job_runner.run_instrumented` passes **`outcome_metrics`** into **`finish_job_run_failure`** when a run ends **`failed`**, so failed job rows are not stored with empty counters. **`compliance_score_snapshots` job_runs slice:** `run_compliance_score_snapshots` returns structured **`outcome_metrics`** (clients + per-property snapshot counts, enumeration failures) and **`outcome_status`** (`conditional_no_output` when no ACTIVE clients; **`degraded`** when any client or property snapshot path fails; **`failed`** when all client portfolio snapshots fail; **`success`** when fully healthy). Catastrophic outer failures **re-raise** (no false-success dict). Property snapshot write failures are counted (**`failed`**) instead of log-only swallowing. **`compliance_recalc_worker` job_runs slice:** Structured **`outcome_metrics`** (batch size, claimed vs claim-skipped, processed to DONE, FAILED-for-retry vs DEAD); **`conditional_no_output`** when **queue empty**; **`success`** with **CONTENTION_ONLY** when due rows exist but **no claims** (race); **`degraded`** / **`failed`** when queue items fail or terminal DEAD so partial/full batch failure is not recorded as generic success. Control Centre skip when **`queue_empty`**. No fake “score changed” metrics. **Admin-only (async recalc honesty):** Automation Centre human-readable summaries for **`compliance_recalc_worker`** (from existing **`job_runs`** counters) clarify empty queue vs contention vs completed vs retry/DEAD for operators—**not** a tenant-facing work-queue or dashboard change. |
| **Files changed (implementation)** | `frontend/src/api/client.js` (`getComplianceScore`); `frontend/src/pages/ClientWorkQueuePage.js`; `frontend/src/pages/ClientWorkQueuePage.test.js`; `frontend/src/utils/scoreFreshnessUi.js` (PVG-004 helpers + fetch-fallback string). **Phase 2:** `backend/services/risk_signal_regen_queue.py`; `backend/services/job_run_service.py` (`finish_job_run_failure` optional `outcome_metrics`); `backend/job_runner.py`; `backend/tests/test_risk_signal_regen_worker_outcomes.py` (new). **Snapshots:** `backend/services/compliance_trending.py`; `backend/services/compliance_snapshot_job_outcomes.py` (new); `backend/services/control_centre_service.py`; `backend/tests/test_compliance_snapshot_job_outcomes.py` (new). **Recalc worker:** `backend/services/compliance_recalc_worker_job_outcomes.py` (new); `backend/job_runner.py` (`run_compliance_recalc_worker`); `backend/tests/test_compliance_recalc_worker_job_outcomes.py` (new). |
| **Tests run** | `npx craco test --watchAll=false --testPathPattern=ClientWorkQueuePage.test` (all passed). Covers: **healthy silence** (no strips when `score_status` is ok); **calculating → resolved** after headline refetch (simulated via `visibilitychange`); **degraded vs processing** testids/copy lanes; **fetch-failure** fallback (not conflated with processing). **Phase 2:** `python -m pytest tests/test_risk_signal_regen_worker_outcomes.py` (6 passed): empty queue; flag skip counters; successful regen; terminal **DEAD** queue path with **failed** job outcome; mixed batch **degraded**; retry **FAILED** queue row unchanged. **Snapshots:** `python -m pytest tests/test_compliance_snapshot_job_outcomes.py` (8 passed). **Recalc worker:** `python -m pytest tests/test_compliance_recalc_worker_job_outcomes.py` (8 passed). |
| **Remaining risks** | **Trust:** prolonged non-ok headline states can still feel like “nothing is working” even with honest copy. **Correctness:** tenant trust depends on **`score_status` classification** matching real backend behaviour. **Refresh:** `visibilitychange` is **opportunistic** — users who never background the tab may not see convergence until a full navigation/refresh; no guarantee of immediate UI sync after recalc. **Observation:** warning fatigue or score-vs-queue confusion if non-ok is frequent — track during beta (`BETA_OBSERVATION_AND_TRUST_REVIEW.md`). **Risk regen job_runs:** Control Centre and other readers must interpret **`count`** as **regenerations only** (not dequeue/attempt totals); callers that assumed legacy “processed” semantics should be validated in ops review. |
| **Next recommended step** | **Paused for broad rollout** — gather **evidence** (frequency/duration of non-ok states, confusion vs defects, fatigue signals) per `BETA_OBSERVATION_AND_TRUST_REVIEW.md` before adding async-honesty to further surfaces. **Allowed without new scope:** small **`scoreFreshnessUi`** / visual-noise tweaks, bug fixes. Next surface for a slice **only** if evidence names it and duplication with Dashboard is avoided. **Ops:** confirm Command Centre / admin job views surface **`outcome_metrics`** for **`risk_signal_regen_worker`** in a tenant-safe, non-misleading way (especially **`outcome_kind`** and **`skipped_feature_flag_count`** vs **`regenerated_count`**). |

---

### PVG-005 — Severity and Urgency Normalisation

| Field | Content |
|-------|---------|
| **ID** | PVG-005 |
| **Priority** | P2 |
| **Related audit sections** | §3.4, §5, §6, §9 |
| **User questions affected** | How urgent is this? What should I deal with first? |
| **Current fragmentation** | Gap severity; risk level; task priority; work order SLA; score impact. |
| **Target continuity outcome** | A **consistent** user-facing urgency model across compliance gaps, risk signals, work orders, and tasks — mapped from existing severities without exposing raw internal SLA mechanics to tenants unless product chooses. |
| **Linked streams** | Stream C, Stream D, Stream E |
| **Authorities to reuse (non-exhaustive)** | Existing severity fields and resolver/priority pipelines; Stream C/D/E matrices for semantics. |
| **Status** | Identified |

---

### PVG-006 — Support Dependency Reduction

| Field | Content |
|-------|---------|
| **ID** | PVG-006 |
| **Priority** | P1 |
| **Related audit sections** | §6, §7, §10, §12 |
| **User questions affected** | Can I understand this without contacting support? Can I trust the platform’s explanation? |
| **Current fragmentation** | Support runbooks; internal correlation view; weak joins in forensics; async explanations; operational recovery knowledge concentrated in admin/support. |
| **Target continuity outcome** | Common confusion points are **explained inside the product** (tenant-safe) before they become tickets — **without** treating internal correlation JSON or admin-only tools as tenant truth. |
| **Linked streams** | Stream B, Stream C, Stream F |
| **Authorities to reuse (non-exhaustive)** | Honest score messaging; Stream C closure semantics in user copy; optional read-only narratives derived from audit/gap facts — not a new remediation engine. |
| **Status** | Partial |
| **Completed work** | **`risk_signal_regen_worker` forensics slice:** Job runs now persist explicit **`outcome_metrics`** (`attempted_count`, `regenerated_count`, `skipped_feature_flag_count`, `failed_count`, `queue_empty`, `outcome_kind`) and aligned **`outcome_status`**, so support and ops can see **no eligible work**, **real regenerations**, **cleared due to predictive-maintenance flag off**, **failed/degraded batches**, and **retry vs DEAD** queue semantics without inferring from a misleading **`processed`-style count**. Failed **`run_instrumented`** completions can store those counters via **`finish_job_run_failure(..., outcome_metrics=...)`**. Audits for success and failure regeneration paths are unchanged. **`compliance_score_snapshots`:** same **`job_runs`** contract — per-client and per-property snapshot counters, truthful **`degraded`** / **`failed`** / **`conditional_no_output`**, Control Centre guard for intentional **no ACTIVE clients** runs. **`compliance_recalc_worker`:** queue batch honesty (claim-skipped vs processed vs retry vs DEAD) on **`job_runs`** without asserting score deltas. **Automation Centre:** human-readable **`compliance_recalc_worker`** outcome summaries (empty queue, contention-only, completed recalculations, retry failures, DEAD items) plus optional technical JSON; degraded/failed **(review)** tooltips are job-aware so this worker is not steered toward Message logs. |
| **Files changed (implementation)** | `backend/services/risk_signal_regen_queue.py`; `backend/services/job_run_service.py`; `backend/job_runner.py`; `backend/tests/test_risk_signal_regen_worker_outcomes.py` (new). **Also:** `backend/services/compliance_trending.py`; `backend/services/compliance_snapshot_job_outcomes.py`; `backend/services/compliance_recalc_worker_job_outcomes.py`; `backend/services/control_centre_service.py`; `backend/tests/test_compliance_snapshot_job_outcomes.py`; `backend/tests/test_compliance_recalc_worker_job_outcomes.py`; Automation Centre / Control Centre presentation files from related admin honesty work. **Recalc Automation Centre UI:** `frontend/src/utils/complianceRecalcWorkerAdminSummary.js`; `frontend/src/utils/complianceRecalcWorkerAdminSummary.test.js`; `frontend/src/utils/automationCentreReviewHints.js`; `frontend/src/utils/automationCentreReviewHints.test.js`; `frontend/src/pages/AdminAutomationCentrePage.js`. |
| **Tests run** | `python -m pytest tests/test_risk_signal_regen_worker_outcomes.py` (6 passed). `python -m pytest tests/test_compliance_snapshot_job_outcomes.py` (8 passed). `python -m pytest tests/test_compliance_recalc_worker_job_outcomes.py` (8 passed). Frontend: `npx craco test --watchAll=false` with `--testPathPattern` matching `complianceRecalcWorkerAdminSummary` and `automationCentreReviewHints` (10 passed, 2 suites). |
| **Remaining risks** | **Admin UX:** raw `job_runs` / Control Centre presentation may still need copy or layout so **`conditional_no_output`** (empty queue or all flag-skips) is not read as “user-visible failure”. **Semantics:** any dashboard aggregating **`count`** for regen must treat it as **regenerated properties**; for **`compliance_score_snapshots`**, **`count`** is **client portfolio successes** in the healthy path (property counts live in **`outcome_metrics`**). **Scope:** other scheduled workers still have their own outcome vocabulary unless extended per evidence. **Control Centre aggregates:** “Automation outcome tallies (24h)” still sum **`attempted_count` / `success_count` / `failed_count`** across jobs with **mixed unit semantics** and may be **dominated by high-frequency `compliance_recalc_worker`** batch attempts — easy to misread as one comparable funnel. |
| **Next recommended step** | **Before public launch:** audit or redesign Control Centre **aggregate outcome tallies** so mixed job units are not misread as a single interpretable funnel. If internal job dashboards list **`risk_signal_regen_worker`**, add or adjust **admin-only** labels/tooltips for **`outcome_kind`** and the counter fields (no tenant-facing claims unless product signs off). Extend the same **outcome_metrics** pattern to other high-ticket batch jobs **only** where audits + `job_runs` gaps are evidenced. |

---

## 4. Rules for future value-gap implementation

Every PR that claims to advance a row in **§3** should document (in PR description or linked design note):

1. **Product value gap ID** (e.g. PVG-001).  
2. **User question improved** (explicit).  
3. **Fragmentation reduced** (which surfaces stitched or retired from user mental model).  
4. **Existing authority reused** (named module/API/doc per architecture tracker).  
5. **Cognitive load:** **increases** or **decreases** — and for whom (tenant admin vs end user).  
6. **New surface?** Yes/no — if yes, why it does not duplicate Today, Command Centre, correlation view, or dashboard without purpose.  
7. **Support dependency:** **reduced**, unchanged, or **risk of new tickets** (honest).  
8. **Second source of truth risk:** explicit **no** or mitigations (e.g. read-only projection from named writers only).

Architecture tracker PR rules (stream label, authority, tests) **still apply**.

---

## 5. What this tracker must not do

- **Must not** create duplicate architecture work or a parallel “stream” system.  
- **Must not** override Streams **A–F** acceptance criteria or the closed-loop architecture tracker’s governance.  
- **Must not** become an unconstrained **feature wishlist** — items stay tied to user questions and continuity outcomes.  
- **Must not** “approve” a **new remediation engine** or new authoritative store without **product and architecture** sign-off and tracker updates.  
- **Must not** treat **internal support tooling** (e.g. flag-gated correlation view, runbook procedures) as **tenant-facing product truth** — user-visible copy and surfaces must remain honest and authority-aligned.

---

## 6. Recommended first design target

**PVG-001 — Unified Compliance Work Queue** is the recommended **first design target**: it addresses the largest fragmentation wedge (§3.2–§3.5, §4, §9–§10) and orients subsequent continuity work.

**Explicit constraints for that design phase:**

- **Design only first** — no implementation commitment from this document alone.  
- **No implementation yet** until design names authorities, boundaries, and stream alignment.  
- **Must reuse existing authorities** (unified tasks, resolver, gaps, risk/ops patterns, audits) — see architecture tracker **Named authorities**.  
- **Must not create a new source of truth** — queue is a **projection** or **orchestration** of existing facts, not a second ledger.  
- **Must not** carelessly **duplicate** Today, Command Centre, or the **remediation correlation view** — differentiate by **tenant continuity** and **one-queue mental model**, or explicitly subsume with product approval.

---

## 7. Beta observation and trust review (stabilization phase)

During **controlled beta stabilization**, product and support use **`BETA_OBSERVATION_AND_TRUST_REVIEW.md`** as the structured framework for **behavioral trust**, **cognitive load**, **fragmentation signals**, and **support patterns** — **without** speculative features, new authorities, or duplicate status systems. Evidence-linked triage: **observe vs implement** per that document.

**PVG-001** and **PVG-004** are in **stabilization / observation** priority: fix defects and trust-preserving clarifications; **defer** broad PVG-004 async-honesty expansion until evidence supports the next surface.

---

## Document control

**Owner:** Product leadership (primary), with platform engineering and compliance architecture as reviewers.  
**Updates:** When a PVG status changes or a gap is added/deferred; keep this file short and reference the **audit** for narrative rationale. **Stabilization observation** milestones: see §7 and `BETA_OBSERVATION_AND_TRUST_REVIEW.md`.
