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
| **Completed work** | **Backend:** read-only assembler `get_unified_compliance_work_queue_v1` in `services/unified_compliance_work_queue_service.py` (calls `get_unified_tasks_for_client` only; excludes `tenant_message` / `tenant_request`; v1 DTO with `urgency_band`, `primary_action` + optional nested `take_action`, `closure_summary_user`, `related_ids`; sorts by unified `impact_score` + id + property). `GET /api/client/work-queue` in `routes/client.py`. `gap_key` copied onto unified task `metadata` in `unified_tasks_service.py` when present on priority actions (for `remediation_key` / related ids). **Frontend:** `clientAPI.getWorkQueue`, `/work-queue` route in `App.js`, `ClientWorkQueuePage.js` (empty state, urgency badge, closure line, primary action via `resolveTaskCta` + `workQueueRowToTask`), dashboard entry button in `ClientDashboard.js` (Inbox snapshot card). **Tests:** `tests/test_unified_compliance_work_queue.py`; `ClientWorkQueuePage.test.js`; `ClientDashboard.workQueueEntry.test.js`. |
| **Files changed (implementation)** | `backend/services/unified_compliance_work_queue_service.py` (new), `backend/services/unified_tasks_service.py`, `backend/routes/client.py`, `backend/tests/test_unified_compliance_work_queue.py` (new); `frontend/src/api/client.js`, `frontend/src/App.js`, `frontend/src/pages/ClientWorkQueuePage.js` (new), `frontend/src/pages/ClientWorkQueuePage.test.js` (new), `frontend/src/pages/ClientDashboard.js`, `frontend/src/pages/ClientDashboard.workQueueEntry.test.js` (new). Design docs unchanged in this slice except this tracker row. |
| **Tests run** | `python -m pytest tests/test_unified_compliance_work_queue.py` (11 passed). `npx craco test --watchAll=false --testPathPattern=ClientWorkQueuePage.test` and `--testPathPattern=ClientDashboard.workQueueEntry` (all passed). |
| **Narrowed v1 scope decision** | Unchanged from design: projection-only, unified pipeline only, no tenant_request rows in UCWQ, three urgency bands, no raw gap primary CTA. **Not shipped in this slice:** `show_inbox_overlay_note`, advanced filters/sort UX, search, snoozed rows in the list. |
| **Remaining blockers before implementation** | During **controlled beta stabilization**, treat **non–bug / non–trust** enhancements as **deferred** unless they meet the expansion gates in the § below. |
| **Remaining risks** | Same as design: projection must never become a ledger; Rule R2 and dedupe-by-requirement-only remain regression targets as the queue gains features; guided-evidence rows depend on `take_action` remaining available inside `primary_action` for resolver parity. **Upstream task identity:** `get_unified_tasks_for_client` uses `task_id` = `requirement:{related_requirement_id}`, so **multiple gap-backed priority actions for the same requirement collapse to one unified task** before UCWQ — affecting Today and Command Centre the same way. See `DECISION_MULTI_GAP_TASK_IDENTITY.md`. |
| **Next recommended step** | Stabilization: production/beta monitoring, trust and copy alignment with design docs, bugs and beta feedback triage. **Multi-gap task identity** remains an explicit architecture/product decision (`DECISION_MULTI_GAP_TASK_IDENTITY.md`) — not a default trigger for UCWQ-only feature work. Deferred enhancements (filters, search, `show_inbox_overlay_note`, etc.) only after stabilization exit criteria or explicit scope change. |

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
| **Status** | Identified |

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

## Document control

**Owner:** Product leadership (primary), with platform engineering and compliance architecture as reviewers.  
**Updates:** When a PVG status changes or a gap is added/deferred; keep this file short and reference the **audit** for narrative rationale.
