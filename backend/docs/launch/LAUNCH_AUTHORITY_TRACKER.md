# Compliance Vault Pro — Launch Authority Tracker

**Program:** Compliance Vault Pro Launch Authority Program  
**Role:** Single source of truth for launch blockers, stabilization, deferred/accepted risks, and governance status.  
**Baseline:** PRE-LAUNCH GOVERNANCE AUDIT (Directions A — Product Hardening, B — User Trust UX, C — Commercial Readiness). *If the audit lives outside this repository, link the canonical export here when available.*

**Allowed status values only:** `READY` | `PARTIAL` | `BLOCKED` | `DEFERRED_FOR_POST_LAUNCH` | `ACCEPTED_LAUNCH_RISK`

**Last tracker update:** 2026-05-08 (+ **L-005 vertical closure** — parent **`READY_FOR_WIDER_LAUNCH`** per [L-005 closure inventory](#l-005--parent-terminal-state-inventory--freeze-2026-05-08); **L-008** / **L-009** / **L-010** unchanged)

---

## Readiness scoring (high level)

| Dimension | Score (1–5) | Status | Notes |
|-----------|-------------|--------|-------|
| A — Product hardening (authorities, queues, recovery) | 4 | PARTIAL | Same as prior + **P2** replay lineage on `enqueue_compliance_recalc_with_fanout` downstream rows; **P4** operator ladder in authority reconciliation doc; optimistic verify write still present |
| B — User trust UX (async honesty, no overclaim) | 4 | PARTIAL | Portfolio recalc honesty fields + UI; property-level strip optional follow-up |
| C — Commercial readiness (billing, notifications, supportability) | 4 | PARTIAL | **L-008** + **L-010** parents **`READY_FOR_WIDER_LAUNCH`** (notification + plan-feature CI); billing/Stripe commercial narrative still separate review |
| **Composite launch posture** | — | **PARTIAL** | **Not** READY FOR WIDER LAUNCH per gate checklist below |

---

## Mandatory wider-launch gate checklist (all must be TRUE)

| # | Gate | As of last update |
|---|------|-------------------|
| 1 | No known conflicting authorities remain | **FALSE** — legacy optimistic requirement `$set` on verify remains; authority reconciles after; single score writer holds |
| 2 | No major stale-state trust risks remain | **PARTIAL** — queue + `compliance_score_pending` observable; some surfaces depend on refresh |
| 3 | No misleading compliance wording remains | **PARTIAL** — improved; ongoing copy review against authority docs |
| 4 | Notification ownership is governed | **PARTIAL** — **L-008** inventory closed for in-scope template governance + high-volume idempotency (**L-008d/e**); **`NOTIFICATION_DISPATCH`** global activation remains intentionally off; deprecated `EmailService` quarantine unchanged |
| 5 | Recovery/reconciliation paths exist | **PARTIAL** — recalc queue, admin validate/repair, SLA monitors; not fully exercised under chaos |
| 6 | Core async flows are observable | **PARTIAL** — fanout / transition observability + **queue replay/idempotency fields** on authority-mutation enqueue; not all clients consume full trace |
| 7 | Operational support flows are viable | **PARTIAL** — support correlation ladder documented (`AUTHORITY_WRITE_PATH_RECONCILIATION.md`); stuck `RUNNING` reclaim still manual |
| 8 | Evidence semantics are consistent | **PARTIAL** — **L-009** inventory closed (bulk/zip, deletes/rejects, admin document mutations); **FE** still does not consume `propagation_notice` (explicit L-009 exclusion); **L-005** parent **`READY_FOR_WIDER_LAUNCH`** for in-scope V2 API + admin UI flag coherence (**L-005e**); wider copy / tier marketing review remains program work |
| 9 | Critical workflows are tested | **PARTIAL** — unit/HTTP suites; Mongo-dependent env gaps remain |
|10 | Remaining risks explicitly accepted | **PARTIAL** — this tracker + audit docs; formal sign-off not recorded here |

**Conclusion:** **READY FOR WIDER LAUNCH — NO.**  
**Controlled beta / paid pilot:** **PARTIAL** — possible only with explicit risk acceptance and ops runbooks (not invented here).

---

## Drift detection — latest implementation pass (2026-05-10)

| Drift signal | Detected? | Disposition |
|--------------|-------------|-------------|
| Duplicate authority | Evidence Review V2 verify previously called `sync_requirement_evidence_authority` **without** RST backbone gate / **without** `enqueue_compliance_recalc_with_fanout` | **Reduced** — V2 verify now uses `authority_sync_with_transition_observability` + `enqueue_compliance_recalc_with_fanout` (same contract as document verify v1 path) |
| Conflicting workflow semantics | Verify V2 vs V1 enqueue semantics diverged on backbone-block skip | **Reduced** — aligned |
| Hidden async behaviour | Recalc enqueue without fanout observation on V2 | **Reduced** |
| Queue inconsistency | Same | **Reduced** |

**Governance verdict for this pass:** **SAFE TO STABILIZE** — no feature expansion; closes a real multi-path mutation gap.

---

## Drift detection — P1 optimistic markers only (2026-05-08)

| Drift signal | Detected? | Disposition |
|--------------|-------------|-------------|
| Duplicated authority / enqueue | **No** | Additive fanout + audit metadata only; authority sync and `enqueue_compliance_recalc_with_fanout` unchanged |
| Hidden fallback behaviour | **No** | Markers are observability-only |
| `NOTIFICATION_DISPATCH` globally activated | **No** | Inventory JSON policy flag remains **false** |
| Replay ambiguity from this change | **Low** | Same ordering: optimistic `$set` → authority sync → enqueue; markers document the window |

---

## Drift detection — P2 replay / enqueue observability (2026-05-08)

| Drift signal | Detected? | Disposition |
|--------------|-------------|-------------|
| Duplicated `enqueue_compliance_recalc` implementation | **No** | Single queue function; fanout helper only wraps + attaches observations |
| New hidden fallback on enqueue failure | **No** | Exception path already logged; fanout row records `ENQUEUE_FAILED` + `error_type` |
| Overclaiming client semantics | **No** | Replay/idempotency fields are **ops/audit-only** on transition traces — not added to public client DTOs |

---

## Mandatory critical-path classification (LAUNCH_CRITICAL vs PILOT_TOLERABLE)

| ID | Launch criticality | Rationale | Blast radius | Mitigation status |
|----|--------------------|-----------|--------------|-------------------|
| **L-001** | **LAUNCH_CRITICAL** | Misread persisted headline vs drivers undermines compliance trust | Wrong prioritization; “score wrong” disputes | **REDUCED** — portfolio/property pending honesty; optional per-detail banner **DEFERRED** |
| **L-002** | **LAUNCH_CRITICAL** | Evidence authority is the legal defensibility spine for requirement truth | Client sees non-authoritative Mongo shape | **REDUCED** — projection + filter enforced; **2026-05-08** CI contract ``services/kpi_authority_projection_contract.py`` + ``routes/properties.py`` counts use ``project_requirement_row_client_runtime``; **ACCEPTED** residual = extend registry when new KPI modules ship |
| **L-003** | **LAUNCH_CRITICAL** | Single score writer protects audit integrity | Divergent scores across surfaces | **READY** — `recalculate_and_persist` + queue worker |
| **L-004** | **LAUNCH_CRITICAL** | Optimistic requirement promotion before consensus creates a narrow contradictory state window | Support “status flipped”; rare race narratives | **REDUCED** — V2 verify aligned to v1 fanout/enqueue; **2026-05-08** fanout + `DOCUMENT_VERIFIED` audit carry `pre_authority_optimistic_requirement_promotion`; removal **DEFERRED_FOR_POST_LAUNCH** (product/authority-only promotion) |
| **L-005** | **PILOT_TOLERABLE** | Half-enabled API is survivable under flag + structured errors | Confused integrators, not silent data corruption | **READY** — parent **`READY_FOR_WIDER_LAUNCH`** (see [closure inventory](#l-005--parent-terminal-state-inventory--freeze-2026-05-08)): **`_v2_guard()`** on all `evidence_review` routes (**CI**); **`GET /admin/dashboard`** `server_feature_flags.evidence_review_v2_enabled` + pending-verification **AI review** gated in admin SPA; **L-005e**; **freeze** active |
| **L-006** | **LAUNCH_CRITICAL** | Queue duplicates / lost jobs harm recovery and trust | Stuck pending; double recalc load | **REDUCED** — idempotency + correlation **READY**; fanout downstream rows now carry replay/idempotency metadata from `enqueue_compliance_recalc_with_fanout`; stuck `RUNNING` reclaim **DEFERRED** |
| **L-007** | **PILOT_TOLERABLE** | Timeline gaps are support/UX pain more than silent authority conflict | “Empty history” tickets | **PARTIAL** — warn-only emission; uniform audit **OPEN** |
| **L-008** | **LAUNCH_CRITICAL** | Wrong-tenant or ungoverned sends are compliance and consent incidents | Regulatory + trust catastrophe | **READY** — parent **`READY_FOR_WIDER_LAUNCH`** (see [L-008 closure inventory](#l-008--parent-terminal-state-inventory--freeze-2026-05-08)): orchestrator primary + bypass test + **`NOTIFICATION_GOVERNANCE_INVENTORY.json`**; **L-008d** `COMPLIANCE_ALERT` fingerprint; **L-008e** CI — production literal `template_key` on `notification_orchestrator.send` + **`EMAIL_EVENTS`** + landlord onboarding IDs ⊆ canonical seed; **freeze** active |
| **L-009** | **LAUNCH_CRITICAL** | Backbone activation gates operational recovery semantics | Blocked transitions without explanation | **READY** — parent domain **`READY_FOR_WIDER_LAUNCH`** (see [closure inventory](#l-009--parent-terminal-state-inventory--freeze-2026-05-08)): all in-scope HTTP mutations that run backbone-gated authority sync / recalc enqueue (or document-touch sync) return optional governed `propagation_notice`; explicit exclusions documented; **freeze** active |
| **L-010** | **PILOT_TOLERABLE** | Plan limits affect commercial scale more than core compliance truth | Wrong entitlements during pilot if misconfigured | **READY** — parent **`READY_FOR_WIDER_LAUNCH`** (see [closure inventory](#l-010--parent-terminal-state-inventory--freeze-2026-05-08)): **`FEATURE_MATRIX`** / metadata / grace / minimum-plan / production **`enforce_feature`**/**`require_feature`** literals / notification **`plan_required_feature_key`** CI; **`test_downgrade_support.py`**; **freeze** active |
| **L-011** | **LAUNCH_CRITICAL** | Admin repair must stay on canonical paths | Manual override without audit trail | **READY** — fanout + bounded enqueue after standalone sync |

---

## Audit item register

Each row: category, subcategory, original audit classification (A/B/C), current status, files/services, risks, impact, mitigation, gaps, evidence/tests, governance notes.

### L-001 Stream B — persisted headline vs live stats

| Field | Value |
|-------|-------|
| **Category** | User trust / scoring |
| **Subcategory** | Headline vs KPI divergence |
| **Original audit classification** | B |
| **Current status** | PARTIAL |
| **Files / services** | `services/compliance_score.py`, `services/scoring_semantics_v1.py`, `frontend` score surfaces |
| **Operational risks** | Users confuse stored score with live drivers |
| **Legal risks** | Overstatement if UI implies instant score change |
| **User trust risks** | Medium |
| **Launch impact** | High if unaddressed |
| **Current mitigation** | `portfolio_pending_score_recalc_*` on compliance-score payload; UI notes (`scoreFreshnessUi.js`, Command Centre, Work queue, Compliance score page) |
| **Remaining gaps** | Per-property pending banner on every requirement detail (optional) |
| **Evidence / tests** | `test_portfolio_pending_score_recalc_snapshot.py`, frontend `scoreFreshnessUi.test.js` |
| **Governance notes** | Aligns with `COMPLIANCE_CLIENT_STATUS_AUTHORITY.md` surface matrix |

### L-002 Evidence authority — single writer / projection

| Field | Value |
|-------|-------|
| **Category** | Product hardening |
| **Subcategory** | Requirement evidence authority |
| **Original audit classification** | A |
| **Current status** | PARTIAL |
| **Files / services** | `services/requirement_evidence_authority.py`, `services/requirement_client_runtime_surface.py`, **`services/kpi_authority_projection_contract.py`**, `routes/properties.py` (list / deadlines / property requirements KPI-adjacent paths) |
| **Operational risks** | Stale KPI if sync skipped |
| **Legal risks** | Mis-reported compliance if client sees raw Mongo |
| **User trust risks** | High if projection bypassed |
| **Launch impact** | Critical |
| **Current mitigation** | Runtime filter + `project_requirement_row_client_runtime` on client surfaces; **CI guard** `assert_kpi_authority_projection_contracts()` registers KPI-authoritative modules per `COMPLIANCE_CLIENT_STATUS_AUTHORITY.md` |
| **Remaining gaps** | Registry must be updated when new KPI routes/services are added; not every client module is in the registry (bounded to matrix-aligned set) |
| **Evidence / tests** | `tests/test_kpi_authority_projection_contract.py`, authority alignment tests, fanout phase tests |
| **Governance notes** | No duplicate client status authorities |

### L-003 Compliance score persistence

| Field | Value |
|-------|-------|
| **Category** | Product hardening |
| **Subcategory** | Score write path |
| **Original audit classification** | A |
| **Current status** | READY |
| **Files / services** | `services/compliance_scoring_service.py` (`recalculate_and_persist`), `job_runner.py` |
| **Operational risks** | Low when queue healthy |
| **Legal risks** | Low — single writer documented |
| **User trust risks** | Low |
| **Launch impact** | Critical |
| **Current mitigation** | Admin validate/repair uses `recalculate_and_persist` only |
| **Remaining gaps** | None identified in last authority reconciliation pass |
| **Evidence / tests** | `tests/test_batch1_score_authority.py`, admin validate tests |
| **Governance notes** | See `docs/audit/AUTHORITY_WRITE_PATH_RECONCILIATION.md` |

### L-004 Document verify — requirement transition consistency

| Field | Value |
|-------|-------|
| **Category** | Product hardening |
| **Subcategory** | Verification / evidence acceptance |
| **Original audit classification** | A |
| **Launch criticality** | **LAUNCH_CRITICAL** (narrow contradictory state window until authority sync completes) |
| **Current status** | PARTIAL |
| **Files / services** | `routes/documents.py` (`verify_document`), `services/evidence_review_verify.py`, `routes/evidence_review.py` (`verify_external`), `services/requirement_transition_observability.py`, `services/authority_mutation_fanout.py` |
| **Operational risks** | Optimistic `requirements.$set` before authority (v1 + v2 promote path + external verify) can briefly diverge from authority truth |
| **Legal risks** | Low if authority always reconciles and client reads projection |
| **User trust risks** | Medium during narrow race window |
| **Blast radius** | Support/ops must explain transient requirement row vs authority; forensic replay must not treat optimistic row as final truth |
| **Launch impact** | High |
| **Current mitigation** | **2026-05-10:** V2 verify uses **same** `authority_sync_with_transition_observability` + `enqueue_compliance_recalc_with_fanout` as document path (RST gate + deduped enqueue semantics). **2026-05-08:** `merge_pre_authority_optimistic_requirement_promotion_marker` on transition fanout + `DOCUMENT_VERIFIED` audit metadata when promotion applied (support/audit only; not client-facing) |
| **Mitigation status** | **RISK REDUCED** (observability + audit breadcrumbs); **not eliminated** — removal still **DEFERRED_FOR_POST_LAUNCH** |
| **Remaining gaps** | Remove optimistic requirement write entirely = **DEFERRED_FOR_POST_LAUNCH** (larger behaviour change; needs product sign-off) |
| **Evidence / tests** | `tests/test_evidence_review_v2_phase1.py`, `tests/test_evidence_match_operations_http.py`, `tests/test_requirement_transition_observability_phase3.py`, document fanout tests |
| **Governance notes** | No silent fallback; gate-blocked paths skip enqueue by design (matches v1). See `docs/audit/AUTHORITY_WRITE_PATH_RECONCILIATION.md` |

### L-005 Evidence Review V2 API surface

| Field | Value |
|-------|-------|
| **Category** | Product hardening |
| **Subcategory** | Feature flag / half-enabled |
| **Original audit classification** | A |
| **Current status** | **READY** (program vocabulary: parent **`READY_FOR_WIDER_LAUNCH`** — see [closure inventory](#l-005--parent-terminal-state-inventory--freeze-2026-05-08); **not** composite wider launch) |
| **Files / services** | **`routes/evidence_review.py`**, **`services/evidence_review_config.py`**, **`routes/admin.py`** (`GET /dashboard` → `server_feature_flags`), **`routes/client.py`** (`server_feature_flags`), **`routes/documents.py`** (verify v1/v2 branch), **`frontend/src/pages/AdminDashboard.js`**, `frontend/src/utils/evidenceReviewUi.js` |
| **Operational risks** | Operators or integrators invoking review surfaces when flag off |
| **Legal risks** | Low — API returns structured error |
| **User trust risks** | Medium if UI shows misleading review state |
| **Launch impact** | Medium |
| **Current mitigation** | **`_v2_guard()`** on every review router handler; client + **admin** dashboard **`evidence_review_v2_enabled`**; client tier coherence (`evidenceReviewUi.js`); **`EVIDENCE_REVIEW_V2_CONFIG_MATRIX.md`**; **L-005e** AST contract + dashboard flag test |
| **Remaining gaps** | **None for in-scope L-005.** **Explicit exclusions:** `POST /admin/documents/backfill-evidence-review-v2` (migration / support batch; no `_v2_guard` by design); marketing copy / non-admin surfaces outside this parent. |
| **Evidence / tests** | **`tests/test_l005_evidence_review_v2_guard_contract.py`**, `test_evidence_review_v2_phase1.py`, `evidenceReviewUi.test.js`, **`AdminDashboard.pendingVerification.test.js`** |
| **Governance notes** | `docs/audit/EVIDENCE_REVIEW_V2_CONFIG_MATRIX.md` — update when adding `@router` handlers under `evidence_review` |

### L-006 Recalculation queue — idempotency

| Field | Value |
|-------|-------|
| **Category** | Product hardening |
| **Subcategory** | Async queue |
| **Original audit classification** | A |
| **Current status** | READY |
| **Files / services** | `services/compliance_recalc_queue.py`, `services/compliance_recalc_correlation.py`, `services/authority_mutation_fanout.py`, `services/requirement_transition_observability.py`, `job_runner.py` |
| **Operational risks** | Duplicate jobs suppressed; visibility counters best-effort; worker crash between persist and DONE leaves `RUNNING` until ops intervene |
| **Legal risks** | Low |
| **User trust risks** | Low if `compliance_score_pending` shown |
| **Launch impact** | High |
| **Current mitigation** | `(property_id, correlation_id)` uniqueness; activation gate; **2026-05-08** `enqueue_compliance_recalc_with_fanout` attaches replay/idempotency fields on downstream rows (`idempotency_boundary`, `enqueue_property_id`, `resolved_queue_correlation_id`, `replay_duplicate_enqueue_safe`) |
| **Remaining gaps** | Automated reclaim of stale `RUNNING` rows; full chaos playbook |
| **Evidence / tests** | `test_compliance_recalc_queue_stabilization_phase1.py`, `test_requirement_transition_fanout_phase4.py` |
| **Governance notes** | Fanout path records duplicate suppression + **support ladder** in `docs/audit/AUTHORITY_WRITE_PATH_RECONCILIATION.md` |

### L-007 Timeline / score events

| Field | Value |
|-------|-------|
| **Category** | Observability |
| **Subcategory** | Score history |
| **Original audit classification** | B |
| **Current status** | PARTIAL |
| **Files / services** | `services/score_events_service.py`, `job_runner.py` (post-recalc `SCORE_RECALCULATED`), `routes/documents.py` (upload events) |
| **Operational risks** | Trend gaps if events fail warn-only |
| **Legal risks** | Low |
| **User trust risks** | Medium if timeline empty but score exists |
| **Launch impact** | Medium |
| **Current mitigation** | Client trend endpoint documents fallback |
| **Remaining gaps** | Uniform emission audit across all transition types |
| **Evidence / tests** | Property/requirement HTTP tests patch `write_score_event` |
| **Governance notes** | Not every transition emits score_events (by design today) |

### L-008 Notification ownership

| Field | Value |
|-------|-------|
| **Category** | Commercial / operations |
| **Subcategory** | Dispatch governance |
| **Original audit classification** | C |
| **Current status** | **READY** (program vocabulary: parent **`READY_FOR_WIDER_LAUNCH`** — see [closure inventory](#l-008--parent-terminal-state-inventory--freeze-2026-05-08); **not** the composite “wider launch” verdict) |
| **Files / services** | `services/notification_orchestrator.py`, `services/jobs.py`, `services/notification_send_idempotency.py`, **`notification_template_seed_definitions.py`**, **`notification_orchestrator_send_template_key_audit.py`**, `services/email_event_registry.py`, `services/email_service.py` (deprecated / quarantined) |
| **Operational risks** | Mis-routed reminders |
| **Legal risks** | Consent / tenant isolation |
| **User trust risks** | High if spam or wrong tenant |
| **Launch impact** | High |
| **Current mitigation** | Orchestrator primary path; `test_notification_bypass_governance.py`; **`NOTIFICATION_GOVERNANCE_INVENTORY.json`**; reminder + alert idempotency (**L-008d**); **L-008e** — audited literal `template_key` sends + **`EMAIL_EVENTS`** + onboarding sequence ⊆ seed (**CI**). |
| **Remaining gaps** | **None for in-scope L-008 closure.** **Explicit exclusions:** `NOTIFICATION_DISPATCH` not globally activated (product policy); shrinking live **`EmailService`** callers remains gradual quarantine; dynamic `template_key` variables must remain bounded by **`EMAIL_EVENTS`** / caller contracts. |
| **Evidence / tests** | `test_notification_bypass_governance.py`, `test_reminder_governance_phase2.py`, **`tests/test_notification_reminder_idempotency.py`**, **`tests/test_notification_compliance_alert_idempotency.py`**, **`tests/test_notification_template_seed_definitions.py`**, **`tests/test_l008_orchestrator_template_seed_contract.py`** |
| **Governance notes** | `docs/audit/NOTIFICATION_OWNERSHIP_READINESS.md` + `docs/audit/NOTIFICATION_GOVERNANCE_INVENTORY.json` |

### L-009 Workflow activation registry

| Field | Value |
|-------|-------|
| **Category** | Product hardening |
| **Subcategory** | RST core backbone / recalc gates |
| **Original audit classification** | A |
| **Current status** | **READY** (program vocabulary: parent **`READY_FOR_WIDER_LAUNCH`** — backend/API `propagation_notice` governance complete per [inventory](#l-009--parent-terminal-state-inventory--freeze-2026-05-08); **not** the composite “wider launch” verdict) |
| **Files / services** | `services/workflow_runtime_activation_registry.py`, `services/authority_mutation_fanout.py`, **`services/client_propagation_notice.py`**, **`routes/documents.py`** (inventory in closure section), **`services/evidence_review_verify.py`**, **`routes/evidence_review.py`**, **`routes/admin.py`** (document routes in inventory) |
| **Operational risks** | Blocked transitions without UX explanation |
| **Legal risks** | Low |
| **User trust risks** | Medium |
| **Launch impact** | High |
| **Current mitigation** | Gate merged into fanout; observability rows; **optional** `propagation_notice` `{code, message}` from **`build_propagation_notice_from_transition_fanout`** / **`merge_propagation_notice_from_ordered_transition_fanouts`** only (stable codes; no raw `activation_reason`); bulk/zip **per-row + merged top-level** notice order = **`results`** iteration order (see `_finalize_bulk_zip_results_propagation_notices` docstring). |
| **Remaining gaps** | **None for in-scope L-009 HTTP inventory.** Residual: **FE** does not read `propagation_notice` (**explicit exclusion**, B-plane); composite gates 1–10 still govern overall launch. |
| **Evidence / tests** | `test_workflow_rst_core_backbone_activation_phase2a.py`, **`tests/test_client_propagation_notice.py`**, **`tests/test_evidence_match_operations_http.py`**, **`tests/test_evidence_review_lifecycle_propagation_notice.py`**, **`tests/test_apply_extraction_propagation_notice.py`**, **`tests/test_client_upload_propagation_notice.py`**, **`tests/test_l009_closure_propagation_notice.py`** |

### L-010 Plan limits / downgrade behaviour

| Field | Value |
|-------|-------|
| **Category** | Commercial |
| **Subcategory** | Entitlements |
| **Original audit classification** | C |
| **Current status** | **READY** (program vocabulary: parent **`READY_FOR_WIDER_LAUNCH`** — see [closure inventory](#l-010--parent-terminal-state-inventory--freeze-2026-05-08); **not** composite wider launch) |
| **Files / services** | **`services/plan_registry.py`**, **`plan_feature_governance_audit.py`**, `middleware/feature_gating.py`, `routes/properties.py`, `routes/documents.py`, `routes/client.py`, `routes/reports.py`, `routes/calendar.py`, `routes/webhooks_config.py`, `services/jobs.py`, `services/branding_resolver_service.py`, `notification_template_seed_definitions.py` |
| **Operational risks** | Misconfigured entitlements at pilot scale |
| **Legal risks** | Incorrect access |
| **User trust risks** | Medium |
| **Launch impact** | Medium |
| **Current mitigation** | **`FEATURE_MATRIX`** single source; **`enforce_feature`** / **`require_feature`**; **L-010e** CI drift guard on feature literals + matrix/metadata/grace/minimum-plan alignment + notification `plan_required_feature_key`; downgrade HTTP tests |
| **Remaining gaps** | **None for in-scope L-010.** **Explicit exclusions:** Stripe price env misconfiguration remains **ops/config** class (see `PriceConfigMissingError`); full billing UX matrix outside this parent. |
| **Evidence / tests** | **`tests/test_downgrade_support.py`**, **`tests/test_l010_plan_feature_governance_contract.py`**, `tests/test_subscription_state_gating_integration.py` (where applicable) |
| **Governance notes** | Distinguish env failure vs product regression; update **`plan_feature_governance_audit.py`** when adding gated routes |

### L-011 Admin evidence match resolution

| Field | Value |
|-------|-------|
| **Category** | Product hardening |
| **Subcategory** | Admin repair |
| **Original audit classification** | A |
| **Current status** | READY |
| **Files / services** | `routes/admin.py` (`admin_resolve_evidence_match`) |
| **Operational risks** | Low |
| **Legal risks** | Override must be audited |
| **User trust risks** | Medium |
| **Launch impact** | Medium |
| **Current mitigation** | `authority_sync_with_transition_observability` + `_enqueue_recalc_after_standalone_authority_sync` |
| **Remaining gaps** | None in last pass |
| **Evidence / tests** | `test_evidence_match_operations_http.py` |
| **Governance notes** | Tests patch fanout module binding |

---

## Explicit recommendations (pick one)

- **SHOULD CONTINUE** — Stabilization on transition fanout, notification matrix, optimistic-write elimination (with sign-off), client “why pending” copy, and **stuck queue row** reclaim design if pilot volume warrants it.
- **SAFE TO STABILIZE** — Yes, for the types of changes in L-004 / test fixes / tracker maintenance.
- **STOP FEATURE WORK** — **Yes for net-new product features** until composite moves toward READY and gate checklist tightens.
- **READY FOR CONTROLLED BETA** — **PARTIAL** only with written acceptance of PARTIAL rows and ops monitoring on queue + score pending.
- **READY FOR PAID PILOT** — **Same as beta** until remaining commercial dimensions (e.g. full billing narrative) move to READY; **L-008** / **L-010** parent domains are **`READY_FOR_WIDER_LAUNCH`** within their scopes.
- **READY FOR WIDER LAUNCH** — **NO** (gate checklist not satisfied).

---

## Finishable unit contract (mandatory for stabilization slices)

Do **not** treat a tracker row as one undifferentiated **PARTIAL** if it can be **split** into smaller units that can each reach a verifiable state. Prefer **named sub-units** (e.g. `L-008a`, or a bullet under the parent row) over a vague “still PARTIAL”.

### Before implementation (planning gate — no code until this is written in the tracker or PR)

Define the **smallest finishable unit** for this pass only. For that unit, specify:

| Element | Requirement |
|---------|-------------|
| **Exact READY criteria** | Observable, testable statements (e.g. “CI asserts X”, “API field Y present when Z”, “no new writer paths”) — not vibes. |
| **Files in scope** | Explicit list; anything else is out of scope. |
| **Tests required** | Named test module(s) or “extend existing test X”; must run in CI where applicable. |
| **Explicitly out of scope** | Adjacent features, global activation, UX redesign, “while we’re here” refactors. |
| **Parent tracker remainder** | One line: what stays **PARTIAL** at the **parent** `L-00x` row after this unit ships, and why that remainder is a **different** unit. |

### After implementation (closure gate)

Mark the **unit** **READY** only if **all** are true:

1. **Wiring** — every file in scope is changed or verified as required; no orphan helpers.  
2. **Tests** — required tests exist and **pass**; no known flake introduced.  
3. **Docs** — tracker and any authority/audit doc touched by the unit are updated (or explicitly “N/A” with reason).  
4. **Authority drift** — no duplicate writers, no hidden enqueue paths, no client-facing overclaim vs `COMPLIANCE_CLIENT_STATUS_AUTHORITY.md` / reconciliation docs.  
5. **No hidden manual-only assumptions** — if ops must do something (e.g. reclaim stuck rows), it is **documented** in an audit/runbook path, not implied.

If the **parent** `L-00x` row remains **PARTIAL**, add **exactly one sentence** explaining why, then list the **next finishable unit** (same table as above) so the parent is visibly a **backlog of READY units**, not an opaque gap.

---

## Deferred / accepted (summary)

| Item | Disposition | Rationale |
|------|-------------|-----------|
| Full template↔notification trigger inventory | DEFERRED_FOR_POST_LAUNCH | Tooling effort; not blocking honest beta if sends are orchestrator-gated |
| Remove optimistic requirement verify writes | DEFERRED_FOR_POST_LAUNCH | Behaviour change; needs coordinated authority-only promotion design |
| Mongo-less CI for all HTTP suites | ACCEPTED_LAUNCH_RISK for local dev | Use CI with Mongo or skip markers where agreed |

---

## Stabilization pass (2026-05-08) — risk movement

| Category | Notes |
|----------|--------|
| **Risks eliminated** | None in this slice — optimistic verify promotion **retained** by design; elimination needs authority-only promotion product decision |
| **Risks reduced** | **L-002** — CI registry + `routes/properties.py` projection; **L-004** — optimistic promotion visibility; **L-006** — fanout replay/idempotency + support ladder; **L-008** — inventory + **daily reminder batch-scoped idempotency**; **L-009** — verify / external-verify `propagation_notice` when backbone defers work |
| **Risks accepted** | Narrow pre-authority optimistic window on verify / external verify / V2 promote until deferred removal lands |
| **Risks deferred** | Per-template idempotency proof; scripted template↔trigger closure; automated `RUNNING`→`PENDING` reclaim; P4 **client-visible** “why” copy (non-debug) |

---

## Stabilization slice (2026-05-10) — L-009b (`admin_resolve_evidence_match`)

| Category | Notes |
|----------|--------|
| **Risks reduced** | **L-009** — optional `propagation_notice` on **`POST /api/admin/documents/{document_id}/resolve-evidence-match`** for approve / reject / relink (**relink:** prior fanout then new fanout; **authority deferred** beats **recalc deferred**); parent **L-009** remains **PARTIAL** for other mutation surfaces. |
| **Drift** | Additive response field only; no new writers, enqueue paths unchanged, `NOTIFICATION_DISPATCH` untouched. |

| File | Change |
|------|--------|
| `services/client_propagation_notice.py` | `merge_propagation_notice_from_ordered_transition_fanouts` |
| `routes/admin.py` | `propagation_notice` on `admin_resolve_evidence_match` success payloads |
| `tests/test_client_propagation_notice.py` | Merge ordering / precedence tests |
| `tests/test_evidence_match_operations_http.py` | Admin resolve propagation_notice tests |

---

## Stabilization slice (2026-05-10) — L-009c (Evidence Review V2 lifecycle)

| Category | Notes |
|----------|--------|
| **Risks reduced** | **L-009** — optional `propagation_notice` on **`POST .../review/start`**, **`.../review/request-information`**, **`.../review/reject`**, **`.../review/mark-expired`**, **`.../review/supersede`** (`routes/evidence_review.py`); reject / mark-expired / supersede compute notice **after** `_sync_prop_recalc` so recalc-enqueue backbone skip is included; parent **L-009** remains **PARTIAL**. |
| **Drift** | Additive JSON only; no new writers; enqueue path unchanged. |

| File | Change |
|------|--------|
| `routes/evidence_review.py` | `propagation_notice` on five lifecycle handlers |
| `tests/test_evidence_review_lifecycle_propagation_notice.py` | Start + reject coverage |
| `docs/launch/LAUNCH_AUTHORITY_TRACKER.md` | L-009c closure |

---

## Stabilization slice (2026-05-10) — L-009d (`apply_ai_extraction` / `apply-extraction`)

| Category | Notes |
|----------|--------|
| **Risks reduced** | **L-009** — optional `propagation_notice` on **`POST /api/documents/{document_id}/apply-extraction`** after authority sync + recalc enqueue fanout (`routes.documents.apply_ai_extraction`); parent **L-009** remains **PARTIAL**. |
| **Drift** | Additive response field only; same stable codes as verify; no new writers. |

| File | Change |
|------|--------|
| `routes/documents.py` | `propagation_notice` on successful `apply_ai_extraction` payload |
| `tests/test_apply_extraction_propagation_notice.py` | Direct-handler test with backbone-deferred fanout |
| `docs/launch/LAUNCH_AUTHORITY_TRACKER.md` | L-009d closure |

---

## Stabilization slice (2026-05-08) — L-009e (client `POST /api/documents/upload`)

| Category | Notes |
|----------|--------|
| **Risks reduced** | **L-009** — optional `propagation_notice` on **`POST /api/documents/upload`** when `requirement_id` is present (`routes.documents.perform_client_document_upload`), after authority sync + `_document_path_enqueue_recalc` (same fanout contract as **L-009d**); parent **L-009** remains **PARTIAL** for bulk/zip and other surfaces. |
| **Drift** | Additive response field only; same stable codes as verify; no new writers. |

| File | Change |
|------|--------|
| `routes/documents.py` | `propagation_notice` on successful `perform_client_document_upload` payload when fanout present |
| `tests/test_client_upload_propagation_notice.py` | Handler test with backbone-deferred authority on upload fanout |
| `docs/launch/LAUNCH_AUTHORITY_TRACKER.md` | L-009e closure |

---

## L-009 — parent terminal state, inventory, and freeze (2026-05-08)

**Parent terminal state (L-009 only):** **`READY_FOR_WIDER_LAUNCH`** — every **in-scope** HTTP mutation that participates in backbone-gated authority sync, document-touch sync, or `enqueue_compliance_recalc_with_fanout` (via `_document_path_enqueue_recalc` or admin `_enqueue_recalc_after_standalone_authority_sync`) exposes optional governed **`propagation_notice`** when deferral is observable on the transition fanout, **or** the surface is **explicitly excluded** below. **No unnamed gaps.**

**Composite program:** still **not** “READY FOR WIDER LAUNCH” (mandatory gate checklist above); this section closes **only** the L-009 domain.

### Finishable units L-009f–j (closure pass)

| Unit | READY criteria | Out of scope | Tests | Freeze impact |
|------|----------------|--------------|-------|----------------|
| **L-009f** | `POST /api/documents/bulk-upload` and `POST /api/documents/zip-upload`: each **`results[]`** row with an authority fanout may include `propagation_notice`; response may include **merged** top-level `propagation_notice` with merge order = **`results`** order and precedence = `merge_propagation_notice_from_ordered_transition_fanouts`. | Changing AI match / plan gating. | `tests/test_l009_closure_propagation_notice.py` | Frozen: helper `_finalize_bulk_zip_results_propagation_notices` only changed for regression / audit. |
| **L-009g** | `DELETE /api/documents/{document_id}` (client): optional `propagation_notice` from `delete_fanout` after enqueue. | WO reconcile internals. | (covered by contract tests; add HTTP test if Mongo-less harness later) | Frozen. |
| **L-009h** | `POST /api/documents/reject/{document_id}` (admin): optional `propagation_notice` from `reject_fanout`. | — | same | Frozen. |
| **L-009i** | `POST /api/documents/admin/upload`, `POST .../admin/extraction-queue/confirm`, `POST .../admin/extraction-queue/reject`, `DELETE /api/documents/admin/{document_id}`: optional `propagation_notice` from respective fanouts after sync (and existing enqueue where present). | Adding enqueue where product never had it. | same + existing admin suites | Frozen. |
| **L-009j** | Every `authority_sync_with_transition_observability` in **`routes/admin.py`** classified: **COVERED** (notice on success JSON) or **EXCLUDED** (documented). | Non-document admin domains. | inventory row + unit tests for f | Frozen inventory table. |

### L-009 inventory — HTTP surfaces (`propagation_notice` = **COVERED** unless marked **EXCLUDED**)

| Location | Route / handler | Notice source | Notes |
|----------|-----------------|---------------|--------|
| `routes/documents.py` | `perform_client_document_upload` / `POST /upload` | `client_upload_fanout` | **COVERED** (L-009e) |
| `routes/documents.py` | `bulk_upload_documents` | per-row + merged via `_finalize_bulk_zip_results_propagation_notices` | **COVERED** (L-009f) |
| `routes/documents.py` | `upload_zip_archive` | same | **COVERED** (L-009f) |
| `routes/documents.py` | `verify_document` v1 | `verify_v1_fanout` | **COVERED** |
| `routes/documents.py` | `apply_ai_extraction` | `apply_ai_fanout` | **COVERED** (L-009d) |
| `routes/documents.py` | `reject_document` | `reject_fanout` | **COVERED** (L-009h) |
| `routes/documents.py` | `delete_document` | `delete_fanout` | **COVERED** (L-009g) |
| `routes/documents.py` | `admin_upload_document` | `admin_upload_fanout` | **COVERED** (L-009i) |
| `routes/documents.py` | `admin_confirm_extraction` | `extraction_fanout_for_notice` | **COVERED** (authority only; no enqueue on this path today) |
| `routes/documents.py` | `admin_reject_extraction` | `reject_touch_fanout` | **COVERED** |
| `routes/documents.py` | `admin_delete_document` | `admin_delete_fanout` | **COVERED** |
| `routes/documents.py` | `reject_ai_extraction` (`POST .../reject-extraction`) | — | **EXCLUDED** — success path does not run backbone-gated authority sync + fanout (status/audit only). |
| `services/evidence_review_verify.py` | V2 verify | transition fanout | **COVERED** |
| `routes/evidence_review.py` | V2 lifecycle + external verify | per-handler fanouts | **COVERED** (L-009c) |
| `routes/admin.py` | `POST .../resolve-evidence-match` | per-action fanouts / merge relink | **COVERED** (L-009b) |
| `routes/admin.py` | `POST .../resolve-scope` | `scope_fanout` when requirement linked | **COVERED** |
| `routes/admin.py` | `POST .../link-requirement` | `link_fanout` | **COVERED** |
| `routes/admin.py` | `POST .../unlink-requirement` | `unlink_fanout` | **COVERED** |
| `routes/admin.py` | `POST .../reject-unresolved` | `rej_fanout` | **COVERED** |
| `routes/admin.py` | `POST .../backfill-evidence-match` | — | **EXCLUDED** — batch support/repair tool; operators use audit + `preview` / counts; not a per-transition client honesty contract. |
| Internal jobs | `_run_analysis_after_upload` → `sync_for_documents_touching` | — | **EXCLUDED** — no synchronous HTTP response; observability remains in logs/fanout if wired elsewhere. |
| Frontend | — | — | **EXCLUDED** from L-009 — no UI consumption of `propagation_notice` in-repo; API remains contract for integrators and admin clients. |

### Freeze criteria (L-009)

* **No** edits to `services/client_propagation_notice.py`, `_finalize_bulk_zip_results_propagation_notices`, or route notice wiring **except** regression fix, audit failure, production incident, or **new** governed route added under a **named** follow-up unit with tracker update.  
* **No** opportunistic FE work under L-009; open under **B / UX** program when picked.  
* **Reopen** inventory row only with explicit rationale row.

### Operational / support narrative

Support and operators trace backbone deferral via existing transition fanout / audit correlation IDs (`AUTHORITY_WRITE_PATH_RECONCILIATION.md`, queue observability). Client-visible honesty for deferral on **in-scope** routes is **`propagation_notice.code`** + stable **`message`** only.

---

## Stabilization slice (2026-05-08) — L-010e (plan feature literals ↔ `FEATURE_MATRIX` CI)

| Category | Notes |
|----------|-------|
| **Risks reduced** | **L-010** — deploy-time drift between **`FEATURE_MATRIX`**, **`FEATURE_METADATA`**, grace / recovery / minimum-plan maps, production **`enforce_feature`** / **`require_feature`** string literals, and notification **`plan_required_feature_key`** seeds. |
| **Drift** | Additive `plan_feature_governance_audit.py` + contract tests; no entitlement behaviour change beyond existing gates. |

| File | Change |
|------|--------|
| `services/plan_registry.py` | `all_feature_matrix_keys()` |
| `plan_feature_governance_audit.py` | `PRODUCTION_ENFORCE_FEATURE_KEY_LITERALS`, `PRODUCTION_REQUIRE_FEATURE_KEY_LITERALS` |
| `tests/test_l010_plan_feature_governance_contract.py` | Matrix / metadata / lists / literals / seed keys alignment |
| `docs/launch/LAUNCH_AUTHORITY_TRACKER.md` | L-010 parent closure |

---

## L-010 — parent terminal state, inventory, and freeze (2026-05-08)

**Parent terminal state (L-010 only):** **`READY_FOR_WIDER_LAUNCH`** — in-scope plan / entitlement governance comprises: (1) **`FEATURE_MATRIX`** as the canonical per-plan boolean map (all plans share an identical key set, verified in CI); (2) **`FEATURE_METADATA`** keys aligned to that set; (3) **`FEATURES_BLOCKED_DURING_GRACE_PERIOD`**, **`LIMITED_RECOVERY_FEATURES`**, and **`MINIMUM_PLAN_FOR_FEATURE`** keys ⊆ matrix keys; (4) **L-010e** — audited production **`enforce_feature`** / **`require_feature`** string literals ⊆ matrix keys (**CI**); (5) non-null **`plan_required_feature_key`** on core + admin client communication notification seed definitions ⊆ matrix keys; (6) downgrade / limit HTTP behaviour covered by **`tests/test_downgrade_support.py`**.

**Composite program:** still **not** “READY FOR WIDER LAUNCH” (other gates / parents); this section closes **only** the L-010 domain.

### Explicit exclusions (not un-named; frozen as policy)

| Item | Rationale |
|------|-----------|
| **Stripe price / catalog env wiring** | **`PriceConfigMissingError`** and related config remain **ops / deployment** class; not asserted as product-complete under L-010. |
| **Full commercial billing UX matrix** | Invoices, dunning, self-serve upgrade flows — separate commercial program when picked. |
| **New plan SKUs or matrix shape changes** | Require explicit product + tracker row; then update **`FEATURE_MATRIX`** (all plans), **`FEATURE_METADATA`**, grace / recovery / minimum-plan maps, **`plan_feature_governance_audit.py`**, and **`tests/test_l010_plan_feature_governance_contract.py`**. |

### Freeze criteria (L-010)

* **No** new production **`enforce_feature(..., "feature_key")`** or **`require_feature("feature_key")`** without **both** matrix + metadata updates (all affected plans) and **`plan_feature_governance_audit.py`** literal set + CI green.  
* **No** new non-null **`plan_required_feature_key`** on governed notification seeds without matrix membership + contract test update.  
* **Reopen** parent only for regression, audit failure, production incident, or **named** follow-up unit.

### Operational / support narrative

Operators distinguish **403 / plan** responses from infra failures via stable error codes and logs; mis-entitlement incidents trace through subscription state + `FEATURE_MATRIX` truth. Drift between code literals and the matrix is **CI-blocked** before deploy (**L-010e**).

---

## Stabilization slice (2026-05-08) — L-005e (Evidence Review V2 guard + admin dashboard flag)

| Category | Notes |
|----------|-------|
| **Risks reduced** | **L-005** — new `routes/evidence_review.py` HTTP handler without **`_v2_guard()`**; admin UI surfacing **AI review** when **`FEATURE_EVIDENCE_REVIEW_V2`** is off (HTTP would 400 but UX looked “live”). |
| **Drift** | AST contract test + admin **`GET /dashboard`** payload extension + SPA gate; no change to review transition semantics when flag is on. |

| File | Change |
|------|--------|
| `routes/admin.py` | `server_feature_flags.evidence_review_v2_enabled` on dashboard JSON |
| `frontend/src/pages/AdminDashboard.js` | Gate **AI review** + disabled hint from flag |
| `tests/test_l005_evidence_review_v2_guard_contract.py` | Router handler ↔ `_v2_guard()` + dashboard flag |
| `frontend/src/pages/AdminDashboard.pendingVerification.test.js` | Flag on/off expectations |
| `docs/audit/EVIDENCE_REVIEW_V2_CONFIG_MATRIX.md` | Admin dashboard row + tests |
| `docs/launch/LAUNCH_AUTHORITY_TRACKER.md` | L-005 parent closure |

---

## L-005 — parent terminal state, inventory, and freeze (2026-05-08)

**Parent terminal state (L-005 only):** **`READY_FOR_WIDER_LAUNCH`** — in-scope Evidence Review V2 half-enablement governance comprises: (1) **`_v2_guard()`** as the first executable statement (after docstring) on **every** `routes/evidence_review.py` **`@router`** handler — **CI** via **`tests/test_l005_evidence_review_v2_guard_contract.py`**; (2) **`FEATURE_EVIDENCE_REVIEW_V2`** read through **`is_feature_evidence_review_v2()`** only; (3) **Admin** pending-verification **AI review** entry points gated on **`GET /admin/dashboard`** → **`server_feature_flags.evidence_review_v2_enabled`** (same boolean semantics as client **`server_feature_flags`**); (4) client label coherence remains **`evidenceReviewUi.js`** + existing tests.

**Composite program:** still **not** “READY FOR WIDER LAUNCH”; this section closes **only** the L-005 domain.

### Explicit exclusions (not un-named; frozen as policy)

| Item | Rationale |
|------|-----------|
| **`POST /admin/documents/backfill-evidence-review-v2`** | Support / migration batch tool; **not** a per-document review mutation API; intentionally **no** `_v2_guard` (may run while flag is off). |
| **Marketing copy and non-admin V2 “tier” narrative** | Wider program / copy-review workstreams — not API/UI flag coherence. |
| **New review HTTP routes** | Require **`_v2_guard()`** first + **`test_l005_evidence_review_v2_guard_contract.py`** green + matrix row if behaviour is user-visible. |

### Freeze criteria (L-005)

* **No** new **`@router`** handler in **`routes/evidence_review.py`** without leading **`_v2_guard()`** + CI green.  
* **No** new admin-only calls to **`/documents/{id}/review/...`** from the SPA without the same **`server_feature_flags.evidence_review_v2_enabled === true`** gate pattern (or documented exception).  
* **Reopen** parent only for regression, audit failure, production incident, or **named** follow-up unit.

### Operational / support narrative

Integrators receive **`EVIDENCE_REVIEW_V2_DISABLED`** when calling gated review endpoints with the flag off. Operators use **`GET /admin/dashboard`** (or env inspection) to see whether **AI review** tooling should appear; Verify / resolve match / reject paths remain as documented in **`EVIDENCE_REVIEW_V2_CONFIG_MATRIX.md`**.

---

## Stabilization slice (2026-05-10) — L-008d (`COMPLIANCE_ALERT` idempotency)

| Category | Notes |
|----------|--------|
| **Risks reduced** | **L-008** — false `duplicate_ignored` / missed alerts when many properties caused **32-character truncation** of sorted `property_id` join to collide across **different** degradation batches same client/day; **backward-compatible** when join length ≤32. **Parent L-008** later reached **`READY_FOR_WIDER_LAUNCH`** with **L-008e** template literal + registry CI (see closure section). |
| **Drift** | **One-time key change** for alerts where sorted join length >32 (first post-deploy send may not dedupe against pre-deploy `message_logs` for that calendar edge); orchestrator + `client_id` unchanged; **no** `NOTIFICATION_DISPATCH` global activation. |

| File | Change |
|------|--------|
| `services/notification_send_idempotency.py` | `compliance_alert_property_scope_fingerprint` |
| `services/jobs.py` | `COMPLIANCE_ALERT` idempotency key uses fingerprint |
| `tests/test_notification_compliance_alert_idempotency.py` | Fingerprint behaviour tests |
| `docs/audit/NOTIFICATION_GOVERNANCE_INVENTORY.json` | Inventory note + `generated_at_iso` |
| `docs/audit/NOTIFICATION_OWNERSHIP_READINESS.md` | COMPLIANCE_ALERT idempotency gap update |
| `docs/launch/LAUNCH_AUTHORITY_TRACKER.md` | L-008d closure |

---

## L-008 — parent terminal state, inventory, and freeze (2026-05-08)

**Parent terminal state (L-008 only):** **`READY_FOR_WIDER_LAUNCH`** — in-scope notification governance comprises: (1) **`NotificationOrchestrator.send`** as canonical tenant-scoped path; (2) bypass governance test forbidding parallel production send patterns; (3) **high-volume idempotency** for daily reminders + **`COMPLIANCE_ALERT`** (**L-008d**); (4) **template drift guard** (**L-008e**) — audited production **string literal** `template_key=` arguments on `notification_orchestrator.send` ⊆ `notification_template_seed_definitions`, plus **`EMAIL_EVENTS`** and **`LANDLORD_ONBOARDING_EVENT_IDS`** ⊆ seed (**CI**).

**Composite program:** still **not** “READY FOR WIDER LAUNCH” (other gates / parents).

### Explicit exclusions (not un-named; frozen as policy)

| Item | Rationale |
|------|-----------|
| **`NOTIFICATION_DISPATCH` globally activated** | Intentional **off** until workflow activation evidence satisfies program; recorded in `NOTIFICATION_GOVERNANCE_INVENTORY.json` `policy`. |
| **Deprecated `EmailService` live sends** | Quarantined; static bypass test blocks **new** orchestrator bypass; shrink legacy callers under separate hygiene units. |
| **Per-route narrative in JSON for every admin broadcast** | Cluster inventory remains **visibility** layer; literal `template_key` drift is **CI-closed** under **L-008e**. |
| **Consent / marketing lane separation** | Lead/marketing clusters documented as **PILOT_TOLERABLE** / non-compliance inbox — not conflated with L-008 closure. |

### Freeze criteria (L-008)

* **No** new production `notification_orchestrator.send(..., template_key="NEW", ...)` without **both** seed row and **`PRODUCTION_ORCHESTRATOR_SEND_TEMPLATE_KEY_LITERALS`** update + CI green.  
* **No** new `EMAIL_EVENTS` `template_key` without seed row.  
* **Reopen** parent only for regression, audit failure, production incident, or **named** follow-up unit (e.g. further `EmailService` removal).

### Operational / support narrative

Operators trace sends via **`message_logs`** + orchestrator metadata; mis-tenant incidents escalate via existing security runbooks. Idempotency collisions for large property sets are mitigated by **L-008d** fingerprints; unknown templates are **CI-blocked** before deploy.

---

## Stabilization slice (2026-05-08) — L-008e (orchestrator `template_key` ↔ seed CI)

| Category | Notes |
|----------|--------|
| **Risks reduced** | **L-008** — silent deploy of orchestrator `template_key` not present in Mongo seed / Postmark alias wiring; drift between `email_event_registry` lifecycle map and DB templates. |
| **Drift** | Additive audit module + tests only; no send-path behaviour change. |

| File | Change |
|------|--------|
| `notification_template_seed_definitions.py` | `all_notification_template_keys_from_seed()` |
| `notification_orchestrator_send_template_key_audit.py` | `PRODUCTION_ORCHESTRATOR_SEND_TEMPLATE_KEY_LITERALS` (audited frozenset) |
| `tests/test_l008_orchestrator_template_seed_contract.py` | Literal ⊆ seed; `EMAIL_EVENTS` ⊆ seed; onboarding IDs |
| `docs/audit/NOTIFICATION_GOVERNANCE_INVENTORY.json` | `unsafe_or_unknown` resolution text + timestamp |
| `docs/audit/NOTIFICATION_OWNERSHIP_READINESS.md` | L-008e seed ↔ trigger CI note |
| `docs/launch/LAUNCH_AUTHORITY_TRACKER.md` | L-008 parent closure |

---

## File-by-file summary (2026-05-08 pass)

| File | Change |
|------|--------|
| `services/requirement_transition_observability.py` | P1: `merge_pre_authority_optimistic_requirement_promotion_marker`; P2: `replay_support_context` on `attach_downstream_trigger_observation` |
| `routes/documents.py` | Merge marker into verify v1 fanout; audit metadata on `DOCUMENT_VERIFIED` when linked requirement promoted |
| `services/evidence_review_verify.py` | Merge marker after `promote_compliance`; audit metadata parity |
| `routes/evidence_review.py` | `verify_external` fanout merge after promote |
| `tests/test_requirement_transition_observability_phase3.py` | Unit coverage for merge helper |
| `docs/audit/NOTIFICATION_GOVERNANCE_INVENTORY.json` | Machine-readable notification governance inventory (policy + sender clusters) |
| `docs/audit/NOTIFICATION_OWNERSHIP_READINESS.md` | Launch criticality / blast radius / support / recommendation + inventory link |
| `docs/audit/AUTHORITY_WRITE_PATH_RECONCILIATION.md` | Optimistic promotion note + **operator support ladder** (score/recalc tracing) |
| `services/authority_mutation_fanout.py` | `_compliance_recalc_replay_support_context` + pass into downstream observations |
| `tests/test_requirement_transition_fanout_phase4.py` | `replay_support_context` merge + unknown-key rejection |
| `docs/launch/LAUNCH_AUTHORITY_TRACKER.md` | P2/P4 updates, L-006, readiness dimension A |
| `services/kpi_authority_projection_contract.py` | L-002 module-level projection / scorer-delegate assertions |
| `tests/test_kpi_authority_projection_contract.py` | CI enforcement |
| `routes/properties.py` | `project_requirement_row_client_runtime` after filter on list, deadlines, property requirements |
| `docs/COMPLIANCE_CLIENT_STATUS_AUTHORITY.md` | Related-code pointer to KPI contract module |
| `services/client_propagation_notice.py` | L-009 client `propagation_notice` builder from transition fanout |
| `tests/test_client_propagation_notice.py` | Unit tests for notice codes |
| `services/notification_send_idempotency.py` | L-008 daily reminder scope fingerprint |
| `services/jobs.py` | Reminder email/SMS idempotency keys include scope fingerprint |
| `tests/test_notification_reminder_idempotency.py` | Fingerprint determinism tests |
| `docs/audit/NOTIFICATION_GOVERNANCE_INVENTORY.json` | jobs_reminders_digest idempotency note |
| `docs/audit/NOTIFICATION_OWNERSHIP_READINESS.md` | Reminder idempotency gap update |

---

## Document index (governance artifacts)

| Document | Purpose |
|----------|---------|
| `docs/audit/AUTHORITY_WRITE_PATH_RECONCILIATION.md` | Score + repair path reconciliation |
| `docs/audit/NOTIFICATION_OWNERSHIP_READINESS.md` | Notification senders / readiness |
| `docs/audit/NOTIFICATION_GOVERNANCE_INVENTORY.json` | Machine-readable sender-cluster governance inventory (not global dispatch activation) |
| `docs/audit/EVIDENCE_REVIEW_V2_CONFIG_MATRIX.md` | V2 flag matrix |
| `docs/COMPLIANCE_CLIENT_STATUS_AUTHORITY.md` | Client status canonical projection |
| `docs/STREAM_B_SCORING_AUTHORITY_MATRIX.md` | Stream B reference |
| `docs/REQUIREMENT_WORKFLOW_CLASS_DECISION_RECORD.md` | Workflow classes |
| `docs/WORKFLOW_BEHAVIOUR_GOVERNANCE.md` | Workflow behaviour |

---

*Maintainers: after each stabilization pass, update the audit register rows, readiness scores, gate checklist, and explicit recommendation; apply the **Finishable unit contract** so PARTIAL rows decompose into READY units where possible. Do not declare wider launch without updating this file and the ten-gate table.*
