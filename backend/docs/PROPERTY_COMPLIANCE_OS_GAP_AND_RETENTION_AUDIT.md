# PROPERTY COMPLIANCE OS — GAP AND RETENTION AUDIT

**Document type:** Permanent product governance — user value, trust, retention, workflow continuity, operational cognition.  
**Not:** a stream tracker, implementation checklist, architecture matrix, or marketing narrative.

**Aligned with (for authority and doctrine; do not replace them):**  
`CLOSED_LOOP_COMPLIANCE_ARCHITECTURE_TRACKER.md`, `STREAM_B_SCORING_AUTHORITY_MATRIX.md`, `STREAM_C_REMEDIATION_CORRELATION_RUNBOOK.md`, `STREAM_D_CTA_PRODUCER_CONSUMER_MATRIX.md`, `STREAM_E_MUTATION_FANOUT_MATRIX.md`, `STREAM_F_RECONSTRUCTION_CONSISTENCY.md`, `RUNBOOK_CONTROLLED_BETA_OPERATIONS.md`.

---

## 1. Purpose of this document

### Why this audit exists

Closed-loop compliance work is governed by streams, matrices, and runbooks that prioritize **correctness**, **single writers**, **audit lineage**, and **operational recovery**. Those artefacts are necessary but **not sufficient** for product success: a system can be **architecturally sound** yet **fail users** if they cannot **infer trust**, **act with confidence**, and **stay oriented** month after month.

This document **permanently preserves** a product-level view: **value**, **trust**, **retention**, **workflow continuity**, **cognitive load**, and **operational burden** — so investment does not drift toward “technically sophisticated but operationally confusing” or “feature-rich but fragmented.”

### Architecture correctness vs user trust

**Architecture correctness** (named authorities, no duplicate truth, fan-out contracts) answers: “Did we build the machine right?”  
**User trust** answers: “Does the product **behave** as a coherent compliance companion — predictable, explainable, and **complete enough** that I do not need a mental model of the machine?”

Those questions diverge whenever **truth exists in multiple temporal forms** (persisted score vs live projections vs exports), **multiple surfaces** show related but non-identical answers, or **recovery depends on support** while the UI implies self-sufficiency.

### Internal authority discipline vs user-perceived reliability

Internal discipline (e.g. score persistence only via `recalculate_and_persist`, CTAs via `requirement_action_resolver`, remediation correlation vocabulary in Stream C) is **essential** and **non-negotiable** for auditability.  
**Perceived reliability** is what users feel when they ask: “After I acted, **did the platform** reflect success **everywhere that matters** — without me cross-checking five places?”

Discipline without **continuity of experience** still produces **distrust**: the backend may be “right,” but the user may conclude the product is “wrong” or “unfinished.”

### Why workflow continuity matters

Compliance work is a **sequence**: notice obligation → gather evidence → resolve gap → see posture update → prove closure. **Retention** lives in that chain feeling **continuous**. When users must **stitch** dashboard headline, property cards, requirement rows, gaps, tasks, work orders, risk surfaces, reports, and queue timing **in their heads**, the product feels like **several tools**, not one OS — even if each subsystem is well built.

### Why retention depends on cognitive simplicity and trust continuity

**Cognitive simplicity** reduces abandonment after onboarding. **Trust continuity** means each step **reinforces** the last (action succeeded → score/gap/task story **agrees** within honest async bounds). Where users need **support or runbook language** to interpret normal states (stale headline, pending recalc, closure vs inbox, applicability nuance), **retention is fragile** regardless of engineering quality.

### Evaluation criterion (explicit)

The platform is evaluated not only on correctness, but on whether users can **confidently** understand:

| Question | Product bar |
|----------|-------------|
| Their compliance state | One interpretable posture, with honest limits |
| What needs attention | One prioritized picture of risk, not scavenger hunts |
| What action to take | Primary actions that **complete** real workflows |
| Whether action succeeded | Visible convergence without forbidden shortcuts |
| Long-term trust | No silent divergence; no promise the UI cannot keep |

---

## 2. Executive summary

**What is strong**

- **Compliance infrastructure** is real: requirements, evidence paths, gap lifecycle, scoring service, recalc queue, SLA monitoring, outcome/fan-out semantics, audits, admin recovery and beta operations runbook (`RUNBOOK_CONTROLLED_BETA_OPERATIONS.md`).
- **Authority discipline** is explicit in tracker and matrices (Streams B–F; Stream A applicability governance still open).
- **Async honesty** work acknowledges persisted vs live and non-OK score states (Stream B matrix; UI honesty patterns aligned with scoring semantics).
- **Operational tooling** exists for support/admin (validate/repair score, enqueue, SLA alerts, correlation view behind product flag — see tracker Stream C notes).

**Core gap**

The platform still **partially** feels like **multiple compliance subsystems** rather than **one coherent Property Compliance OS**: users must often **reconcile** score story, remediation story, task/inbox story, risk/ops story, and operations story **themselves**. That is a **product continuity** gap, not merely an architecture backlog.

**Conclusion: not yet fully value-complete**

**Why:** Streams B–F remain **partial** in lifecycle terms; Stream A remains **material governance risk** for “what applies to me.” Remediation **correlation** is strong as **doctrine and internal tooling** but **not** a single tenant-visible **start-to-finish remediation lifecycle**. Async recalc and eventual fan-out (Stream E) are **honest** technically but still **tax** users who expect instant, unified truth. **Retention durability** therefore depends too much on **ICP fit** (compliance-literate users + support) rather than on **self-guiding** product continuity alone.

---

## 3. Core user-value questions

Strategic analysis only — not an implementation backlog.

### 3.1 Am I compliant right now?

| Dimension | Assessment |
|-----------|------------|
| **Strengths** | Portfolio headline metadata (`score_status`, messages, authority class) and per-surface honesty work (Stream B); dashboard combines summary counts and per-property status driven from requirement projections (`client` dashboard payload patterns). |
| **Weaknesses** | “Right now” **splits** across persisted headline timing, live requirement-derived signals, and async queue state; users must infer **which clock** answers their question. |
| **Fragmentation** | Headline vs property vs requirement narratives can **diverge** during pending recalc or partial coverage. |
| **Trust / cognitive-load risks** | Users treat one number or one color as **oracle**; honesty copy helps only if **seen and understood**. |
| **Workflow continuity** | Action → posture update is **eventual**; continuity breaks if marketing or layout implies immediacy. |
| **Maturity** | **Partial** (honest **partial** states exist; not **misleading** if surfaced well — **misleading** if oversold). |
| **Highest-leverage direction** | **Single interpretable “posture” framing** everywhere scores appear: timing context + scope + what “pending” means — without duplicating matrix content here. |

### 3.2 What exactly is missing, expired, risky, overdue, or stalled?

| Dimension | Assessment |
|-----------|------------|
| **Strengths** | Dashboard aggregates; requirement/gap surfaces; operational priorities exist for admin; client priority/unified task patterns exist. |
| **Weaknesses** | Taxonomy is **not one inventory**; “stalled” often maps to **queue/SLA** (ops), not a unified tenant “stuck work” model. |
| **Fragmentation** | Gaps, issues, work orders, risks, tasks — **related** but not **one list** with one urgency grammar. |
| **Trust risks** | User thinks they cleared work in one surface while another still shows open. |
| **Cognitive-load risks** | User must learn **which surface is authoritative for which noun** (Stream C closure vs inbox semantics). |
| **Maturity** | **Fragmented**. |
| **Highest-leverage direction** | **Unified compliance work queue** (conceptual): one ranked view of obligations + blockers with **explicit** non-closure paths where Stream C forbids fake completeness. |

### 3.3 What should I do next?

| Dimension | Assessment |
|-----------|------------|
| **Strengths** | Resolver-backed `take_action` for requirement-shaped work (Stream D); priority/unified digest endpoints; onboarding checklist on dashboard. |
| **Weaknesses** | Multiple “next” sources; closure semantics mean **compliance next** may differ from **inbox next** (Stream C runbook). |
| **Fragmentation** | Competing “next” without strict global ordering philosophy in product UX. |
| **Trust risks** | User follows wrong “next” and misses compliance-critical path. |
| **Maturity** | **Partial**. |
| **Highest-leverage direction** | **Narrow, ranked “next three”** that only includes rows with a **real** primary path or an explicit “manual / external” state — no decorative CTAs. |

### 3.4 How urgent is the issue?

| Dimension | Assessment |
|-----------|------------|
| **Strengths** | Severities on gaps/tasks; internal SLA monitor thresholds for recalc health. |
| **Weaknesses** | Deep urgency for **platform processing** is often **admin/ops** visibility, not mirrored as a **user-safe** unified urgency model. |
| **Fragmentation** | “Urgent” in UI vs “urgent” in SLA alerts vs “urgent” in risk — not one scale. |
| **Trust risks** | User underestimates risk of score lag or overestimates crisis from one red badge. |
| **Maturity** | **Operational-only** for infra-level urgency; **partial** for compliance urgency in UI. |
| **Highest-leverage direction** | **Unified urgency model** (product concept): map user-visible severities to honest async and SLA **without** exposing internal queue mechanics to tenants. |

### 3.5 Can I act directly inside the platform?

| Dimension | Assessment |
|-----------|------------|
| **Strengths** | Requirement resolver contract and parity enforcement direction (Stream D matrix + tests); evidence submission routes; workflows API. |
| **Weaknesses** | Risk/ops navigation intentionally **not** the requirement resolver (Stream D doctrine); Phase gaps (e.g. navigable URL completeness per tracker) still affect “always clickable.” |
| **Fragmentation** | Different action **grammar** for requirement vs risk vs ops. |
| **Trust risks** | Broken or empty primary CTA — user dead-end; support must not paper over with forbidden gap URL edits (runbook). |
| **Maturity** | **Partial** (strong where contract holds; **fragile** where contract breaks). |
| **Highest-leverage direction** | **No primary action without valid workflow** (product principle); expand **parity coverage** from real incident shapes (strategy: fixture-driven discipline — not task list here). |

### 3.6 Can I track remediation from start to finish?

| Dimension | Assessment |
|-----------|------------|
| **Strengths** | Stream C correlation doctrine; internal correlation view (flagged, non-authoritative); audits and reconstruction docs (Stream F). |
| **Weaknesses** | **No single tenant-visible lifecycle record** that spans gap → issue → WO → score (tracker: product-gated scope). |
| **Fragmentation** | Tenant sees slices; support sees correlation JSON; forensics sees joins — **continuity breaks at role boundary**. |
| **Trust risks** | “Where did my fix go?” — user cannot **narrate** closure across systems without help. |
| **Maturity** | **Fragmented** / **operational-only** for full story. |
| **Highest-leverage direction** | **End-to-end remediation continuity** for the **tenant** (read-only timeline acceptable): stable keys, explicit states, no false “done.” |

### 3.7 Can I trust recommendations, scores, and automation?

| Dimension | Assessment |
|-----------|------------|
| **Strengths** | Single score writer; admin validate/repair; mismatch audits; digest/PDF authority labeling direction (Stream B); async honesty in UI. |
| **Weaknesses** | Trust requires **literacy** in timing and snapshots; automation (recalc, fan-out) is **not invisible** to users emotionally. |
| **Fragmentation** | Export vs dashboard vs headline — **honest** but **easy to misunderstand**. |
| **Trust risks** | “Not lying” ≠ feeling **fair**; 500-class failures on evidence paths if dependencies fail undermine **emotional** trust. |
| **Maturity** | **Partial** (technical honesty strong; **emotional trustworthiness** incomplete). |
| **Highest-leverage direction** | **Emotional trust layer**: predictable failure surfaces, timing context on every score, export disclaimers **as product**, not footnotes only. |

### 3.8 Can I understand operational and financial impact?

| Dimension | Assessment |
|-----------|------------|
| **Strengths** | ROI-style summaries exist as separate client surfaces; compliance summary counts on dashboard. |
| **Weaknesses** | Integrated **impact per issue** (operational + compliance + financial) is **not** one coherent model in UX. |
| **Fragmentation** | ROI approximations vs compliance counts vs risk — user stitches meaning. |
| **Trust risks** | Over-precision perception on ROI-style metrics. |
| **Maturity** | **Partial**; risk of **misleading** if presented as precision. |
| **Highest-leverage direction** | **Impact framing** tied to top open items only — honest bounds, no fake precision. |

### 3.9 Does the platform reduce mental load?

| Dimension | Assessment |
|-----------|------------|
| **Strengths** | Checklist, summaries, guided evidence modes, resolver-backed CTAs reduce **search** cost for aligned ICP. |
| **Weaknesses** | Applicability complexity (Stream A), eventual consistency (Stream E), closure semantics (Stream C) **increase** load for general users. |
| **Fragmentation** | Many concepts visible without **progressive disclosure**. |
| **Trust / cognitive-load** | High **support-interpretation** risk for “normal” async states. |
| **Maturity** | **Partial**; **misleading** if marketed as “simple.” |
| **Highest-leverage direction** | **Applicability confidence** for end users: fewer unexplained rows; visible override semantics where operator truth exists. |

### 3.10 Does the platform feel complete enough for long-term retention?

| Dimension | Assessment |
|-----------|------------|
| **Strengths** | Ops runbook, SLA monitor, admin repair, queue — **operationally serious**. |
| **Weaknesses** | Self-serve **reliability narrative** incomplete; post-setup “why is it still yellow?” moments. |
| **Fragmentation** | Tenant UX vs admin recovery vs internal correlation — **continuity gap**. |
| **Trust risks** | Churn when users expected **set-and-forget** compliance truth. |
| **Maturity** | **Not value-complete** for broad retention; **operational-only** completeness internally. |
| **Highest-leverage direction** | **Self-guiding reliability**: in-product health and “what happens next” without opening runbooks. |

---

## 4. Workflow continuity analysis

**Where continuity holds**

- Requirement-shaped paths: evidence → authority sync intent → recalc enqueue (see client evidence routes and Stream E matrix rows for which mutations enqueue).
- Score updates: authoritative persistence path and admin repair when mismatch is real (Stream B).

**Where continuity breaks**

- **Requirements ↔ gaps ↔ tasks ↔ risks ↔ jobs**: users cross **different nouns and UIs**; backend joins exist for forensics (Stream F) but **tenant narrative** is not one thread.
- **Score updates ↔ dashboards ↔ exports**: different **time semantics** (persisted vs live vs snapshot) — documented in matrices but **not absorbed** as one user journey.
- **Remediation “done”**: compliance closure vs operational closure (Stream C) — **correct** but **discontinuous** for users expecting one “done.”

**Preserved insight**

> The backend often knows the truth better than the user does.

When queue state, fan-out stages, and audit chains hold richer truth than any **single** screen, users **infer incorrectly** unless the product **selects and narrates** truth for them. That asymmetry is a **retention risk**: users blame the product when their **mental model** (single screen = full truth) fails.

---

## 5. Trust continuity analysis

**Dimensions**

| Topic | Risk |
|-------|------|
| **Persisted vs live** | User compares two screens and concludes “bug.” |
| **Async recalc** | Honest states exist; without omnipresent timing context, feels like “laggy product.” |
| **Queue delay** | Internal truth; tenant sees only outcomes — **opacity** hurts trust during incidents. |
| **Contradictory screens** | Often **honest multi-clock** problem framed as contradiction. |
| **Export vs dashboard** | Snapshots vs live — **technically honest**, **emotionally** feels like “two products.” |
| **Support-dependent explanations** | Retention hazard: product **outsources** meaning to humans. |
| **Hidden operational complexity** | Recalc SLA, DEAD jobs, correlation view — **necessary** complexity must not **silently** change what users believe. |

**Technical honesty vs emotional trustworthiness**

“Not lying” means fields and states are **defensible**. **Emotional trustworthiness** means users feel **treated fairly**: predictable errors, clear next steps, **no** bait-and-switch between surfaces, and **no** score without **when** and **what scope**.

**Why “not lying” is not enough**

Long-term paying relationships require **low surprise**. Surprise is emotional. Architecture can be **correct** while the product **feels capricious** if users must constantly **re-learn** which surface to believe.

---

## 6. Cognitive load analysis

Users are implicitly asked to understand:

| Burden | Source (doctrinal / product) |
|--------|------------------------------|
| **Engineering concepts** | Pending recalc, queue, fan-out stages (Stream E logs). |
| **State timing** | `compliance_last_calculated_at`, headline vs drivers. |
| **Reconciliation** | Portfolio coverage vs per-property persistence. |
| **Task semantics** | Unified tasks vs compliance closure (Stream C). |
| **Closure semantics** | Today / risk / WO vs compliance met. |
| **Applicability complexity** | Pipeline vs effective truth (Stream A). |
| **Multiple operational surfaces** | Client dashboard, property detail, score pages, command center patterns, reports. |

**Preserved concern**

If **correct interpretation** of normal operation requires **support** or **internal runbook** language (`RUNBOOK_CONTROLLED_BETA_OPERATIONS.md`), the product is **not yet self-guiding** at the retention bar for a general property operations audience.

---

## 7. Retention risks

| Risk | Mechanism |
|------|-------------|
| **Support dependency** | Users hit async, CTA, or remediation discontinuity; only support/admin paths explain or recover safely. |
| **Workflow fragmentation** | No single “compliance OS” thread; users revert to spreadsheets/email for **narrative**. |
| **Stale-state confusion** | Headline vs detail during recalc or partial fan-out windows. |
| **Remediation continuity** | Cannot **show** end-to-end story to tenant without overstepping non-authoritative tools. |
| **Applicability confusion** | “Why is this here?” undermines every downstream surface. |
| **Operational confidence** | Incidents invisible to tenants; trust erodes when “the system feels stuck.” |

**Where abandonment happens**

After **initial setup**, when the product **does not converge** visually to the user’s mental model of “done,” or when **every update** requires **reconciliation** across modules. Power users may stay; **broad retention** weakens.

---

## 8. What currently feels strongest

| Strength | Why it matters commercially |
|----------|------------------------------|
| **Scoring authority discipline** | Defensible audits; repair path; fewer “silent wrong numbers” long-term. |
| **Auditability** | Enterprise buyers and regulated operators care about **story of change**. |
| **Resolver-backed actions** | Reduces random deep links; central contract (Stream D). |
| **Evidence flows** | Core operational value — capture proof where work happens. |
| **Async honesty work** | Prevents the worst trust failure: **lying** headline claims. |
| **Operational monitoring + admin recovery** | Platform can be **operated** seriously in beta/production with discipline (runbook + SLA). |

These are **differentiators** vs lightweight checklist tools — **if** the product layer completes the **continuity story** for users.

---

## 9. What currently feels fragmented

| Story | Fragmentation symptom |
|-------|------------------------|
| **Score** | Headline, drivers, property detail, exports — multiple clocks. |
| **Remediation** | Gaps, issues, WOs, tasks — **correlated internally**, not **experienced** as one. |
| **Task / inbox** | Operational priority ≠ compliance closure (Stream C). |
| **Risk** | Separate navigation contract from requirement CTAs (Stream D). |
| **Operations** | Queue health, SLA alerts, admin actions — **invisible** to typical tenant admin. |
| **Admin vs tenant** | Recovery and correlation power **concentrated**; tenant sees **partial** projection. |

Net: **coherence is backend-heavy, UX-heavy stitching** — classic “collection of features” risk until continuity closes.

---

## 10. Highest-leverage product improvements

Strategic directions only:

1. **Unified compliance work queue** — one ranked, honest list of “what matters” with valid primary paths or explicit external/manual states.  
2. **End-to-end remediation continuity (tenant-visible)** — read-only timeline acceptable; must respect non-authoritative rules for internal correlation JSON.  
3. **Applicability confidence** — close Stream A governance goals **as user-visible confidence**: fewer unexplained obligations; explicit operator override semantics when present.  
4. **Unified urgency model** — user-safe mapping of severity across gaps/tasks/risk without exposing raw queue.  
5. **Reduced support dependence** — translate runbook truths into **in-product** guidance for tenant admins where safe (status, timing, “what happens next”).  
6. **Emotional trust layer** — structured handling of dependency failures; always show **timing context** with scores.  
7. **Workflow continuity over feature count** — resist shipping more surfaces before existing threads **connect** for users.

---

## 11. Product principles going forward

1. **Users should not need to mentally reconcile contradictory compliance states** — if two surfaces disagree, the product must **explain the clocks** or **converge the presentation**.  
2. **No remediation item without a real completion path** — or an explicit “cannot complete in app” state (Stream C closure honesty).  
3. **No primary action without a valid workflow** — primary CTA must map to a **real** resolver/engineering-complete path (Stream D).  
4. **No hidden operational state that changes user trust silently** — queue health may be admin-only, but **user-visible posture** must reflect honest pending/partial states.  
5. **No score without timing context** — “as of” is part of the score (Stream B honesty).  
6. **Do not leak unnecessary operational complexity into tenant UX** — sophistication belongs in **admin/ops** surfaces unless user-safe.  
7. **Workflow continuity > feature count** — one completed thread beats three partial dashboards.  
8. **Trust continuity is a core product feature** — on par with correctness; ship accordingly.

---

## 12. Final judgment

**Judgment: the platform is not yet fully value-complete.**

**Why (concise):** Correctness machinery and authority discipline are **substantial**, but **user-perceived completeness** — one coherent Property Compliance OS — **lags**. Streams remain **partial**; applicability governance **still open** at P0; remediation **correlation is not tenant continuity**; async and fan-out **honesty** still place **cognitive burden** on users; **support-dependent** interpretation remains a **retention weak point**.

**What would need to become true** before calling the platform a **coherent Property Compliance OS** that is **operationally trustworthy**, **retention-strong**, and **scalable without heavy support interpretation**:

| Bar | Meaning |
|-----|---------|
| **Coherent OS** | Users can **narrate** compliance posture and work in one mental model, backed by surfaces that **agree** within declared async bounds. |
| **Operational trustworthiness** | Normal failure and delay modes are **understood without runbooks**; admin power stays admin, tenant truth stays honest. |
| **Retention-strong** | Post-setup users still **prefer** the product over external tools for “what’s wrong / what’s next / did it work.” |
| **Scalable support** | First-line support is not the **primary interpreter** of correctness; product carries **meaning**. |

Until then, the honest product stance is: **strong compliance engine, incomplete OS experience** — which is **not** marketing failure alone; it is a **continuity and trust** gap that this document exists to prevent from being forgotten or “papered over” by architecture progress alone.

---

## Document control

**Owner:** Product + compliance platform leadership (with engineering and support leads as readers).  
**Updates:** When materially shifting user-facing posture semantics, remediation doctrine, or stream **closed** milestones — revise this audit’s **judgment sections** in the same change train as tracker updates, without turning this file into a second tracker.
