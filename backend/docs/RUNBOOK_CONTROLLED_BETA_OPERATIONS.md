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

### 4.8 Guided evidence — “submission disappeared” (TRUST-01)

**TRUST-01 frontend remediation:** implemented and verified through OPS-VERIFY-01 Journey A browser re-submit path (2026-05-18). Local dev: allow both `http://localhost:3000` and `http://127.0.0.1:3000` CORS origins when using split host API URL.

1. Confirm the user completed **Submit evidence** (authoritative `POST /compliance-evidence`), not only **Upload supporting files** (document upload is informational until submit).  
2. In the client UI, open **Requirement details** → **Your submission** (or primary **View submission** when lifecycle is pending review). Payload is read from persisted CER via `GET …/compliance-evidence`, not lifecycle labels alone.  
3. If submit succeeded but panel is empty: verify CER exists for `requirement_id` (non-archived) in `compliance_evidence_records`; do **not** patch requirement status for display.  
4. Escalate **S2** only when CER is missing after a confirmed successful POST (data integrity), not when the user stopped after supporting upload.

### 4.9 Client evidence journeys — operational verification (OPS-VERIFY-01)

**Unit status:** **COMPLETE (A/B/C)** — Journey D optional, not executed. Pilot bundle `docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/`.

When users report “submitted but nothing shows” or “upload didn’t count”:

1. Distinguish **supporting upload** vs **POST compliance-evidence** (RUNBOOK §4.8).
2. Run OPS-VERIFY-01 checklist: CER exists → authority blob → queue DONE → UI inspect (Requirement details → Your submission).
3. Capture read-only bundles via `python -m scripts.ops_verify_01_capture` (baseline → post-submit → convergence) and classify via `python -m scripts.ops_verify_01_classify`.
4. Do not treat D1/C2 pass as proof the client journey worked — check OPS-VERIFY-01 artefacts.
5. **Pilot closure (2026-05-20):** A = existing-CER re-submit (`?open=resolve`); clean first-submit remains **watchlist**. B = **fire_alarm** primary upload. C = supporting-only with truthful copy after TRUST remediation. D = not run.

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

**Wales HMO pilot acceptance (2026-05-16):** After B1, **8** client-visible planner-aligned families is accepted operational truth for tenant `6fd5ac4c…`. `emergency_lighting` / `fire_extinguisher` are **not** defects — intentionally non-visible (no overlay). **C1** queue proof **DONE**, **C2** downstream convergence **DONE**, and **D1** propagation fanout proof **DONE** on this tenant (2026-05-17); see §12.7 C1, C2, and D1 below.

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

#### C2 — Downstream convergence after recalc (only after C1 **DONE**; launch unit **C2**)

**Authority:** `LAUNCH_AUTHORITY_TRACKER.md` § **C2** (rev 4 DoD) + § **C2a**; `CLOSED_LOOP_COMPLIANCE_ARCHITECTURE_TRACKER.md`. **Not** fanout repair, activation policy redesign, notification proof, queue/recalc changes, or unified_tasks architecture work.

**Prerequisites:** C1 **DONE** for tenant; B1 visibility accepted; staging `MONGO_URL` + `DB_NAME`; pilot `CID` + `PID`; control unrelated `(CID', PID')` recorded in `c2_control_selection_*.json`.

| # | Step | Command / action | Pass criteria |
|---|------|------------------|---------------|
| C2-0 | **Preflight** | `python -m scripts.c2_preflight_capture --client-id CID --property-id PID` | `c2_convergence_before_*`, `c2_unrelated_surface_integrity_*` (note: §7c baseline at verification **run start** uses normalized fingerprints — see C2 closure) |
| C2-1 | **R1 — first C2-M1** | Client `POST /api/properties/PID/requirements/sync` (same as C1-M1) | Queue **DONE**; gaps/risk/priority/tasks/KPI converge within §3 lag bounds; append `convergence_order_timeline[]` |
| C2-2 | **Surface snapshots** | Captured by staging script | `c2_gaps_*`, `c2_risk_priority_*`, `c2_dashboard_tasks_*`, `c2_exclusions_*`, `c2_stale_decay_*`, `c2_consistency_hashes_*`, `c2_lineage_trace_*` |
| C2-3 | **R2/R3 — stable replay** | Repeat C2-M1 ×2 | `enqueued=false`; **normalized** `tasks_today` fingerprint R2=R3; full cross-surface R2=R3; lineage fingerprint R2=R3 |
| C2-4 | **§7c unrelated integrity** | Control tenant fingerprints before/after pilot window | `unrelated_mutation_delta` **0** on gaps, risk_priority, dashboard_tasks (normalized keys), property, gap_count, `score_last_calculated_at` |
| C2-5 | **Full verification** | `python -m scripts.c2_staging_verification --client-id CID --property-id PID` | `c2_verification_report_*` with `c2_pass=true`; `temporal_ordering_violations_empty` (settled recalc ≠ resolved compliance) |
| C2-6 | **Regression (§9)** | `pytest tests/test_c2_verification_contract.py` (+ C1 suite) | All pass before **VERIFIED** / **DONE** |

**Fingerprint mode (mandatory since C2a):** `normalized_stable_business_keys_c2a` — hash stable business keys from `fetch_client_priority_actions`, **not** volatile `risk_signal:rs_*` task ids. Legacy volatile-id fingerprint retained as `fingerprint_legacy_volatile_ids` for diagnostics only.

**Temporal ordering (C2-RC-13):** Do **not** treat `compliance_score_pending=false` alone as “all clear” while gaps remain OPEN. Fire only when downstream **explicitly** asserts resolved/healthy with OPEN gaps still present.

**Watchlist (non-blocking):** `risk_signal:rs_*` task **ids** may rotate when `regeneration_requeued=true` on materialise — C2a proved priority stream and business-key fingerprints remain stable; no product `_stable_source_id` fix shipped.

**Forbidden:** Using notification/`message_logs` as convergence proof; fanout/activation fixes under C2; raw Mongo gap/task edits; treating preflight legacy fingerprints as §7c end-state baseline.

**Pilot reference (2026-05-16):** `6fd5ac4c-3fd4-4112-ade7-156977deb49f` / `d35a58ae-3c81-491c-9694-1d021dd3b8ad` — artifacts: `c2_verification_report_6fd5ac4c_d35a58ae.json`, `c2a_task_drift_analysis_6fd5ac4c_d35a58ae.json`, `c2_consistency_hashes_6fd5ac4c_d35a58ae.json`, `c2_replay_6fd5ac4c_d35a58ae.json`, `c2_unrelated_surface_integrity_6fd5ac4c_d35a58ae.json`. Tracker status: **DONE**.

#### D1 — Workflow propagation fanout (only after C2 **DONE**; launch unit **D1** + harness **D1b**)

**Authority:** `LAUNCH_AUTHORITY_TRACKER.md` § **D1** (rev 3 DoD) + § **D1b**; `STREAM_E_MUTATION_FANOUT_MATRIX.md` (observe-only). **Not** fanout topology repair, activation policy redesign, queue semantics changes, scheduler redesign, notification proof, or production route changes.

**Prerequisites:** C1 + C2 **DONE** for tenant; staging `MONGO_URL` + `DB_NAME`; pilot `CID` + `PID`; control unrelated pair in `d1_control_selection_*` (may reuse C2 control).

| # | Step | Command / action | Pass criteria |
|---|------|------------------|---------------|
| D1-0 | **Preflight** | `python -m scripts.d1_preflight_capture --client-id CID --property-id PID` | `d1_fanout_before_*`, `d1_control_selection_*` (optional; D1b rerun may reuse) |
| D1-1 | **R1 — first fanout (D1-M1)** | Staging script: `enqueue_compliance_recalc_with_fanout` + synthetic `transition_fanout` | Cardinality **2** branches; recalc duplicate suppression on replay path observable |
| D1-2 | **R2/R3 — stable replay** | Repeat D1-M1 ×2 | `fanout_row_fingerprint` R2=R3; `suppression_replay_equal`; `replay_collapse_state` stable; `noise_pass` on R2/R3 (overlay vs **prior replay state**) |
| D1-3 | **Lineage replay window** | Captured pre-M2 in script | `lineage_replay_stable=true` — correlation-attributed propagation fingerprint R2=R3 (**not** property-wide score-history poll) |
| D1-4 | **M2 — new correlation** | Admin registry sync once (script `_d1_m2`) | New `ADMIN_MANUAL_JOB:REGISTRY_SYNC:…` correlation; separate `d1b_lineage_trace_m2_*` |
| D1-5 | **Full verification** | `python -m scripts.d1_staging_verification --artifact-prefix d1b --verification-run d1b_harness_rerun_v3 --client-id CID --property-id PID` | `d1b_verification_report_*` with **`d1_pass=true`** |
| D1-6 | **Regression (§12)** | `pytest tests/test_d1_verification_contract.py` | All pass before **DONE** |

**Driver vs production (open governance):** D1 staging uses **`enqueue_compliance_recalc_with_fanout`**. Production client **`POST /api/properties/{property_id}/requirements/sync`** still uses **direct** `enqueue_compliance_recalc` — documented in report; **not** remediated in D1. Aligning the HTTP route requires a **separate approved unit** with its own DoD.

**Artifact authority:** **`d1b_*` authoritative** for D1 closure (`verification_run=d1b_harness_rerun_v3` on pilot). Original **`d1_*`** preserved (first run harness false positives incl. **D1-RC-15**).

**Forbidden:** Mutating `authority_mutation_fanout` routing; converting production sync to `_with_fanout` under D1; notification/scheduler changes; treating `message_logs` as propagation proof.

**Pilot reference (2026-05-17):** `6fd5ac4c-3fd4-4112-ade7-156977deb49f` / `d35a58ae-3c81-491c-9694-1d021dd3b8ad` — authoritative: `d1b_verification_report_6fd5ac4c_d35a58ae.json`, `d1b_propagation_replay_6fd5ac4c_d35a58ae.json`. Tracker status: **DONE**.

#### E1 — Evidence / document state authority (only after D1 **DONE**; launch unit **E1**)

**Authority:** `LAUNCH_AUTHORITY_TRACKER.md` § **E1** (rev 3 DoD). **Not** authority-engine redesign, reconciliation redesign, extraction redesign, workflow/queue/fanout/scheduler/notification changes, or production route alignment.

**Prerequisites:** D1 + D1b **DONE**; C1 + C2 **DONE**; staging `MONGO_URL` + `DB_NAME=pleerity_staging`; pilot `CID` + `PID`; control pair in `e1_control_selection_*` (may reuse D1/C2 control `04ceda9f…` / `6d939c70…`).

| # | Step | Command / action | Pass criteria |
|---|------|------------------|---------------|
| E1-0 | **Fixture seed (E1b)** | `python -m scripts.e1b_staging_fixture_seed --client-id CID --property-id PID` | `e1b_fixture_seed_*`; classification **authority-capable** |
| E1-0a | **Preflight (E1a gate)** | `python -m scripts.e1a_preflight_capture --client-id CID --property-id PID` | `e1a_fixture_classification_*` — fail-fast if authority-incapable |
| E1-1 | **R1/R2/R3 — authority replay (E1-M1)** | `python -m scripts.e1b_staging_verification --verification-run e1b_staging_proof_v1` | Semantic replay stable R2=R3; `e1b_pass=true` |
| E1-2 | **Reconciliation observe (E1-M7)** | Captured inside E1b script | `dry_run=True` only |
| E1-3 | **Contract regression** | `pytest tests/test_e1_verification_contract.py tests/test_e1a_verification_contract.py` | Green |
| E1-4 | **Baseline suites (§14)** | Per tracker E1 DoD §14 | Required before **DONE** (not yet closed) |
| E1-5 | **Report** | `e1b_verification_report_{slug}.json` | **Authoritative for VERIFIED**; `e1_*`/`e1a_*` preserved for history |

**Governed mutations (harness v1):** **E1-M1** (replay), **E1-M7 observe** (dry_run). **E1-M2–M6, M8–M9** deferred to expanded harness if DoD requires additional mutation paths.

**RC discipline:** On `e1_pass=false`, **preserve all artifacts**, record `primary_rc_branch` (**E1-RC-1**–**E1-RC-24**), **stop** — no remediation without separate approved unit.

**Forbidden:** Raw Mongo authority edits; reconciliation **apply** under initial proof unless explicitly approved; OCR/extraction model changes; fanout/queue/scheduler/notification changes; bundling fixes into verification PRs.

**Pilot reference (2026-05-17):** `6fd5ac4c-3fd4-4112-ade7-156977deb49f` / `d35a58ae-3c81-491c-9694-1d021dd3b8ad` — authoritative: `e1b_verification_report_6fd5ac4c_d35a58ae.json` (`e1b_pass=true`). Preserved history: `e1_*` (E1-RC-2, authority-incapable), `e1a_*` (E1a-RC-FIXTURE). Tracker status: **VERIFIED** (parent **not DONE**).

#### F1 — Notification governance replay (only after E1 **VERIFIED**; launch unit **F1** + harness **F1a**)

**Authority:** `LAUNCH_AUTHORITY_TRACKER.md` § **F1** (rev 2 DoD) + § **F1a**; `audit/NOTIFICATION_GOVERNANCE_INVENTORY.json`; **L-008**. **Not** orchestrator/provider/queue/scheduler/template redesign, retry redesign, acknowledgement-system redesign, or global `NOTIFICATION_DISPATCH` activation.

**Prerequisites:** E1 **VERIFIED**; D1 + C1 + C2 **DONE**; staging `MONGO_URL` + `DB_NAME=pleerity_staging`; pilot `CID` + `PID`; control pair in `f1a_control_selection_*` (default `04ceda9f…` / `6d939c70…`).

| # | Step | Command / action | Pass criteria |
|---|------|------------------|---------------|
| F1-0 | **Preflight** | `python -m scripts.f1a_preflight_capture --client-id CID --property-id PID` | `f1a_fixture_classification_*` — **notification-replay-capable** |
| F1-1 | **R1/R2/R3 — F1-M1 replay** | `python -m scripts.f1a_staging_verification --verification-run f1a_harness_refinement_rerun_v1` | R2/R3 `duplicate_ignored`; semantic replay stable; no log growth |
| F1-2 | **Ack replay-pair (F1a)** | Captured in `f1a_acknowledgement_semantics_*` | `acknowledgement_replay_equal=true` on M1 row — **not** population diversity |
| F1-3 | **F1-M8 observe** | `NOTIFICATION_DISPATCH` off in inventory | Activation-blocked observe only |
| F1-4 | **Contract regression** | `pytest tests/test_f1_verification_contract.py tests/test_f1a_verification_contract.py` | Green |
| F1-5 | **Baseline suites (§8)** | `pytest tests/test_f1*_verification_contract.py` + L-008 notification suites (programme CI) | Harness contract green; full L-008 matrix programme-owned |
| F1-6 | **Report** | `f1a_verification_report_{slug}.json` | **Authoritative for F1 DONE**; `f1_*` preserved permanently |

**Governed mutations (proof scope):** **F1-M1** (stable idempotency replay probe); **F1-M8** observe. **F1-M2–M7** deferred.

**RC / critical-stop discipline:** On replay defect signals (amplification, cross-tenant bleed, ack certainty **escalation on replay**, delivery-authority contradiction): **preserve artifacts**, record `primary_rc_branch`, **stop** — **no** remediation without separate approved unit.

**First-run history:** Original `f1_*` (`f1_first_governed_staging_run_v1`) critical-stopped **F1-RC-15** — **reclassified** as harness methodology (population ack compare), **not** product instability. **Do not delete** `f1_verification_report_*`.

**Replay normalization (observational only):** Timestamp fields + run labels may be stripped for **semantic replay compare** only. **Never** normalize delivery authority, visible user impact, acknowledgement certainty on replay pair, suppression state, lineage, or amplification signals.

**Watchlist (visible after DONE — not hidden debt):** Historical `inferred_acknowledgement` in population; raw timestamp observational drift; provider/inbox certainty out of scope; **F1-M2–M7** unproven; `NOTIFICATION_DISPATCH` off.

**DONE interpretation:** F-layer replay-governance proof **complete** for approved **F1-M1** scope. **Not** architecture finality. Future work = **separate verification or remediation units** only.

**Forbidden:** Raw Mongo `message_logs` injection; orchestrator/provider/queue/scheduler/template redesign under F1 guise; treating provider **SENT** or platform **DELIVERED** as guaranteed user receipt; silent F1 scope extension.

**Pilot reference (2026-05-17):** `6fd5ac4c-3fd4-4112-ade7-156977deb49f` / `d35a58ae-3c81-491c-9694-1d021dd3b8ad` — authoritative: `f1a_verification_report_6fd5ac4c_d35a58ae.json` (`f1a_rc15_cleared=true`, exit 0). Preserved: `f1_*` (**F1-RC-15** harness — **do not delete**). Tracker status: **DONE** (**F1a DONE**).

#### G1 — Launch governance surveillance (LGS) — Tranche T1 placeholder

**Authority:** `LAUNCH_AUTHORITY_TRACKER.md` § **G1** (recovery LGS — **signed off** 2026-05-17). **Not** constitutional operating system; **not** remediation.

| Posture | Rule |
|---------|------|
| **Status** | **IN_PROGRESS** — Tranche **T1** harness **pending** (no staging surveillance execution yet) |
| **Surveillance** | **Read-only** when implemented — no product mutation |
| **Degraded mode** | `g1_pass` **must be false** if `degraded_mode=true` or not `SURVEILLANCE_FULL` |
| **Authoritative reruns** | Preserve `d1b_*`, `e1b_*`, `f1a_*` as Tier-0; historical `d1_*` / `e1_*` / `f1_*` **not** deleted |
| **T1 scope** | Manifest integrity, registry erasure checks, critical authoritative presence — **G1-P1**, **G1-P2**, **G1-P5**, **G1-RC-21**, **G1-RC-27** only |

**Operational procedures:** **Not yet defined** — await T1 harness merge and separate staging surveillance approval.

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
