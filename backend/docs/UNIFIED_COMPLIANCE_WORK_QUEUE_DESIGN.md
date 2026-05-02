# Unified Compliance Work Queue — product design

**Product value gap:** PVG-001 (`PRODUCT_VALUE_GAP_TRACKER.md`)  
**Document type:** Product design — **not** an architecture matrix, stream tracker, or implementation spec.  
**Aligned with:** `STREAM_C_REMEDIATION_CORRELATION_RUNBOOK.md`, `STREAM_D_CTA_PRODUCER_CONSUMER_MATRIX.md`, `STREAM_E_MUTATION_FANOUT_MATRIX.md`, `PROPERTY_COMPLIANCE_OS_GAP_AND_RETENTION_AUDIT.md`.

**Non-goals for this document:** New collections, new remediation source of truth, replacing Today or Command Centre, exposing support-only correlation JSON to tenants, or bypassing named authorities.

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

## Tenant-facing DTO (row shape)

Each row is a **view model**, not authoritative storage. Align with Stream C §5 “minimum viable remediation row” where applicable.

| Field | Purpose |
|-------|---------|
| `queue_item_id` | Stable UI key: **`task_id`** from unified tasks **or** deterministic `source_system` + `remediation_key` when not task-backed. |
| `source_system` | Closed vocabulary: `gap`, `risk_signal`, `work_order`, `maintenance_issue`, `requirement`, `approval`, `tenant_inbox`, … per Stream C §4. |
| `remediation_key` | Per Stream C §3; **prefer `gap_key`** when a gap row exists. |
| `property_id`, `client_id` | Scope. |
| `title`, `subtitle` | From existing label services / priority row / issue title — no new copy authority. |
| `urgency` | Normalised **display band** (see Urgency model) — sorting only. |
| `compliance_impact` | Coarse class: e.g. statutory gap, evidence gap, risk-only, operational-only, billing-adjacent — inferred from `source_system` + gap_kind / risk_type (product-tuned). |
| `primary_action` | Resolver `take_action` for requirement-backed; **operations** deep link for risk/WO/issue per Stream D. |
| `primary_action_authority` | e.g. `canonical_take_action`, `operations_constructed`, `tenant_inbox_navigation` — user-visible transparency. |
| `compliance_closure_state` | Where source has truth: e.g. gap `open` / `resolved` — **not** inferred from inbox. |
| `operational_closure_state` | WO/issue terminal when known from source. |
| `inbox_visibility_state` | Task overlay: snoozed / dismissed / reviewed — **non-compliance** closure. |
| `proof_state` | Coarse: none / pending_review / verified — from evidence hints where available without a new ledger. |
| `score_context` | Optional one-liner: property or portfolio `score_status` / pending recalc honesty — aligns with PVG-004; **not** a second score. |
| `related_ids` | `requirement_id`, `gap_key`, `signal_id`, `issue_id`, `work_order_id` — for deep links only. |

---

## Urgency model

**Not** a new global urgency engine (deeper normalisation is **PVG-005**).

**v1:** Map **existing** severities / SLA proximity / overdue flags to **3–5 display bands** (e.g. critical / high / medium / low / informational) for **sorting and badges only**.

**Inputs:** Gap severity, risk tier, WO SLA breach proximity, overdue / cert-expiring flags from priority stream, issue priority.

**Tie-break:** `last_seen_at`, due date, stable `task_id` order — **never** dedupe or sort by **`requirement_id` alone** when multiple `gap_key`s can exist (Stream C §6).

---

## Action model

| Source | Primary action |
|--------|----------------|
| Requirement-backed obligation | **`take_action`** from `requirement_action_resolver` (same contract as unified tasks / Property Detail). |
| Risk | Constructed **`/operations/risk-signals?signal_id=`** + risk workflow — **not** resolver. |
| WO / issue / approval | Existing **operations** URLs from `client_priority_stream` (Stream D exception table). |
| **Forbidden** | Raw **`recommended_url` / `recommended_action_label`** from gap documents as **client primary** CTA (**Rule R2**). |
| Tenant_request rows | Prefer **`metadata.take_action`** when resolver can attach; log mismatch when canonical ≠ primary (existing D-P06 pattern). |

---

## Completion / closure semantics

Three **orthogonal** dimensions (Stream C §7, correlation runbook §2):

| Dimension | Meaning |
|-----------|---------|
| **Compliance closure** | Gap **resolved** per persistence + engine inference; **risk dismiss does not close gaps**. |
| **Operational closure** | WO completed / issue closed — **may not** imply compliance met (Stream E outcome matrix). |
| **Inbox / visibility** | Today dismiss, snooze, reviewed — **does not** complete compliance. |

**UI:** Separate **badges** or sublabels per dimension when applicable; never show inbox dismiss as “compliant.”

---

## UX principles

1. **One list, multiple truths labelled** — do not collapse compliance closure and inbox closure into one checkmark.  
2. **No fake completeness** — navigation-only rows labelled **Review / Open**, not “Fix compliance.”  
3. **Timing honesty** — where Stream E implies lag, show a **short** score/recalc context on property-scoped rows.  
4. **Do not duplicate Today or Command Centre** — UCWQ is **work-queue-first** (sort/filter, property-centric); Today retains **inbox** behaviour; Command Centre retains **snapshot/urgent bundle** unless product later **explicitly** merges.  
5. **Progressive disclosure** — default **narrow** row; expand for IDs and “why this matters” from existing templates, not new legal claims.

---

## Risks

| Risk | Mitigation |
|------|------------|
| Second source of truth | Assembler is **read-only projection**; keys from Stream C. |
| **Rule R2** regression | Single assembler path; no raw gap primary CTA. |
| `requirement_id`-only dedupe | Dedupe by **`task_id`** or **`gap_key`**; never merge multiple gaps on one requirement without explicit product rule. |
| Risk vs gap **double count** | Often **valid** (distinct systems); label clearly or product-gate collapse (Stream C). |
| Eventual consistency | Row-level **score_context** + honest async copy; no instant headline promise. |
| Cognitive overload | Default **minimal** columns; expand for power users. |
| Support correlation JSON to tenants | **Forbidden** — tenant DTO only. |

---

## Implementation phases (product / engineering)

| Phase | Focus |
|-------|--------|
| **D** | Design sign-off (this document + product review). |
| **I1** | UX wireframes; freeze tenant DTO v1. |
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
**Next step:** Product sign-off on DTO, urgency model, and UX before implementation (see `PRODUCT_VALUE_GAP_TRACKER.md`).
