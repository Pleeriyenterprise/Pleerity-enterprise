# Beta observation and trust review

**Purpose:** Structured **stabilization and observation** during controlled beta — **behavioral trust**, **cognitive load**, **operational consistency**, and **fragmentation** signals — **without** replacing `PRODUCT_VALUE_GAP_TRACKER.md`, `CLOSED_LOOP_COMPLIANCE_ARCHITECTURE_TRACKER.md`, stream matrices, or `RUNBOOK_CONTROLLED_BETA_OPERATIONS.md`.

**Audience:** Product, engineering leads, support leads (triage), compliance architecture reviewers.

**Constraints (this phase):** No new product systems, no new authorities, no speculative UX features, no duplicate truth. Allowed work remains per `PRODUCT_VALUE_GAP_TRACKER.md` (stabilization, bugs, trust-preserving copy clarifications, small visual-noise reductions where evidence-backed).

**Aligned with:** `PROPERTY_COMPLIANCE_OS_GAP_AND_RETENTION_AUDIT.md` (continuity, trust, cognitive load); `RUNBOOK_CONTROLLED_BETA_OPERATIONS.md` (recovery discipline, support vs engineering escalation); stream docs **A–F** for authority vocabulary only (not new streams).

---

## 1. Scope and current priorities

| Priority | Intent |
|----------|--------|
| **Stabilize PVG-001** | Unified Compliance Work Queue in real usage — projection honesty, CTA/resolver parity, urgency/closure copy, **no** scope expansion beyond stabilization gates in the PVG row. |
| **Stabilize PVG-004** | Work Queue async-honesty slice only — **do not** add async-honesty banners broadly; observe trust, fatigue, confusion before further rollout. |
| **Observe** | Recurring confusion, trust failures, async misunderstandings, warning fatigue, support patterns. |
| **Preserve** | Named authorities (architecture tracker); no parallel remediation or scoring semantics. |

**Surfaces in focus for observation (not an implementation backlog):** client **Work queue**, **Dashboard** entry paths, **Today / unified tasks**, **Command Centre** bundles, **compliance score** headline patterns — as users actually navigate them.

---

## 2. Observation categories

### 2.1 Recurring user confusion

| Signal | Healthy | Risky | Evidence sources |
|--------|---------|-------|------------------|
| Users describe **one** mental model for “what needs work” | Language aligns with **unified task / queue** wording | Same user gives **contradictory** descriptions in one session | Interviews, support macros, session notes |
| Users know **where** to act | Primary CTA path matches resolver intent | “I clicked but nothing happened” **without** API/500 errors | Tickets tagged route + symptom |

### 2.2 Trust failures

| Signal | Healthy | Risky | Evidence sources |
|--------|---------|-------|------------------|
| Posture vs tasks | User accepts **honest async** (score lag, closure vs inbox) | User asserts **“wrong number”** or **“lying UI”** when authorities are consistent | Compare ticket to `validate-compliance-score` / runbook §4.1 |
| Score headline | User defers to Dashboard/compliance for **timing** | User treats Work queue **global** strip as **per-row** queue failure | Qualitative + route |

### 2.3 Async-state misunderstandings

| Signal | Healthy | Risky | Evidence sources |
|--------|---------|-------|------------------|
| “Calculating / stale” | Understood as **eventual** update | Interpreted as **broken** or **stuck job** | Support taxonomy; Stream B runbook alignment in responses |
| Tab / return | User returns later; headline **converges** when backend ok | **Single-tab** users never see update **and** blame product | Frequency of non-ok **duration** (ops/analytics if available) |

### 2.4 Warning fatigue signals

| Healthy | Risky |
|---------|-------|
| Non-ok score messaging **rare**; users **notice** when it appears | Same users see **amber** on **every** visit; “I ignore the yellow bar” |
| One primary warning **type** per screen | **Stacked** amber: list error + score strip + other |

**Evidence:** survey snippets, support “banner blind” language, repeat visits with same non-ok status (ops).

### 2.5 Abandonment after warnings

| Healthy | Risky |
|---------|-------|
| User completes **task** path despite headline non-ok | User **stops** using queue/dashboard after warning **without** defect |
| Session continues to **resolution** surfaces | **Bounce** after warning with no error logs |

**Evidence:** funnel if instrumented; support “gave up”; qualitative.

### 2.6 CTA confusion

| Healthy | Risky |
|---------|-------|
| Primary action matches **Stream D** resolver outcome | Clicks lead to **unexpected** surface **and** user says product is wrong | Compare to `STREAM_D` matrix / parity fixtures |
| Resolver gaps | **Engineering** defect (missing `take_action`) | **UX** defect (label vs outcome) |

**Evidence:** broken-CTA runbook path (`RUNBOOK_CONTROLLED_BETA_OPERATIONS.md` §4.4); API capture.

### 2.7 Support escalation patterns

| Healthy | Risky |
|---------|-------|
| Tickets map to **runbook** recovery or **known** limitation | Same **UX** question becomes **L2** without defect |
| **Infrastructure** incidents isolated | **Confusion** tickets scale with users, not incidents |

**Evidence:** ticket tags, escalation reason codes, volume vs MAU.

### 2.8 Repeated “system feels broken” reports

| Healthy | Risky |
|---------|-------|
| Reports tie to **logged** errors, queue stuck, mismatch | **No** repro; **no** defect; language = **distrust** / overload |
| Resolved with **validate** or enqueue | Resolved only by **explaining five surfaces** |

**Evidence:** correlation with incidents; post-mortem whether defect existed.

### 2.9 Cognitive overload indicators

| Healthy | Risky |
|---------|-------|
| Users complete **one** primary task per visit | “Too many statuses”; **paralysis** in interviews |
| Badges + copy **discriminable** | **Same** urgency color for **different** semantics |

### 2.10 Fragmentation across surfaces

| Healthy | Risky |
|---------|-------|
| Dashboard vs Work queue **stories** align within **honest** async | User maintains **spreadsheet** to reconcile **obligation** state |
| **One** place for “what to do next” for beta scope | **Scavenger hunt** across Today, CC, queue, gaps (audit §3.2) |

**Evidence:** user journey maps; support “where do I look?” frequency.

---

## 3. Observation signals (detailed)

For each signal: **healthy**, **risk**, **evidence**, **do not implement reactively**.

### 3.1 Non-ok `score_status` frequency (PVG-004)

| | |
|--|--|
| **Healthy** | Episodic; correlates with **real** recalc/backlog windows; clears when user returns to tab or later session. |
| **Risk** | **Majority** of sessions non-ok; **long** dwell with healthy backend. |
| **Evidence** | Aggregated status distribution (if instrumented); ops queue health; **not** gut feel alone. |
| **Do NOT trigger** | New polling, new timing UI, **duplicate** banners on Dashboard + Work queue **without** evidence of confusion. |

### 3.2 “Queue stuck” language when list API is 200

| **Healthy** | User distinguishes **task list** from **score headline**. |
| **Risk** | Support tickets: queue “not updating” when only **compliance-score** non-ok. |
| **Evidence** | Ticket text + same-session API health. |
| **Do NOT trigger** | Second queue semantics; **fake** live updates. |

### 3.3 Refresh / retry loops

| **Healthy** | Occasional refresh after **fetch failure** or documented incident. |
| **Risk** | Habitual F5 with **no** 5xx and **no** fetch-failure. |
| **Evidence** | Analytics; support. |
| **Do NOT trigger** | Polling; “always refresh” copy. |

### 3.4 Multi-gap / single row (PVG-001, `DECISION_MULTI_GAP_TASK_IDENTITY.md`)

| **Healthy** | Power users understand **one row per requirement** from unified pipeline; or issue **rare**. |
| **Risk** | Recurring “missing gap” when **multiple** `gap_key` exist — **documented** upstream behavior. |
| **Evidence** | Tickets referencing **same requirement**, multiple gaps; correlation view (support-only) confirms. |
| **Do NOT trigger** | UCWQ-only **second projection** that diverges from `get_unified_tasks_for_client` without architecture decision. |

---

## 4. Operational guidance

### 4.1 When to observe vs when to implement

| Situation | Action |
|-----------|--------|
| **Single** ticket, no repro | Log; **observe**; no product change. |
| **Pattern** (≥3 similar, **evidenced**) | Review in **cadence** §6; **may** allow copy/clarification in existing authorities. |
| **Defect** (500, wrong payload, resolver violation) | **Implement** fix per stream authority; update tracker if stream-affecting. |
| **Trust** issue with **no** defect | **Observe** first; prefer **support playbook** + runbook language; product narrative. |

### 4.2 Support issue: UX confusion vs system defect

| Clue | Likely confusion | Likely defect |
|------|------------------|---------------|
| Logs clean, APIs 200, score validate **match** | Mental model / fragmentation | Rare |
| 5xx, mismatch on validate, DEAD queue, R2 URL drift | **Defect** or ops | Escalate engineering per runbook |
| User cites **one** number **vs** another | Check **scope** (property vs portfolio vs export snapshot) — often **honest** divergence | If same scope **and** validate fails → defect |

**Trust issues** can coexist with **healthy** architecture — distinguish **explainability** from **incorrectness**.

### 4.3 Trust vs infrastructure failure

| Trust (product) | Infrastructure |
|-----------------|----------------|
| “I don’t understand why…” | Outage, timeout, error rate spike |
| Resolves with **education** / copy | Resolves with **rollback**, scale, fix deploy |
| **Fragmentation** in audit sense | **SLO** breach |

---

## 5. Do not overreact

Risks of **premature** reaction:

| Reaction | Risk |
|----------|------|
| **More banners** | Warning fatigue; users discount **all** warnings. |
| **More warnings** | Same; **anxiety** without **new** information. |
| **More processing states exposed** | **Trains** distrust of score; **cognitive** load ↑. |
| **Polling / realtime** | New **timing** expectations; violates **Stream B** honesty; **authority** creep. |
| **Duplicate status systems** | Second source of truth; **contradicts** architecture tracker rule 1. |
| **Parallel remediation flows** | Bypasses Stream C/E; audit and support **nightmare**. |

**Instead:** evidence → **single** shared semantics (`scoreFreshnessUi`-style), **one** surface at a time, **support** scripts aligned with runbook.

---

## 6. Lightweight evidence review record

Use one row per **significant** observation (not every ticket).

| Field | Description |
|-------|-------------|
| **Observation** | Short factual description (user language or metric). |
| **Affected surface** | e.g. Work queue, Dashboard, Today, Command Centre. |
| **Frequency** | one-off / occasional / recurring / widespread. |
| **Severity** | low / medium / high (trust, retention, ops). |
| **Evidence** | Ticket IDs, interview note, chart, incident link. |
| **Likely root cause** | UX fragmentation / defect / ops / education gap — **hypothesis**. |
| **Recommended action** | Observe / support macro / copy tweak / engineering fix / architecture decision — **no** code here. |
| **Implementation required?** | yes / no |
| **Related PVG** | e.g. PVG-001, PVG-004, PVG-006. |
| **Related Stream** | e.g. B, D, E — **coordination** only. |

---

## 7. Severity classification (observation)

| Level | Meaning | Typical response |
|-------|---------|------------------|
| **S0** | Safety/compliance misrepresentation **if** true defect | Immediate engineering + comms per runbook |
| **S1** | Widespread trust failure or **blocked** workflows | Evidence review within days; fix or comms |
| **S2** | Recurring confusion pattern; **no** single defect | Product/support playbook; **defer** feature expansion |
| **S3** | Isolated confusion | Log; monitor |

---

## 8. Observation review cadence

| Cadence | Activity |
|---------|----------|
| **Weekly** (beta active) | Support lead: **top** confusion tags, volume vs incidents; **any** new “feels broken” cluster. |
| **Bi-weekly** | Product + eng: **evidence table** review §6; decide **observe** vs **small** clarification vs **defect**. |
| **Monthly** | Revisit **PVG-001 / PVG-004** rows in `PRODUCT_VALUE_GAP_TRACKER.md` — **status** change only with evidence. |

**Exit from “heavy observation”** when product defines **verified** criteria (support rate, qualitative bar) — **not** this document alone.

---

## 9. What this product is becoming (identity lens)

**Current evidence from governance docs:** The programme combines **compliance intelligence** (scores, applicability, gaps), **operational compliance workspace** (tasks, queue, priorities), **remediation coordination** (Stream C correlation, CTAs, work orders), and **audit readiness** (Stream F, exports, honesty about snapshots). The **retention audit** explicitly warns against feeling like **multiple subsystems** rather than **one OS**.

| Archetype | Fit (today) | Risk if unclear |
|-----------|-------------|-----------------|
| **Compliance intelligence platform** | Strong: scoring, requirements, headlines | Users expect **oracle** certainty **vs** honest async |
| **Operational compliance workspace** | Strong: unified tasks, UCWQ slice | **Fragmentation** if every surface reinvents **status** |
| **Remediation coordination layer** | Partial: correlation strong **internal**; tenant lifecycle **fragmented** | Support carries **closure** narrative |
| **Audit readiness platform** | Strong on lineage; **tenant** narrative partial | Export vs live **confusion** |
| **Hybrid** | **Most accurate** today | **Identity** drift → roadmap fights; **warning** sprawl |

**Risk of unclear identity:** Inconsistent copy and **warning** patterns; users expect **one** product promise; engineering ships **local** optimizations that **sum** to **incoherence**.

**Observation implication:** Track **which** metaphor users use (“dashboard for compliance,” “task list,” “audit pack”) — **signals** where continuity work should **converge**, not new features.

---

## 10. Related documents

| Document | Role |
|----------|------|
| `PRODUCT_VALUE_GAP_TRACKER.md` | PVG statuses, stabilization gates, **do-not** rules |
| `PROPERTY_COMPLIANCE_OS_GAP_AND_RETENTION_AUDIT.md` | User questions, fragmentation diagnosis |
| `CLOSED_LOOP_COMPLIANCE_ARCHITECTURE_TRACKER.md` | Authorities, streams — **do not duplicate** |
| `RUNBOOK_CONTROLLED_BETA_OPERATIONS.md` | Support recovery, forbidden actions, escalation |
| `DECISION_MULTI_GAP_TASK_IDENTITY.md` | UCWQ / unified task cardinality decision point |
| `STREAM_B_SCORING_AUTHORITY_MATRIX.md` | Score semantics, consumers |
| `STREAM_D_CTA_PRODUCER_CONSUMER_MATRIX.md` | CTA ownership |
| `STREAM_C_REMEDIATION_CORRELATION_RUNBOOK.md` | Remediation vocabulary |
| `STREAM_E_MUTATION_FANOUT_MATRIX.md` | Event / recalc expectations |
| `STREAM_F_RECONSTRUCTION_CONSISTENCY.md` | Audit / reconstruction |

---

## Document control

**Owner:** Product (primary); support and engineering leads as contributors.  
**Updates:** When cadence §8 changes, or when a **major** observation pattern is confirmed; keep **evidence-linked**.
