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
| **SLA alert delivery** | `OPS_ALERT_EMAIL` set; `COMPLIANCE_SLA_ALERT` template path verified in beta env. |
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

## Document control

**Owner:** Platform / compliance engineering + support lead.  
**Updates:** When admin routes, SLA env defaults, or Stream B–F matrices change materially, update this runbook in the **same** change train as tracker/matrix edits.
