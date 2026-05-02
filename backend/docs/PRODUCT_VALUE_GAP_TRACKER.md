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
| **Status** | In Design |
| **Completed work** | Unified Compliance Work Queue design in `UNIFIED_COMPLIANCE_WORK_QUEUE_DESIGN.md`. **Sign-off review completed** (scope lock, urgency mapping, closure language, navigation, v2 deferrals). **Tenant wireframe & copy spec drafted** in `UNIFIED_COMPLIANCE_WORK_QUEUE_WIREFRAME_V1.md` (page purpose, nav, empty state, row layout, urgency/closure/action copy, filters/sort, mobile, v1 exclusions, a11y, acceptance criteria). |
| **Files changed (design commit)** | `UNIFIED_COMPLIANCE_WORK_QUEUE_DESIGN.md`, `PRODUCT_VALUE_GAP_TRACKER.md` (PVG-001); `UNIFIED_COMPLIANCE_WORK_QUEUE_WIREFRAME_V1.md` (wireframe/copy spec). |
| **Tests run** | N/A (docs only). |
| **Narrowed v1 scope decision** | **Included:** priority/unified pipeline only (requirement/gap-overlay, risk, WO, issue, approval) — **no** raw gaps, **no** tenant_request rows. **DTO:** `closure_summary_user` + `show_inbox_overlay_note` (not three closure columns). **Urgency:** three bands from existing `_urgency_level` mapping. **Positioning:** secondary to Today / Command Centre. |
| **Remaining blockers before implementation** | **Product sign-off** on `UNIFIED_COMPLIANCE_WORK_QUEUE_WIREFRAME_V1.md` (nav label final choice: “Work queue” vs “Open work”, dashboard entry treatment, empty-state variant). **Engineering** route path + assembler contract review (no new authority). **No code** until product sign-off on wireframe spec. |
| **Remaining risks** | Second source of truth if projection becomes a ledger; **Rule R2** regression (raw gap `recommended_*` as primary); **`requirement_id`-only dedupe**; risk vs gap **double count** (often valid — needs clear UX); **eventual consistency** (mitigated by no v1 per-row score strip); **cognitive overload** if v1 ships wide columns (mitigated by narrow DTO). |
| **Next recommended step** | Formal **product approval** of wireframe/copy spec → PVG-001 → **In Implementation**; first PR implements assembler + route per design + wireframe, streams C/D/E, tests per design doc. |

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
