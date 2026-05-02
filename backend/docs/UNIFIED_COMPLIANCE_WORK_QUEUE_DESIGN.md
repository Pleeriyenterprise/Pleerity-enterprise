# Unified Compliance Work Queue — product design

**Product value gap:** PVG-001 (`PRODUCT_VALUE_GAP_TRACKER.md`)  
**Document type:** Product design — **not** an architecture matrix, stream tracker, or implementation spec.  
**Tenant UX (v1):** `UNIFIED_COMPLIANCE_WORK_QUEUE_WIREFRAME_V1.md` (wireframe + copy spec for implementation).  
**Aligned with:** `STREAM_C_REMEDIATION_CORRELATION_RUNBOOK.md`, `STREAM_D_CTA_PRODUCER_CONSUMER_MATRIX.md`, `STREAM_E_MUTATION_FANOUT_MATRIX.md`, `PROPERTY_COMPLIANCE_OS_GAP_AND_RETENTION_AUDIT.md`.

**Non-goals for this document:** New collections, new remediation source of truth, replacing Today or Command Centre, exposing support-only correlation JSON to tenants, or bypassing named authorities.

**v1 implementation readiness:** After sign-off review, this document locks **V1 scope lock**, **Urgency Mapping v1**, **User-facing Closure Language**, **Navigation and Product Positioning**, **tenant_request deferred to v2**, and **Explicit v2 deferrals**. **Wireframe/copy spec** is in `UNIFIED_COMPLIANCE_WORK_QUEUE_WIREFRAME_V1.md`; **product sign-off** on that spec remains the last gate before code.

---

## Pre-coding checklist

| # | Question | Answer |
|---|----------|--------|
| 1 | **Product Value Gap ID** | **PVG-001** — Unified Compliance Work Queue. |
| 2 | **Architecture stream(s)** | **Stream C** (remediation identity, closure semantics, `remediation_key` / `source_system`); **Stream D** (requirement `take_action`, gap→priority overlay, non-resolver risk/ops URLs); **Stream E** (eventual consistency, recalc lag — honest row-level context); **Stream F** (optional read-side joins for proof/audit hints — not tenant SSOT). Stream A only if rows later expose applicability context (later phase; not required for v1 design). |
| 3 | **Existing authorities to reuse** | `unified_tasks_service`; `client_priority_stream`; `requirement_action_resolver` / `resolve_take_action_for_priority_action`; `compliance_gap_engine.gaps_to_priority_actions`; `risk_signal_service`; constructed ops URLs per Stream D exception table; `compliance_scoring_service` / score **status** for context lines only — not a second score. |
| 4 | **Duplicate truth / parallel workflow risk** | **High** if the queue becomes a persisted remediation ledger or if UI uses raw `compliance_gaps.recommended_*` or `requirement_id`-only dedupe. **Mitigation:** queue is a **read projection** over existing sources; stable identity = **`remediation_key` + `source_system`** (Stream C); requirement-primary CTA **only** from resolver; dedupe per Stream C §6. |
| 5 | **Implementation sequencing (high level)** | **D:** design sign-off (this doc). **I1:** UX + tenant-safe DTO contract. **I2:** backend assembler calling **only** existing services / same reads as Today+priority — no new collection. **I3:** one client surface consuming assembler — does not remove Today/CC. **I4:** contract/regression tests. **No** phase introduces a remediation SSOT. |

---

## User problem

Tenants today stitch **dashboard counts**, **Today / unified tasks**, **priority actions**, **gaps**, **risk**, **issues**, **work orders**, and **score timing** to answer: *what is wrong, what is next, how urgent, can I act, is it done?* That fragmentation drives **wrong prioritisation**, **false “done”** (inbox dismiss vs compliance), and **mistrust** when surfaces disagree.

**Target:** One **tenant-facing** operational queue — an **ordered, filterable** list of attention items with **valid** primary actions and **explicit** closure semantics — **without** a new lifecycle database or second source of truth.

---

## Authorities reused (explicit)

| Authority | Role in UCWQ |
|-----------|----------------|
| `unified_tasks_service` | Task DTO shape, `task_id` = `{source_type}:{source_id}`, `metadata.take_action` for requirement-backed rows. |
| `client_priority_stream` | Compliance priority rows (including `gaps_to_priority_actions` overlay), risk, WO, issue, approval — same choke point as Today. |
| `requirement_action_resolver` | Canonical `take_action` envelope for requirement-shaped work. |
| `compliance_gap_engine.gaps_to_priority_actions` | **Rule R2:** resolver / `canonical_take_action` over raw gap `recommended_*`. |
| `risk_signal_service` | Risk copy/codes; **not** routed through requirement resolver. |
| Stream D matrix | Intentional non-`take_action` URLs for risk, WO, issue, approval. |
| `compliance_scoring_service` / `score_status` | **Context** (“score may still be updating”) — not the row’s compliance closure truth. |
| Stream C runbook | `remediation_key`, `source_system`, compliance vs operational vs inbox closure. |

---

## Source systems — included and excluded

### Included (v1 projection)

Eligible families **already** fed by unified priority + tasks: **requirement** (via priority/unified), **compliance_gaps** (only as bridged through priority actions with resolver overlay), **risk_signal**, **maintenance_issue**, **work_order**, **approval/invoice** where present in stream, **tenant_request / tenant_message** if product includes them — with **inbox semantics** explicit.

### Excluded or forbidden as primary paths

| Exclusion | Reason |
|-----------|--------|
| Raw Mongo `compliance_gaps` as a **parallel** consumer | Bypasses `gaps_to_priority_actions` — **Rule R2** / duplicate-truth risk. |
| `POST .../remediation-correlation-view` payloads to tenants | Support-only, **non_authoritative**; not tenant product truth. |
| New persisted “unified_remediation” or queue ledger collection | Would become SSOT — **out of scope**. |
| Admin `priority_actions` / admin priority stream | Different product audience; keep separate. |

---

## V1 scope lock

**Sign-off review (2026):** v1 is intentionally **narrow** — projection-only, same upstream rows as Today/unified tasks, **three** user-facing urgency bands, **one** primary closure line + expand detail, **no** tenant_request rows, **no** new scoring or ledger.

### Included sources (v1)

Rows assembled **only** from the same **client priority → unified task** pipeline already used by Today (no parallel Mongo readers for raw gaps):

| Source | Mechanism |
|--------|-----------|
| **Requirement-shaped compliance** | `ACTION_OVERDUE_COMPLIANCE`, `ACTION_MISSING_DOCUMENT`, `ACTION_CERT_EXPIRING_SOON` → `resolve_take_action_for_priority_action` / resolver overlay (`gaps_to_priority_actions`). |
| **Gap-backed compliance** | Only as **priority actions** after overlay — **never** raw `compliance_gaps` documents. |
| **Risk signals** | `ACTION_RISK_SIGNAL` — ops URL pattern per Stream D. |
| **Work orders** | `ACTION_WORK_ORDER_*` — near breach, breached, open WO. |
| **Maintenance issues** | `ACTION_OPEN_ISSUE`. |
| **Approvals / invoice** | `ACTION_PENDING_APPROVAL`. |

### Excluded sources (v1)

| Source | Reason |
|--------|--------|
| **tenant_request / tenant_message** | **Deferred to v2** — Stream D `D-P06` metadata vs primary mismatch risk; v1 ships without inbox-request rows in UCWQ (Today may still show them). |
| Raw **`compliance_gaps`** collection | Rule R2 — use priority overlay only. |
| **`POST .../remediation-correlation-view`** | Support-only, non-authoritative. |
| **Admin** `priority_actions` | Different audience. |
| **New persisted queue / remediation SSOT** | Forbidden. |

### Final v1 DTO fields (ship these only)

| Field | Purpose |
|-------|---------|
| `queue_item_id` | Stable key: `task_id` from unified tasks (`source_type:source_id`) or deterministic `source_system` + `remediation_key`. |
| `source_system` | From closed vocabulary for rows included above (e.g. `requirement`, `risk_signal`, `work_order`, `issue`, `approval`; gap identity via `remediation_key` / related ids — not `tenant_inbox` in v1). |
| `remediation_key` | Stream C §3; **prefer `gap_key`** when present. |
| `property_id`, `client_id` | Scope. |
| `title`, `subtitle` | From existing priority/unified labels — no new copy authority. |
| `urgency_band` | **Urgent \| Soon \| Watch** — see **Urgency Mapping v1** (derived only). |
| `primary_action_type`, `primary_action_label`, `primary_action_url` | Same contract as unified task primary CTA (resolver or ops URL). |
| `primary_action_authority` | `canonical_take_action` \| `operations_constructed` \| `fallback` — transparency for support QA. |
| `closure_summary_user` | **Single** user-facing line summarising posture (see **User-facing Closure Language**). |
| `show_inbox_overlay_note` | Boolean or enum: whether row has **only** inbox/snooze/dismiss relevance — must **not** read as “compliant.” |
| `related_ids` | `requirement_id`, `gap_key`, `signal_id`, `issue_id`, `work_order_id`, `invoice_id` as applicable — deep links only. |

### Deferred DTO fields (not in v1 API)

| Field | Deferred to |
|-------|-------------|
| Separate `compliance_closure_state`, `operational_closure_state`, `inbox_visibility_state` columns | **v2** — v1 uses **`closure_summary_user`** + optional expand from same sources. |
| `compliance_impact` taxonomy | **v2** (see **Explicit v2 deferrals**). |
| `proof_state` | **v2**. |
| Per-row / broad `score_context` | **v2** (PVG-004). |
| `tenant_request` / `tenant_message` task shape | **v2** with strict Stream D rules. |

### v1 filters and sorting

| Capability | v1 behaviour |
|------------|----------------|
| **Sort** | Default: same composite intent as existing unified sort — reuse **`_impact_score`** / priority ordering from upstream task list where available; **tie-break:** `task_id` lexicographic, then `property_id`. **Never** sort by `requirement_id` alone when multiple `gap_key`s exist. |
| **Filter** | `property_id` (required for multi-property clients), `urgency_band`, `source_system` (coarse). |
| **Search** | **Out of scope v1** (defer to v2 unless trivial title match). |

### v1 urgency bands (labels only)

Three bands — **no** new engine; collapse of existing internal levels:

| `urgency_band` | Meaning for user |
|----------------|-------------------|
| **Urgent** | Needs action now (overdue compliance, breached SLA, critical/high internal severity). |
| **Soon** | Needs attention in the near term (medium internal level, approaching deadlines). |
| **Watch** | Lower immediate pressure (low internal level; still visible). |

---

## Urgency mapping v1

**Rule:** UCWQ does **not** compute new scores. For every row, reuse the **same inputs** already used by `unified_tasks_service._urgency_level(action_type, severity, overdue_days)` and map its **output string** to **`urgency_band`**:

| Existing `_urgency_level` result | `urgency_band` |
|----------------------------------|----------------|
| `critical` | **Urgent** |
| `high` | **Urgent** |
| `medium` | **Soon** |
| `low` | **Watch** |

**Source types and inputs (reference — all already on priority/unified rows):**

| Source type (concept) | Existing input fields (do not re-fetch) | Feeds `_urgency_level` via |
|----------------------|----------------------------------------|------------------------------|
| Requirement / gap-backed compliance | `action_type` (`ACTION_*`), `severity`, requirement `due_at` → `overdue_days` | Same row as unified task. |
| Risk signal | `action_type` = `ACTION_RISK_SIGNAL`, risk **severity** on priority row | Same. |
| Work order | `action_type` (`ACTION_WORK_ORDER_*`), WO SLA fields → overdue / breach flags reflected in `action_type` and **severity** | Same. |
| Issue | `action_type` = `ACTION_OPEN_ISSUE`, **severity** / priority on row | Same. |
| Approval | `action_type` = `ACTION_PENDING_APPROVAL`, **severity** | Same. |

**Assembler obligation:** Build the UCWQ list from **the same unified task objects** (or bitwise-identical computation) so urgency is **not** recomputed with different rules. If a row cannot supply `severity` / `overdue_days`, inherit defaults already used by unified tasks for that `action_type`.

**Tie-break (unchanged):** never dedupe by `requirement_id` alone; use `task_id` / `gap_key` per Stream C §6.

---

## User-facing closure language

Replace internal terms (“compliance closure”, “operational closure”) on **default rows** with short, user-tested strings. **Systems definitions** remain in Stream C runbook for engineering.

| Concept | User-facing label (v1 default copy — product may A/B) |
|---------|--------------------------------------------------------|
| **Compliance cleared** | **“Cleared for compliance”** or **“No open compliance issue for this item”** — only when gap / obligation persistence shows resolved **or** requirement shows compliant per authority (not inbox). |
| **Operational follow-up** | **“Operational follow-up”** or **“Contractor / maintenance in progress”** — WO/issue active; **does not** alone mean statutory compliance is met. |
| **Hidden or snoozed** | **“Hidden from your list”** or **“Snoozed — not resolved”** — Today dismiss / snooze / reviewed **only** affects **visibility**, not whether an obligation exists. |

**`closure_summary_user`:** One line built from the above templates from **existing** row state (gap status, WO/issue status, task overlay flags) — **no** new persisted closure ledger.

### Clarifications (must appear in UX microcopy or help)

1. **Inbox actions do not mean compliant** — Snoozing, dismissing, or marking “reviewed” does **not** clear a compliance obligation.  
2. **Operational completion ≠ always compliant** — Completing a work order or closing an issue **may not** clear a compliance gap (Stream E outcome matrix); users may still need evidence or obligation work.

---

## Navigation and Product Positioning

| Question | v1 decision |
|----------|-------------|
| **How UCWQ relates to Today** | Today remains the **inbox-first** experience (visibility, snooze, dismiss). UCWQ is the **property-centric work queue** — “what needs doing across compliance + ops,” sortable and filterable. **No** removal or merge of Today in v1. |
| **How UCWQ relates to Command Centre** | Command Centre remains the **snapshot / urgent bundle** entry. UCWQ is the **deep operational list** for users who want **one table** of open work — not a duplicate of the CC **layout**; may **link** to the same underlying tasks. |
| **Primary user journey (v1)** | **Secondary surface:** user lands in **dashboard → Today or Command Centre** as today; **UCWQ** is reachable from **primary nav** “Work queue” (or equivalent) for users who opt into list-first operations. **Not** replacing CC/Today as default home. |
| **Positioning sentence** | “**All open work in one sortable list** — same actions as Today, without replacing your inbox.” |

**IA requirement:** Entry point must be **one click** from dashboard; **no** orphan screen.

---

## Explicit v2 deferrals

The following are **out of scope for v1**; track under PVG-001 / PVG-005 / PVG-003 / PVG-004 as appropriate when implemented:

| Item | Notes |
|------|--------|
| **`proof_state`** | Evidence hints without new ledger — needs product rules. |
| **`compliance_impact` taxonomy** | Statutory vs operational vs billing — deferred to v2+ with PVG-005 alignment. |
| **Advanced dedupe / collapse** | Risk vs gap double appearance collapse rules (Stream C product-gated). |
| **Multi-band urgency normalisation (5+)** | PVG-005 — global model; v1 uses **three** bands only. |
| **Applicability explanation layer** | “Why this applies” — PVG-003 / Stream A; not on UCWQ rows in v1. |
| **Broad score context overlays** | Per-row / portfolio score status strips — PVG-004. |
| **`tenant_request` / `tenant_message` in UCWQ** | Include in v2 **with** Stream D metadata/primary alignment rules and tests (`D-P06`). |
| **Separate DTO columns** for three closure dimensions | v1 uses **`closure_summary_user`** + help copy; v2 may expose structured badges if user research supports it. |
| **Full search** | Title/property search beyond filters — v2. |

---

## Tenant-facing DTO (reference — full conceptual model)

Each row is a **view model**, not authoritative storage. **v1 ships the subset in “V1 scope lock” — final v1 DTO fields only.** The table below is the **long-form reference** for v2+ and documentation alignment with Stream C §5.

| Field | Purpose |
|-------|---------|
| `queue_item_id` | Stable UI key: **`task_id`** from unified tasks **or** deterministic `source_system` + `remediation_key` when not task-backed. |
| `source_system` | Closed vocabulary per Stream C §4 (v1 excludes `tenant_inbox` rows). |
| `remediation_key` | Per Stream C §3; **prefer `gap_key`** when a gap row exists. |
| `property_id`, `client_id` | Scope. |
| `title`, `subtitle` | From existing label services / priority row / issue title — no new copy authority. |
| `urgency` | See **V1 scope lock** — v1 exposes **`urgency_band`** only. |
| `compliance_impact` | **v2** — coarse class taxonomy. |
| `primary_action` | Resolver `take_action` for requirement-backed; **operations** deep link for risk/WO/issue per Stream D. |
| `primary_action_authority` | e.g. `canonical_take_action`, `operations_constructed` — user-visible transparency. |
| `compliance_closure_state` | **v2 column** — v1 folded into `closure_summary_user`. |
| `operational_closure_state` | **v2 column** — v1 folded into `closure_summary_user`. |
| `inbox_visibility_state` | **v2 column** — v1 uses `show_inbox_overlay_note`. |
| `proof_state` | **v2** — none / pending_review / verified. |
| `score_context` | **v2** — PVG-004. |
| `related_ids` | `requirement_id`, `gap_key`, `signal_id`, `issue_id`, `work_order_id` — for deep links only. |

---

## Urgency model (non-v1 reference)

**Not** a new global urgency engine (deeper normalisation is **PVG-005**).

**v1** uses **Urgency Mapping v1** only.

**v2+:** Additional bands or cross-entity normalisation — PVG-005.

**Tie-break:** `last_seen_at`, due date, stable `task_id` order — **never** dedupe or sort by **`requirement_id` alone** when multiple `gap_key`s can exist (Stream C §6).

---

## Action model

| Source | Primary action |
|--------|----------------|
| Requirement-backed obligation | **`take_action`** from `requirement_action_resolver` (same contract as unified tasks / Property Detail). |
| Risk | Constructed **`/operations/risk-signals?signal_id=`** + risk workflow — **not** resolver. |
| WO / issue / approval | Existing **operations** URLs from `client_priority_stream` (Stream D exception table). |
| **Forbidden** | Raw **`recommended_url` / `recommended_action_label`** from gap documents as **client primary** CTA (**Rule R2**). |
| **tenant_request / tenant_message** | **v2** — see **V1 scope lock** and **Explicit v2 deferrals** (Stream D `D-P06` alignment required before inclusion). |

---

## Completion / closure semantics (engineering reference)

Three **orthogonal** dimensions (Stream C §7, correlation runbook §2) — **internal** truth model:

| Dimension | Meaning |
|-----------|---------|
| **Compliance closure** | Gap **resolved** per persistence + engine inference; **risk dismiss does not close gaps**. |
| **Operational closure** | WO completed / issue closed — **may not** imply compliance met (Stream E outcome matrix). |
| **Inbox / visibility** | Today dismiss, snooze, reviewed — **does not** complete compliance. |

**v1 UI:** Use **`closure_summary_user`** and **User-facing Closure Language** — not three jargon badges on every row. **v2** may expose structured columns if research supports it.

---

## UX principles

1. **One list, multiple truths labelled** — do not collapse compliance closure and inbox closure into one checkmark.  
2. **No fake completeness** — navigation-only rows labelled **Review / Open**, not “Fix compliance.”  
3. **Timing honesty (v1)** — **No** per-row score overlay; rely on existing dashboard/score pages for async honesty (PVG-004 / Stream B). **v2** may add **score_context** per **Explicit v2 deferrals**.  
4. **Do not duplicate Today or Command Centre** — UCWQ is **secondary** list-first surface in v1 (see **Navigation and Product Positioning**); Today retains **inbox**; Command Centre retains **snapshot/urgent bundle**.  
5. **Progressive disclosure** — default **narrow** row; expand for IDs and “why this matters” from existing templates, not new legal claims.

---

## Risks

| Risk | Mitigation |
|------|------------|
| Second source of truth | Assembler is **read-only projection**; keys from Stream C. |
| **Rule R2** regression | Single assembler path; no raw gap primary CTA. |
| `requirement_id`-only dedupe | Dedupe by **`task_id`** or **`gap_key`**; never merge multiple gaps on one requirement without explicit product rule. |
| Risk vs gap **double count** | Often **valid** (distinct systems); label clearly or product-gate collapse (Stream C). |
| Eventual consistency | Users directed to **existing** score/dashboard honesty; **no** v1 per-row score strip (deferred v2). |
| Cognitive overload | Default **minimal** columns; expand for power users. |
| Support correlation JSON to tenants | **Forbidden** — tenant DTO only. |

---

## Implementation phases (product / engineering)

| Phase | Focus |
|-------|--------|
| **D** | Design sign-off (**complete** for architecture — wireframes + copy pass remain). |
| **I1** | UX wireframes + **`closure_summary_user`** copy; freeze tenant DTO v1 per **V1 scope lock**. |
| **I2** | Backend **assembler** — calls existing `get_unified_tasks_for_client` / priority assembly only; **no** new Mongo collection. |
| **I3** | Client surface (route or tab) consuming assembler — **does not** remove Today/CC. |
| **I4** | Contract and regression tests (see Tests needed). |

---

## Tests needed (when implementation begins)

Not part of this design commit; required before release:

- **Contract:** Requirement rows’ primary action matches **CTA parity** / resolver expectations.  
- **Regression:** When `take_action` exists, primary URL **not** from raw gap `recommended_*`.  
- **Dedupe:** Multiple **`gap_key`** on one **`requirement_id`** → distinct rows or explicit merge **preserving** `gap_key`.  
- **Risk row:** URL matches **operations** pattern, not resolver.  
- Optional: snapshot test of queue JSON for fixture DB.

---

## Tracker update rules

| Tracker | When to update |
|---------|------------------|
| **`PRODUCT_VALUE_GAP_TRACKER.md`** | Move PVG-001 status (e.g. Identified → In Design → In Implementation); append **completed work**, **files changed**, **tests run**, **remaining risks**, **next step** per PR or design milestone. |
| **`CLOSED_LOOP_COMPLIANCE_ARCHITECTURE_TRACKER.md`** | **Only if** named architecture authority changes, a stream status changes, or a new hard dependency is introduced — **not** for this design-only doc. |
| **`PROPERTY_COMPLIANCE_OS_GAP_AND_RETENTION_AUDIT.md`** | Optional narrative refresh if judgment shifts; not required per PVG-001 design. |

**Do not** duplicate stream matrices or implementation checklists in this file.

---

## Document control

**Owner:** Product + platform architecture (review).  
**PVG:** PVG-001.  
**Next step:** Final **UX wireframes** and **closure copy** product approval → move PVG-001 to **In Implementation** in `PRODUCT_VALUE_GAP_TRACKER.md` (no architecture tracker change required).
