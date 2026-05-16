# Controlled Beta — Operations Runbook

**Purpose:** Operational execution and **recovery discipline** for **support and admin** staff during a **controlled beta** only.  
**Not:** public launch readiness, architecture redesign, or a substitute for Streams **A–F** matrices and runbooks.

**Audience:** Support, operations, and admin users with appropriate RBAC.

**Source:** Consolidates the latest **operational readiness**, **pre-beta stabilization**, and **public-launch gap** audits (support actions, escalation model, triage flows, monitoring, training). Detailed mutation semantics remain in:

- `CLOSED_LOOP_COMPLIANCE_ARCHITECTURE_TRACKER.md`
- `STREAM_B_SCORING_AUTHORITY_MATRIX.md`
- `STREAM_C_REMEDIATION_CORRELATION_RUNBOOK.md` (+ `SUPPORT_REMEDIATION_CORRELATION_VIEW_V1.md`)
- `STREAM_D_CTA_PRODUCER_CONSUMER_MATRIX.md` / `STREAM_D_CTA_PARITY_ENFORCEMENT.md`
- `STREAM_E_MUTATION_FANOUT_MATRIX.md`
- `STREAM_F_RECONSTRUCTION_CONSISTENCY.md` / `STREAM_F_FORENSICS_JOIN_RECIPE.md`
- `CLOSED_LOOP_ARCHITECTURAL_GAP_ANALYSIS.md` §18 (architecture doctrine)
- `audit/NOTIFICATION_OWNERSHIP_READINESS.md` — operational email deep links vs portal truth; preference vs mandatory sends (cross-check with product)

---

## 1. Purpose and scope

| Item | Policy |
|------|--------|
| **Scope** | **Controlled beta** tenants and environments only. |
| **Explicitly out of scope** | **Public launch** sign-off; unconstrained general availability. |
| **Role** | **Support/admin operational guide** — how to observe, triage, escalate, and use **existing** recovery paths without creating second sources of truth. |
| **When to stop** | If an action would **bypass** a named authority or **edit** authoritative persisted fields directly, **do not** perform it — escalate (see §5–§6). |

---

## 2. Authority discipline

### 2.1 Named authorities (must match tracker)

Use the **Named authorities** table in `CLOSED_LOOP_COMPLIANCE_ARCHITECTURE_TRACKER.md`. In short:

| Concern | Authority (do not replace) |
|---------|----------------------------|
| Property compliance **score persistence** | `compliance_scoring_service.recalculate_and_persist` |
| Async **recalc scheduling** | `enqueue_compliance_recalc` → `job_runner.run_compliance_recalc_worker` |
| Requirement **primary CTAs** | `requirement_action_resolver` (`take_action` / `resolve_take_action_*`) + parity with frontend `requirementTakeActionResolver.js` |
| **Risk / ops navigation URLs** | Constructed operations pattern (separate from requirement resolver) — see Stream D matrix §3 |
| **Remediation correlation vocabulary** | `STREAM_C_REMEDIATION_CORRELATION_RUNBOOK.md` |
| **Mutation fan-out** | `STREAM_E_MUTATION_FANOUT_MATRIX.md` |
| **Audit / reconstruction order** | `create_audit_log`; `STREAM_F_RECONSTRUCTION_CONSISTENCY.md` + join recipe |

### 2.2 What support **may** use (read + sanctioned writes)

- **Read:** Admin GETs for recalc/SLA status; `audit_logs` and domain collections per **Stream F** order; optional **remediation correlation view** when enabled (§8).
- **Write (sanctioned):**  
  - `POST /api/admin/properties/{property_id}/validate-compliance-score` (`fix=false` diagnose, `fix=true` repair via **`recalculate_and_persist`**).  
  - `POST /api/admin/clients/{client_id}/actions/recalculate-compliance` (bulk **enqueue**).  
  - **Product-approved** document / requirement / workflow actions that follow normal client/admin routes (they already carry fan-out per **Stream E** — do not invent shortcuts).

### 2.3 What support **must never** edit directly

Any field or document that represents **authoritative** compliance posture without going through the named writers:

- `properties.compliance_score`, breakdown / history fields written by scoring  
- `requirements` status / evidence / authority blobs “to match the UI”  
- `compliance_gaps` URLs or labels used as **client-primary** navigation when resolver / `canonical_take_action` exists (**Rule R2**)  
- `compliance_recalc_queue` rows (e.g. forcing `status: DONE`)  
- Fabricated `client_task_*` / inbox rows for “missing” work  

---

## 3. Forbidden support actions

| Forbidden action | Reason |
|------------------|--------|
| **Score field edits** in Mongo | Violates single writer; breaks ledger/audit story. |
| **Requirement status / evidence edits** “to fix display” | Bypasses authority sync, gap engine, matrix fan-out. |
| **Gap `recommended_url` / label edits** for primary CTA | **Stream D Rule R2** — drift vs `take_action`. |
| **Queue job marked DONE** without successful `recalculate_and_persist` | False recovery; `compliance_score_pending` / headline lie. |
| **Fake closure** (treating Today dismiss, risk resolve, WO complete, issue close as **compliance met** alone) | **Stream C** runbook §7–§8. |
| **Sharing internal correlation JSON** (`remediation-correlation-view` response) with tenants | **`non_authoritative`**; support-only unless product/legal explicitly approves. |
| **Deduping by `requirement_id` alone** across gaps | **Forbidden** when multiple `gap_key`s exist. |
| **Quiet operator gap sync** “fixed” by forcing full gap lifecycle audits | Breaks intentional **Stream E** design. |

---

## 4. Safe recovery actions (by failure type)

All recovery must end in: **observable** queue drain, **`validate-compliance-score` match**, and/or **audited** `recalculate_and_persist` — not hand-patched documents.

### 4.1 Stale score

1. `GET .../compliance-recalc-status` and/or `GET .../compliance-sla` for the property.  
2. If queue moving: explain **persisted headline vs live stats** (**Stream B** §5–7); use client **freshness** copy where present.  
3. If stuck pending / mismatch: `validate-compliance-score` **`fix=false`** → then **`fix=true`** if confirmed mismatch.  
4. If client-wide incident after data fix: `admin_action_recalculate_compliance` with **change control** (queue load).

### 4.2 DEAD recalc job

1. Read `last_error`, `attempts`, `correlation_id`, `trigger_reason` on the `DEAD` row.  
2. **Do not** set status to DONE manually.  
3. After **root cause** addressed (infra, data, code deploy): **new** enqueue via sanctioned admin route or normal mutation path — worker creates a **new** job.

### 4.3 Queue backlog

1. Mongo aggregates: counts by `status` on `compliance_recalc_queue`.  
2. Confirm **`compliance_recalc_worker`** is scheduled/running.  
3. **Throttle** further bulk recalcs until drain if **S4**-scale (see §5).  
4. Use logs `event=compliance_fanout`, `stage=dedupe` to explain duplicate suppressions.

### 4.3a In-app Automation Control Centre

During beta, operators use **Admin → Automation** together with **Control Centre** and **Incidents**:

| Symptom | First actions |
|---------|----------------|
| Stale scheduler heartbeat | Treat as **S4**-class platform signal — restore API/scheduler process; confirm `scheduler_heartbeat` collection updates. |
| Degraded / failed job rows | Open **Message logs** for the run; correlate template, channel, recipient, error. |
| Delivery still `unknown` after SLA hours | Provider webhooks / Postmark (or equivalent) + `delivery_reconciliation` job outcomes. |
| Open incidents | **Incidents** list — dedupe narrative; link back to job name and time window. |

**Do not** invent new recovery writes beyond §2.2 sanctioned routes.

### 4.4 Broken CTA

1. Capture API payload: `take_action`, `metadata.take_action`, `primary_action_*`.  
2. If resolver payload missing/wrong: **escalate engineering** — **no** Mongo URL edits for requirement-primary.  
3. **Temporary** user guidance: approved navigation (e.g. Property → requirement → documents) until fix deploys.

### 4.5 Missing remediation action

1. Distinguish **compliance closure** vs **priority / inbox** presentation (**Stream C** §7).  
2. If flag enabled: `POST .../remediation-correlation-view` with `gap_key` / `issue_id` / `work_order_id` / `risk_signal_id`.  
3. If gap open but no task: **S2** engineering — visibility/unified-task rules; **no** manual task rows.

### 4.6 Contradictory dashboard states

1. Confirm same **client** / property scope.  
2. Use `score_status`, `score_status_message`, `compliance_last_calculated_at`, queue state.  
3. Explain **headline (persisted)** vs **stats (live projection)**; exports use **snapshot** semantics where documented.  
4. Escalate **S3** if persisted headline is wrong **after** successful recalc and validate match.

### 4.7 Partial fan-out / gap–score skew

1. Check **`STREAM_E`** row for the mutation the user performed.  
2. Inspect **`compliance_fanout_extra`** logs for `op` / `stage` / partial failures.  
3. Some outcome paths **omit** authority refresh until a later mutation (**Stream E** cross-cutting §2) — document **eventual convergence**; if user blocked: use **document / requirement** paths that include `sync_requirement_evidence_authority` per matrix, or escalate for product-prioritised matrix extension.

---

## 5. Escalation severity model (S1–S4)

| Level | Name | Examples | **Owner** | Response discipline |
|-------|------|----------|-----------|------------------------|
| **S1** | Minor | Single user confused by headline vs counts; one slow `PENDING` that clears | L1 support | Document + monitor; no bulk enqueue. |
| **S2** | Major | Repeated `FAILED` approaching thresholds; property `PENDING_STUCK` SLA WARN; missing task pattern across a few users | Senior support / on-call | Scoped diagnosis; coordinate with engineering same business day. |
| **S3** | Critical (property/data) | `DEAD` + `compliance_score_pending` stuck; `validate` mismatch **after** `fix=true`; reproducible resolver gap affecting one client | Engineering + DB | **Stop** bulk recalc; root-cause before re-enqueue. |
| **S4** | Critical (platform) | Worker/scheduler stopped; many `RUNNING_STUCK`; queue not draining multi-client | Ops + Engineering leadership | Incident command; pause risky admin actions; restore workers first. |

**Align with SLA monitor:** `SEVERITY_WARN` ↔ S1–S2 entry; `SEVERITY_CRIT` ↔ S2–S4 by **blast radius**.

---

## 6. Incident triage flows (step-by-step)

### 6.1 DEAD job

1. Admin GET recalc status / SLA for `property_id`.  
2. Record `last_error`, `correlation_id`, `trigger_reason`.  
3. Search `audit_logs` for `COMPLIANCE_RECALC_FAILED` / SLA breach metadata.  
4. If transient: restore infra → **new** enqueue (admin or normal path).  
5. If persistent: **S3** — engineering; **forbidden:** mark job DONE in DB.

### 6.2 Stale score

1. GET status + SLA.  
2. If worker healthy and `PENDING` old: check SLA **`PROPERTY_PENDING_TOO_LONG`**.  
3. `validate-compliance-score` diagnose → repair if mismatch.  
4. If only stats vs headline: language from **Stream B** honesty; no score edits.

### 6.3 Broken CTA

1. Reproduce; export API JSON for task/requirement.  
2. Confirm `take_action` / `metadata.take_action`.  
3. **S2/S3** to engineering with fixture; **no** gap URL patch.

### 6.4 Missing remediation action

1. Runbook §7 closure table — is it compliance or inbox?  
2. Correlation view if enabled.  
3. Engineering if unified stream gap.

### 6.5 Queue backlog

1. Global counts by `status`; trend.  
2. Confirm `compliance_recalc_worker` + job scheduler.  
3. **S4** if global stall.  
4. Throttle `admin_action_recalculate_compliance` until stable.

### 6.6 Contradictory dashboard state

1. Same tenant scope.  
2. `score_status` + timestamps + queue.  
3. Headline vs stats explanation.  
4. **S3** if wrong persisted headline post-successful recalc.

---

## 7. Monitoring checklist before beta

| Check | How |
|-------|-----|
| **Queue depth** | Mongo `compliance_recalc_queue` counts by `status`. |
| **DEAD jobs** | Filter `status=DEAD`; correlate with `ALERT_DEAD_JOB` (`compliance_sla_alerts`). |
| **Pending age** | `PENDING` jobs vs `COMPLIANCE_RECALC_SLA_PENDING_SECONDS` (default **120**). |
| **Running stuck** | `RUNNING` + `updated_at` vs `COMPLIANCE_RECALC_SLA_RUNNING_SECONDS` (default **300**) → **CRIT**. |
| **Repeated failures** | `attempts` vs `SLA_MAX_FAILURES_WARN` (3) / `SLA_MAX_FAILURES_CRIT` (5). |
| **Property pending too long** | `compliance_score_pending` + stale `compliance_last_calculated_at` → `ALERT_PROPERTY_PENDING_TOO_LONG`. |
| **SLA alert delivery** | `OPS_ALERT_EMAIL` set; `COMPLIANCE_SLA_ALERT` template path verified in beta env. Bodies use operator-first layout (`internal_alert_layout` + structured sections; full diagnostics in plaintext/debug). |
| **Fan-out anomaly logs** | Search `event=compliance_fanout` spikes (`partial`, `failed`, `dedupe`). |
| **Audit volume** | `COMPLIANCE_RECALC_FAILED`, `COMPLIANCE_RECALC_SLA_BREACH` / `RESOLVED`, repair audit chain. |

**Jobs:** `compliance_recalc_worker`, `compliance_recalc_sla_monitor` present in scheduler config (`job_runner.JOB_RUNNERS`).

---

## 8. Feature flag / rollback procedures

| Lever | Procedure |
|-------|-----------|
| **`FEATURE_REMEDIATION_CORRELATION_VIEW_V1`** | Set **off** → `POST .../remediation-correlation-view` returns **404** (“disabled”). Support uses manual runbook queries only. |
| **Bulk recalc pause** | **Stop** invoking `admin_action_recalculate_compliance` under change control until queue **SLA** healthy. |
| **Unstable client surface** | Use **existing** product/feature flags for beta-only UI if available; **do not** add parallel APIs. |
| **Worker / job rollback** | Disable worker only with **incident comms** — scores freeze; prefer **fix-forward** after root cause. Document who approves stop/start. |

---

## 9. Support training checklist

- [ ] **Authority map** (one page): score writer, enqueue+worker, resolver, risk URL pattern, correlation runbook.  
- [ ] **Forbidden actions** (§3) — acknowledgement.  
- [ ] **Admin endpoints:** `validate-compliance-score`, `recalculate-compliance`, `compliance-recalc-status`, `compliance-sla`.  
- [ ] **Queue lifecycle:** `PENDING` → `RUNNING` → `DONE` / `FAILED` / `DEAD`; backoff (10s → 10m).  
- [ ] **Stale-state language:** headline vs stats; snapshot exports.  
- [ ] **Closure semantics:** Today / risk / WO vs compliance (**Stream C** §7).  
- [ ] **Correlation view:** flag, RBAC, `non_authoritative`, caps, **no** tenant sharing.  
- [ ] **Escalation rules:** S1–S4 and **when to stop enqueue**.  
- [ ] **`STREAM_F`:** reconstruction order — not timestamp-only causality.
- [ ] **Landlord vocabulary (no internal jargon):** **Today** = operational inbox; **Dashboard** = portfolio KPIs/trends; **Command Center** = one-screen triage; **Requirements** = obligations that feed scoring rules; **Documents** = evidence vault; **Score headline** = stored calculation (may lag uploads until confirm + recalc).  
- [ ] **Trust collapse phrases:** “Accepted on file (not externally verified)” ≠ regulator proof; “Awaiting confirmation” = landlord or extraction confirm step on Documents; “Awaiting verification” / queue pending = automation or review still in flight — do not paraphrase as “broken.”

---

## 10. Beta entry checklist (objective yes/no)

| # | Item | ☐ |
|---|------|---|
| 1 | Beta **env vars** documented (`OPS_ALERT_EMAIL`, `COMPLIANCE_RECALC_SLA_*` as needed). | ☐ |
| 2 | **`compliance_recalc_sla_monitor`** scheduled and verified once in staging. | ☐ |
| 3 | **`OPS_ALERT_EMAIL`** receives a **test** SLA alert (or documented exception). | ☐ |
| 4 | Support completed **§9** training sign-off. | ☐ |
| 5 | Admin **recovery endpoints** smoke-tested (`compliance-recalc-status`, `compliance-sla`). | ☐ |
| 6 | **`validate-compliance-score`** tested `fix=false` and `fix=true` on a **non-prod** property. | ☐ |
| 7 | **`remediation-correlation-view`** tested in staging with flag **on** and **off**. | ☐ |
| 8 | Backend **`pytest tests/test_cta_parity_contract.py`** (or CI equivalent) **green** on beta branch. | ☐ |
| 9 | **`compliance_recalc_worker`** processes a synthetic `PENDING` job in staging. | ☐ |
| 10 | **`CLOSED_LOOP_COMPLIANCE_ARCHITECTURE_TRACKER.md`** **Last updated** / streams reviewed for beta scope. | ☐ |

---

## 11. What still blocks **public launch** (summary)

Controlled beta may proceed with discipline; **public launch** remains gated until programme criteria advance (see latest tracker + gap analysis):

- **Stream A (P0)** applicability governance still **open** — reader/writer alignment and operator/provenance discipline not finished as “closed”.  
- **Streams B–F** remain **partial** in the tracker lifecycle table — no stream marked **Closed**.  
- **Stream D:** Phase **3** (non-empty navigable URL where contract requires) still **open** — tenant CTA safety.  
- **Stream E:** Documented **partial** outcome paths and **eventual consistency** (e.g. cross-cutting §2); optional phase **4** (outbox/debounce) **deferred** without product/infra.  
- **Stream F:** **Legacy** rows without `correlation_id`; **weak joins** documented — forensics harder at scale.  
- **Stream C:** **Product** decision on **risk vs gap dedupe** still pending before collapsing user-visible remediation.  
- **Product / legal:** Marketing and in-app claims must stay within **§18.J** doctrine (`CLOSED_LOOP_ARCHITECTURAL_GAP_ANALYSIS.md`).

**This runbook does not** waive any of the above; it only governs **beta operations**.

---

## 12. Pre-pilot operational validation checklist (rehearsal)

**Authority:** This section is the **single in-repo rehearsal checklist** for controlled beta / paid pilot readiness. It does **not** replace `LAUNCH_AUTHORITY_TRACKER.md` (gates) or `PILOT_LAUNCH_GOVERNANCE.md` (risk acceptance); it extends **operational** verification for support and ops. Rehearse in **staging** (or a dedicated pilot tenant) before widening cohort size.

### 12.1 Authentication & session

| # | Check | ☐ |
|---|------|---|
| A1 | Client login, logout, and session refresh behave as expected; invalid/expired token shows governed error (no silent blank shell). | ☐ |
| A2 | Admin login / impersonation (if used) matches policy; logout clears sensitive context. | ☐ |
| A3 | Password reset flow completes end-to-end for a test user. | ☐ |

### 12.2 Billing / Stripe

| # | Check | ☐ |
|---|------|---|
| B1 | **TEST vs LIVE** Stripe keys and price IDs match the target environment (`plan_registry` / config review). | ☐ |
| B2 | New subscription → entitlements reflected in app (gated routes match plan). | ☐ |
| B3 | Upgrade / downgrade path does not leave contradictory `feature_enabled` vs UI (403 surfaces are explainable). | ☐ |

### 12.3 Automation & notifications (scheduler / delivery)

| # | Check | ☐ |
|---|------|---|
| N1 | Scheduler heartbeat collection updates on schedule; stale heartbeat treated as **S4-class** signal per §4.3a. | ☐ |
| N2 | Degraded automation runs visible in **Admin → Automation**; message logs correlate template / channel / error. | ☐ |
| N3 | Delivery reconciliation outcomes understood (`unknown` vs `delivered` / bounces) — no manual DB edits. | ☐ |
| N4 | Incidents list usable for dedupe narrative linked to job name and window. | ☐ |

### 12.4 Compliance workflows (async truth)

| # | Check | ☐ |
|---|------|---|
| C1 | Document upload → extraction / confirm path → requirement row updates without bypassing authority sync. | ☐ |
| C2 | Optional `propagation_notice` on mutations: client sees read-only notice when returned; support can explain queue deferral. | ☐ |
| C3 | Score recalculation: `PENDING` queue moves to `DONE` or explainable `FAILED`/`DEAD`; headline vs stats language matches **Stream B** / `COMPLIANCE_CLIENT_STATUS_AUTHORITY.md`. | ☐ |
| C4 | Evidence verification / accepted-unverified semantics explainable to a landlord (see support phrases §9 and presentation governance). | ☐ |
| C5 | Not applicable + reopen paths audited and **sanctioned** only via normal routes (no Mongo hand patches). | ☐ |
| C6 | Reminders: governed templates only; no `NOTIFICATION_DISPATCH` surprise activation. | ☐ |

### 12.5 Customer “first time” journeys (smoke)

| # | Check | ☐ |
|---|------|---|
| F1 | First property → appears on dashboard / properties; no dead-end navigation. | ☐ |
| F2 | First upload (Documents) → file listed; pending / confirm states honest. | ☐ |
| F3 | First requirement primary action (resolver-backed CTA) completes or shows structured plan/limit response. | ☐ |
| F4 | First report (if entitled) or governed upgrade path — no false “success” when gated. | ☐ |
| F5 | Empty Today / empty Command Center: user sees orientation copy and a next step (not a broken shell). | ☐ |

### 12.6 Admin recovery (support drill)

| # | Check | ☐ |
|---|------|---|
| R1 | Identify a **DEAD** recalc job → follow §6.1 (no manual `DONE`). | ☐ |
| R2 | `validate-compliance-score` `fix=false` then `fix=true` on a **non-prod** property documented. | ☐ |
| R3 | Affected users identified via audit / property scope — not ad hoc guesswork. | ☐ |

### 12.7 Obligation materialisation & visibility (A1–B proof)

**Authority:** `LAUNCH_AUTHORITY_TRACKER.md` § Recovery implementation plan (**A1–G2**) + § **Recovery unit implementation contract**; `PUBLISHED_REGISTRY_CLIENT_TRUTH_AUDIT.md`; `GOVERNANCE_INDEX.md`. **Do not** use notifications or queue health as proof of obligation creation.

**Recovery unit verification:** After implementing any **A2+** unit, operators must complete that unit’s Definition of Done staging steps before the launch tracker moves to **DONE**. Status must pass through **`IMPLEMENTED_PENDING_VERIFICATION`** → **`VERIFIED`** (not straight to DONE after merge).

**Prerequisites:** Staging `MONGO_URL`, `DB_NAME`; admin token; one affected `CID` + `PID`.

#### A1 — Classification checklist

| # | Check | Command / endpoint | Record |
|---|-------|-------------------|--------|
| O1 | Client onboarding | `db.clients.findOne({client_id:"CID"},{onboarding_status:1,provisioning_status:1,subscription_status:1,_id:0})` | |
| O2 | Provisioning job | `db.provisioning_jobs.find({client_id:"CID"}).sort({updated_at:-1}).limit(1)` | |
| O3 | Properties | `db.properties.countDocuments({client_id:"CID"})` | |
| O4 | Raw requirements | `db.requirements.countDocuments({client_id:"CID",property_id:"PID"})` | |
| O5 | Admin provisioning (HTTP) | `GET /api/admin/provisioning/CID` | |
| O6 | Runtime explain | `GET /api/admin/compliance/registry/runtime-requirements/explain?client_id=CID&property_id=PID` → `raw_count`, `included_count`, top `exclusion_reason` | |
| O7 | Client API (filtered) | `GET /api/properties/PID/requirements` (client auth) — count vs O6 `included_count` | |
| O8 | **Classification** | **A-only** if O4=0 and not PROVISIONED or provision failed; **B-only** if O4>0 and O6 `included_count`=0; **A+B** if both; **Neither** if O4>0 and O6≈O7 and obligations visible | |

**Script (recommended):** From `backend/` with `MONGO_URL` + `DB_NAME` set:

`python -m scripts.a1_obligation_tenant_classification --client-id CID --property-id PID`

Add `--json` for machine-readable output. Records classification + top `exclusion_reason` values.

Record result in tracker **A1 classification record** table.

#### A2 — Materialisation repair (if A-only / A+B)

| # | Action | Verification |
|---|--------|--------------|
| O9 | Admin: complete/retry provisioning (`force_provision` / billing path per policy) — **not** raw Mongo | O1 → `PROVISIONED`; O4 > 0 |
| O10 | Confirm generation source | `db.requirements.findOne({client_id:"CID",property_id:"PID"},{requirement_generation_source:1,requirement_type:1,_id:0})` → expect `catalog_registry` for plan rows |

#### A3 — Controlled sync (if stale vs registry)

| # | Action | Verification |
|---|--------|--------------|
| O11 | `POST /api/admin/properties/PID/requirements/sync-from-registry` (staff) or client sync with audit | Re-run O6; plan types match property attributes |

#### B1 — NOT_REQUIRED persistence repair (B-only / A+B)

| # | Check | Notes |
|---|-------|-------|
| B1-1 | **Before explain** | `python -m scripts.b1_preflight_capture --client-id CID --property-id PID` → `docs/audit/b1_explain_before_*.json` |
| B1-2 | **Governed triple-sync** | `materialize_requirements_for_property(CID, PID, reconcile_obsolete=True)` ×3 (tenant-scoped only; no fleet rematerialise) |
| B1-3 | **Replay** | Run 2 `aggregate_state_hash` = run 3; `reopened_from_not_required=0`; `reconciled_obsolete=0` on runs 2–3 |
| B1-4 | **Reconcile idempotency** | Converged `registry_metadata.reconciled_obsolete` rows must not refresh `updated_at` / audit on repeat sync |
| B1-5 | **After explain + report** | `python -m scripts.b1_staging_verification --client-id CID --property-id PID` → `b1_explain_after_*.json`, `b1_verification_report_*.json` |
| B1-6 | **Parity** | O6 `included_count` = client API array length |
| B1-7 | **A1 re-run** | `python -m scripts.a1_obligation_tenant_classification --client-id CID --property-id PID --json` |

**Provenance:** automated `NOT_REQUIRED` uses `registry_metadata.automated_not_required`; operator-curated rows (override, audit reason ≥10 chars) are preserved. Do not weaken `requirement_client_runtime_surface` filters.

**Wales HMO pilot acceptance (2026-05-16):** After B1, **8** client-visible planner-aligned families is accepted operational truth for tenant `6fd5ac4c…`. `emergency_lighting` / `fire_extinguisher` are **not** defects — intentionally non-visible (no overlay). **C1** queue proof **DONE** on this tenant (2026-05-16); see §12.7 C1 below.

#### B2 — Published registry overlay (if overlay-missing only)

| # | Check | Notes |
|---|-------|-------|
| O12 | Explain exclusions | Group `exclusion_reason` on excluded rows — fix **one** proven cause per PR |
| O13 | Published registry | Confirm active published snapshot covers portfolio label for missing types |
| O14 | Parity | O6 `included_count` = client API array length |

#### C1 — Queue / recalc convergence (only after B-layer accepted; launch unit **C1**)

**Authority:** `LAUNCH_AUTHORITY_TRACKER.md` § **C1** (rev 2 DoD); `runbooks/SCHEDULER_AND_COMPLIANCE_JOBS.md` (semantics unchanged). **Not** notification dispatch, scheduler redesign, or `updated_at` write optimization.

**Prerequisites:** B1 visibility accepted for tenant; staging `MONGO_URL` + `DB_NAME`; pilot `CID` + `PID` documented in tracker.

| # | Step | Command / action | Pass criteria |
|---|------|------------------|---------------|
| C1-0 | **Preflight** | `python -m scripts.c1_preflight_capture --client-id CID --property-id PID` | Writes `docs/audit/c1_queue_before_*.json` (queue counts, pending markers, reclaim thresholds) |
| C1-1 | **R1 — first enqueue (C1-M1)** | Client `POST /api/properties/PID/requirements/sync` (or script equivalent) | `enqueued=true`; new `REQUIREMENTS_SYNC:PID` row → `DONE`; `compliance_score_pending` clears; `job_runs` success for `compliance_recalc_worker` |
| C1-2 | **R2 — stable replay** | Repeat C1-M1 once | `enqueued=false`, `duplicate_suppression_reason` set (e.g. `duplicate_pending`); **no** new queue row |
| C1-3 | **R3 — stable replay** | Repeat C1-M1 again | Same as R2; score fingerprint / `compliance_last_calculated_at` / score-history Δ **0** |
| C1-4 | **M2 — legitimate regeneration** | Admin `POST /api/admin/properties/PID/requirements/sync-from-registry` **once** | `enqueued=true` with **new** `ADMIN_MANUAL_JOB:REGISTRY_SYNC:…` correlation; row → `DONE` |
| C1-5 | **Recalc stability** | Inspect `c1_recalc_stability_*.json` from verification script | R2/R3: no semantic score churn; no score-history / score-event writes |
| C1-6 | **Reclaim observability** | `c1_reclaim_observability_*.json`; optional `db.compliance_recalc_queue.find({property_id:"PID",status:"RUNNING"})` | `stuck_running=0` on pilot; reclaim thresholds documented |
| C1-7 | **Notification boundary** | Preflight/after snapshots | `notification_retry_pending` stable at **0**; no fanout storm |
| C1-8 | **Full verification** | `python -m scripts.c1_staging_verification --client-id CID --property-id PID` | Writes `c1_replay_*`, `c1_queue_after_*`, `c1_verification_report_*` |
| C1-9 | **Regression (§9)** | `pytest` files listed in tracker C1 DoD §9 | All pass before **VERIFIED** / **DONE** |

**Watchlist (non-blocking):** Materialisation may log **11 upsert passes** per sync — C1 staging proved this does **not** cause extra queue rows or recalc churn on suppressed replay (R2/R3).

**Correlation rules:** Use **C1-M1** (stable `REQUIREMENTS_SYNC:{property_id}`) for replay-idempotency proof only. Do **not** use **C1-M2** admin sync for R2/R3 (new correlation per call by design).

**Forbidden:** Raw Mongo enqueue; manual queue `DONE`/`DEAD`; fleet batch enqueue; direct `$set` on `requirements.status`; treating `message_logs` as obligation or queue health proof.

**Pilot reference (2026-05-16):** `6fd5ac4c-3fd4-4112-ade7-156977deb49f` / `d35a58ae-3c81-491c-9694-1d021dd3b8ad` — artifacts under `backend/docs/audit/c1_*`. Tracker status: **DONE**.

---

## 13. Instrumentation & analytics (pilot observation)

**Goal:** Know whether real users stall without building surveillance-heavy tracking.

| Signal | In-repo / product today | Gap / pilot action |
|--------|-------------------------|---------------------|
| Today engagement | Client `emitTodayAnalytics` → backend `product_analytics_service` (see Today page module docstring) | No single “funnel dashboard” in-repo; pilot: sample export / DB review on agreed events |
| Upload / Documents | No dedicated abandonment metric wired in SPA from Documents page | Pilot: support tags + optional server access logs for repeated failed POSTs |
| Plan friction | 403 + `UpgradePrompt` / governed discoverability | Correlate support tickets to route + `feature_key`; no new tracking required for beta if ticket discipline exists |
| Pending-state confusion | Freshness / recalc / propagation copy on KPI surfaces | Train §9 phrases; extend copy via `presentationLanguage.js` + governance, not ad hoc |

**Rule:** New client-side beacons must stay **governed** (event names, PII minimization) and require explicit product sign-off — default for pilot is **ticket + runbook** correlation, not silent behavioural tracking.

---

## Document control

**Owner:** Platform / compliance engineering + support lead.  
**Updates:** When admin routes, SLA env defaults, or Stream B–F matrices change materially, update this runbook in the **same** change train as tracker/matrix edits.
