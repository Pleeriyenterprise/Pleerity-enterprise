# Governance index — canonical navigation spine

```yaml
---
Status: ACTIVE
Authority Level: TIER_0_ROUTING (navigation only — not behavioural authority)
Related Docs: GOVERNANCE_CONSUMPTION_MAP.md, LAUNCH_AUTHORITY_TRACKER.md
Supersedes: informal doc discovery only (no document retired by this file)
Superseded By: —
Last Governance Review: 2026-05-16
Implementation Scope: All engineers, Cursor sessions, ops, launch review
Runtime Authority Areas: routing, inventory, remediation-map
---
```

**Purpose:** Single entry point for *which document is authoritative* for each concern. This file does **not** define product behaviour; it routes to documents that do.

**Rules for all governance work**

1. **Extend before create** — add sections to the canonical doc for that concern; do not add parallel trackers or “master” docs.
2. **One behavioural authority per concern** — if two docs disagree, the **lower tier** yields to **TIER_1** (see tiers below).
3. **Code wins disputes** — when docs drift from code, log drift in `LAUNCH_AUTHORITY_TRACKER.md` or `CLOSED_LOOP_COMPLIANCE_ARCHITECTURE_TRACKER.md`, then fix doc or code in a deliberate PR.
4. **No new remediation tracker** for obligation/workflow recovery — use § [Recovery governance map](#recovery-governance-map-obligation--workflow) below.
5. **Recovery units (A1–G2)** — implement only per `LAUNCH_AUTHORITY_TRACKER.md` § **Recovery unit implementation contract** (end-to-end DoD, status lifecycle, no partial DONE).

---

## Authority tiers

| Tier | Meaning | Change control |
|------|---------|----------------|
| **TIER_0** | Routing / inventory only (`GOVERNANCE_INDEX.md`) | Update when docs added, merged, or deprecated |
| **TIER_1** | Canonical **behavioural** authority — must match code or drive code change | Product + platform sign-off for normative changes |
| **TIER_2** | Operational implementation guidance, runbooks, matrices | Ops/engineering; must not contradict TIER_1 |
| **TIER_3** | Audits, phase JSON snapshots, gap analyses, designs (non-normative until promoted) | Reference only; promote findings into TIER_1/2 |
| **TIER_4** | Historical, superseded, or wrong-environment assumptions | Do not use for new work; keep for archaeology |

---

## Quick route — “where does X belong?”

| Concern | Canonical home (TIER) | Code anchor (verify) |
|---------|------------------------|---------------------|
| **Obligation materialisation** | `compliance_requirement_registry.py` + `compliance_registry_publish_service.py` (TIER_1 via code); doc: `PUBLISHED_REGISTRY_CLIENT_TRUTH_AUDIT.md` (TIER_2) | `materialize_requirements_for_property`, `build_requirement_plan_for_property`, `provisioning._generate_requirements` |
| **Client/runtime visibility of obligations** | `requirement_client_runtime_surface.py` (TIER_1 code); `COMPLIANCE_CLIENT_STATUS_AUTHORITY.md` (TIER_1 doc) | `filter_requirement_rows_for_client_runtime_surfaces` |
| **Workflow class semantics** | `WORKFLOW_BEHAVIOUR_GOVERNANCE.md` (TIER_1) + `workflow_behaviour_governance.py` (TIER_1) | `registry_workflow_semantics`, resolver |
| **Workflow activation (enqueue gates)** | `workflow_runtime_activation_registry.py` (TIER_1 code); readiness: `workflow_activation_readiness.py` (TIER_2 metadata) | `resolve_compliance_recalc_activation_gate`, RST backbone gate |
| **Mutation fan-out / propagation** | `authority_mutation_fanout.py` (TIER_1); doc: `STREAM_E_MUTATION_FANOUT_MATRIX.md` (TIER_2) | `enqueue_compliance_recalc_with_fanout`, `sync_requirement_evidence_authority` |
| **Evidence / document review state** | `evidence_review_*` services + `COMPLIANCE_CLIENT_STATUS_AUTHORITY.md` | `evidence_review_verify`, `document_operational_state` (presentation) |
| **Compliance score authority** | `compliance_scoring_service.recalculate_and_persist` (TIER_1); `STREAM_B_SCORING_AUTHORITY_MATRIX.md` (TIER_2 inventory) | `compliance_recalc_queue` worker |
| **Applicability / operator override** | `applicability_effective_resolver` + `RUNBOOK_APPLICABILITY_RESOLUTION_OPERATIONS.md` (TIER_2) | `applicability_operator_actions` |
| **Scheduler / background jobs** | `runbooks/SCHEDULER_AND_COMPLIANCE_JOBS.md` (TIER_2); registry: `job_runner.JOB_RUNNERS` + `server.py` | APScheduler, `job_runs`, `compliance_recalc_queue` |
| **Notifications** | `audit/NOTIFICATION_GOVERNANCE_INVENTORY.json` (TIER_1 policy) + `audit/NOTIFICATION_OWNERSHIP_READINESS.md` (TIER_2) | `notification_orchestrator.send` |
| **Launch / pilot constraints** | `launch/PILOT_LAUNCH_GOVERNANCE.md` (TIER_1 acceptance) + `launch/LAUNCH_AUTHORITY_TRACKER.md` (TIER_1 status) | Feature flags, activation registry |
| **Closed-loop programme (streams A–F)** | `CLOSED_LOOP_COMPLIANCE_ARCHITECTURE_TRACKER.md` (TIER_1 tracker) + `CLOSED_LOOP_ARCHITECTURAL_GAP_ANALYSIS.md` (TIER_3 audit) | Per-stream named authorities in tracker |
| **Presentation / copy** | `docs/governance/PRESENTATION_LANGUAGE_GOVERNANCE.md` (TIER_1 UX semantics) | `presentationLanguage.js`, workspace copy modules |
| **Trust-language / operational explanations** | `docs/governance/TRUST_LANGUAGE_GOVERNANCE.md` (TIER_1) | `trust_language_governance.py`, `trustLanguageGovernance.js`, `scoring_explanation_copy.py`, `scoringExplanationCopy.js` |
| **Plan / entitlements** | `plan_registry.py` + `docs/governance/PLAN_GATING_UX_GOVERNANCE.md` (TIER_1 commercial) | `enforce_feature`, `FEATURE_MATRIX` |

---

## Governance inventory (major documents)

### TIER_1 — Canonical behavioural / launch authority

| Path | Purpose | Overlaps | Action | Covers (partial) |
|------|---------|----------|--------|------------------|
| `WORKFLOW_BEHAVIOUR_GOVERNANCE.md` | Workflow class semantics, precedence, non-equivalence | `REQUIREMENT_WORKFLOW_CLASS_DECISION_RECORD.md` (open decisions) | **Extend** for new class rules; DR for per-code approvals | Workflow propagation semantics |
| `COMPLIANCE_CLIENT_STATUS_AUTHORITY.md` | Client-facing status strings, surface matrix, projection rules | `STREAM_B_SCORING_AUTHORITY_MATRIX.md`, presentation docs | **Preserve**; extend surface rows only | State authority (client), visibility |
| `launch/LAUNCH_AUTHORITY_TRACKER.md` | Launch blockers L-001…, drift detection, freeze domains | `PILOT_LAUNCH_GOVERNANCE`, closed-loop tracker | **Extend** for new launch items; **do not** duplicate | Activation, propagation, reconciliation status |
| `launch/PILOT_LAUNCH_GOVERNANCE.md` | Pilot risk acceptance, forbidden guarantees | LAUNCH_AUTHORITY_TRACKER | **Preserve** | Launch constraints |
| `audit/NOTIFICATION_GOVERNANCE_INVENTORY.json` | Notification send policy, global dispatch flag | `NOTIFICATION_SEND_INVENTORY.md`, template matrix | **Extend** inventory only; no parallel JSON | Notification governance |
| `services/workflow_runtime_activation_registry.py` | Deterministic activation gates (code authority) | `workflow_activation_readiness.py` (labels only) | **Preserve** code; document changes in TIER_2 reports | Activation governance |
| `services/compliance_requirement_registry.py` | Requirement **generation** plan (code SoT) | Published registry overlay | **Preserve** | Materialisation |
| `services/requirement_client_runtime_surface.py` | Client obligation **visibility** gates (code SoT) | `PUBLISHED_REGISTRY_CLIENT_TRUTH_AUDIT.md` | **Preserve** | Runtime visibility |
| `services/authority_mutation_fanout.py` | Post-mutation enqueue + observability | `STREAM_E_MUTATION_FANOUT_MATRIX.md` | **Preserve** | Workflow propagation |
| `services/governance_coverage_registry.py` | CI surface registry (machine) | `GOVERNANCE_CONSUMPTION_MAP.md` | **Preserve** | Drift detection |

### TIER_2 — Operational / implementation guidance

| Path | Purpose | Overlaps | Action | Covers (partial) |
|------|---------|----------|--------|------------------|
| `GOVERNANCE_CONSUMPTION_MAP.md` | Which runtime surfaces are GOVERNED vs not | This index § consumption | **Extend** rows; link here from index | Partial all areas |
| `runbooks/SCHEDULER_AND_COMPLIANCE_JOBS.md` | Scheduler owner, recalc worker SLA, Render | `AUTOMATION_CONTROL_CENTRE_AND_JOB_RUNS.md`, `RUNBOOK_CONTROLLED_BETA_OPERATIONS.md` | **Extend**; single scheduler runbook home | Scheduler execution |
| `RUNBOOK_CONTROLLED_BETA_OPERATIONS.md` | Beta ops discipline, rehearsal checklist | LAUNCH_AUTHORITY_TRACKER | **Extend** §12–13 only in one place | Operational recovery |
| `audit/AUTHORITY_WRITE_PATH_RECONCILIATION.md` | Verify/authority write ladder, support correlation | STREAM_B matrix | **Preserve** | State authority, reconciliation |
| `STREAM_B_SCORING_AUTHORITY_MATRIX.md` | Score writer inventory | COMPLIANCE_CLIENT_STATUS_AUTHORITY | **Preserve**; update on new writers | State authority (score) |
| `STREAM_E_MUTATION_FANOUT_MATRIX.md` | Who calls gap sync / recalc enqueue | authority_mutation_fanout.py | **Preserve** | Workflow propagation |
| `STREAM_D_CTA_PARITY_ENFORCEMENT.md` | take_action contract | `STREAM_D_CTA_PRODUCER_CONSUMER_MATRIX.md` | **Merge** matrices into D over time | Client actions |
| `RUNBOOK_APPLICABILITY_RESOLUTION_OPERATIONS.md` | PR4 operator commands | APPLICABILITY_PROVENANCE_LEGACY_APPLICABILITY_STATE | **Preserve** | Applicability |
| `PUBLISHED_REGISTRY_CLIENT_TRUTH_AUDIT.md` | Registry vs client truth migration policy | requirement_client_runtime_surface | **Extend** when publish/rematerialise policy changes | Materialisation + visibility |
| `compliance_registry_publish_service.py` docstring + `REMATERIALISATION_INFO` | Publish does not fleet-rematerialise | Admin publish runbooks | **Extend** in publish service doc + pointer here | Materialisation |
| `audit/NOTIFICATION_OWNERSHIP_READINESS.md` | Rendered email truth, CTA routes | NOTIFICATION_TEMPLATE_MATRIX | **Preserve** | Notifications |
| `audit/REGISTRY_WORKFLOW_DRIFT_AUDIT.md` | Registry vs resolver drift script output | governance_validation_engine | **Preserve** (generated + committed snapshots) | Workflow semantics drift |
| `audit/EVIDENCE_REVIEW_V2_CONFIG_MATRIX.md` | Evidence Review V2 flags/routes | LAUNCH_AUTHORITY_TRACKER L-005 | **Preserve** | Evidence review |
| `docs/governance/PRESENTATION_LANGUAGE_GOVERNANCE.md` | UX/copy semantics | DESIGN_SYSTEM, PLAN_GATING | **Preserve** (repo-root `docs/governance/`) | Presentation |
| `docs/governance/PLAN_GATING_UX_GOVERNANCE.md` | Plan gating UX | plan_registry | **Preserve** | Plan gating |
| `POLICY_CLASSIFICATION_VERSION_GOVERNANCE.md` | Policy classification version field | materialization policy_facts | **Preserve** | Materialisation metadata |

### TIER_1 tracker (programme — not behavioural law)

| Path | Purpose | Overlaps | Action | Covers (partial) |
|------|---------|----------|--------|------------------|
| `CLOSED_LOOP_COMPLIANCE_ARCHITECTURE_TRACKER.md` | Streams A–F implementation tracker, named authorities | CLOSED_LOOP_ARCHITECTURAL_GAP_ANALYSIS, PRODUCT_VALUE_GAP_TRACKER | **Extend** for programme work; **only** cross-cutting tracker | Remediation tracking (architecture) |
| `launch/LAUNCH_AUTHORITY_TRACKER.md` | Launch domain status | PILOT_LAUNCH_GOVERNANCE | **Extend** for L-00x items | Launch remediation |

### TIER_3 — Audits, designs, phase snapshots (reference)

| Path | Purpose | Action |
|------|---------|--------|
| `CLOSED_LOOP_ARCHITECTURAL_GAP_ANALYSIS.md` | Closed-loop mesh audit (2026) | **Preserve**; cite in tracker, do not re-audit in new doc |
| `PROPERTY_COMPLIANCE_OS_GAP_AND_RETENTION_AUDIT.md` | Product value / retention | **Preserve**; not architecture tracker |
| `PRODUCT_VALUE_GAP_TRACKER.md` | Product gaps (not architecture) | **Preserve** separate from closed-loop tracker |
| `REQUIREMENT_WORKFLOW_CLASS_DECISION_RECORD.md` | Per-code workflow class **decisions** (OPEN) | **Extend** until closed; then fold into WORKFLOW_BEHAVIOUR |
| `UNIFIED_COMPLIANCE_WORK_QUEUE_DESIGN.md` + wireframe | Future product design | **Preserve**; not runtime authority |
| `STREAM_*` (C, F forensics, correlation) | Stream-specific read-only audits | **Preserve**; link from tracker |
| `audit/*.json` (phase 1–6) | Point-in-time audit bundles | **Preserve** as snapshots; promote deltas to TIER_1/2 |
| `BETA_OBSERVATION_AND_TRUST_REVIEW.md` | Trust UX observations | Link from PILOT_LAUNCH |
| `docs/WORKFLOW_ENGINE_AUDIT.md` | **Order/document-pack** workflow (different domain) | **Do not confuse** with compliance obligation workflows |
| `docs/knowledge-centre-drafts/*` | Pilot KB drafts (non-authoritative until published) | **TIER_4** for governance |

### TIER_4 — Deprecated / historical / duplicate risk

| Path | Issue | Action |
|------|-------|--------|
| `NOTIFICATION_SEND_INVENTORY.md` + `NOTIFICATION_TEMPLATE_MATRIX.md` | Overlap with JSON inventory | **Deprecate** for policy; use JSON + OWNERSHIP_READINESS |
| `ENTERPRISE_NOTIFICATION_TASK_GAP_ANALYSIS.md` | Pre-governance gap analysis | **Historical** |
| Multiple `OPERATIONAL_CONFIRMATION_*` JSON phases | Superseded by later phases | **Archive reference** only |
| `docs/EMAIL_TRIGGER_MAP.md` | May drift from orchestrator | Verify against JSON inventory before use |

---

## Duplicated authorities & conflicts (explicit)

### Behavioural semantics (workflow)

| Conflict | Documents | Resolution rule |
|----------|-----------|-----------------|
| Workflow class meaning | `WORKFLOW_BEHAVIOUR_GOVERNANCE.md` vs `REQUIREMENT_WORKFLOW_CLASS_DECISION_RECORD.md` (open) | **TIER_1:** WORKFLOW_BEHAVIOUR; DR holds pending per-code decisions only |
| Upload = compliant implication | WORKFLOW_BEHAVIOUR vs legacy UI copy | WORKFLOW_BEHAVIOUR wins; fix copy via PRESENTATION_LANGUAGE |
| Registry evidence_resolution vs defaults | WORKFLOW_BEHAVIOUR § precedence vs `DEFAULT_EVIDENCE_RESOLUTION_*` | Published registry > governance > resolver > defaults |

### State / status authority

| Conflict | Documents | Resolution rule |
|----------|-----------|-----------------|
| Client badge vs Mongo `status` | `COMPLIANCE_CLIENT_STATUS_AUTHORITY.md` vs raw `requirements.status` | **Projection + evidence authority** win on client surfaces |
| Optimistic verify mirror | LAUNCH_AUTHORITY_TRACKER L-004 vs authority sync | Documented window; authority is SoT after sync |
| Admin list vs client list | Unfiltered `requirements.find` vs `filter_requirement_rows_*` | **Client path** is authoritative for portal; admin must label “internal view” |

### Activation vs notifications

| Conflict | Documents | Resolution rule |
|----------|-----------|-----------------|
| “Workflow activated” vs orchestrator sends | `workflow_runtime_activation_registry.py` vs `NOTIFICATION_GOVERNANCE_INVENTORY.json` | **Separate concerns** — activation gates enqueue/score; notifications use orchestrator regardless of NOTIFICATION_DISPATCH family flag |
| NOTIFICATION_DISPATCH globally off | JSON policy vs product expectation of reminders | **Pilot:** PILOT_LAUNCH_GOVERNANCE + scheduler jobs still run via orchestrator paths — **verify env** |

### Trackers (avoid parallel remediation systems)

| Tracker | Scope | Use for obligation/workflow recovery? |
|---------|-------|--------------------------------------|
| `launch/LAUNCH_AUTHORITY_TRACKER.md` | Launch gates L-001… | **Yes** — new L-0xx rows for launch blockers |
| `CLOSED_LOOP_COMPLIANCE_ARCHITECTURE_TRACKER.md` | Streams A–F architecture | **Yes** — cross-cutting implementation phases |
| `PRODUCT_VALUE_GAP_TRACKER.md` | Product value | **No** — separate product lane |
| `PROPERTY_COMPLIANCE_OS_GAP_AND_RETENTION_AUDIT.md` | Retention/product | **No** — reference only |
| New “obligation recovery tracker” | — | **Do not create** — use § Recovery map below |

### Implementation drift (docs vs code) — known hotspots

| Topic | Doc assumption | Code reality (verify in PR) |
|-------|----------------|----------------------------|
| Obligations at intake | KB drafts imply immediate obligations | Materialisation at **provisioning** / property create |
| Registry publish | Operators may expect auto-rematerialise | **No fleet rematerialise** — per-property sync |
| Reminders UNGOVERNED | GOVERNANCE_CONSUMPTION_MAP | Jobs exist via `jobs.py` — governance linkage partial |
| TODAY_TASK rebuild | Deferred family | Tasks built via `unified_tasks_service` without that family |

---

## Recovery governance map (obligation & workflow)

**Do not add a new recovery doc.** Extend these only.

| Issue area | Canonical document | Supporting docs | Tracker / verification | Owner area | Sequence |
|------------|-------------------|-----------------|------------------------|------------|----------|
| **A. Requirements not materialised** | `PUBLISHED_REGISTRY_CLIENT_TRUTH_AUDIT.md` + code: `provisioning.py` | `RUNBOOK_CONTROLLED_BETA_OPERATIONS.md` § provisioning | New **L-0xx** or closed-loop note in `LAUNCH_AUTHORITY_TRACKER` / stream row in closed-loop tracker | Platform / provisioning | 1. Prove `onboarding_status`; 2. `requirements.count`; 3. fix provisioning |
| **B. Materialised but client-invisible** | `COMPLIANCE_CLIENT_STATUS_AUTHORITY.md` + `requirement_client_runtime_surface.py` | `PUBLISHED_REGISTRY_CLIENT_TRUTH_AUDIT.md` | Closed-loop **Stream A/B** matrix rows; Mongo queries in runbook | Registry + client surfaces | 1. Compare raw vs filtered API; 2. registry overlay keys; 3. `requirements/sync` |
| **C. Score/tasks not updating** | `runbooks/SCHEDULER_AND_COMPLIANCE_JOBS.md` | `STREAM_E_MUTATION_FANOUT_MATRIX.md`, `AUTHORITY_WRITE_PATH_RECONCILIATION.md` | `job_runs`, `compliance_recalc_queue`, LAUNCH **L-006** | Platform ops | 1. Scheduler owner; 2. queue drain; 3. activation gate logs |
| **D. Workflow propagation blocked** | `authority_mutation_fanout.py` + `STREAM_E_MUTATION_FANOUT_MATRIX.md` | `WORKFLOW_BEHAVIOUR_GOVERNANCE.md` | Transition fanout traces; LAUNCH **L-009** | Compliance platform | 1. Prove backbone gate; 2. fix enqueue path |
| **E. Document/evidence state stale** | `COMPLIANCE_CLIENT_STATUS_AUTHORITY.md` + `audit/AUTHORITY_WRITE_PATH_RECONCILIATION.md` | Extraction supersession (operational runbook § in beta runbook) | Admin verify + client API parity tests | Evidence review | After A–C proven |
| **F. Notifications / reminders** | `audit/NOTIFICATION_GOVERNANCE_INVENTORY.json` | `NOTIFICATION_OWNERSHIP_READINESS.md`, `runbooks/SCHEDULER_AND_COMPLIANCE_JOBS.md` | `message_logs`, pilot checklist PILOT_LAUNCH | Notifications | After core truth stable |
| **G. Operator/support confusion** | `RUNBOOK_CONTROLLED_BETA_OPERATIONS.md` | `STREAM_F_FORENSICS_JOIN_RECIPE.md`, `SUPPORT_REMEDIATION_CORRELATION_VIEW_V1.md` | Support rehearsal §12 | Support / ops | Continuous |

**Verification location (single):** `RUNBOOK_CONTROLLED_BETA_OPERATIONS.md` §12 rehearsal + Mongo queries documented in recovery investigation (attach to **LAUNCH_AUTHORITY_TRACKER** as appendix row, not new file).

**Implementation sequence (governed):** A → B → C → D → E → F; no code-first on F until A–C pass/fail per tenant.

---

## Where each runtime authority area belongs

| Runtime authority area | Primary doc home | Primary code home | Secondary |
|------------------------|------------------|-------------------|---------|
| **Obligation materialisation** | `PUBLISHED_REGISTRY_CLIENT_TRUTH_AUDIT.md` (policy); publish service docstring | `requirement_materialization_service.py`, `compliance_requirement_registry.py` | `RUNBOOK_APPLICABILITY` (applicability only) |
| **Workflow propagation** | `WORKFLOW_BEHAVIOUR_GOVERNANCE.md`, `STREAM_E_MUTATION_FANOUT_MATRIX.md` | `authority_mutation_fanout.py`, `requirement_evidence_authority.py` | `trigger_propagation_audit.py` |
| **Scheduler operational** | `runbooks/SCHEDULER_AND_COMPLIANCE_JOBS.md` | `server.py`, `job_runner.py`, `compliance_recalc_queue.py` | `AUTOMATION_CONTROL_CENTRE_AND_JOB_RUNS.md` |
| **Runtime visibility** | `COMPLIANCE_CLIENT_STATUS_AUTHORITY.md` | `requirement_client_runtime_surface.py` | `document_operational_state.py` (presentation only) |
| **Reconciliation (score/authority)** | `audit/AUTHORITY_WRITE_PATH_RECONCILIATION.md` | `compliance_scoring_service`, reclaim scripts | LAUNCH_AUTHORITY_TRACKER L-004, L-006 |
| **State authority (requirement row)** | `COMPLIANCE_CLIENT_STATUS_AUTHORITY.md` | `requirement_evidence_authority.py`, `requirement_truth.py` | `evidence_review_migration.py` |
| **Activation governance** | `launch/PILOT_LAUNCH_GOVERNANCE.md` + LAUNCH tracker L-009 | `workflow_runtime_activation_registry.py` | Phase JSON reports (TIER_3) |
| **Notification governance** | `audit/NOTIFICATION_GOVERNANCE_INVENTORY.json` | `notification_orchestrator` | Template matrix (TIER_4) |

---

## Machine-readable governance (CI)

| Asset | Tier | Role |
|-------|------|------|
| `services/governance_coverage_registry.py` | TIER_1 | Surface → enforcement metadata |
| `services/governance_validation_engine.py` | TIER_1 | CI validation rules |
| `services/governance_observability.py` | TIER_2 | Optional telemetry hooks |
| `services/workflow_behaviour_governance.py` | TIER_1 | Workflow capability matrix (code) |
| `tests/snapshots/governance_phase1_*.json` | TIER_3 | CI snapshots |

---

## Frontend governance (repo-root)

| Path | Tier | Notes |
|------|------|-------|
| `docs/governance/TRUST_LANGUAGE_GOVERNANCE.md` | TIER_1 | Scoring/operational explanation copy, causal language, AI constraints, drift prevention |
| `docs/governance/PRESENTATION_LANGUAGE_GOVERNANCE.md` | TIER_1 | Copy/CTA semantics |
| `docs/governance/PLAN_GATING_UX_GOVERNANCE.md` | TIER_1 | Entitlement UX |
| `docs/governance/DESIGN_SYSTEM_GOVERNANCE.md` | TIER_2 | Visual system |
| `docs/CLIENT_PORTAL_WORKFLOW_MATRIX.md` | TIER_3 | Portal map; must align with TIER_1 backend |

---

## Services / scripts (not docs — but authority)

| Module | Role |
|--------|------|
| `workflow_activation_governance_report.py` | Read-only reports (TIER_3 output) |
| `workflow_activation_governance_report_bundle.py` | Bundle/diff reports |
| `reporting_semantic_governance_audit.py` | Reporting copy audit |
| `requirement_workflow_audit.py` | Admin workflow mismatch flags |
| `scripts/registry_workflow_drift_audit.py` | Drift script |
| `scripts/sync_registry_properties_batch.py` | Batch materialise (ops) |

---

## Minimum document set — propose

### Create (approved)

| Doc | Reason |
|-----|--------|
| **`GOVERNANCE_INDEX.md`** (this file) | Genuine gap: no canonical router existed |

### Extend (preferred over new docs)

| Doc | What to add |
|-----|-------------|
| `launch/LAUNCH_AUTHORITY_TRACKER.md` | Appendix: **Obligation & workflow recovery** (link to § Recovery map here) |
| `CLOSED_LOOP_COMPLIANCE_ARCHITECTURE_TRACKER.md` | Stream note: materialisation + propagation recovery under existing streams |
| `runbooks/SCHEDULER_AND_COMPLIANCE_JOBS.md` | § “Governance cross-links” pointing here |
| `PUBLISHED_REGISTRY_CLIENT_TRUTH_AUDIT.md` | § Provisioning vs intake vs sync timing |
| `GOVERNANCE_CONSUMPTION_MAP.md` | Banner: “See GOVERNANCE_INDEX.md for full topology” |
| `RUNBOOK_CONTROLLED_BETA_OPERATIONS.md` | §12 queries for obligation visibility vs materialisation |

### Merge (over time, not urgent)

| Target | Sources to fold in |
|--------|-------------------|
| `STREAM_D_CTA_PARITY_ENFORCEMENT.md` | `STREAM_D_CTA_PRODUCER_CONSUMER_MATRIX.md` |
| `audit/NOTIFICATION_OWNERSHIP_READINESS.md` | Retire duplicate tables from `NOTIFICATION_TEMPLATE_MATRIX.md` |

### Deprecate (mark TIER_4 in index; do not delete yet)

| Doc | Reason |
|-----|--------|
| Ad-hoc phase remediation JSON (orphan) | Superseded by later phase bundles |
| `NOTIFICATION_SEND_INVENTORY.md` | Superseded by JSON inventory |
| Duplicate gap analyses at repo root (`docs/*GAP*`) | Historical unless referenced in tracker |

### Do **not** create

| Avoid | Reason |
|-------|--------|
| `OBLIGATION_RECOVERY_TRACKER.md` | Use LAUNCH_AUTHORITY_TRACKER + closed-loop tracker |
| `WORKFLOW_PROPAGATION_GOVERNANCE.md` | Extend WORKFLOW_BEHAVIOUR + STREAM_E |
| `MASTER_GOVERNANCE.md` | This index is sufficient TIER_0 |
| New extraction/supersession governance doc | Extend AUTHORITY_WRITE_PATH + beta runbook |

---

## Metadata header template (for TIER_1 / TIER_2 docs)

Apply incrementally when touching a file; do not bulk-edit unrelated docs.

```markdown
---
Status: ACTIVE | DEPRECATED | OPEN
Authority Level: TIER_1 | TIER_2 | TIER_3 | TIER_4
Related Docs: path1, path2
Supersedes: path or —
Superseded By: path or —
Last Governance Review: YYYY-MM-DD
Implementation Scope: who must follow this
Runtime Authority Areas: materialisation | propagation | scheduler | visibility | reconciliation | activation | notifications | state
---
```

---

## Cursor session protocol

1. Read **this index** → identify concern row in [Quick route](#quick-route--where-does-x-belong).
2. Open **canonical TIER_1** doc + **code anchor**.
3. If changing behaviour, update **tracker** (launch or closed-loop) in same PR.
4. If adding governance text, **extend** canonical doc; update this index only when topology changes.
5. Never create a second tracker for the same programme.

---

## Changelog (index only)

| Date | Change |
|------|--------|
| 2026-05-16 | Recovery unit implementation contract (end-to-end DoD, status lifecycle) in launch tracker |
| 2026-05-16 | Initial topology audit; recovery map; tier assignments; inventory table |
