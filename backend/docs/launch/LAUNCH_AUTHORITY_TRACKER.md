# Compliance Vault Pro — Launch Authority Tracker

**Program:** Compliance Vault Pro Launch Authority Program  
**Role:** Single source of truth for launch blockers, stabilization, deferred/accepted risks, and governance status.  
**Baseline:** PRE-LAUNCH GOVERNANCE AUDIT (Directions A — Product Hardening, B — User Trust UX, C — Commercial Readiness). *If the audit lives outside this repository, link the canonical export here when available.*

**Allowed status values only:** `READY` | `PARTIAL` | `BLOCKED` | `DEFERRED_FOR_POST_LAUNCH` | `ACCEPTED_LAUNCH_RISK`

**Last tracker update:** 2026-05-17 (F1 **DONE**; **G1** **IN_PROGRESS** — Tranche **T1** harness only; surveillance execution pending)

**TIER_0 routing:** [GOVERNANCE_INDEX.md](../GOVERNANCE_INDEX.md) — canonical navigation spine; this tracker remains launch gate status only (no duplicate recovery authority).

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
| 3 | No misleading compliance wording remains | **PARTIAL** — improved; `PRESENTATION_LANGUAGE_GOVERNANCE.md` semantic families + `presentationLanguage.js` / vault formatters; ongoing copy review against authority docs |
| 4 | Notification ownership is governed | **PARTIAL** — **L-008** inventory closed for in-scope template governance + high-volume idempotency (**L-008d/e**); **`NOTIFICATION_DISPATCH`** global activation remains intentionally off; deprecated `EmailService` quarantine unchanged |
| 5 | Recovery/reconciliation paths exist | **PARTIAL** — recalc queue, admin validate/repair, SLA monitors; not fully exercised under chaos |
| 6 | Core async flows are observable | **PARTIAL** — fanout / transition observability + **queue replay/idempotency fields** on authority-mutation enqueue; not all clients consume full trace |
| 7 | Operational support flows are viable | **PARTIAL** — support correlation ladder documented (`AUTHORITY_WRITE_PATH_RECONCILIATION.md`); **RUNBOOK §12–§13** rehearsal checklist + analytics gaps for pilot observation; stuck `RUNNING` reclaim still manual |
| 8 | Evidence semantics are consistent | **PARTIAL** — **L-009** inventory closed (bulk/zip, deletes/rejects, admin document mutations); **standard client** read-only `propagation_notice` on **Documents** + **Bulk upload** when API returns it (B-plane, 2026-05-12); other FE surfaces unchanged; **L-005** parent **`READY_FOR_WIDER_LAUNCH`** for in-scope V2 API + admin UI flag coherence (**L-005e**); wider copy / tier marketing review remains program work |
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
| **Governance notes** | `backend/docs/audit/NOTIFICATION_OWNERSHIP_READINESS.md` (operational deep links + drift guardrails) + `backend/docs/audit/NOTIFICATION_GOVERNANCE_INVENTORY.json` |

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
| **Remaining gaps** | **None for in-scope L-009 HTTP inventory.** Residual: **standard client** surfaces `propagation_notice` **read-only** on **Documents** + **Bulk upload** when API returns it (`frontend/src/utils/propagationNoticePresentation.js`, `PropagationNoticeCallout.jsx`); other routes unchanged — extend only under named B-plane follow-up + tracker row. |
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
- **PILOT GOVERNANCE** — **`docs/launch/PILOT_LAUNCH_GOVERNANCE.md`** — residual-risk acceptance + pilot positioning; **public pricing / marketing feature lists** must match **`services/plan_registry.py`** `FEATURE_MATRIX` (no entitlement drift).
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
| Frontend | — | — | **PARTIAL (B-plane)** — Standard client **read-only** display of optional `propagation_notice` on **Documents** (`/documents` upload + apply-extraction) and **Bulk upload** (`/documents/bulk-upload`, `/documents/zip-upload`) when API returns it; does not alter authority or enqueue semantics; broader FE inventory still open. |

### Freeze criteria (L-009)

* **No** edits to `services/client_propagation_notice.py`, `_finalize_bulk_zip_results_propagation_notices`, or route notice wiring **except** regression fix, audit failure, production incident, or **new** governed route added under a **named** follow-up unit with tracker update.  
* **B-plane (client read-only):** Additional surfaces may display returned `propagation_notice` **only** as informational copy (no new writes, no authority shortcuts); each expansion updates this inventory row + `PILOT_LAUNCH_GOVERNANCE.md` / `PRESENTATION_LANGUAGE_GOVERNANCE.md` cross-refs as applicable.  
* **Reopen** inventory row only with explicit rationale row.

### Operational / support narrative

Support and operators trace backbone deferral via existing transition fanout / audit correlation IDs (`AUTHORITY_WRITE_PATH_RECONCILIATION.md`, queue observability). Client-visible honesty for deferral on **in-scope** routes is **`propagation_notice.code`** + stable **`message`** on the API; where the standard client surfaces it (Documents, Bulk upload), the UI shows the **server `message`** verbatim (read-only).

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

## UI / brand consistency governance (frontend)

**Status:** PARTIAL — governed token layer and CTA semantics tightened; full-page drift burn-down is continuous.

| Rule | Requirement |
|------|--------------|
| No hardcoded marketing hex drift | Prefer `src/config/branding.js`, `src/design-tokens.js`, Tailwind `midnight-blue` / `electric-teal` / `brand-*`, or CSS variables in `src/index.css`. **Never** use truncated midnight (`#0B1D3`); canonical is **`#0B1D3A`**. |
| No parallel styling systems | Do not introduce alternate theme objects per feature module. New surfaces use shadcn primitives + governed tokens. |
| Canonical components | Buttons, cards, alerts, and tables should use `@/components/ui/*` patterns; avoid one-off button colour stacks unless documented in `docs/governance/DESIGN_SYSTEM_GOVERNANCE.md`. |
| CTA hierarchy | **Primary actions:** Electric Teal (`Button` default variant). **Framework / nav:** Midnight Blue. Do not invert without design review. |
| Async honesty | UI must not imply instant legal finality, guaranteed verification, or completed authority reconciliation. Visual “success” states follow existing backend payloads only (L-004, scoring pending, `propagation_notice` policy unchanged). |
| No page-level drift | New pages use `--background` canvas (`#F8FAFC`), card white, borders `#E5E7EB`, and semantic status colours per Brand v1.0. |

**Reference:** `docs/governance/DESIGN_SYSTEM_GOVERNANCE.md` (repo root `docs/`, not under `backend/docs/`).

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
| `docs/governance/DESIGN_SYSTEM_GOVERNANCE.md` (repo) | Pleerity Brand v1.0 — UI tokens, forbidden patterns, async-honesty visual rules |

---

## Recovery appendix — obligation & workflow (A→G)

**Purpose:** Lightweight **status + links** for the governed recovery sequence. **Do not** duplicate behavioural authority here — use [GOVERNANCE_INDEX.md § Recovery map](../GOVERNANCE_INDEX.md#recovery-governance-map-obligation--workflow).

**Proof methodology:** `RUNBOOK_CONTROLLED_BETA_OPERATIONS.md` §12 (extend with Mongo/API checks below). **Admin explain (B):** `GET /api/admin/compliance/registry/runtime-requirements/explain?client_id=&property_id=` (read-only).

| Step | Area | Canonical authority | Verification | Owner | Risk | Status | Closure evidence |
|------|------|---------------------|--------------|-------|------|--------|------------------|
| **A** | Materialisation | Code: `provisioning.py` → `materialize_requirements_for_property`; doc: [PUBLISHED_REGISTRY_CLIENT_TRUTH_AUDIT.md](../PUBLISHED_REGISTRY_CLIENT_TRUTH_AUDIT.md) | `clients.onboarding_status`, `provisioning_jobs`, `requirements.count` per property, `requirement_generation_source` | Platform / provisioning | **LAUNCH_CRITICAL** | **IN_PROGRESS** (proof pass 2026-05-16) | Per-tenant: `onboarding_status=PROVISIONED` + `requirements` rows exist with `catalog_registry` source; admin `GET /provisioning/{client_id}` |
| **B** | Client runtime visibility | Code: `requirement_client_runtime_surface.py`; doc: [COMPLIANCE_CLIENT_STATUS_AUTHORITY.md](../COMPLIANCE_CLIENT_STATUS_AUTHORITY.md) | Raw vs filtered: explain endpoint + client `GET /api/properties/{id}/requirements` vs admin unfiltered read | Registry + client surfaces | **LAUNCH_CRITICAL** | **IN_PROGRESS** (proof pass 2026-05-16) | `included_count` / `raw_count` on explain; exclusion_reason populated; client API count ≤ raw |
| **C** | Scheduler / queue + downstream convergence | [runbooks/SCHEDULER_AND_COMPLIANCE_JOBS.md](../runbooks/SCHEDULER_AND_COMPLIANCE_JOBS.md); **L-006**; C2 DoD | `job_runs`, `compliance_recalc_queue`; gap/risk/priority/tasks/KPI surfaces | Platform ops | **LAUNCH_CRITICAL** | **DONE** (units **C1** + **C2** 2026-05-16) | C1 queue/recalc replay; C2 downstream convergence — see § C1/C2 closure |
| **D** | Workflow propagation fanout | `authority_mutation_fanout.py`; [STREAM_E_MUTATION_FANOUT_MATRIX.md](../STREAM_E_MUTATION_FANOUT_MATRIX.md); **L-009** | Transition fanout traces after governed mutation | Compliance platform | **LAUNCH_CRITICAL** | **NOT_STARTED** | Fanout row + enqueue or documented gate-block + `propagation_notice` |
| **E** | Evidence / document state | [COMPLIANCE_CLIENT_STATUS_AUTHORITY.md](../COMPLIANCE_CLIENT_STATUS_AUTHORITY.md); [AUTHORITY_WRITE_PATH_RECONCILIATION.md](../audit/AUTHORITY_WRITE_PATH_RECONCILIATION.md); **L-004** | Admin verify → client list parity | Evidence review | **LAUNCH_CRITICAL** | **NOT_STARTED** | Client projection matches authority after verify (no dual pending badges) |
| **F** | Notification governance | [NOTIFICATION_GOVERNANCE_INVENTORY.json](../audit/NOTIFICATION_GOVERNANCE_INVENTORY.json); **L-008** | `message_logs`; orchestrator path only | Notifications | **PILOT_TOLERABLE** until A–D pass | **NOT_STARTED** | Send proves delivery only — **not** obligation health |
| **G** | Support operations | [RUNBOOK_CONTROLLED_BETA_OPERATIONS.md](../RUNBOOK_CONTROLLED_BETA_OPERATIONS.md); [STREAM_F_FORENSICS_JOIN_RECIPE.md](../STREAM_F_FORENSICS_JOIN_RECIPE.md) | Support rehearsal §12–§13 | Support / ops | **PILOT_TOLERABLE** | **CONTINUOUS** | Rehearsal checklist signed per pilot cohort |

**Sequence rule:** Complete **A → B** proof per affected tenant before **C**; do not treat **F** as proof of obligation workflows.

**Proof audit source (2026-05-16):** Architectural A→B proof — materialisation at **provisioning** (not intake); client visibility gated by **published overlay** when active published map is non-null. Verification commands: `RUNBOOK_CONTROLLED_BETA_OPERATIONS.md` §12.7.

**Tracker rows:** Add **L-0xx** launch items here only when a step is **BLOCKED** for pilot — do not create a separate recovery tracker. **Finishable units** below (`A1`…`G2`) are the implementation plan; cross-stream mapping: `CLOSED_LOOP_COMPLIANCE_ARCHITECTURE_TRACKER.md` § Obligation recovery programme.

**Implementation gate:** No product implementation for a selected unit until **§ Recovery unit implementation contract** is satisfied (Definition of Done written; status lifecycle followed). Stabilization slices (**L-00x**) continue to use **§ Finishable unit contract** above; recovery units (**A1–G2**) use the recovery contract below (stricter end-to-end rule).

---

## Recovery unit implementation contract (mandatory)

Applies to every **A1–G2** unit selected for implementation. Supplements **§ Finishable unit contract** (does not relax it).

### Non-negotiable implementation rules

| Rule | Requirement |
|------|-------------|
| **No partial implementation** | A unit is not shippable if any required layer in its Definition of Done is missing or stubbed. |
| **No placeholder wiring** | No TODO routes, dead UI buttons, feature flags that always return success, or “backend only for now” without a tracked follow-up sub-unit. |
| **No backend-only fix** | If client UI, admin tools, runbook, tests, or governance docs are in scope for the unit, they ship in the **same** change train. |
| **No immediate DONE** | After code merge, status is **`IMPLEMENTED_PENDING_VERIFICATION`** until staging verification and governance closure complete. |
| **Split before coding** | If a unit cannot be completed end-to-end safely in one reviewable PR, **split into sub-units** (e.g. `B2a`, `B2b`) in this tracker **before** `IN_PROGRESS`, each with its own Definition of Done. |

### End-to-end layers (implement all that apply)

When a unit is selected, implement across **every applicable** layer — mark **N/A** in Definition of Done only with explicit rationale:

| Layer | Examples |
|-------|----------|
| Backend services | Authority modules, materialisation, filters, fanout |
| Routes / endpoints | Client + admin HTTP; explain/diagnostic APIs |
| Data model / migrations / indexes | Only when schema/index change is required |
| Admin tools / explain views | Provisioning panel, explain endpoint UX, ops signals |
| Client UI | Requirements lists, honesty copy, empty states |
| Scheduler / queue / fanout | When unit touches async propagation |
| Audit logs / observability | `create_audit_log`, fanout traces, admin-visible failure reasons |
| Tests | Unit + HTTP/integration; CI green |
| Runbook | `RUNBOOK_CONTROLLED_BETA_OPERATIONS.md` §12.7+ as applicable |
| Governance docs | Canonical authority docs listed on the unit row |
| Tracker closure | Status, evidence paste, next unit unlock |

### Allowed unit statuses (only these)

| Status | Meaning |
|--------|---------|
| **NOT_STARTED** | Not selected; or split sub-units not yet defined. |
| **BLOCKED** | Waiting on prior unit, A1 classification, or explicit approval. |
| **IN_PROGRESS** | Definition of Done approved; implementation active. |
| **IMPLEMENTED_PENDING_VERIFICATION** | Code/docs merged; staging verification not yet recorded. |
| **READY_FOR_STAGING_VERIFICATION** | Deployed or available on staging; verifier assigned. |
| **VERIFIED** | Staging evidence captured; governance docs updated pending final DONE. |
| **DONE** | All ten DONE gates below satisfied; closure evidence pasted. |
| **DEFERRED** | Explicitly deferred with approver + rationale; not blocking false DONE. |
| **SUPERSEDED** | Replaced by a sub-unit or renamed unit; do not implement. |

**Forbidden as terminal status:** `READY`, `PARTIAL`, `REQUIRED_BEFORE_FIX` on recovery units — use the table above.

### Status transitions (mandatory path)

```
NOT_STARTED → BLOCKED → IN_PROGRESS → IMPLEMENTED_PENDING_VERIFICATION
  → READY_FOR_STAGING_VERIFICATION → VERIFIED → DONE
```

- **Do not skip** `IMPLEMENTED_PENDING_VERIFICATION` or `VERIFIED`.
- **Do not** move to **DONE** in the same PR as the initial implementation without a separate verification pass recorded in the tracker.
- Reopen: **DONE → IN_PROGRESS** only with incident/rationale row (date, approver).

### Definition of Done (write before `IN_PROGRESS`)

Each selected unit (or sub-unit) must add a **Definition of Done** block under its row **before** coding. Template:

| Element | Content |
|---------|---------|
| **Root cause proven** | Cite A1 classification, explain output, or incident ID |
| **Layers in scope** | Checklist from end-to-end table; list **N/A** with reason |
| **Exact acceptance criteria** | Observable, testable (API counts, fields, UI strings, job states) |
| **Files / routes in scope** | Explicit list |
| **Tests required** | Named modules + commands |
| **Staging verification steps** | RUNBOOK §12.7 refs or unit-specific steps |
| **Governance docs to update** | From unit row |
| **Rollback / safety** | Idempotency, revert path, forbidden ops |
| **Out of scope** | Prevents scope creep |
| **Sub-units** | If split: IDs and dependencies |

### DONE gates (all ten required)

A unit may move to **DONE** only when **all** are true:

1. **Root cause proven** — evidence linked (A1 row, explain JSON, fanout trace, etc.).
2. **Implementation complete** — every in-scope layer from Definition of Done shipped; no partial paths.
3. **Tests pass** — required suites green in CI (or documented env skip with approver).
4. **Staging verification** — passed **or** documented evidence attached (commands, screenshots, API snippets, dates).
5. **Runbook updated** — operator can repeat verification without reading PR diff.
6. **Governance docs updated** — canonical authority docs reflect behaviour.
7. **Rollback / safety recorded** — in tracker closure block.
8. **Closure evidence pasted** — below the unit (summary + key metrics + PR link).
9. **No known partial paths** — no open “follow-up” for the same concern without a new sub-unit ID.
10. **Next gated unit unlocked** — exactly one sentence naming the next unit ID and trigger.

### Closure evidence block (paste when reaching DONE)

```markdown
#### <UNIT-ID> closure evidence (YYYY-MM-DD)
- Classification / root cause:
- PR(s):
- Staging verification (who/when/env):
- Tests:
- Governance docs touched:
- Rollback note:
- Next unit unlocked:
```

### Splitting oversized units

If implementation discovery shows the unit is too large:

1. Set parent to **DEFERRED** or keep **IN_PROGRESS** only as umbrella (not DONE).
2. Add sub-units `<ID>a`, `<ID>b`, … each with full Definition of Done and own status.
3. Parent reaches **DONE** only when **all** children are **DONE** and parent closure summarizes children.

---

## Recovery implementation plan (finishable units)

**Unit status:** Use **§ Recovery unit implementation contract** statuses only.

**Safety (all units):** No raw Mongo hand-edits to `requirements` / score / queue unless **emergency recovery** is explicitly approved in writing. Use provisioning repair, `requirements/sync`, governed reconciliation jobs, audited admin actions only.

### A1 — Tenant-level classification

| Field | Value |
|-------|-------|
| **ID** | A1 |
| **Priority** | P0 — **REQUIRED BEFORE FIX** |
| **Trigger** | Before any A2/B1 product fix |
| **Purpose** | Classify one affected `CID`/`PID` as **A-only** (obligations absent), **B-only** (hidden), **A+B** (both), or **Neither** (downstream — proceed to C only after A+B pass) |
| **Canonical authority** | [GOVERNANCE_INDEX.md](../GOVERNANCE_INDEX.md); [PUBLISHED_REGISTRY_CLIENT_TRUTH_AUDIT.md](../PUBLISHED_REGISTRY_CLIENT_TRUTH_AUDIT.md) |
| **Code areas** | Read-only: `provisioning.py`, `requirement_client_runtime_surface.py`, `explain_runtime_requirement_rows_for_property` |
| **Unit status** | **DONE** (2026-05-16) — lifecycle: IN_PROGRESS → READY_FOR_STAGING_VERIFICATION → VERIFIED → DONE |
| **Required evidence** | `onboarding_status`; `provisioning_jobs` status; `properties` count; `raw_count` (Mongo or explain); `included_count` (explain); top `exclusion_reason` values; classification label recorded in this tracker |
| **Verification** | RUNBOOK §12.7 checklist complete; classification row filled below |
| **Governance docs after** | This appendix (A1 result row); optional **L-0xx** if pilot-blocked |
| **Regression tests** | Script smoke (`--help`); optional CI job to run script in staging pipeline — **N/A** for product pytest |
| **Rollback / safety** | Read-only; no mutations |

#### A1 — Definition of Done (ops unit; approved 2026-05-16)

| Layer | In scope? |
|-------|-----------|
| Backend services | **N/A** — read-only script calls existing explain |
| Routes | **N/A** |
| Data model | **N/A** |
| Admin tools | **N/A** — uses existing explain HTTP if manual |
| Client UI | **N/A** |
| Scheduler / fanout | **N/A** |
| Audit / observability | **N/A** |
| Tests | Script import/`--help`; optional staging harness |
| Runbook | §12.7 commands + script documented |
| Governance | A1 classification row + unlock next unit |
| Tracker closure | Classification + top exclusions pasted |

**Acceptance:** Script output or manual O1–O8 → classification **A-only \| B-only \| A+B \| Neither** recorded; status → **VERIFIED** then **DONE** after row filled (no code PR).

**A1 classification record (staging — 2026-05-16):**

| CID | PID | Class | raw_count | included_count | onboarding_status | Date |
|-----|-----|-------|-----------|----------------|-------------------|------|
| `6fd5ac4c-3fd4-4112-ade7-156977deb49f` | `d35a58ae-3c81-491c-9694-1d021dd3b8ad` | **A+B** | 21 | 4 | PROVISIONED | 2026-05-16 |

**Tenant selection rationale:** Discovered via `--discover-affected` (score 97): `visibility_gap_raw_21_included_4` on Wales HMO property; exhibits admin/client mismatch (21 Mongo rows vs 4 client-runtime rows). Not INTAKE_PENDING/checkout-incomplete. Not zero-requirement PROVISIONED.

**First divergence point:** **B** — `B: partial visibility suppression (4/21 included)` — materialisation present; client filter excludes 17 rows (primary: `not_required_row` ×13).

**Failure characterization:** **Deterministic** + **migration/reconciliation-related** (bulk `NOT_REQUIRED` updates ~2026-04-14 on many rows) + **registry-publish-related** (published overlay keys present on excluded rows, e.g. `EICR|DEFAULT`, `LEGIONELLA|DEFAULT`). **Not** scheduler-first (recalc queue `DONE`; worker `success`). **Not** intermittent on this read (stable counts at query time).

**Full structured output:** [audit/a1_tenant_classification_2026-05-16_6fd5ac4c.json](../audit/a1_tenant_classification_2026-05-16_6fd5ac4c.json)

**A1 runner:** `backend/scripts/a1_obligation_tenant_classification.py` (`--discover-affected`, `--json`). RUNBOOK §12.7.

#### A1 closure evidence (2026-05-16)

- **Classification / root cause:** **A+B** label; operational root cause is **B1** (persisted `status`/`applicability` = `NOT_REQUIRED` on rows that still carry published registry matches). Provisioning **succeeded** 2026-04-03 (`PROVISIONED`, `provisioning_completed_at` set); **A2 not triggered** for this CID.
- **PR(s):** None (ops read-only). Script enhancement for full JSON capture only.
- **Staging verification:** `pleerity_staging` DB; run_at `2026-05-16T17:00:46Z`; verifier: A1 script.
- **Tests:** Script `--help`; staging classification run.
- **Governance docs touched:** This tracker (A1 record + unlock matrix).
- **Rollback note:** N/A (read-only).
- **Next units unlocked (this tenant only):**
  - **B1** — **UNLOCKED** (primary): fix proven `not_required_row` / applicability truth for active obligations.
  - **A3** — **UNLOCKED** (secondary): investigate 2026-04-14 reconciliation wave vs current planner; controlled sync if plan drift.
  - **B2** — **BLOCKED** until B1: overlay keys often present on excluded rows; open only if B1 leaves overlay gaps.
  - **A2** — **NOT UNLOCKED** (materialisation present: 21 rows, `catalog_registry` on active PENDING rows).
  - **C1** — **DONE** (2026-05-16); **C2** DoD drafting unlocked.

**Top exclusion_reason (explain):** `not_required_row` (13), `excluded_by_alias_dedupe_or_runtime_policy` (3), `not_in_planner_membership` (1).

**Included types (4) at A1 time:** `gas_safety`, `fire_alarm`, `occupation_contract`, `hmo_fire_risk_evidence` (alias winner over `hmo_fire_risk`).

**Published registry:** 23 active entries; `active_published_updated_at` 2026-04-26T15:34:25Z.

#### A1 post-B1 acceptance note (2026-05-16 — product/governance)

**Classification label remains `A+B`** (materialisation present + client-runtime count &lt; raw Mongo). **Operational interpretation after B1 + product sign-off:**

| Topic | Accepted truth |
|-------|----------------|
| **Client-visible obligations** | **8 planner-aligned families** on property `d35a58ae…`: `eicr`, `legionella`, `epc`, `gas_safety`, `hmo_license`, `fire_alarm`, `hmo_fire_risk_evidence`, `occupation_contract`. Client API count = explain `included_count` = **8**. |
| **Raw vs included** | **21 raw** Mongo rows include legacy duplicates, alias siblings, reconciled-obsolete, and out-of-jurisdiction types — **not** a target of 21/21 client visibility. |
| **`emergency_lighting` / `fire_extinguisher`** | **Intentionally non-visible** for Wales HMO pilot — no overlay publication, no planner expansion, no filter change. Materialised rows may exist; runtime correctly excludes (missing published overlay). |
| **Residual exclusions** | **Expected governance behaviour** (reconcile obsolete, alias dedupe winners, out-of-planner, jurisdiction) or **legacy/admin hygiene residue** (stale `not_applicable` on loser rows) — **not** launch-blocking product defects for this tenant. |
| **B1 outcome** | Primary persistence defect fixed (`included_count` **4→8**). Remaining gap vs raw_count is **by design**, not open B-layer work. |
| **Downstream** | **C1** may proceed (queue/workflow proof) — visibility acceptance decouples scheduler verification from closing 21/21 raw parity. |

**Post-B1 artifact:** [audit/a1_tenant_classification_post_b1_6fd5ac4c_d35a58ae.json](../audit/a1_tenant_classification_post_b1_6fd5ac4c_d35a58ae.json) · [audit/b1_verification_report_6fd5ac4c_d35a58ae.json](../audit/b1_verification_report_6fd5ac4c_d35a58ae.json)

---

### Post-A1 unlock matrix (tenant `6fd5ac4c…`)

| Unit | Status after A1 | Notes |
|------|-----------------|-------|
| **A1** | **DONE** | — |
| **A2** | **BLOCKED** | Not triggered — PROVISIONED + raw_count=21 |
| **A3** | **NOT_STARTED** (unlocked) | Applicability/NOT_REQUIRED reconciliation timing |
| **B1** | **DONE** | Closed 2026-05-16; Wales HMO 8-family visibility accepted |
| **B2** | **BLOCKED** | **Product decision** — no overlay work; emergency_lighting/fire_extinguisher intentionally non-visible |
| **B3** | **BLOCKED** | No projection drift on pilot; defer |
| **C1** | **DONE** (2026-05-16) | Administrative closure; evidence § C1 closure below |
| **C2** | **DONE** (2026-05-16) | Normalized staging `c2_pass=true`; RC-8/RC-13/RC-14 cleared — § C2 closure |
| **C2a** | **DONE** | Root cause: `regenerated_ids` + `verification_fingerprint_normalization`; no product fix |
| **D1** | **DONE** (2026-05-17) | Authoritative `d1b_harness_rerun_v3` — `d1_pass=true`; § D1 closure below |
| **D1b** | **DONE** (2026-05-17) | Harness refinement; `d1b_*` authoritative; original `d1_*` preserved |
| **E1** | **VERIFIED** (2026-05-17; **E1a**/**E1b DONE**) | Authoritative: `e1b_verification_report_*` `e1b_pass=true`; § E1 closure below — **not DONE** (review discipline) |
| **F1** | **DONE** (2026-05-17; **F1a DONE**) | Authoritative: `f1a_*`; `f1_*` preserved (**F1-RC-15** harness history); § F1 DONE closure — **F1-M1** replay proof scope complete |
| **G1** | **IN_PROGRESS** (Tranche **T1** harness only) | LGS recovery **signed off** 2026-05-17; read-only surveillance harness scaffolding; **no** staging surveillance execution yet |
| **G2** | **NOT_STARTED** | Parallel observability hardening — unchanged |
| **C3+** | **BLOCKED** | No formal unit |

---

### A2 — Provisioning / materialisation repair

| Field | Value |
|-------|-------|
| **ID** | A2 |
| **Priority** | P0 |
| **Trigger** | **Only if A1 = A-only or A+B** |
| **Scope** | Retry/complete stuck provisioning; prove `_generate_requirements` per property; prove `materialize_requirements_for_property` persists canonical rows; failures visible in admin provisioning tools; **no** raw Mongo edits |
| **Canonical authority** | `services/provisioning.py`; `services/requirement_materialization_service.py`; [PUBLISHED_REGISTRY_CLIENT_TRUTH_AUDIT.md](../PUBLISHED_REGISTRY_CLIENT_TRUTH_AUDIT.md) § Materialisation timing |
| **Code areas likely affected** | `provisioning.py`, `routes/admin_billing.py` (`force_provision_client`), provisioning job runner, admin `GET /provisioning/{client_id}` |
| **Unit status** | **BLOCKED** (A1 DONE — **not triggered** for tenant `6fd5ac4c…`; materialisation present) |
| **Verification evidence** | `requirements.count` > 0 per affected property; `requirement_generation_source` present (`catalog_registry` expected); correct `client_id`/`property_id`; `onboarding_status=PROVISIONED` / `provisioning_status` aligned; `audit_logs` / provisioning job records |
| **Governance docs after** | `PUBLISHED_REGISTRY_CLIENT_TRUTH_AUDIT.md`; this tracker A2 → **READY**; RUNBOOK §12.7 |
| **Regression tests** | Extend provisioning/materialisation integration tests if behaviour changes |
| **Rollback / safety** | Re-run provision is idempotent; document client_id before force-provision |

---

### A3 — Registry / materialisation sync after publish

| Field | Value |
|-------|-------|
| **ID** | A3 |
| **Priority** | P0 |
| **Trigger** | A1 passes materialisation presence but rows **stale** vs registry plan, or registry publish changed expected obligations |
| **Scope** | `POST /api/admin/properties/{property_id}/requirements/sync-from-registry` or client `POST /api/properties/{property_id}/requirements/sync`; confirm publish does **not** fleet-rematerialise; controlled per-property sync only |
| **Canonical authority** | `compliance_registry_publish_service.REMATERIALISATION_INFO`; [PUBLISHED_REGISTRY_CLIENT_TRUTH_AUDIT.md](../PUBLISHED_REGISTRY_CLIENT_TRUTH_AUDIT.md) § Controlled sync |
| **Code areas likely affected** | `routes/admin.py`, `routes/properties.py`, `requirement_materialization_service.py` (if sync semantics change) |
| **Unit status** | **NOT_STARTED** (unlocked for tenant `6fd5ac4c…` — applicability/NOT_REQUIRED reconciliation wave) |
| **Verification evidence** | Raw rows match `build_requirement_plan_for_property` for property; no surprise mass `NOT_REQUIRED`; sync audited (`audit_logs` / admin action) |
| **Governance docs after** | `PUBLISHED_REGISTRY_CLIENT_TRUTH_AUDIT.md`; registry publish runbook cross-ref |
| **Regression tests** | `test_properties_requirement_materialisation_http.py`; materialisation policy tests |
| **Rollback / safety** | `reconcile_obsolete=True` may mark obsolete rows — capture before/after counts |

---

### B1 — Runtime visibility repair (NOT_REQUIRED / applicability persistence)

| Field | Value |
|-------|-------|
| **ID** | B1 |
| **Priority** | P0 |
| **Trigger** | A1 **DONE** — tenant `6fd5ac4c…` / `d35a58ae…`: **A+B**; `raw_count=21`, `included_count=4`; **13** × `not_required_row` |
| **Scope** | Fix **persisted** `status` / `applicability` = `NOT_REQUIRED` on obligations that are **genuinely applicable** under current planner + Wales HMO property metadata + published registry; **do not** change client runtime filter semantics |
| **Canonical authority** | `requirement_materialization_service.py` (write/reconcile); `applicability_provenance_pipeline.py`; `requirement_client_runtime_surface.py` (read gate only); [COMPLIANCE_CLIENT_STATUS_AUTHORITY.md](../COMPLIANCE_CLIENT_STATUS_AUTHORITY.md) |
| **A1 artifact** | [audit/a1_tenant_classification_2026-05-16_6fd5ac4c.json](../audit/a1_tenant_classification_2026-05-16_6fd5ac4c.json) |
| **Unit status** | **DONE** (2026-05-16) — VERIFIED after reconcile idempotency fix + triple-sync re-run |
| **Staging artifacts** | [b1_explain_before_6fd5ac4c_d35a58ae.json](../audit/b1_explain_before_6fd5ac4c_d35a58ae.json), [b1_explain_after_6fd5ac4c_d35a58ae.json](../audit/b1_explain_after_6fd5ac4c_d35a58ae.json), [b1_replay_after_6fd5ac4c_d35a58ae.json](../audit/b1_replay_after_6fd5ac4c_d35a58ae.json), [b1_verification_report_6fd5ac4c_d35a58ae.json](../audit/b1_verification_report_6fd5ac4c_d35a58ae.json), [a1_tenant_classification_post_b1_6fd5ac4c_d35a58ae.json](../audit/a1_tenant_classification_post_b1_6fd5ac4c_d35a58ae.json) |
| **Closure** | Primary fix: `is_operator_curated_not_required` + reopen in-plan automated rows; `is_already_reconciled_obsolete` skip on repeat reconcile. Pilot: `included_count` **4→8**; `not_required_row` **13→9**; replay hash stable; `reconciled_obsolete=0` runs 2–3; audit/queue delta 0 on run 3. **Product sign-off (2026-05-16):** 8 visible families = accepted operational truth; residual exclusions expected; no further B-layer work for this tenant. |
| **B2 unlock** | **Not triggered — blocked by product** — Wales HMO pilot: `emergency_lighting` and `fire_extinguisher` **must not** be client-visible; no overlay publication |
| **C1 unlock** | **DONE** (2026-05-16) — queue/workflow proof complete; **C2** DoD drafting unlocked |
| **Watchlist** | In-plan upsert `updated_at` churn on repeat sync (11 rows) — no proven queue/audit side effect; future hardening only |
| **Rollback / safety** | Governed rematerialise/sync only; preserve user-curated `not_required_reason` rows; no filter weakening |

---

#### B1 — Definition of Done (rev 2 — 2026-05-16; approved with mandatory additions)

##### 1. Root-cause proof (required before IN_PROGRESS)

**Observed (A1):** PROVISIONED client; materialisation succeeded 2026-04-03; **21** Mongo rows; **4** client-runtime rows; **13** excluded with `exclusion_reason: not_required_row`; many rows `legacy_requirement_state: active` while `status`/`applicability` = `NOT_REQUIRED`; excluded rows often have `matched_published_key` (e.g. `EICR|DEFAULT`, `LEGIONELLA|DEFAULT`) — overlay present, filter not the first bug.

**Investigation branches (must prove or rule out per branch):**

| # | Hypothesis | Evidence to collect | Likely code / data |
|---|------------|---------------------|-------------------|
| **B1-RC-1** | **`reconcile_obsolete`** marked in-plan types obsolete when planner snapshot differed, then planner/registry caught up without rematerialise reopen | `registry_metadata.reconciled_obsolete`, `reconciled_at` on excluded rows; `applicability_resolution_audit` `event_type=MATERIALIZATION_RECONCILE_OBSOLETE_APPLICABILITY`; compare `planned_types` today vs row types | `requirement_materialization_service.py` L287–338 |
| **B1-RC-2** | **2026-04-14 bulk wave** — migration, registry publish, batch sync, or fleet script | Cluster `updated_at` ~2026-04-14T22:28–22:30Z on 10+ rows; `audit_logs` / admin actions that day; git history of scripts run on staging | `scripts/published_registry_client_truth_migration.py`, `scripts/sync_registry_properties_batch.py`, `scripts/backfill_applicability_provenance.py`, `scripts/run_policy_backfill.py` |
| **B1-RC-3** | **Materialise reopen path not applied** — rows `NOT_REQUIRED` **without** `not_required_reason` should reset to `UNKNOWN`/`PENDING` on sync (L211–214) but were not rematerialised since April | Run **dry** trace: `build_requirement_plan_for_property` includes `eicr`, `legionella`, etc.; confirm sync not run post-publish; check `not_required_reason` absent on wrongly suppressed rows | `materialize_requirements_for_property` L205–226 |
| **B1-RC-4** | **Applicability pipeline** — `resolve_policy_facts` / `pipeline_applicability_state` incorrectly `NOT_REQUIRED` for Wales HMO | `applicability_state`, `pipeline_applicability_state`, provenance fields on sample rows | `policy_field_normalizer.py`, `applicability_effective_resolver.py`, `applicability_provenance_pipeline.py` |
| **B1-RC-5** | **Operator override** — `MARK_NOT_APPLICABLE` / catalog with `not_required_reason` | `not_required_reason` preset present; `applicability_resolution_audit` operator events | `requirement_mark_not_applicable_catalog.py`, `applicability_operator_actions.py` |
| **B1-RC-6** | **Property metadata change** — jurisdiction Wales / `is_hmo` toggles changed planner membership | `property.updated_at` 2026-05-05 vs row timestamps; planner diff before/after | `routes/properties.py` PATCH materialise path |
| **B1-RC-7** | **Legacy migration** — `legacy_requirement_state: active` + `hidden_deprecated` mixed with `NOT_REQUIRED` | Per-row `legacy_requirement_state`, `client_surface_visible` | `scripts/published_registry_client_truth_migration.py`, ghost audit scripts |
| **B1-RC-8** | **Registry planner mismatch** — type not in `planned_types` but published overlay exists | Explain `not_in_planner_membership` (1 row) + per-type planner membership | `compliance_requirement_registry.build_requirement_plan_for_property` |

**Root-cause proof deliverable:** One-page conclusion in tracker B1 closure naming **primary** branch (expected: **B1-RC-1** and/or **B1-RC-3** with **B1-RC-2** contributing to April wave) with Mongo/audit excerpts for tenant PID.

##### 1b. Reconciliation reversibility and idempotency (mandatory)

B1 must **prove in code and staging** (not assume) that materialisation / reconcile / sync behaviour is:

| Property | Requirement | Verification |
|----------|-------------|--------------|
| **Reversible** | When a type **enters** `planned_types` after previously being reconciled obsolete, governed materialise **reopens** without manual Mongo | Test: remove type from plan → reconcile NOT_REQUIRED → add back to plan → sync → row applicable again |
| **Deterministic** | Same property doc + published snapshot + client doc → same post-sync row states | Two consecutive runs produce identical `status`/`applicability`/provenance hashes per `requirement_id` |
| **Convergent** | Repeated materialise/sync (≥3 runs) reaches **stable** state — no further row mutations on run 3 | Compare row checksums / `updated_at` after run 2 vs run 3 |
| **No oscillation** | Rows do not flip `NOT_REQUIRED` ↔ `PENDING`/`UNKNOWN` across replays when planner membership unchanged | Test + staging: triple sync with frozen property/registry inputs |

**Explicit replay-safety checks:**

- Log `planned_types`, `reconciled_obsolete` count, reopen count per run in materialisation return payload (extend if missing).
- Staging: `POST …/requirements/sync` ×3 on pilot PID; assert explain `included_count` and per-row `status`/`applicability` **unchanged** between run 2 and run 3.
- Regression: `test_b1_materialisation_convergence_idempotent.py` (or extend materialisation tests) — triple `materialize_requirements_for_property` mock DB.

##### 2. Affected code paths (inspect list)

| Area | Path | Role in B1 |
|------|------|------------|
| Materialisation + reconcile | `services/requirement_materialization_service.py` | Upsert plan rows; **reconcile_obsolete** → `NOT_REQUIRED`; reopen rows without `not_required_reason` |
| Runtime visibility (read-only) | `services/requirement_client_runtime_surface.py` | `not_required_row` gate L402–403 — **verify unchanged** |
| Applicability writes | `services/applicability_provenance_pipeline.py` | Provenance + `maybe_audit_applicability_transition` |
| Policy facts | `services/policy_field_normalizer.py`, `resolve_policy_facts` | Pipeline applicability on materialise |
| Effective read | `services/applicability_effective_resolver.py` | Client/admin read alignment |
| Operator N/A | `services/requirement_mark_not_applicable_catalog.py`, `applicability_operator_actions.py` | Legitimate NOT_REQUIRED — must remain |
| Planner | `services/compliance_requirement_registry.py` | Wales HMO plan membership |
| Property rematerialise | `routes/properties.py` (PATCH), `provisioning.py` `_generate_requirements` | Trigger paths |
| Admin sync | `routes/admin.py` `requirements/sync-from-registry`, `routes/properties.py` `requirements/sync` | Governed repair |
| Explain | `explain_runtime_requirement_rows_for_property`, `routes/admin_compliance_registry.py` | Verification + clearer `exclusion_reason` if needed |
| Client API | `routes/properties.py` list/requirements + `project_requirement_row_client_runtime` | Parity proof |
| Migrations / ops | `scripts/published_registry_client_truth_migration.py`, `scripts/sync_registry_properties_batch.py`, `scripts/backfill_applicability_provenance.py`, `scripts/run_policy_backfill.py` | Historical cause only — no re-run without approval |
| Audit | `applicability_resolution_audit`, `audit_logs` | Prove write actor + event type |

##### 3. Safe implementation boundary

| Allowed | Forbidden |
|---------|-----------|
| Fix **materialisation / reconcile / applicability write** logic so in-plan applicable rows are not left wrongly `NOT_REQUIRED` | Raw Mongo `$set` on `requirements.status` / `applicability` |
| Governed **`POST …/requirements/sync`** on **one** affected property **after** code fix (staging proof) | **Fleet-wide** rematerialisation or batch sync across all clients |
| Re-open rows **without** `not_required_reason` that are in current `planned_types` | **Blanket-reopen** all `NOT_REQUIRED` rows |
| Preserve rows with **explicit** `not_required_reason` (user/operator curated) | Bypass **planner membership** or revive **genuinely non-applicable** obligations |
| Add audit/provenance for **automated** NOT_REQUIRED / reopen (§3b) | **Weaken** `requirement_client_runtime_surface` filter semantics |
| Idempotent converge + reversibility tests (§1b) | Hide `exclusion_reason` or degrade explain tooling |
| Before/after explain snapshots (§6b) | Scheduler/notification proof as visibility proof |
| Sub-unit split if reconcile fix ≠ reopen fix | — |

##### 3b. Mandatory automated provenance for NOT_REQUIRED (mandatory)

All **automated/system** transitions to `NOT_REQUIRED` (including `reconcile_obsolete`, pipeline applicability, automated reopen **from** NOT_REQUIRED) must persist **governed provenance** so future audits and explain tooling can answer *why* a row became `NOT_REQUIRED`.

| Field | Required on automated transition | Notes |
|-------|----------------------------------|-------|
| **reason** | Machine-readable code (e.g. `RECONCILE_OBSOLETE`, `PIPELINE_NOT_APPLICABLE`) | Distinct from user `not_required_reason` presets |
| **source subsystem** | e.g. `requirement_materialization`, `applicability_provenance_pipeline` | Service name constant |
| **reconcile / materialisation source** | `reconcile_obsolete`, `MATERIALIZATION_PIPELINE`, etc. | Align with `applicability_resolution_audit.event_type` |
| **planner / applicability context** | Snapshot: `planned_types` hash or list, `published_line_version`, `pipeline_applicability_state` | Where available at write time |
| **timestamp** | ISO UTC on row + audit row | `updated_at`, audit `created_at` |
| **classification** | `automated` vs `manual` | Manual operator paths **unchanged** — do not weaken `not_required_reason` / operator audit |

**Storage (minimum):** `applicability_resolution_audit` append + row-level provenance fields via `merge_provenance_into_requirement_patch` / `registry_metadata` as appropriate. **Explain endpoint** should surface provenance summary on excluded rows when present (B1 scope if ops-critical).

**Out of scope for B1:** Changing operator `MARK_NOT_APPLICABLE` governance or consent flows.

##### 4. Desired architectural outcome

| Principle | Outcome |
|-----------|---------|
| **Applicable obligations** | Reopen **deterministically** through governed materialisation / reconciliation paths when planner + property + registry say they belong |
| **Non-applicable obligations** | Remain `NOT_REQUIRED` with **explainable** automated or manual provenance |
| **Runtime visibility** | Remains governed by **canonical filters** (`requirement_client_runtime_surface`) — B1 fixes persistence, not filter bypass |
| **Explain tooling** | Operationally trustworthy: exclusion reason + provenance + planner membership visible for support |

**Tenant `6fd5ac4c…` targets:** `included_count` ↑ from 4; `not_required_row` ↓ only where justified; **eicr** and other in-plan Wales HMO types visible when applicable; England-only types stay excluded; no duplicate alias rows.

##### 5. End-to-end layers

| Layer | In scope for B1? | Acceptance |
|-------|------------------|------------|
| Backend authority / materialisation | **Yes** | Reconcile + reopen semantics correct |
| Applicability provenance | **Yes** | §3b mandatory fields on automated NOT_REQUIRED / reopen |
| Admin explain | **Yes** | Provenance + suppression fields on excluded rows; before/after snapshots §6b |
| Client API projection | **Verify only** | No change unless projection drops new fields |
| Audit logs | **Yes** | `MATERIALIZATION_*` / applicability audit rows |
| Runbook | **Yes** | §12.7 B1 verification steps |
| Regression tests | **Yes** | See §7 |
| Governance docs | **Yes** | See §8 |
| Frontend UI | **N/A** unless client list uses field absent from API — verify only |
| Scheduler / queue / notifications | **Out of scope** | C1 blocked until B1 DONE |

##### 6. Verification (staging — tenant `6fd5ac4c…` / `d35a58ae…`)

| Step | Command / action | Pass criteria |
|------|------------------|---------------|
| V1 | `python -m scripts.a1_obligation_tenant_classification ... --json` | `included_count` **>** 4; `not_required_row` **↓** only where justified |
| V2 | `GET /api/admin/compliance/registry/runtime-requirements/explain?...` | `eicr` (if applicable) `included: true` or valid manual `not_required_reason` + provenance |
| V3 | Client `GET /api/properties/{pid}/requirements` | Length **=** explain `included_count` |
| V4 | Wales-inappropriate types (`right_to_rent`, etc.) | Remain excluded |
| V5 | Alias families | No duplicate client-visible rows |
| V6 | No notification/queue proof | — |

##### 6b. Before/after explain snapshots (mandatory)

Capture and persist **full** explain JSON for pilot PID:

| Artifact | When | Path (governed) |
|----------|------|-----------------|
| **Before** | First action after B1 → **IN_PROGRESS** (pre-code or pre-deploy baseline) | `backend/docs/audit/b1_explain_before_6fd5ac4c_d35a58ae.json` |
| **After** | `VERIFIED` staging pass | `backend/docs/audit/b1_explain_after_6fd5ac4c_d35a58ae.json` |
| **Diff summary** | B1 closure | Tracker closure + optional `b1_explain_diff_6fd5ac4c.md` in same folder |

**Compare (per row + totals):** `raw_count`, `included_count`, `exclusion_reason`, `matched_published_key`, planner membership (`baseline_key` / in-plan), `applicability` / provenance fields, `included` flag.

**Baseline:** A1 artifact remains historical baseline; **before** snapshot must be taken at B1 implementation start (may match A1 if no drift).

##### 6c. Replay / sync verification (mandatory)

| Step | Action | Pass criteria |
|------|--------|---------------|
| R1 | `POST …/requirements/sync` (or admin sync-from-registry) **×3** on same PID without property/registry change between runs 2–3 | Run 2 ≡ run 3: same `included_count`, same per-`requirement_id` `status`/`applicability` |
| R2 | A1 script after each run (optional runs 1–3) | No oscillation: counts stable after run 2 |
| R3 | Explain after triple sync | Payload **stabilises** — byte-stable or semantically equal row decisions |
| R4 | Alias / dedupe check | No new duplicate winners; no reopen/reclose churn in audit log for frozen inputs |

**Status path after implementation:** `IN_PROGRESS` → `IMPLEMENTED_PENDING_VERIFICATION` → `READY_FOR_STAGING_VERIFICATION` → `VERIFIED` → **DONE**.

##### 7. Regression tests required

| Test module | Scenario |
|-------------|----------|
| `tests/test_requirement_materialization_policy_fields.py` (extend) | `NOT_REQUIRED` without `not_required_reason` + in `planned_types` → rematerialise reopens to non-NOT_REQUIRED |
| `tests/test_requirement_materialization_policy_fields.py` (extend) | `NOT_REQUIRED` **with** `not_required_reason` → rematerialise **preserves** |
| `tests/test_requirement_materialization_policy_fields.py` (extend) | `reconcile_obsolete` does not mark type that is in current `planned_types` |
| `tests/test_requirement_materialization_policy_fields.py` (extend) | **Triple materialise** → stable row states (idempotency / convergence) |
| `tests/test_requirement_materialization_policy_fields.py` (extend) | Planner membership change → reconcile reversible → re-sync reopens |
| `tests/test_requirement_materialization_policy_fields.py` (extend) | Automated NOT_REQUIRED writes provenance fields + audit event |
| `tests/test_requirement_client_runtime_surface.py` (extend) | Row `NOT_REQUIRED` excluded with `not_required_row`; row `PENDING` + published overlay **included** |
| `tests/test_requirement_client_runtime_surface.py` (new) | Wales HMO fixture: applicable core types pass gates when not NOT_REQUIRED |
| `tests/test_mixed_jurisdiction_portfolio_runtime.py` (extend if needed) | Wales property does not show England-only applicable types |
| `tests/test_properties_requirement_materialisation_http.py` (extend) | Sync endpoint triggers reopen semantics |
| New: `tests/test_b1_not_required_reopen_wales_hmo.py` (optional consolidate) | End-to-end materialise + filter for Wales HMO |
| Admin explain | HTTP or unit test: excluded rows expose provenance + `exclusion_reason`; snapshot fields stable |

**CI:** All above green; no flake on Mongo-less mocks.

##### 8. Governance updates (on DONE)

| Document | Update |
|----------|--------|
| `LAUNCH_AUTHORITY_TRACKER.md` | B1 closure evidence; unlock matrix; link explain before/after artifacts |
| `PUBLISHED_REGISTRY_CLIENT_TRUTH_AUDIT.md` | § NOT_REQUIRED vs reconcile_obsolete; § automated provenance; reversibility |
| `COMPLIANCE_CLIENT_STATUS_AUTHORITY.md` | Only if client-visible status strings for reopened rows need matrix row |
| `RUNBOOK_CONTROLLED_BETA_OPERATIONS.md` §12.7 | B1 substeps: explain snapshots, triple-sync convergence, provenance interpretation |
| `backend/docs/audit/b1_explain_before_*.json`, `b1_explain_after_*.json` | Persisted regression evidence (commit in B1 PR) |

##### 9. Completion rules & next-unit unlock

| Gate | Requirement |
|------|-------------|
| Start implementation | DoD **rev 2 approved** → status **IN_PROGRESS**; capture **explain before** snapshot first |
| **DONE** | §1b reversibility proved; §3b provenance shipped; §6b–6c snapshots + triple-sync; §7 tests; §8 docs |
| **Unlock on DONE** | **B2** only if A1 re-run still shows overlay-missing exclusions; **B3** if projection drift found; **C1** only after B1 **DONE** and A1 re-classification **Neither** or partial B resolved |
| **Do not unlock** | **A2** (not triggered); **F1** / notifications |

**Suspected primary fix (hypothesis — prove in RC phase):** Correct **reconcile_obsolete** scope and/or ensure **in-plan** rows without `not_required_reason` are reopened on materialise; staging may require one governed **sync** after code deploy — not a substitute for code fix.

---

### B2 — Published registry overlay coverage

| Field | Value |
|-------|-------|
| **ID** | B2 |
| **Priority** | P0 |
| **Trigger** | B1 implicates **missing published overlay** (`exclusion_reason` implicit: no overlay + not legacy_readonly) or empty published map suppressing catalog rows — **not** Wales HMO pilot types ruled non-visible by product (2026-05-16) |
| **Scope** | Align published entries with canonical types; avoid duplicate aliases; preserve planner membership; **governance decision** if empty published map should suppress — default: fix coverage, do not weaken gate without sign-off |
| **Canonical authority** | `compliance_registry_publish_service.py`; `audit/REGISTRY_WORKFLOW_DRIFT_AUDIT.md`; [PUBLISHED_REGISTRY_CLIENT_TRUTH_AUDIT.md](../PUBLISHED_REGISTRY_CLIENT_TRUTH_AUDIT.md) |
| **Code areas likely affected** | Registry publish queue, admin compliance registry routes, `scripts/repair_published_registry_coverage.py` (ops) |
| **Unit status** | **BLOCKED** — **product decision (2026-05-16):** Wales HMO pilot — `emergency_lighting` and `fire_extinguisher` **intentionally non-visible**; no overlay publication |
| **Verification evidence** | N/A for pilot tenant — B2 not in scope; re-open only if a **new** tenant requires missing-overlay repair |
| **Governance docs after** | `PUBLISHED_REGISTRY_CLIENT_TRUTH_AUDIT.md`; `NOTIFICATION_GOVERNANCE_INVENTORY.json` N/A |
| **Regression tests** | `test_registry_runtime_jurisdiction_and_publish_hardening.py`; published-mode surface tests |
| **Rollback / safety** | Publish is versioned; document published line version before change |

---

### B3 — Projection parity enforcement

| Field | Value |
|-------|-------|
| **ID** | B3 |
| **Priority** | P1 |
| **Trigger** | After B1/B2 stable for pilot tenant; or audit finds client route bypassing filter |
| **Scope** | Endpoint audit: all client/runtime paths use `filter_requirement_rows_for_client_runtime_surfaces` + `project_requirement_row_client_runtime`; document intentional admin raw bypasses; extend `kpi_authority_projection_contract` if needed |
| **Canonical authority** | `kpi_authority_projection_contract.py`; `GOVERNANCE_CONSUMPTION_MAP.md`; Stream B matrix |
| **Code areas likely affected** | `routes/properties.py`, `routes/client.py`, dashboard/command centre services, `governance_coverage_registry.py` |
| **Unit status** | **BLOCKED** (pending B1/B2) |
| **Verification evidence** | Projection map updated; grep/CI shows no new unfiltered client KPI paths |
| **Governance docs after** | `COMPLIANCE_CLIENT_STATUS_AUTHORITY.md`; `GOVERNANCE_CONSUMPTION_MAP.md` |
| **Regression tests** | `test_kpi_authority_projection_contract.py` |
| **Rollback / safety** | Additive CI guards preferred over behaviour change |

---

### C1 — Scheduler and queue proof

| Field | Value |
|-------|-------|
| **ID** | C1 |
| **Priority** | P0 (launch) |
| **Trigger** | Materialisation present; **B-layer visibility accepted** for pilot tenant (A1 post-B1 note) — queue/workflow proof may proceed without 21/21 raw parity |
| **Scope** | Prove `compliance_recalc_queue` enqueue after materialisation/mutation; worker processes queue; stuck RUNNING/PENDING handling; `job_runs`; scheduler owner per Render |
| **Canonical authority** | [runbooks/SCHEDULER_AND_COMPLIANCE_JOBS.md](../runbooks/SCHEDULER_AND_COMPLIANCE_JOBS.md); **L-006** |
| **Code areas likely affected** | `server.py`, `job_runner.py`, `compliance_recalc_queue.py`, `compliance_recalc_running_reclaim.py` (if reclaim gaps) |
| **Unit status** | **DONE** (2026-05-16) — lifecycle: IN_PROGRESS → READY_FOR_STAGING_VERIFICATION → VERIFIED → **DONE** |
| **Pilot tenant** | `6fd5ac4c-3fd4-4112-ade7-156977deb49f` / `d35a58ae-3c81-491c-9694-1d021dd3b8ad` (Wales HMO) |
| **Verification evidence** | See § C1 Definition of Done below — artifacts under `backend/docs/audit/c1_*` |
| **Governance docs after** | This tracker; `RUNBOOK_CONTROLLED_BETA_OPERATIONS.md` §12.7 C1; `SCHEDULER_AND_COMPLIANCE_JOBS.md` (if semantics change); `GOVERNANCE_INDEX.md` cross-ref |
| **Regression tests** | `test_compliance_recalc_queue_stabilization_phase1.py` + new/extended C1 convergence tests |
| **Rollback / safety** | Do not mark queue `DONE` / `DEAD` manually; do not raw-insert queue rows; document scheduler owner before tests |

---

#### C1 — Definition of Done (rev 2 — 2026-05-16; approved — **DONE** 2026-05-16)

**Purpose:** Prove **deterministic** downstream **enqueue → worker pickup → queue completion → recalc execution → downstream convergence** after **governed authoritative mutations**. C1 is **not** general workflow repair, notification dispatch, reminder systems, or scheduler redesign.

**Upstream precondition (accepted):** A1 **DONE**, B1 **DONE**, Wales HMO pilot visibility accepted (8 families). Materialisation/reconcile state trustworthy enough to test queue layer in isolation.

##### 1. Root-cause scope isolation (mandatory branches)

C1 investigations and staging failures must classify into **one primary branch** (secondary tags allowed). Do **not** collapse into a generic “workflow broken” ticket.

| Branch | ID | Symptom / detection | Primary authority |
|--------|-----|---------------------|-------------------|
| Enqueue never created | **C1-RC-1** | Mutation succeeds; no `compliance_recalc_queue` row; `compliance_score_pending` not set | `compliance_recalc_queue.enqueue_compliance_recalc`, activation gate logs |
| Enqueue suppressed (idempotent duplicate) | **C1-RC-1b** | `EnqueueComplianceRecalcResult.enqueued=false`, `duplicate_suppression_reason` set | `compliance_recalc_correlation`, unique index `(property_id, correlation_id)` |
| Worker never picks up | **C1-RC-2** | Row `PENDING` beyond SLA; no matching `job_runs` for `compliance_recalc_worker` | `job_runner.run_compliance_recalc_worker`, scheduler owner |
| Worker fails mid-run | **C1-RC-2b** | Row `FAILED` / retry; `job_runs.status=failed` | `job_runner`, worker exception logs |
| Stuck `RUNNING` | **C1-RC-4** | Row `RUNNING` with stale `heartbeat_at` / `updated_at` | `compliance_recalc_running_reclaim`, `COMPLIANCE_RECALC_RUNNING_STALE_SECONDS` |
| Reclaim misbehaviour | **C1-RC-3** | Rows flip `RUNNING`→`PENDING`/`DEAD` incorrectly; retry storms | `compliance_recalc_running_reclaim.py` |
| Recalc execution failure | **C1-RC-5** | Queue `DONE` but score not updated / `validate` mismatch | `compliance_scoring_service.recalculate_and_persist` |
| Downstream projection lag | **C1-RC-6** | Queue `DONE`, score fresh, but gaps/dashboard/priority stream stale | Stream C/E services (observe only; **C2** owns full fanout convergence) |
| Unintended notification/fanout | **C1-RC-7** | Replay creates notification jobs / fanout rows not attributable to mutation | `authority_mutation_fanout`, notification collections — **observe & bound only** |
| Semantic recalc churn on stable replay | **C1-RC-8** | R2/R3 change persisted score, freshness, projection timestamps, or score-history/audit writes without semantic compliance change | `recalculate_and_persist`, `property_compliance_score_history`, score-event audit |

##### 2. Governed mutation sources (verification only)

| Allowed (primary for pilot) | Endpoint / flow | Enqueue | Correlation id |
|----------------------------|-----------------|---------|----------------|
| **C1-M1 (recommended replay)** | Client `POST /api/properties/{property_id}/requirements/sync` | Yes — `TRIGGER_PROPERTY_UPDATED`, `ACTOR_CLIENT` | **Stable:** `REQUIREMENTS_SYNC:{property_id}` |
| **C1-M2 (admin proof)** | Admin `POST /api/admin/properties/{property_id}/requirements/sync-from-registry` | Yes — `TRIGGER_ADMIN_MANUAL_JOB`, `ACTOR_ADMIN` | **New per call:** `ADMIN_MANUAL_JOB:REGISTRY_SYNC:{property_id}:{uuid}` — use for **first enqueue** proof only, not replay-idempotency proof |
| **C1-M3 (optional)** | Admin property PATCH that materialises + enqueues (jurisdiction / `is_hmo`) | Per route | Document correlation from route |

| Forbidden as proof | Reason |
|------------------|--------|
| `python -m scripts.*` materialise-only (no enqueue) | B1 path; does not exercise C1 |
| Raw Mongo insert into `compliance_recalc_queue` | Bypasses governance |
| Synthetic fake queue rows | Not production path |
| Manual `$set` of `status: DONE` / `DEAD` | Invalid proof |
| Fleet batch enqueue scripts without approval | Out of C1 tenant scope |

**Pilot tenant:** `client_id=6fd5ac4c-3fd4-4112-ade7-156977deb49f`, `property_id=d35a58ae-3c81-491c-9694-1d021dd3b8ad`, staging `pleerity_staging`.

##### 3. Queue lifecycle verification plan

**Pre-mutation snapshot (artifact `c1_queue_before_{slug}.json`):**

- `compliance_recalc_queue.find({property_id})` — last 10 rows (all statuses)
- Counts by `status` for property + client
- Property: `compliance_score_pending`, `compliance_last_calculated_at`, `compliance_score` (if present)
- `job_runs` last 5 for `job_name=compliance_recalc_worker`
- `scheduler_heartbeat.last_heartbeat_at` (if readable)

**Mutation (single governed call):** **C1-M1** preferred — client requirements sync with pilot auth token.

**Post-mutation poll (bounded, e.g. max 10 min):**

| Step | Pass criterion |
|------|----------------|
| Enqueue | Exactly **one** new queue row for the mutation’s `(property_id, correlation_id)` OR idempotent suppression documented with `duplicate_suppression_reason` on replay |
| Pending flag | `properties.compliance_score_pending === true` after enqueue (until worker completes) |
| Worker pickup | Row transitions `PENDING` → `RUNNING` → `DONE` (or documented `FAILED`→retry→`DONE`) |
| Job evidence | ≥1 `job_runs` row for `compliance_recalc_worker` with `started_at` / `finished_at` overlapping queue row window |
| Completion | Queue row `status=DONE`; `finished_at` / `updated_at` set |
| Pending clear | `compliance_score_pending === false` after `DONE` |
| Score freshness | `compliance_last_calculated_at` advances (or equals now within skew) |

**Post-mutation snapshot (artifact `c1_queue_after_{slug}.json`):** same shape as before + enqueue result fields if captured from API response/logs.

##### 4. Replay methodology

**Goal:** Repeated **identical** governed mutations must not cause queue storms, duplicate downstream work, or stale pending markers.

| Run | Mutation | Expected enqueue | Expected queue depth delta |
|-----|----------|------------------|----------------------------|
| R1 | **C1-M1** client sync ×1 | 1 row inserted (or 1 pending cycle) | +1 pending → processed |
| R2 | **C1-M1** client sync ×1 (same correlation) | **No new row** — `duplicate_suppression_reason` OR regeneration semantics per `EnqueueComplianceRecalcResult` | 0 new `PENDING` after R1 `DONE` |
| R3 | **C1-M1** client sync ×1 | Same as R2 | 0 |

**Compare (queue layer):** queue row counts by `correlation_id`, `job_runs` count delta, property `compliance_score_pending` between R2 and R3.

**Explicit non-goals on replay:** Do not use **C1-M2** admin sync for replay-idempotency proof (new correlation per call by design).

**Queue replay safety alone is insufficient.** C1 must also prove **recalc convergence stability** (§4b).

##### 4c. Duplicate suppression vs legitimate regeneration (mandatory — rev 2 final)

C1 must **explicitly distinguish** two behaviours and prove **both** without hardening the queue into over-suppression.

| Behaviour | Definition | How to verify | Pass criterion |
|-----------|------------|---------------|----------------|
| **Duplicate enqueue suppression** | Same `(property_id, correlation_id)` while an existing queue row is active or terminal (`PENDING`/`RUNNING`/`DONE`/`DEAD`) | **C1-M1** stable replay R2/R3 with correlation `REQUIREMENTS_SYNC:{property_id}` | `EnqueueComplianceRecalcResult.enqueued=false`; `duplicate_suppression_reason` set (e.g. `duplicate_pending` when prior row `DONE`); **no** new queue row; **no** queue amplification |
| **Legitimate enqueue / recalc** | Governed mutation that **meaningfully** changes compliance inputs or uses a **new** correlation contract | **C1-M2** admin `sync-from-registry` (new `ADMIN_MANUAL_JOB:REGISTRY_SYNC:…` correlation per call) **or** documented semantic mutation (C1-M3) with **new** correlation | **New** queue row inserted **or** documented `FAILED`→retry path; worker runs; `compliance_score_pending` cycle; score/recalc outputs update when inputs changed |

**Risk-signal regen** (`regeneration_requeued` on `EnqueueComplianceRecalcResult`) is a **separate debounced path** (`risk_signal_regen_queue`) — log in artifacts but **do not** confuse with compliance-queue duplicate suppression.

**Anti-pattern (forbidden in C1 fixes):** Changes that cause stable replay to suppress **new** legitimate work after semantic mutation, or that block `FAILED` retry requeue semantics (`retry_requeued` classification).

**Artifact:** Record per-run in `c1_replay_{slug}.json`: `enqueued`, `duplicate_suppression_reason`, `regeneration_requeued`, `correlation_id`, queue row `status` before/after.

##### 4b. No-op recalculation churn verification (mandatory — rev 2)

After R1 completes and semantic compliance inputs are unchanged, **R2 and R3** must not produce persistent downstream recalculation churn.

**Capture per run (R1, R2, R3)** — snapshot after each sync + after queue drain (if any):

| Field / signal | Compare R1 → R2 → R3 |
|----------------|----------------------|
| Persisted **compliance score** values (headline + material fields used by validate) | **Stable** on R2/R3 (hash or field-wise equality) |
| **`compliance_last_calculated_at`** | Must **not** advance on R2/R3 if no semantic change (or document single R1 advance only) |
| **Score freshness metadata** (`compliance_score_pending`, pending honesty fields on property/client if present) | **Stable** false after R1; no flip-flop on R2/R3 |
| **Downstream projection timestamps** (e.g. gap `updated_at`, priority stream cursor — spot-check) | **No churn** on R2/R3 beyond documented tolerance |
| **Audit noise** (`score_events`, `property_compliance_score_history` insert count, applicability audit unrelated to mutation) | **Δ = 0** on R2/R3 vs post-R1 baseline |
| **Unnecessary recalc persistence writes** | No new score-history rows / duplicate `COMPLIANCE_SCORE_UPDATED`-class events on R2/R3 |

**Pass criterion:** Repeated governed replay with **unchanged semantic compliance state** creates **no** persistent recalculation churn. If `recalculate_and_persist` runs on R2/R3, persisted outputs must be **byte/logically identical** to post-R1 state.

**Artifact:** `c1_recalc_stability_{slug}.json` — per-run field hashes, timestamp matrix, audit deltas (R1/R2/R3 columns). May extend `c1_replay_{slug}.json` if combined.

##### 5. Stale / reclaim verification plan (minimum observability mandatory — rev 2)

**Synthetic reclaim simulation may be deferred**, but **minimum reclaim observability proof is required** for C1 **DONE**.

**5a. Configuration & assumptions (document in `c1_reclaim_observability_{slug}.json`):**

| Item | Source |
|------|--------|
| `COMPLIANCE_RECALC_RUNNING_STALE_SECONDS` | env / default (1800) |
| `COMPLIANCE_RECALC_HEARTBEAT_SECONDS` | env / default (45) |
| Worker cadence | `server.py` — 15s, `max_instances=1` |
| Scheduler owner | Render service name running APScheduler (`SCHEDULER_AND_COMPLIANCE_JOBS.md`) |
| Reclaim implementation | `compliance_recalc_running_reclaim.py` |

**5b. Operational detection path (mandatory capture):**

- `build_recalc_queue_operational_snapshot` or admin **System Health** / `GET /health-summary` → `recalc_queue_health` (stuck RUNNING, dead letter, `stale_running_reclaimed_last_24h`)
- Operator runbook pointer: where stuck `RUNNING` is detected (`RUNBOOK_CONTROLLED_BETA_OPERATIONS.md`, `SCHEDULER_AND_COMPLIANCE_JOBS.md`)
- Screenshot or JSON excerpt in artifact — not prose-only

**5c. Pilot tenant verification (mandatory):**

- During full C1 window (R1–R3): **zero hidden stale `RUNNING`** rows for `property_id=d35a58ae…` (query `compliance_recalc_queue` where `status=RUNNING` and liveness exceeded threshold)
- After each run: stuck RUNNING count for property = **0** unless actively processing

**5d. Simulation (optional):**

| Mode | Action | Pass criterion |
|------|--------|----------------|
| **Simulate (staging only, if safe)** | Test harness stale `RUNNING` injection (not raw Mongo proof path) | Reclaim → `PENDING` or `DEAD` per policy — append to `c1_reclaim_observability_{slug}.json` |

If simulation deferred: closure must still include **5a–5c** evidence; label simulation **DEFERRED**, not **WAIVED**.

##### 6. Downstream convergence proof (C1 boundary)

After queue `DONE`, within documented SLA (≤10 min worker schedule registry max delay unless incident):

| Surface | Check | C1 scope |
|---------|-------|----------|
| Property score | `compliance_score_pending=false`; `compliance_last_calculated_at` fresh | **In scope** |
| Score vs requirements | No contradiction: included obligations reflected in score inputs (spot-check via admin validate or explain) | **In scope (spot-check)** |
| Compliance gaps | Gap rows exist / update for property (no mass stale `OPEN` inconsistent with score) | **Observe** |
| Dashboard / priority stream / today tasks | Timestamps align with recalc window | **Observe only** — full proof is **C2** |
| Notifications / reminders | Count before/after replay — **no storm** on R2/R3 | **Boundary: count only** |

**Artifact:** `c1_convergence_{slug}.json` — property score fields, optional gap count, notification job count delta (if easily queried), timestamp alignment notes.

##### 7. C1 boundary (explicit — rev 2)

**C1 remains:**

| In scope | Out of scope |
|----------|--------------|
| Queue / recalc **lifecycle** verification (enqueue → worker → DONE → pending clear) | Scheduler redesign |
| Replay safety (queue + **semantic recalc** stability) | Write optimization / noop timestamp normalization |
| Minimum **reclaim observability** proof | Notification overhaul |
| Downstream convergence **spot-check** + R2/R3 stability | Workflow architecture refactor |
| Correlation-id enqueue idempotency | Materialisation `updated_at` churn fixes (B1 watchlist) |

**B1 `updated_at` churn watchlist:** Remains **non-blocking** unless C1 proof shows it **creates extra queue rows**, **triggers repeated recalcs**, or **generates downstream propagation noise**. Observing churn alone does not expand C1 scope.

##### 8. Notification and fanout boundary

| In scope | Out of scope |
|----------|--------------|
| Prove replay does **not** multiply `enqueue_compliance_recalc` rows beyond idempotency rules | Fixing reminder templates |
| Prove R2/R3 do **not** increase notification/fanout counts vs post-R1 baseline | Full workflow orchestration |
| Log if `enqueue_compliance_recalc_with_fanout` observation rows appear on sync path | Scheduler architecture redesign |

##### 9. Required artifact capture (staging)

All under `backend/docs/audit/` (commit in C1 PR):

| Artifact | Contents |
|----------|----------|
| `c1_queue_before_{slug}.json` | Pre-mutation queue + property + job_runs |
| `c1_queue_after_{slug}.json` | Post-mutation queue + property + job_runs |
| `c1_replay_{slug}.json` | R1–R3 enqueue + queue outcomes |
| `c1_recalc_stability_{slug}.json` | R1/R2/R3 score, freshness, projection timestamps, audit deltas (§4b) |
| `c1_job_runs_{slug}.json` | Worker runs overlapping proof window |
| `c1_convergence_{slug}.json` | Score pending clear + downstream spot-check |
| `c1_reclaim_observability_{slug}.json` | Thresholds, health snapshot, operator path, pilot RUNNING scan (§5); simulation optional |
| `c1_verification_report_{slug}.json` | Summary, branch IDs, pass/fail, unlock recommendation |

Optional script (implementation phase): `scripts/c1_staging_verification.py` — read-only snapshots + HTTP mutation driver (no raw Mongo writes).

##### 10. Regression test plan (implementation phase)

Extend / add tests (names indicative):

| Test area | File (existing or new) | Assertions |
|-----------|------------------------|------------|
| Enqueue idempotency | `test_compliance_recalc_queue_stabilization_phase1.py` | Same `(property_id, correlation_id)` → no duplicate insert |
| Replay safety | new `test_c1_enqueue_replay_idempotent.py` | Triple enqueue mock → ≤1 effective pending job |
| Queue completion | stabilization tests | `PENDING`→`DONE` sets pending false on property |
| Reclaim | `test_compliance_recalc_running_reclaim.py` (if exists) or extend | Stale RUNNING → `PENDING`/`DEAD` per policy |
| HTTP sync enqueue | `test_properties_requirement_materialisation_http.py` / `test_admin_property_requirements_sync_from_registry_http.py` | Sync calls `enqueue_compliance_recalc` with expected trigger/correlation |
| Convergence | new `test_c1_recalc_clears_pending_marker.py` | Worker completion clears `compliance_score_pending` |
| No duplicate on stable replay | new | Second sync with same correlation → `enqueued=false` or safe regeneration path documented |
| No-op recalc churn | new `test_c1_replay_no_semantic_recalc_churn.py` | Triple sync/recalc path → persisted score + history unchanged when inputs unchanged |
| Recalc stability | extend convergence test | `compliance_last_calculated_at` / score fields stable on suppressed replay |

**CI:** All above green; no flake on Mongo-less mocks.

##### 11. Governance updates (on C1 DONE)

| Document | Update |
|----------|--------|
| `LAUNCH_AUTHORITY_TRACKER.md` | C1 closure evidence; C2 unlock matrix; link `c1_*` artifacts |
| `RUNBOOK_CONTROLLED_BETA_OPERATIONS.md` §12.7 | C1 substeps: snapshots, C1-M1/M2, replay, reclaim note |
| `runbooks/SCHEDULER_AND_COMPLIANCE_JOBS.md` | Only if reclaim/heartbeat semantics changed in code |
| `GOVERNANCE_INDEX.md` | C1 → C2 handoff cross-ref if needed |
| `CLOSED_LOOP_COMPLIANCE_ARCHITECTURE_TRACKER.md` | Stream C1 row → DONE |

##### 12. Rollback / safety

- Do not manually set queue `status` to `DONE`/`DEAD` to “fix” staging.
- Do not delete queue rows without incident record.
- If worker stuck: use documented reclaim + scheduler owner check before re-enqueue storm.
- Record Render service name owning scheduler before starting proof.

##### 13. Completion gates

| Gate | Requirement |
|------|-------------|
| **Start `IN_PROGRESS`** | **DoD rev 2 + §4c approved**; pilot tenant + C1-M1/C1-M2 identified; before artifacts captured; §4b + §5 in plan |
| **`IMPLEMENTED_PENDING_VERIFICATION`** | Code/tests merged (if any fixes); snapshot script optional |
| **`READY_FOR_STAGING_VERIFICATION`** | All §9 artifacts captured (incl. `c1_recalc_stability_*`, `c1_reclaim_observability_*`) |
| **`VERIFIED`** | §3–§6 pass; **queue** R2=R3 stable; **semantic recalc** R2=R3 stable (§4b); reclaim observability (§5a–5c) |
| **`DONE`** | §10 tests green; §11 docs updated; closure row; **C2 unlock decision** documented |

**C1 cannot move to DONE unless all of the following are proven on staging:**

1. Stable replay → **no queue amplification** (§4).
2. Stable replay → **no semantic recalc churn** (§4b) — persisted score, freshness, projections, audit stable across R2/R3.
3. **Reclaim observability** captured (§5a–5c) — simulation optional, observability **not** optional.
4. **Downstream convergence** stable across R2/R3 replay (§6) — pending clear, no contradictory state.

**Unlock on DONE:** **C2** — **DoD drafting only** (implementation remains **BLOCKED** until C2 DoD approved). **Do not unlock** notification overhaul, B2, or B3 from C1 alone.

**Watchlist (non-blocking unless proven causal):** In-plan materialisation `updated_at` churn (B1) — C1 staging proved **11 upsert passes per sync do not** cause extra compliance-queue rows or recalc churn on suppressed replay (R2/R3).

#### C1 — Closure evidence (2026-05-16 — **DONE**)

**Pilot:** `client_id=6fd5ac4c-3fd4-4112-ade7-156977deb49f`, `property_id=d35a58ae-3c81-491c-9694-1d021dd3b8ad`, `pleerity_staging`.

**Governed mutations:** **C1-M1** (stable `REQUIREMENTS_SYNC:{property_id}`) ×3 replay; **C1-M2** (new `ADMIN_MANUAL_JOB:REGISTRY_SYNC:…` correlation per call) legitimate enqueue.

| Proof | Result |
|-------|--------|
| **R1** | `enqueued=true` → queue **DONE**; worker `compliance_recalc_worker` success; score 23→52; `compliance_score_pending` cleared |
| **R2** | `enqueued=false`, `duplicate_suppression_reason=duplicate_pending`; queue TOTAL Δ **0** |
| **R3** | Same as R2; `suppressed_duplicate_enqueue_count=2` on stable row |
| **C1-M2** | `enqueued=true` → new correlation → **DONE** (+1 queue row) |
| **Recalc stability (§4b)** | R2/R3: fingerprint stable; `score_history`/`score_events` Δ **0**; `compliance_last_calculated_at` unchanged |
| **Reclaim observability (§5)** | Thresholds documented; ops snapshot `stuck_running=0`; pilot stale RUNNING **[]** |
| **Notification boundary** | `notification_retry_pending` **0** throughout; no storm |
| **Queue before/after** | 115 → 117 TOTAL (+2 expected: R1 + M2 rows only) |

**Artifacts (committed under `backend/docs/audit/`):**

- `c1_queue_before_6fd5ac4c_d35a58ae.json`
- `c1_queue_after_6fd5ac4c_d35a58ae.json`
- `c1_replay_6fd5ac4c_d35a58ae.json`
- `c1_recalc_stability_6fd5ac4c_d35a58ae.json`
- `c1_reclaim_observability_6fd5ac4c_d35a58ae.json`
- `c1_reclaim_observability_before_6fd5ac4c_d35a58ae.json`
- `c1_verification_report_6fd5ac4c_d35a58ae.json`

**Regression (§9):** **41 passed** — `test_compliance_recalc_queue_stabilization_phase1.py`, `test_c1_enqueue_suppression_vs_regeneration.py`, `test_compliance_recalc_running_reclaim.py`, `test_properties_requirement_materialisation_http.py`, `test_admin_property_requirements_sync_from_registry_http.py`, `test_compliance_recalc_worker_job_outcomes.py`.

**PR(s):** C1 verification scripts (`c1_preflight_capture.py`, `c1_staging_verification.py`); B1 materialisation governance (prior PR). No queue semantics code change required for C1 pass.

**Governance docs:** This tracker; `RUNBOOK_CONTROLLED_BETA_OPERATIONS.md` §12.7 C1; `CLOSED_LOOP_COMPLIANCE_ARCHITECTURE_TRACKER.md` recovery row. `SCHEDULER_AND_COMPLIANCE_JOBS.md` **unchanged** (semantics unchanged).

**DONE gates (administrative closure 2026-05-16):** Ten recovery gates satisfied — staging artifacts committed; §9 regression **41 passed**; governance docs updated; no queue semantics code change required; C2 unlock = **DoD drafting only**.

**Next approved step:** Draft **C2** Definition of Done only. **Do not** start C2 implementation, notifications/fanout work, `updated_at` optimization, or scheduler redesign.

---

### C2 — Authoritative convergence verification

| Field | Value |
|-------|-------|
| **ID** | C2 |
| **Priority** | P1 |
| **Trigger** | After C1 |
| **Scope** | Prove downstream convergence: requirements → gaps → risk → priority stream → dashboard → score → today/tasks within bounded time |
| **Canonical authority** | `CLOSED_LOOP_COMPLIANCE_ARCHITECTURE_TRACKER.md` Streams B, C, E; `STREAM_E_MUTATION_FANOUT_MATRIX.md` |
| **Code areas likely affected** | `compliance_gap_sync.py`, `client_priority_stream.py`, `unified_tasks_service.py`, `compliance_scoring_service.py` |
| **Unit status** | **DONE** (2026-05-16) — lifecycle: IN_PROGRESS → READY_FOR_STAGING_VERIFICATION → VERIFIED → **DONE** |
| **Verification evidence** | See § C2 Definition of Done below — artifacts under `backend/docs/audit/c2_*` |
| **Governance docs after** | This tracker; `RUNBOOK_CONTROLLED_BETA_OPERATIONS.md` §12.7 C2; `CLOSED_LOOP_COMPLIANCE_ARCHITECTURE_TRACKER.md`; `STREAM_E_MUTATION_FANOUT_MATRIX.md` (observe-only cross-ref) |
| **Regression tests** | Gap sync, priority stream, KPI contract, unified tasks — see C2 §9 |
| **Rollback / safety** | `validate-compliance-score` diagnose before `fix=true`; no manual gap/task row edits |

---

#### C2 — Definition of Done (rev 4 — 2026-05-16; **approved** — **DONE** 2026-05-16)

**Purpose:** Prove that after **successful compliance recalc** (queue `DONE`, `compliance_score_pending=false`, score persisted via `recalculate_and_persist`), **downstream operational surfaces converge** within bounded lag in a **sane temporal order**, remain **causally attributable** to the governing mutation, respect **authoritative precedence**, **decay stale residue**, preserve **deterministic replay lineage**, remain **stable on governed replay**, and cause **no cross-entity downstream bleed**. C2 is **downstream convergence verification only** — not distributed tracing redesign, event bus redesign, lineage infrastructure rewrite, fanout repair, scheduler redesign, notification overhaul, activation policy redesign, topology rewrite, or task-system redesign.

**Upstream precondition (accepted):** A1 **DONE**, B1 **DONE**, C1 **DONE** on pilot tenant; B-layer visibility accepted (8 families Wales HMO); queue/recalc replay safety proven.

**Pilot tenant (staging verification only):** `client_id=6fd5ac4c-3fd4-4112-ade7-156977deb49f`, `property_id=d35a58ae-3c81-491c-9694-1d021dd3b8ad`, `pleerity_staging`. Product logic must remain **tenant-agnostic** (no hardcoded IDs in services/tests).

##### 1a. Authoritative precedence order (mandatory — rev 2)

When surfaces disagree during or after convergence, C2 adjudicates using this **governed precedence chain** (highest authority first):

```
requirements / applicability truth (materialised + runtime surface)
  → compliance gaps
    → risk signals
      → priority stream
        → tasks / Today
          → dashboard / KPI projections
```

| Rule | Requirement |
|------|-------------|
| **No downstream override** | Lower-order surfaces must **not** override upstream authority (e.g. KPI cannot imply an obligation state that contradicts included requirements + gaps) |
| **Bounded lag** | Lower-order surfaces may **temporarily lag** upstream within §3 SLA — not a failure |
| **Persistent contradiction** | Any contradiction **beyond documented SLA** without governed exclusion (§6b) is a **C2 failure** — classify **C2-RC-11** |
| **Replay** | Precedence must hold on R2/R3, not only immediately post-R1 |

**Artifact:** Record precedence spot-checks in `c2_verification_report_{slug}.json` (`precedence_violations[]` empty on pass).

##### 1c. Temporal convergence ordering (mandatory — rev 3)

C2 must verify that downstream convergence follows a **sane operational sequence** aligned with §1a precedence — not only that surfaces eventually match, but that they do not converge in **operationally contradictory order**.

**Expected convergence order (approximate):**

```
requirements / applicability
  → gaps
    → risk
      → priority stream
        → tasks / Today
          → dashboard / KPI
```

| Clarification | Rule |
|---------------|------|
| Timestamps | Exact strict serialization **not** required |
| Consistency model | **Bounded eventual consistency** within §3 SLA is acceptable |
| Failure | **Persistent** contradictory ordering **beyond SLA** → **C2-RC-13** |
| Replay | R2/R3 must **not** reorder downstream convergence unpredictably vs R1 post-convergence baseline |

**Invalid convergence examples (classify C2-RC-13 if persistent beyond SLA):**

| Invalid pattern | Meaning |
|-----------------|---------|
| KPI clears before gaps close | Dashboard/KPI “healthy” while gaps still open/stale |
| Tasks disappear before priority stream updates | Task surface ahead of stream authority |
| Priority stream updates before upstream deficits exist | Actions without gap/risk/requirement basis |
| Dashboard healthy while risk/gaps stale | Lower surfaces converged before upstream within SLA window expired |

**Capture per poll tick:** `convergence_order_timeline[]` in `c2_verification_report_{slug}.json` — array of `{ "t": ISO, "requirements_ready": bool, "gaps_ready": bool, "risk_ready": bool, "priority_ready": bool, "tasks_ready": bool, "kpi_ready": bool, "ordering_violation": null | string }`.

**Pass:** No entry with persistent `ordering_violation` beyond §3 bound; R2/R3 timelines **order-isomorphic** to R1 settled state (no new violations).

##### 1. Governed mutation sources (verification only)

C2 observes convergence **after** the C1-proven enqueue → worker → recalc chain. Mutations must use production HTTP/service paths (no raw Mongo writes to gaps/tasks/KPI collections).

| Allowed (primary) | Endpoint / flow | Triggers recalc (C1 path) | Downstream chain under test |
|-------------------|-----------------|---------------------------|-----------------------------|
| **C2-M1 (primary)** | Client `POST /api/properties/{property_id}/requirements/sync` | Yes — stable `REQUIREMENTS_SYNC:{property_id}` | Materialise → enqueue → worker → `recalculate_and_persist` → gap sync / risk regen / priority stream / tasks |
| **C2-M2 (semantic change)** | Admin `POST /api/admin/properties/{property_id}/requirements/sync-from-registry` | Yes — new `ADMIN_MANUAL_JOB:REGISTRY_SYNC:…` correlation | Same chain; use for **first convergence** after meaningful registry delta only |
| **C2-M3 (optional observe)** | Governed requirement transition with fanout (e.g. evidence verify path per `STREAM_E_MUTATION_FANOUT_MATRIX.md`) | Per matrix row | **Observe only** — see §1b; no fanout/activation remediation in C2 |

| Forbidden as proof | Reason |
|--------------------|--------|
| Raw Mongo `$set` on `compliance_gaps`, `risk_signals`, tasks, or score fields | Bypasses authority |
| Manual gap close/open without operator command path | Not production convergence proof |
| Fleet-wide backfill scripts without approval | Out of pilot scope |
| C2-M2 for replay-idempotency proof | New correlation per call (same rule as C1) |
| Notification send / reminder dispatch | Out of scope |

**Replay mutations for §7:** Use **C2-M1** only (stable correlation), after initial convergence window completes.

##### 1b. Fanout observation boundary (mandatory — rev 2)

Fanout observation during C2 is **strictly non-mutating**:

| Allowed during C2 | Forbidden during C2 |
|-------------------|---------------------|
| Read fanout / activation outcome rows | Mutate activation policy or registry |
| Record propagation success/failure/block reason | Change queue topology or enqueue contracts |
| Classify outcome into **C2-RC-10** (or related) | Alter fanout routing or matrix semantics |
| Defer remediation to **D1** | Broaden scope into **D1** implementation |

**Rule:** Any discovered activation/fanout corruption must be **classified** (primary branch **C2-RC-10**; secondary tags as needed), captured in artifacts, and **remediation deferred to D1** — C2 must not ship fanout fixes disguised as convergence proof.

**Artifact:** `c2_fanout_observe_{slug}.json` (optional when C2-M3 exercised) — read-only traces; `mutations_attempted: false` attestation.

##### 2. Before/after convergence snapshots (mandatory)

Capture **before** first governed mutation and **after** bounded poll window (see §3). Optional mid-window snapshots at T+2m, T+5m if lag ambiguous.

**Artifact:** `c2_convergence_before_{slug}.json`, `c2_convergence_after_{slug}.json`

**Minimum snapshot fields (per surface):**

| Surface | Authority / read path | Fields |
|---------|----------------------|--------|
| Property score | `properties` | `compliance_score`, `compliance_score_pending`, `compliance_last_calculated_at`, `risk_level`, `compliance_top_deficits`, `compliance_top_next_actions` |
| Requirements (client) | `GET /api/properties/{id}/requirements` | Count, stable keys, status summary hash |
| Requirements (explain) | Admin runtime explain | `raw_count`, `included_count`, top `exclusion_reason` |
| Gaps | `compliance_gaps` | Counts by `status` for `(client_id, property_id)`; sample open rows: `gap_key`, `requirement_id`, `updated_at` |
| Risk signals | `risk_signals` | Open count for property; sample `signal_key`, `updated_at` |
| Risk regen queue | `risk_signal_regen_queue` | `PENDING`/`RUNNING` count for property (observe debounce — not C1 duplicate-suppression proof) |
| Priority stream | `client_priority_stream` build or `GET` client tasks/priority API | Action count, top action keys, cursor/generation timestamp if exposed |
| Dashboard / KPI | Client dashboard/compliance summary endpoints + `kpi_authority_projection_contract` | Headline score, pending honesty fields, deficit counts — **authoritative** fields only |
| Today / tasks | `GET` unified tasks digest + Today-related client routes | Task count, top task ids, `remediation_key` / source_system where present |
| Admin parity | Matching admin read where exists | No contradiction vs client filtered view on included obligations |

**Pass (snapshot layer):** `c2_convergence_after` documents all surfaces captured; no missing mandatory section.

##### 2b. Stale-surface decay verification (mandatory — rev 2)

After upstream state resolves (requirement compliant, gap closed, risk cleared, recalc complete), C2 must verify **absence or governed decay** of stale downstream residue within §3 bounds.

| Stale residue class | Verification | Pass criterion |
|---------------------|--------------|----------------|
| Pending badges | Client KPI / property pending flags | Cleared when score pending false and upstream terminal |
| Orphaned priority actions | Priority stream vs gaps/requirements | No action for closed/excluded upstream keys |
| Closed gap + active task | Tasks vs `compliance_gaps.status` | No active task solely referencing closed gap |
| Resolved risk + stale KPI warning | KPI breakdown vs `risk_signals` | No warning contradicting resolved risk |
| Today/task residue | Today + unified tasks after convergence | No “attention required” for resolved upstream items |
| Stale attention markers | Dashboard/Today copy fields | Decay within SLA or governed exclusion documented |

**Replay (R2/R3):** Stale residue counts must **not increase**; decay fingerprints stable (§7b).

**Artifacts:** `c2_stale_decay_{slug}.json` — per-class before/after/R2/R3 counts; `c2_replay_{slug}.json` includes decay deltas.

##### 3. Bounded lag expectations (mandatory)

Document assumed scheduler cadence from `runbooks/SCHEDULER_AND_COMPLIANCE_JOBS.md` in `c2_verification_report_{slug}.json`.

| Stage | Expected bound (pilot default) | Pass criterion |
|-------|------------------------------|----------------|
| Queue `DONE` → score persisted | ≤ **10 min** (worker schedule + processing) | `compliance_score_pending=false`; `compliance_last_calculated_at` fresh |
| Score persisted → open gaps reflect requirements | ≤ **10 min** after recalc **or** synchronous on mutation path per matrix | No open gap contradicting included requirement terminal state (spot-check §4) |
| Score persisted → risk regen processed | ≤ **15 min** (debounced `risk_signal_regen_queue`) | Regen queue not stuck `RUNNING`; open risk count stable post-window |
| Gaps/risk → priority stream / tasks | ≤ **10 min** after upstream stable | Task/priority counts align with gap/risk spot-check |
| Dashboard/KPI | ≤ **10 min** | Client KPI reads authoritative persisted headline; no “pending” lie |

**Failure if:** Any surface remains contradictory **beyond documented bound** without classified branch (§8).

**Poll protocol:** Max wait **15 min** per run; record `poll_timeline[]` in verification report.

##### 4. Gap sync verification (mandatory)

**Authority:** `compliance_gap_sync.sync_compliance_gaps_for_requirement`, `compliance_gap_engine`, `compliance_gap_policy_aggregate`.

| Check | Method | Pass criterion |
|-------|--------|----------------|
| Gap existence | Mongo `compliance_gaps` for property | Open gaps have valid `gap_key`, `requirement_id` linkage |
| Policy alignment | Compare gap `status`/reason to included requirement terminal states | No gap **OPEN** for requirement that is compliant/NOT_REQUIRED per runtime surface |
| Quiet close | After replay (§7) | Open gap count **stable**; no close/reopen storm |
| Sync errors | Service return `errors[]` on governed path (if exposed) | Empty on happy path |
| Alias alignment | Spot-check known alias families (e.g. `hmo_fire_risk` vs `hmo_fire_risk_evidence`) | Scoring/gap alias rules per `test_scoring_gap_alias_alignment.py` |

**Artifact:** `c2_gaps_{slug}.json` — before/after counts, sample rows, spot-check matrix.

##### 5. Risk / priority stream verification (mandatory)

**Authority:** `risk_signal_regen_queue.enqueue_risk_signal_regen` (post-recalc), `risk_signal_service`, `client_priority_stream`, `compliance_requirement_engine.requirement_row_in_client_priority_stream`.

| Check | Method | Pass criterion |
|-------|--------|----------------|
| Risk regen enqueue | After recalc, observe `risk_signal_regen_queue` | ≤1 effective pending cycle per recalc window; debounced replay does not storm |
| Risk signals | `risk_signals` for property | Signals consistent with open gaps/deficits (spot-check) |
| Priority stream | Build stream or client API | Actions reference valid requirement/gap keys; no orphan actions for excluded types |
| Dedupe | Repeat read | Stable action set post-convergence |

**Artifact:** `c2_risk_priority_{slug}.json`

##### 6. Dashboard / task parity verification (mandatory)

**Authority:** `kpi_authority_projection_contract`, `unified_tasks_service`, `today_projection_service`, `command_center_service` (observe).

| Check | Method | Pass criterion |
|-------|--------|----------------|
| KPI authority | Client compliance/dashboard endpoints | Headline score = persisted `properties.compliance_score`; pending flags honest |
| Deficit parity | `compliance_top_deficits` vs gaps/tasks | Every deficit **either** appears downstream **or** has explicit governed exclusion (§6b) |
| Unified tasks | `GET` client tasks / digest routes | Count and top items align with priority stream within tolerance; no silent omissions |
| Today surface | Today page data path (API used by SPA) | No stale “all clear” when open gaps exist (spot-check) |
| Admin vs client | Explain + client requirements count | `included_count` = client API length (B1 acceptance carries forward) |

**Artifact:** `c2_dashboard_tasks_{slug}.json`

##### 6b. Governed downstream exclusion reasons (mandatory — rev 2)

**Silent disappearance is not acceptable.** Every entity present upstream but **missing** from a downstream surface must carry an **explicit governed exclusion reason** traceable to runtime explain or documented product governance.

| Allowed exclusion provenance (examples) | Must be recorded |
|----------------------------------------|------------------|
| Intentionally excluded obligation family (product decision) | `exclusion_reason` / governance note |
| Suppressed by planner policy | `not_in_planner_membership` or equivalent |
| Hidden by product governance (non-client-visible) | Runtime surface + tracker acceptance |
| Alias-family dedupe (loser row) | `excluded_by_alias_dedupe_or_runtime_policy` |
| Non-client-visible category | Explain + B-layer acceptance reference |

| Check | Pass criterion |
|-------|----------------|
| Missing gap/task/KPI for included obligation | **Fail** unless exclusion reason populated |
| Missing priority action for open gap | **Fail** unless governed deferral reason documented |
| Replay R2/R3 | Must **not** silently remove downstream representations |

**Artifact:** `c2_exclusions_{slug}.json` — matrix: entity key → surfaces present → exclusion_reason or `present`.

##### 7. Replay stability proof (mandatory)

After **initial convergence** (§3–§6 pass on **C2-M1** run **R1**), repeat **C2-M1** ×2 (**R2**, **R3**) with unchanged semantic compliance state (same rules as C1 §4b).

| Compare R1 → R2 → R3 | Pass criterion |
|----------------------|----------------|
| Open gap count / gap `updated_at` churn | **Δ = 0** spurious writes on R2/R3 |
| Risk signal open count | Stable |
| Priority stream action set hash | Stable |
| Unified task count / top ids | Stable |
| KPI headline + pending flags | Stable |
| Score history / score_events beyond C1 proof | No **additional** churn attributable to downstream sync |

**Artifact:** `c2_replay_{slug}.json` — per-run surface hashes, decay deltas (§2b), consistency fingerprints (§7b), **lineage fingerprints** (§7d), and `replay_lineage_drift[]` (§7d).

**Explicit:** Queue/recalc suppression already proven in C1 — C2 replay failures are **downstream projection** failures (branch **C2-RC-8**).

##### 7d. Causal traceability and replay lineage stability (mandatory — rev 4)

C2 must prove downstream convergence is **operationally explainable** from the originating governed mutation — not merely “correct-looking but causally opaque.” C2 does **not** add global distributed tracing; it verifies traceability within **existing** governed `correlation_id` / lineage fields.

**1. Causal traceability (all runs R1–R3 and M2 if used)**

Downstream updates must remain attributable to:

| Lineage anchor | Source |
|----------------|--------|
| **C2-M1** | Stable `REQUIREMENTS_SYNC:{property_id}` |
| **C2-M2** | `ADMIN_MANUAL_JOB:REGISTRY_SYNC:{property_id}:{uuid}` |
| Governed mutation | `TRIGGER_*`, `ACTOR_*`, fanout rows per matrix (observe only) |

**Surfaces requiring lineage spot-check:**

| Surface | Traceability expectation |
|---------|-------------------------|
| Gap updates | `compliance_gaps` rows link to `requirement_id` / `gap_key`; audit or metadata references mutation window |
| Risk regen | `risk_signal_regen_queue` correlation prefix `RECALC:` + reason chain from recalc |
| Priority stream | Actions reference requirement/gap keys present in upstream state |
| Tasks / Today | `remediation_key` / `source_system` align with stream/gap lineage where supported |
| KPI / dashboard freshness | Score history / `score_change_log` / audit carry `correlation_id` when governance supports |
| Convergence artifacts | `c2_*` JSON records mutation `correlation_id` used per run |

| Check | Pass criterion |
|-------|----------------|
| Lineage present | Where platform already stores `correlation_id` or equivalent — value matches governing mutation |
| Operational explainability | Reviewer can narrate: mutation → recalc → gap/risk/stream/task/KPI without orphan writes |
| Opaque convergence | Surfaces updated with **no** attributable lineage where expected → **C2-RC-15** |

**Artifacts:**

| Artifact | Contents |
|----------|----------|
| `c2_lineage_trace_{slug}.json` | Per-run: mutation id, queue row, recalc history ids, gap/risk/regen samples with correlation fields |
| `c2_verification_report_{slug}.json` | `downstream_lineage_summary[]` — `{ surface, entity_key, correlation_id, attributable: bool, notes }` |

**Failure branch:** **C2-RC-15** = downstream convergence not causally attributable to governed mutation lineage.

**2. Replay lineage stability (R2/R3 vs R1 settled)**

Stable replay must **not** fork downstream causal ancestry.

| Must not occur on R2/R3 | Pass criterion |
|-------------------------|----------------|
| Duplicate lineage ancestry | No second parallel chain for same stable correlation |
| Forked causal chains | Downstream artifacts do not split across conflicting parent ids |
| Inconsistent `correlation_id` attachment | New writes must not bind to wrong correlation |
| Lineage non-determinism | `lineage_fingerprint_r2` == `lineage_fingerprint_r3` == post-R1 settled fingerprint |

**Capture in `c2_replay_{slug}.json`:**

```json
{
  "lineage_fingerprint_r1": "...",
  "lineage_fingerprint_r2": "...",
  "lineage_fingerprint_r3": "...",
  "replay_lineage_drift": [],
  "r2_r3_lineage_equal": true
}
```

`replay_lineage_drift[]` — list of `{ "run": "R2"|"R3", "surface", "drift_type", "detail" }` (empty on pass).

**Clarification:** **Legitimate** new mutation (new **C2-M2** correlation per call) **may** create **new** lineage tree. **Stable C2-M1** replay of identical governed mutation **must not**.

**Failure branch:** **C2-RC-16** = replay lineage divergence.

##### 7b. Cross-surface consistency hashing (mandatory — rev 2)

C2 must compute **convergence fingerprints** per surface to detect hidden churn despite stable queue/recalc (C1 proven).

| Fingerprint key | Source (normalized) |
|-----------------|---------------------|
| `requirements_applicability` | Included requirement keys + terminal statuses + top exclusion_reason histogram |
| `gaps` | Open/closed counts + sorted `gap_key` + status tuple |
| `risk_signals` | Open count + sorted `signal_key` + severity tuple |
| `priority_stream` | Sorted action keys + action_type tuple |
| `tasks_today` | Task count + sorted task/remediation ids |
| `kpi_dashboard` | Headline score + pending flags + top deficit keys |

**Verification:**

| Run | Pass criterion |
|-----|----------------|
| R2 vs R3 | **All fingerprints equal** (stable replay) |
| R1 vs R2/R3 | May differ only on first convergence; thereafter stable |
| vs C1 | Queue/recalc stable (C1) but fingerprint drift on R2/R3 → **C2-RC-8** |

**Artifact:** `c2_consistency_hashes_{slug}.json` — `{ "R1": {...}, "R2": {...}, "R3": {...}, "r2_equals_r3": true }`.

##### 7c. Unrelated-surface non-mutation verification (mandatory — rev 3)

C2 replay/mutation proof on the **pilot** property must **not** create downstream bleed into **unrelated** entities. Queue replay storms often manifest as **cross-tenant** or **cross-property** gap/task/risk/KPI churn — C2 must explicitly rule this out for the pilot replay path.

**Scope of “unrelated” (staging):** At minimum one **control** `client_id` + `property_id` pair (different from pilot) on same `pleerity_staging` DB, selected before proof and recorded in the verification report.

| Must remain unchanged (Δ = 0 writes / fingerprint stable) | Fingerprint source |
|-------------------------------------------------------------|-------------------|
| Unrelated tenant aggregate | Gap/risk/regen-queue counts by `client_id` (control tenant) |
| Unrelated property | Same counts + property score pending for control `property_id` |
| Unrelated gaps/tasks/risk/KPI | Normalized hashes matching §7b keys for control entity |

**Capture:**

| Field | Location |
|-------|----------|
| `unrelated_control_client_id`, `unrelated_control_property_id` | `c2_verification_report_{slug}.json` |
| Before/after unrelated fingerprints | `c2_unrelated_surface_integrity_{slug}.json` |
| `unrelated_mutation_delta` | Per-collection write/count deltas (must be **0** on pass) |

**Pass criterion:**

- Unrelated tenants **not** mutated
- Unrelated properties **not** recalculated (no new `compliance_last_calculated_at` advance on control)
- Unrelated gaps/tasks/risk/KPI surfaces **unchanged**
- Replay R2/R3 produces **no** cross-tenant propagation noise

**Failure branch:** **C2-RC-14** = cross-entity / unrelated-surface downstream bleed.

**Clarification:** This is **verification only** — not multi-tenant architecture redesign, fanout topology rewrite, scheduler redesign, or global propagation optimization (§12).

##### 8. Failure taxonomy (mandatory)

Classify staging failures into **one primary branch** (secondary tags allowed):

| Branch | Symptom | Likely authority |
|--------|---------|------------------|
| **C2-RC-1** | Recalc done; gaps never appear/update | `compliance_gap_sync`, materialisation → gap hook |
| **C2-RC-2** | Gaps stale vs included requirements | `compliance_gap_engine`, policy aggregate |
| **C2-RC-3** | Risk regen stuck / never drains | `risk_signal_regen_queue`, worker |
| **C2-RC-4** | Risk signals contradict gaps/score | `risk_signal_service` |
| **C2-RC-5** | Priority stream missing/extra actions | `client_priority_stream` |
| **C2-RC-6** | Tasks/Today disagree with stream | `unified_tasks_service`, `today_projection_service` |
| **C2-RC-7** | Dashboard/KPI shows wrong score or pending | `kpi_authority_projection_contract`, client routes |
| **C2-RC-8** | Replay causes downstream write churn | Gap sync idempotency, stream rebuild guards |
| **C2-RC-9** | Lag exceeds bound without recovery | Scheduler cadence, worker ownership — **observe only**, no redesign in C2 |
| **C2-RC-10** | Fanout blocked (activation gate) | `workflow_runtime_activation_registry` — **observe only** (§1b), defer fix to **D1** |
| **C2-RC-11** | Persistent cross-surface contradiction beyond SLA | Precedence violation (§1a) — lower surface overrides upstream |
| **C2-RC-12** | Stale downstream residue fails to decay | §2b — pending badges, orphan actions, closed-gap tasks, stale KPI/Today markers |
| **C2-RC-13** | Temporal convergence contradiction | §1c — operationally invalid ordering beyond SLA; `convergence_order_timeline[]` |
| **C2-RC-14** | Unrelated-surface downstream bleed | §7c — cross-tenant/property churn on pilot replay path |
| **C2-RC-15** | Causally opaque downstream convergence | §7d — not attributable to C2-M1/M2 / governed lineage |
| **C2-RC-16** | Replay lineage divergence | §7d — duplicate ancestry, forked chains, wrong correlation on R2/R3 |

##### 9. Regression tests required (implementation phase)

Extend / add (names indicative); all must pass before **VERIFIED**:

| Test area | File (existing or new) | Assertions |
|-----------|------------------------|------------|
| Gap sync | `test_compliance_gap_sync.py`, `test_compliance_gap_engine_governed.py` | Governed requirement → gap rows |
| Gap alias | `test_scoring_gap_alias_alignment.py` | Alias families align with scoring |
| Priority / tasks | `test_phase21_priority_unification.py` | Stream → unified tasks shape |
| KPI contract | `test_kpi_authority_projection_contract.py` | No unfiltered client KPI paths |
| Downstream after recalc | **new** `test_c2_downstream_convergence_after_recalc.py` | Mock recalc → gap sync + regen enqueue called; pending clear |
| Replay projection stability | **new** `test_c2_replay_no_downstream_churn.py` | Double sync mock → gap/task/priority write count stable |
| Consistency fingerprints | **new** `test_c2_cross_surface_consistency_hashes.py` | R2=R3 hash equality on stable replay mock |
| Stale decay | **new** `test_c2_stale_surface_decay.py` | Resolved upstream clears downstream residue in mock window |
| Governed exclusions | **new** `test_c2_downstream_exclusion_provenance.py` | Missing representation requires exclusion_reason |
| Temporal ordering | **new** `test_c2_temporal_convergence_ordering.py` | Mock timeline — no persistent ordering violation beyond bound |
| Unrelated integrity | **new** `test_c2_unrelated_surface_non_mutation.py` | Pilot mutation does not mutate control tenant/property fingerprints |
| Causal lineage | **new** `test_c2_downstream_causal_lineage.py` | Downstream writes carry expected correlation where supported |
| Replay lineage stability | **new** `test_c2_replay_lineage_determinism.py` | Stable replay → equal lineage fingerprint; no forked ancestry |
| C1 regression (no regress) | C1 suite (46 tests) | Still green |

**CI:** Full C2 suite + C1 suite green; no flake on Mongo-less mocks.

##### 10. Governance docs to update (on C2 DONE)

| Document | Update |
|----------|--------|
| `LAUNCH_AUTHORITY_TRACKER.md` | C2 closure evidence; unlock **D1** decision |
| `RUNBOOK_CONTROLLED_BETA_OPERATIONS.md` §12.7 | Add **C2** substeps (snapshots, lag table, replay) |
| `CLOSED_LOOP_COMPLIANCE_ARCHITECTURE_TRACKER.md` | C2 row → DONE; stream B/E notes |
| `STREAM_E_MUTATION_FANOUT_MATRIX.md` | Cross-ref only if observe findings — **no matrix rewrite** unless D1 |
| `GOVERNANCE_INDEX.md` | C2 handoff cross-ref |
| `runbooks/SCHEDULER_AND_COMPLIANCE_JOBS.md` | Only if lag semantics change in code |

##### 11. Completion gates

| Gate | Requirement |
|------|-------------|
| **Start `IN_PROGRESS`** | C2 DoD rev 4 **approved**; pilot + control unrelated entities identified |
| **`IMPLEMENTED_PENDING_VERIFICATION`** | Code/tests merged (if any fixes); `scripts/c2_*` optional |
| **`READY_FOR_STAGING_VERIFICATION`** | All §2 + §2b + §7b + §7c + §7d artifacts captured on staging |
| **`VERIFIED`** | §1a–§1c, §3–§7, §6b, §2b, §7b–§7d pass |
| **`DONE`** | §9 tests green; §10 docs updated; §11 rev-4 DONE checklist; **D1** unlock decision documented |

**C2 cannot move to DONE unless all proven on staging (rev 4 tightening):**

1. Post-recalc **downstream surfaces converge** within §3 bounds.
2. **Precedence ordering holds** (§1a) — no persistent downstream override beyond SLA.
3. **Temporal convergence ordering is sane** (§1c) — no persistent contradictory ordering beyond SLA; replay does not unpredictably reorder.
4. Gap/risk/priority/tasks/KPI **mutually consistent** (§4–§6) with **governed exclusions explainable** (§6b).
5. **Stale residue decays correctly** (§2b) — no orphan pending/actions/tasks/KPI/Today markers beyond SLA.
6. **Cross-surface hashes converge on replay** (§7b) — **R2 == R3**; no hidden churn despite stable queue/recalc (C1).
7. **Unrelated downstream surfaces remain unchanged** (§7c) — `unrelated_mutation_delta` = 0; no cross-tenant bleed.
8. **Downstream convergence remains causally attributable** (§7d) — `downstream_lineage_summary[]` clean; no **C2-RC-15**.
9. **Replay lineage remains deterministic** (§7d) — `lineage_fingerprint_r2` == `lineage_fingerprint_r3`; `replay_lineage_drift[]` empty; no **C2-RC-16**.
10. **R2/R3 replay** produces no downstream projection churn on pilot (§7).
11. **Fanout observation remains non-mutating** (§1b) — any corruption classified and deferred to **D1**.
12. No notification/fanout/activation/scheduler/lineage-infrastructure/global-propagation semantics change shipped under C2 guise.

**Unlock on DONE:** **D1** DoD drafting (fanout propagation proof) — **not** F1 notifications, **not** B2 overlay.

##### 12. Explicit out-of-scope boundaries (rev 4)

**C2 remains:** downstream convergence verification after recalc (precedence, temporal ordering, causal lineage, replay lineage determinism, decay, hashes, governed exclusions, unrelated-surface integrity) — **verification only** within existing correlation/audit semantics.

**C2 is NOT:**

| Out of scope | Owner / note |
|--------------|--------------|
| Queue enqueue, worker, reclaim, duplicate suppression | **C1 DONE** |
| Distributed tracing redesign | Platform — C2 uses existing fields only |
| Event bus redesign | Platform |
| Lineage infrastructure rewrite | Platform |
| Topology refactor | **D1** / platform |
| Multi-tenant architecture redesign | Platform — C2 **detects** bleed only |
| Global propagation optimization | Platform / **D1** |
| Fanout repair / routing changes | **D1** |
| Activation policy redesign | **D1** |
| Queue topology rewrite | **D1** / platform |
| Notification overhaul, send paths, `message_logs` proof | **F1** |
| Scheduler ownership redesign, new cron jobs | Platform — incident only |
| Task system / Today architecture redesign | Product — out of C2 |
| `authority_mutation_fanout` architecture rewrite | **D1** |
| `updated_at` / materialisation write optimization | B1 watchlist — only if C2 proves causal downstream harm |
| Zero-row / provisioning materialisation | **A2** |
| Published overlay / 21/21 raw parity | **B2 BLOCKED** (product) |
| Portfolio-wide batch convergence | Separate approved unit |
| Fixing every “requirements not recorded” scenario | **A2/A3/B2** as classified |

**C2 scope boundary (one line):** Proves **operational read surfaces converge after recalc** in **sane temporal order**, with **causal lineage, deterministic replay lineage, precedence, decay, fingerprinted replay stability, explainable exclusions, and no unrelated-entity bleed** — verification only within existing correlation semantics; not tracing/event-bus/lineage-infrastructure/topology/fanout/scheduler/notification redesign.

##### C2 — Proposed verification method

1. Select pilot `(CID, PID)` + control unrelated `(CID', PID')`; record in report
2. `python -m scripts.c2_preflight_capture --client-id CID --property-id PID` → `c2_convergence_before_*` + `c2_unrelated_surface_integrity_*` (before)
3. **R1:** **C2-M1** client sync → poll until queue `DONE` + §3 lag bounds; append `convergence_order_timeline[]` each tick
4. Capture `c2_gaps_*`, `c2_risk_priority_*`, `c2_dashboard_tasks_*`, `c2_exclusions_*`, `c2_stale_decay_*`, `c2_consistency_hashes_*`, `c2_lineage_trace_*` (optional `c2_fanout_observe_*` if C2-M3)
5. **R2/R3:** repeat **C2-M1** → `c2_replay_*` + update hashes/decay/timeline/lineage fingerprints/`replay_lineage_drift[]`/unrelated integrity (after)
6. `python -m scripts.c2_staging_verification ...` → `c2_verification_report_*` (incl. `precedence_violations[]`, `r2_equals_r3`, `convergence_order_timeline[]`, `unrelated_mutation_delta`, `downstream_lineage_summary[]`)
7. Run §9 pytest suite

**Scripts (implementation phase, optional):** `scripts/c2_preflight_capture.py`, `scripts/c2_staging_verification.py` — read-only snapshots + HTTP drivers (mirror C1 pattern; CLI defaults overridable, no tenant logic in services).

**Staging verification:** Initial run 2026-05-16 `c2_pass=false` (RC-8 tasks volatile-id fingerprint; RC-13 false positive on `pending=false`). **C2a DONE** — root cause `regenerated_ids` + `verification_fingerprint_normalization`; normalization + RC-13 semantics in `c2_snapshot.py` only. **Normalized rerun** 2026-05-16 `c2_pass=true` — `tasks_today` R2=R3=`62c957fe1ca22589db0af66c177d0b53`; `temporal_ordering_violations_empty`; control §7c delta zero after run-start normalized baseline. Report: [audit/c2_verification_report_6fd5ac4c_d35a58ae.json](../audit/c2_verification_report_6fd5ac4c_d35a58ae.json) (`verification_run=c2_normalized_rerun_c2a`). **RC-14** initial fail was preflight legacy fingerprint vs normalized end-state — not cross-tenant bleed.

##### 1c-rev. Temporal ordering detector semantics (proposal — post C2 staging)

**Problem:** Initial detector treated `compliance_score_pending=false` + open gaps as `kpi_clear_while_gaps_open` — conflates **settled recalc** with **resolved compliance**.

| State | Definition | Example signals |
|-------|------------|-----------------|
| **Settled recalc** | Queue/recalc cycle complete; score persisted | `compliance_score_pending=false`, fresh `compliance_last_calculated_at` |
| **Resolved compliance** | Upstream obligations/gaps no longer require action | Open gap count **0** for included families, or governed exclusions documented |

**Revised C2-RC-13 rules (verification only):**

| Fire C2-RC-13 | Do **not** fire C2-RC-13 |
|---------------|-------------------------|
| Dashboard/Today asserts **all clear** / **no action needed** while gaps **OPEN** | `pending=false` with **non-zero** open gaps and score **&lt; 100** (expected pilot state) |
| KPI headline implies **fully compliant** while gaps contradict | Score settled at **52** with 5 open gaps — **settled recalc**, not temporal contradiction |
| Tasks disappear **before** priority stream loses matching actions | Open gaps with stable priority stream keys |
| Downstream surface converges **before** upstream deficits exist | Documented in `convergence_order_timeline[]` with SLA breach |

**Detector rename (implementation in verification script, not product):** replace `kpi_clear_while_gaps_open` with `downstream_asserts_resolved_while_gaps_open` (requires explicit all-clear copy/flag, not pending flag alone).

---

### C2a — Task replay determinism investigation

| Field | Value |
|-------|-------|
| **ID** | C2a |
| **Parent** | **C2** (blocked on RC-8 tasks fingerprint) |
| **Priority** | P1 |
| **Trigger** | C2 staging `c2_pass=false`; `tasks_today` hash drift R1/R2/R3 while other surfaces stable |
| **Scope** | **Investigate only** — classify drift source; no product fix until root cause proven and approved |
| **Canonical authority** | `unified_tasks_service._action_to_task`, `_stable_source_id`; `client_priority_stream.fetch_client_priority_actions`; `risk_signal_regen_queue` |
| **Unit status** | **DONE** (2026-05-16) — root cause: regenerated_ids + verification_fingerprint_normalization |
| **Verification evidence** | `c2a_task_drift_analysis_{slug}.json`; updated recommendation in C2 report |
| **Governance docs after** | This tracker; refine C2 §7b fingerprint rules after classification |
| **Regression tests** | Extend `test_c2_verification_contract.py` with drift classification fixtures (no product change) |
| **Rollback / safety** | Preserve all `c2_*` artifacts; analysis is additive only |

#### C2a — Definition of Done (rev 1 — 2026-05-16)

**Purpose:** Determine why `tasks_today` consistency fingerprint drifts on **stable C2-M1 replay** (R2/R3) when gaps, risk, priority stream, and KPI fingerprints are stable. **Not** a unified_tasks redesign.

##### 1. Inputs (mandatory — preserved)

| Input | Path |
|-------|------|
| C2 replay | `c2_replay_{slug}.json` |
| C2 dashboard/tasks | `c2_dashboard_tasks_{slug}.json` |
| C2 consistency hashes | `c2_consistency_hashes_{slug}.json` |
| C2 risk/priority | `c2_risk_priority_{slug}.json` |
| C2 verification report | `c2_verification_report_{slug}.json` |

**Do not delete or overwrite existing `c2_*` artifacts.**

##### 2. Drift classification (mandatory)

Classify into **one primary** bucket:

| Bucket | Meaning |
|--------|---------|
| **true_semantic_task_churn** | Task set/count/sections change with business meaning |
| **ordering_instability** | Same tasks, different sort order in fingerprint input |
| **volatile_fields** | Timestamps, scores, or labels in hash input |
| **regenerated_ids** | Stable semantic task, unstable `task.id` (e.g. risk_signal suffix) |
| **grouping_instability** | Section membership changes without semantic change |
| **verification_fingerprint_normalization** | C2 script hashes wrong field; product behaviour acceptable |

##### 3. Per-run diff (mandatory)

| Run pair | Compare |
|----------|---------|
| R1 vs R2 | `task_ids_sample`, section counts, priority stream keys |
| R2 vs R3 | Same |
| R2 vs R3 hashes | `tasks_today` only |

Record **exact field** that changed (e.g. `risk_signal:rs_*`).

##### 4. Code-path trace (read-only)

| Step | Module | Question |
|------|--------|----------|
| C2-M1 replay | `enqueue_compliance_recalc` | Is `regeneration_requeued=true` on suppressed replay? |
| Risk regen | `risk_signal_regen_queue`, worker | New `signal_id` per regen? |
| Priority stream | `client_priority_stream` | Stable `action_type\|title\|requirement_id` keys? |
| Unified tasks | `_stable_source_id`, `_action_to_task` | Does `task_id` use volatile `related_risk_signal_id`? |

##### 5. Recommendation output (mandatory — no implementation)

One of:

| Recommendation | When |
|----------------|------|
| **verification_normalization_only** | Semantic task set stable; fingerprint should use stream-stable keys not display `task.id` |
| **targeted_task_determinism_fix** | Product should use stable risk identity (e.g. `signal_key`) in `_stable_source_id` for risk_signal only |
| **true_downstream_semantic_defect** | Task set/sections materially change on replay without upstream change |

##### 6. Completion gates

| Gate | Requirement |
|------|-------------|
| **DONE** | Primary drift bucket + per-run diff + code-path trace + recommendation recorded in `c2a_task_drift_analysis_{slug}.json` |
| **C2 unblock** | C2 governance updated per recommendation; separate approval for any product fix |

**Out of scope:** `unified_tasks_service` redesign; notifications; D1/F1; queue/recalc changes; general task-system work.

#### C2a — Investigation findings (2026-05-16 — pilot staging)

**Artifact:** [audit/c2a_task_drift_analysis_6fd5ac4c_d35a58ae.json](../audit/c2a_task_drift_analysis_6fd5ac4c_d35a58ae.json)

| Finding | Value |
|---------|-------|
| **Primary classification** | **regenerated_ids** (secondary: **verification_fingerprint_normalization**) |
| **Exact drift** | Single task slot: `risk_signal:rs_*` — `rs_0f56a8454586` (R1) → `rs_77fd6f275f29` (R2) → `rs_a5210ba0f31d` (R3) |
| **Stable across replay** | 6/7 task ids unchanged; section counts identical (urgent=1, upcoming=4, in_progress=2, total=7) |
| **Priority stream** | Fingerprint **stable** R1–R3 (`risk_signal\|…\|Electrical safety concern`) |
| **Enqueue side-effect** | Each C2-M1: `enqueued=false`, `regeneration_requeued=true` (risk regen debounce path fires on materialise despite queue suppression) |
| **Recommendation** | **verification_normalization_only** for C2 re-run; optional **targeted_task_determinism_fix** (risk_signal `_stable_source_id` only) if product parity required — **declined** |

**C2a closure (2026-05-16):** **DONE** — accepted classifications; applied `normalized_stable_business_keys_c2a` in `c2_snapshot.py`; C2-RC-13 detector revised (§1c-rev). No product change.

---

### D1 — Workflow propagation fanout

| Field | Value |
|-------|-------|
| **ID** | D1 |
| **Priority** | P0 (launch) |
| **Trigger** | **Only after A+B+C pass** for pilot tenant |
| **Scope** | `authority_mutation_fanout`; RST backbone gate; recalc/regen enqueue; document activation-blocked cases |
| **Canonical authority** | `authority_mutation_fanout.py`; `workflow_runtime_activation_registry.py`; **L-009**; `STREAM_E_MUTATION_FANOUT_MATRIX.md` |
| **Code areas likely affected** | Fanout, evidence verify paths, `requirement_transition_observability.py` |
| **Unit status** | **DONE** (2026-05-17) — lifecycle: IN_PROGRESS → VERIFIED (D1b) → **DONE** |
| **Verification evidence** | Authoritative: `docs/audit/d1b_verification_report_6fd5ac4c_d35a58ae.json` (`verification_run=d1b_harness_rerun_v3`); full `d1b_*` set; original `d1_*` retained |
| **Governance docs after** | This tracker; `RUNBOOK_CONTROLLED_BETA_OPERATIONS.md` §12.7 D1; `CLOSED_LOOP_COMPLIANCE_ARCHITECTURE_TRACKER.md`; `STREAM_E_MUTATION_FANOUT_MATRIX.md` (observe-only cross-ref) |
| **Regression tests** | Fanout phase-4/5 suites + D1 §12 — see DoD |
| **Rollback / safety** | Do not bypass activation registry; do not mutate fanout routing in D1 verification |

---

#### D1 — Definition of Done (rev 3 — 2026-05-16; **approved** — **DONE** 2026-05-17 via D1b authoritative staging)

**Rev 2 additions (2026-05-16):** propagation cardinality (§3b); partial propagation convergence (§5b); replay collapse semantics (§4b); delegated lineage preservation (§9b); observability-noise stability (§10b); **D1-RC-11**–**D1-RC-15**; tightened DONE gates (§14).

**Rev 3 additions (2026-05-16):** propagation behaviour classes (§3c); bounded propagation growth (§4c); suppression determinism (§10c); **D1-RC-16**–**D1-RC-18**; further DONE gate tightening (§14).

**Purpose:** Prove **deterministic workflow propagation fanout** behaviour using **existing** governed propagation semantics (`authority_mutation_fanout.py`, `requirement_transition_observability.py`, `workflow_runtime_activation_registry.py`) aligned to `STREAM_E_MUTATION_FANOUT_MATRIX.md`. D1 verifies that governed mutations produce **expected, attributable, replay-stable propagation traces** — including **class-correct** branch behaviour, **cardinality-correct** branch counts, **bounded** propagation growth, activation-gated suppression, **deterministic** suppression on replay, duplicate downstream suppression, **replay-collapse** determinism, **delegated lineage** preservation, **partial-convergence** detection, **observability-noise** stability, and legitimate new-correlation propagation — without cross-tenant bleed, silent suppression, or propagation saturation.

**Upstream precondition (accepted):** A1 **DONE**, B1 **DONE**, C1 **DONE**, C2 **DONE**, C2a **DONE** on pilot tenant. Queue/recalc replay safety and downstream convergence already proven; D1 does **not** re-prove C1 queue semantics or C2 surface fingerprints except where fanout lineage must chain to them.

**Pilot tenant (staging verification only):** `client_id=6fd5ac4c-3fd4-4112-ade7-156977deb49f`, `property_id=d35a58ae-3c81-491c-9694-1d021dd3b8ad`, `pleerity_staging`. **Control unrelated** entity pair documented in `d1_control_selection_{slug}.json` (may reuse C2 control `04ceda9f…` / `6d939c70…` unless a fresher isolation candidate is recorded). Product logic must remain **tenant-agnostic** (no hardcoded IDs in services/tests).

##### 1. Scope and authoritative boundary (mandatory)

**D1 verifies (in scope):**

| Layer | What D1 proves |
|-------|----------------|
| **Transition fanout trace** | `transition_fanout` / `build_transition_fanout_trace` shape; `downstream_rows[]`; `propagation_stage`; `downstream_target`; `enqueue_attempted` / `enqueue_result`; `duplicate_suppression_reason` |
| **Authority fanout entrypoints** | `authority_sync_with_transition_observability`, `enqueue_compliance_recalc_with_fanout`, `attach_risk_regen_delegate_row` observation rows |
| **Activation gating** | `resolve_requirement_state_transition_core_backbone_gate` outcomes merged via `merge_rst_core_backbone_activation_into_fanout` — permitted vs blocked paths **observable** |
| **Matrix alignment** | Selected `STREAM_E_MUTATION_FANOUT_MATRIX.md` rows exercised on pilot match **documented** gap sync / recalc / quiet / Enq expectations (observe-only; matrix not rewritten in D1) |
| **Replay propagation** | Stable governed replay does **not** multiply fanout branches; legitimate new-correlation mutation **does** propagate |
| **Propagation cardinality** | Expected vs actual branch counts; suppressed/blocked/unexpected branches explicit (§3b) |
| **Partial convergence** | Expected fanout branches vs downstream completion matrix — no silently stalled subtrees (§5b) |
| **Replay collapse** | Redundant branch suppression on replay is deterministic and lineage-visible (§4b) |
| **Delegated lineage** | Regen/delegate rows retain originating `correlation_id` ancestry (§9b) |
| **Observability noise** | Stable replay does not amplify logs, overlays, audits, or blocked-state churn (§10b) |
| **Propagation behaviour classes** | Each branch classified; expected vs observed replay behaviour explicit (§3c) |
| **Bounded propagation growth** | Branch/delegate growth curves finite and convergent on replay cycles (§4c) |
| **Suppression determinism** | Identical replay → identical suppression fingerprints (§10c) |
| **Lineage** | Fanout `correlation_id` / `transition_id` chains to queue row, score history sample, and audit sample where matrix requires |
| **Cross-tenant isolation** | Pilot fanout activity does not mutate control-tenant fanout fingerprints or unrelated downstream enqueue targets |
| **Suppression provenance** | Every blocked or suppressed propagation path records a **governed reason** — silent suppression is **D1 failure** |

**Ownership boundaries (explicit — D1 does not verify):**

| Owner | Remains responsible for | D1 relationship |
|-------|-------------------------|-----------------|
| **C1 (C-layer)** | Queue enqueue/worker/reclaim/duplicate suppression on `compliance_recalc_queue`; recalc execution | D1 **consumes** C1 pass; may reference queue `correlation_id` in lineage joins — does not re-open C1 unless fanout proves enqueue contract regression |
| **C2 (C-layer)** | Downstream surface convergence, precedence, stale decay, normalized task fingerprints | D1 **consumes** C2 pass; fanout proof must not contradict C2 lineage — does not re-run full C2 hash suite unless D1-RC implicates downstream churn |
| **F1** | Notification orchestrator, `message_logs`, template governance (**L-008**) | **Out of scope** — D1 may **count** notification delegate rows in fanout trace if present but does **not** prove delivery, consent, or template correctness |
| **Scheduler / runbook** | `job_runner` ownership, heartbeat, reclaim thresholds (`SCHEDULER_AND_COMPLIANCE_JOBS.md`) | **Observe only** — worker pickup already C1; D1 does not redesign cadence or ownership |
| **Task systems** | `unified_tasks_service`, Today projection, volatile `risk_signal:rs_*` ids (C2a watchlist) | **Out of scope** — risk regen **delegate row** in fanout may be observed; task identity not remediated in D1 |

**D1 is NOT:** notification overhaul; scheduler redesign; workflow rewrite; event bus redesign; queue topology redesign; fanout architecture replacement; activation-policy mutation; routing rewrites; task-system redesign; broad remediation disguised as verification.

**One-line boundary:** D1 proves **governed propagation fanout is behaviour-class-correct, cardinality-correct, growth-bounded, deterministic on replay (incl. collapse + suppression), lineage-stable (incl. delegates), suppression-explainable, free of partial silent stall and saturation, observability-stable, temporally sane, and cross-tenant isolated** — using existing infrastructure only.

##### 2. Governed mutation sources (verification only)

Mutations must use **production HTTP/service paths** that populate `transition_fanout` via `authority_mutation_fanout` (or documented matrix-equivalent callers). **No raw Mongo** fanout injection. **No synthetic** `transition_fanout` fixtures in staging proof.

| ID | Endpoint / flow | Matrix row(s) | Fanout under test | Correlation contract |
|----|-----------------|----------------|-------------------|----------------------|
| **D1-M1 (primary replay)** | Client `POST /api/properties/{property_id}/requirements/sync` | 10–11 (materialise touch) | Materialise → `enqueue_compliance_recalc_with_fanout` rows; risk regen delegate | **Stable:** `REQUIREMENTS_SYNC:{property_id}` |
| **D1-M2 (legitimate new propagation)** | Admin `POST /api/admin/properties/{property_id}/requirements/sync-from-registry` | 10–11 | New fanout chain with **new** correlation | **New per call:** `ADMIN_MANUAL_JOB:REGISTRY_SYNC:…` |
| **D1-M3 (transition fanout rich path)** | Governed requirement transition with fanout (pilot-safe): e.g. admin document verify / evidence review verify on linked requirement | 6–7 | `authority_sync_with_transition_observability` + enqueue fanout; optional outcome **Sync** row | Per route / transition (`DOCUMENT_VERIFIED`, etc.) |
| **D1-M4 (quiet / governed suppression observe)** | Applicability operator action or matrix **Quiet** path — **observe only** if pilot has safe fixture | 12 | Gap sync quiet; **no** recalc enqueue expected — suppression must be **explicit** in trace | Per operator audit |
| **D1-M5 (activation-blocked observe)** | Same as D1-M1 or D1-M3 with `rst_core_backbone_activation.permitted=false` staging state **or** read-only capture of blocked trace from audit | — | `rst_core_backbone_blocked_*` stages; `enqueue_attempted=false` | N/A — blocked path |

| Forbidden as proof | Reason |
|--------------------|--------|
| Raw Mongo insert into `transition_fanout` collections or manual `downstream_rows` | Bypasses authority |
| Direct `enqueue_compliance_recalc()` without fanout wrapper | Not propagation proof |
| Fleet batch / admin recalculate-all-properties | Out of pilot scope; amplification risk |
| Notification send / reminder dispatch as propagation proof | **F1** scope |
| C1-M2 for **replay-idempotency** fanout proof | New correlation per call by design |
| Scripts that only materialise without fanout observability | B-layer only |

**Replay rule:** Use **D1-M1** only for R2/R3 fanout fingerprint comparison (stable correlation). Use **D1-M2** once per verification window for legitimate new-branch proof.

##### 3. Propagation topology verification (mandatory)

For each governed mutation (R1 and optional M3/M4/M5), capture **propagation topology snapshot** before/after:

| Check | Pass criterion |
|-------|----------------|
| **Expected downstream paths** | Each matrix-selected mutation produces documented targets in `downstream_rows[]` (e.g. `compliance_recalc_queue.enqueue_compliance_recalc`, `risk_signal_regen_queue.enqueue_risk_signal_regen` delegate) when matrix expects **Enq** |
| **Governed suppression paths** | Duplicate enqueue suppression surfaces `duplicate_suppression_reason` on fanout row **and** matches C1 `EnqueueComplianceRecalcResult` |
| **Blocked propagation** | Activation-blocked paths show `enqueue_attempted=false`, `rst_core_backbone_activation` overlay, non-empty `activation_reason` |
| **Quiet paths** | Quiet gap sync paths do **not** claim full recalc propagation; any skipped enqueue is **documented** (not silent) |
| **Replay-safe propagation** | R2/R3 on D1-M1: fanout **branch-count** and **suppression-state fingerprint** stable |

**Artifact:** `d1_propagation_topology_{slug}.json` — per run: `{ "mutation": "D1-M1", "run": "R1", "downstream_targets": [...], "branch_count": N, "blocked_count": N, "suppressed_count": N, "matrix_row_refs": [6,7,10] }`.

##### 3b. Propagation cardinality verification (mandatory — rev 2)

D1 must verify **branch counts**, not only branch existence, replay stability, and suppression provenance.

| Field | Definition |
|-------|------------|
| `expected_branch_count` | Matrix + mutation contract: count of **distinct** expected `downstream_target` branches (incl. documented delegate rows) |
| `actual_branch_count` | Observed distinct branches in `downstream_rows[]` + documented delegate attachments |
| `suppressed_branch_count` | Branches with governed duplicate/idempotent suppression (`duplicate_suppression_reason` set) |
| `blocked_branch_count` | Branches blocked by activation gate (`enqueue_attempted=false`, `activation_reason` set) |
| `unexpected_branch_count` | `actual - expected - suppressed - blocked` (must be **0** on pass) |

**Verification must prove:**

| Requirement | Failure signal |
|-------------|----------------|
| No hidden duplicate branches | Same `(downstream_target, propagation_stage)` appears >1 without documented reason |
| No replay-created branch amplification | R2/R3 `actual_branch_count` ≠ R1 settled (unless documented collapse — §4b) |
| No missing expected propagation targets | `expected_branch_count` > attributable actual+suppressed+blocked |
| No undeclared extra fanout branches | `unexpected_branch_count` > 0 |

**Report:** `propagation_cardinality_summary[]` in `d1_verification_report_{slug}.json` — per run: `{ "run", "mutation", "expected_branch_count", "actual_branch_count", "suppressed_branch_count", "blocked_branch_count", "unexpected_branch_count", "cardinality_pass": bool }`.

**Artifact:** `d1_branch_cardinality_{slug}.json` — full per-run cardinality tables + target-level diff.

**Failure:** **D1-RC-11** = propagation cardinality drift.

##### 3c. Propagation behaviour classes (mandatory — rev 3)

D1 must **classify** each observed propagation branch by governed behaviour type. This is **governance classification only** — **not** permission to redesign propagation logic, routing, or enqueue contracts.

**Governed behaviour classes (indicative — extend only via tracker amendment):**

| Class | Operational meaning | Expected replay on D1-M1 (stable correlation) |
|-------|---------------------|-----------------------------------------------|
| `idempotent` | Duplicate-safe; no new downstream work when inputs unchanged | R2/R3: same suppression or no-op outcome as R1 |
| `replay-collapsible` | Redundant branch creation suppressed on replay; lineage retained (§4b) | R2/R3: branch collapsed with `suppressed_replay_branches[]` entry |
| `replay-regenerative` | Debounced regen path may re-fire observation without new enqueue branch | R2/R3: delegate/regen row observable; cardinality bounded (§4c) |
| `always-propagating` | New correlation or semantic mutation always creates new governed branch | R1 only on stable replay; **D1-M2** may trigger |
| `quiet-suppressed` | Matrix **Quiet** path — gap sync without full fanout enqueue | Explicit quiet reason; no undeclared enqueue |
| `activation-blocked` | RST backbone gate blocks enqueue | `enqueue_attempted=false`; `activation_reason` set |
| `delegated-regenerative` | `regen_delegate` / risk regen delegate from recalc fanout | Delegate attached to parent `correlation_id`; growth bounded (§4c, §9b) |

**Per-branch verification (in** `d1_branch_behaviour_classes_{slug}.json` **):**

| Field | Requirement |
|-------|-------------|
| `propagation_behaviour_class` | One governed class from table above |
| `expected_replay_behaviour` | Declared expectation for R2/R3 (e.g. `collapse_stable`, `suppress_duplicate`, `delegate_observable`) |
| `observed_replay_behaviour` | Measured outcome on R2/R3 — must match `expected_replay_behaviour` |
| `behaviour_explainable` | Non-empty operational note when class is non-obvious |

**Verification must prove:** each branch behaves per its class; replay expectations are explicit and deterministic; branch behaviour is explainable operationally.

**Failure:** **D1-RC-16** = propagation behaviour class mismatch (`observed_replay_behaviour` ≠ `expected_replay_behaviour` or unclassified branch).

##### 4. Replay amplification protection (mandatory)

**Goal:** Stable replay must not multiply propagation branches or re-fire unattributed downstream work.

| Run | Mutation | Expected fanout behaviour |
|-----|----------|---------------------------|
| **R1** | D1-M1 ×1 | Full governed fanout chain recorded; queue enqueue attempted or suppressed with reason |
| **R2** | D1-M1 ×1 | **No new fanout branches** vs R1 settled state; duplicate suppression rows consistent; `branch_count_delta=0` |
| **R3** | D1-M1 ×1 | Same as R2 |
| **M2 once** | D1-M2 ×1 | **New** correlation → **new** enqueue fanout branch permitted (+1 documented branch vs stable baseline) |

**Compare:** `d1_propagation_replay_{slug}.json` — per run: `fanout_fingerprint`, `branch_count`, `downstream_rows_hash`, `suppression_fingerprint`, `regen_delegate_fingerprint`.

**Explicit non-goals:** Do not conflate `regeneration_requeued` (risk regen debounce) with fanout branch amplification — record both; classify amplification only when **unexplained new downstream_rows** appear on R2/R3.

##### 4b. Replay collapse semantics (mandatory — rev 2)

**Replay collapse** = governed reduction of **redundant fanout branch creation** on stable replay (R2/R3) while preserving causal visibility. These are **governance verification rules** — **not** queue suppression rewrites, topology changes, or `enqueue_compliance_recalc` contract changes.

| Rule | Requirement |
|------|-------------|
| **Redundant branch suppression permitted** | Stable replay may suppress re-creation of branches already settled in R1 |
| **Lineage visibility preserved** | Collapse must **not** hide legitimate ancestry — `suppressed_replay_branches[]` lists collapsed branches with reasons |
| **Delegated/regenerated propagation observable** | `regeneration_requeued` / risk regen delegate rows remain visible even when enqueue suppressed |
| **Deterministic collapse** | R2 and R3 produce **identical** `replay_collapse_state` (§10c suppression fingerprint aligned) |

**Capture:** `replay_collapse_state`, `suppressed_replay_branches[]`, `retained_lineage_visibility` in `d1_propagation_replay_{slug}.json` and `d1_verification_report_{slug}.json`.

**Failure:** **D1-RC-13** = replay collapse inconsistency.

##### 4c. Bounded propagation growth verification (mandatory — rev 3)

D1 must verify propagation growth remains **operationally finite** across replay and legitimate-mutation cycles. **Observational/governance only** — **not** topology redesign, fanout architecture rewrite, or replay-engine changes.

| Requirement | Pass criterion |
|-------------|----------------|
| **Stable replay unbounded accumulation** | R1→R2→R3 cumulative `actual_branch_count` and distinct `downstream_target` keys do not grow without bound |
| **Delegated chains bounded** | `delegated_growth_delta` = 0 on R2/R3 vs R1 settled for `regen_delegate` / `delegated-regenerative` classes (§3c) |
| **Replay + legitimate regeneration finite** | D1-M2 may add **one** documented branch bump; no runaway chain after M2 |
| **Growth converges** | `branch_growth_curve[]` plateaus within verification window — `bounded_growth_pass=true` |

**Especially verify:** `regen_delegate` rows; delegated propagation chains; `replay-regenerative` branches (§3c).

| Field | Definition |
|-------|------------|
| `branch_growth_curve[]` | Per run: `{ "run", "cumulative_branch_count", "cumulative_delegate_count" }` |
| `branch_growth_delta` | R3 cumulative − R1 settled cumulative (must be **0** on stable replay pass) |
| `delegated_growth_delta` | Change in delegate row count R2/R3 vs R1 (must be **0** unless documented `replay-regenerative` observation-only) |
| `bounded_growth_pass` | **true** iff no saturation pattern detected |

**Artifact:** `d1_bounded_growth_{slug}.json`.

**Failure:** **D1-RC-17** = propagation saturation / unbounded branch growth.

##### 5. Cross-stream lineage integrity (mandatory)

Fanout traces must remain **causally attributable** across streams:

```
governed mutation (HTTP)
  → transition_fanout (correlation_id, transition_id)
    → compliance_recalc_queue row (same correlation_id)
      → property_compliance_score_history / score_change_log sample (when F2-A populated)
        → audit_logs sample (matrix-required types)
```

| Rule | Requirement |
|------|-------------|
| **Attribution** | `d1_lineage_trace_{slug}.json` links fanout `correlation_id` to queue entity key and ≥1 downstream persistence sample |
| **No orphan fanout** | Fanout rows with `enqueue_attempted=true` must have matching queue row **or** documented suppression reason on same trace |
| **No divergent trees** | R2/R3 lineage fingerprint equals R1 settled fingerprint — no forked `transition_id` ancestry for same correlation |
| **C2 handoff** | Lineage must not contradict C2 `downstream_lineage_summary[]` on same pilot replay window |

**Failure:** **D1-RC-2** (orphan), **D1-RC-3** (divergence).

##### 5b. Partial propagation convergence detection (mandatory — rev 2)

D1 must detect **partially completed propagation trees** — distinct from orphan fanout (§5), blocked propagation (§3/§10), and silent suppression (§10).

| Pattern | Example | Detection |
|---------|---------|-----------|
| **Upstream fanout complete, downstream surface incomplete** | Gaps updated; priority stream missing expected actions | `propagation_completion_matrix[]` row `gaps=complete`, `priority_stream=incomplete` |
| **Risk path partial** | Risk regen delegate fired; risk/priority fingerprints not ready within SLA | `risk=complete`, `priority_stream=incomplete` |
| **Branch-level stall** | Some `downstream_rows` show success; sibling expected branch never appears without suppression reason | `expected_vs_completed_branches` lists missing targets |

**Artifacts:**

| Artifact | Contents |
|----------|----------|
| `propagation_completion_matrix[]` | In `d1_verification_report_{slug}.json` — per branch: `{ "branch", "expected": bool, "fanout_observed": bool, "downstream_complete": bool, "within_sla": bool }` |
| `expected_vs_completed_branches` | Set diff of expected targets vs completed (fanout + C2 surface spot-check where matrix ties fanout to read model) |
| `partial_convergence_reason` | Non-empty when incomplete — governed string (e.g. `priority_stream_lag`, `gap_sync_without_stream`) |
| `d1_partial_convergence_{slug}.json` | Full matrix + SLA window + C2 cross-reference snapshot |

**Clarification — not classified as partial convergence:**

| Condition | Correct RC |
|-----------|------------|
| Single orphan `enqueue_attempted=true` without queue/suppression | **D1-RC-2** |
| Activation-blocked with overlay + reason | **D1-RC-4** (not partial — fully blocked) |
| Skipped path with no reason | **D1-RC-7** |

**Failure:** **D1-RC-12** = partial propagation convergence.

##### 6. Temporal propagation ordering (mandatory)

D1 verifies **propagation event order** is operationally sane — not strict millisecond serialization.

**Expected propagation order (approximate):**

```
authority sync / evidence authority (when applicable)
  → gap sync observation (when matrix requires)
    → fanout enqueue observation (recalc)
      → risk regen delegate observation (when enqueued/debounced)
        → worker pickup (C1 — observe timestamp only)
          → recalc persist (C1/C2 — observe timestamp only)
```

| Clarification | Rule |
|---------------|------|
| **Bounded lag** | Worker/recalc steps may lag fanout observation within C1 §3 / C2 §3 bounds — not D1 failure alone |
| **Contradiction** | Fanout claims `enqueue_result=true` but no queue row ever appears (beyond SLA) → **D1-RC-5** |
| **Blocked-before-authority** | `rst_core_backbone_blocked_pre_authority_sync` must precede any claimed enqueue on blocked path |
| **Replay** | R2/R3 timelines must not introduce **new** ordering violations vs R1 |

**Artifact:** `convergence_order_timeline[]` in `d1_verification_report_{slug}.json` — `{ "t", "fanout_ready", "enqueue_observed", "queue_done", "ordering_violation": null | string }`.

##### 7. Fanout observation boundary (mandatory)

| Allowed during D1 | Forbidden during D1 |
|-------------------|---------------------|
| Read fanout traces, activation registry state, queue rows | Mutate `workflow_runtime_activation_registry` policy |
| Record `propagation_notice` / deferral copy when HTTP returns it (**L-009**) | Change `enqueue_compliance_recalc` contracts or unique indexes |
| Classify defects into **D1-RC-*** | Alter `authority_mutation_fanout` routing or matrix semantics |
| Defer remediation to **future D1-remediation sub-unit** (explicit approval) | Ship fanout fixes under D1 verification guise |
| Observe notification delegate rows | Redesign notification delivery (**F1**) |
| Reuse C2 control tenant for §8 | Scheduler topology / cron ownership changes |

**Rule:** D1 staging scripts are **read-only** with respect to fanout policy. Any code fix requires separate approved remediation unit — not bundled into initial D1 proof.

##### 8. Cross-tenant isolation (mandatory)

Reuse C2 §7c methodology adapted for **fanout fingerprints**:

| Surface | Control fingerprint |
|---------|---------------------|
| `transition_fanout` row count / hash sample for control property | No delta attributable to pilot D1-M1 R1–R3 window |
| Control queue fanout-related correlations | No new pilot-correlation rows on control `property_id` |
| Control `message_logs` / notification jobs | **Observe only** — count delta 0 for pilot-driven proof window (F1 not proven) |

**Baseline:** Capture control fanout snapshot at verification **run start** (same fingerprint algorithm as end). **RC-14 lesson:** do not compare legacy preflight fingerprints to revised end-state algorithms.

**Artifact:** `d1_unrelated_surface_integrity_{slug}.json` — `unrelated_mutation_delta`, `unrelated_mutation_count` (must be **0** on pass).

##### 9. Propagation convergence hashing (mandatory)

| Fingerprint key | Source (normalized) |
|-----------------|---------------------|
| `fanout_downstream_rows` | Sorted stable tuple of `(downstream_target, propagation_stage, enqueue_attempted, duplicate_suppression_reason)` |
| `fanout_branch_count` | Count of `downstream_rows[]` with `enqueue_attempted` or delegate trigger |
| `suppression_state` | Set of suppression reasons + activation blocked flags |
| `lineage_correlation` | `correlation_id` + `transition_id` + queue entity key |
| `regen_delegate` | Risk regen delegate row fingerprint (observe-only; C2a non-blocking id churn allowed in **task ids**, not in fanout row keys) |

**Replay pass:** `lineage_fingerprint_r2 == lineage_fingerprint_r3`; `fanout_fingerprint_r2 == fanout_fingerprint_r3`; `branch_count_r2 == branch_count_r3`.

**Artifact:** `d1_convergence_fingerprints_{slug}.json` — `{ "R1": {...}, "R2": {...}, "R3": {...}, "r2_equals_r3": true }`.

##### 9b. Delegated propagation lineage preservation (mandatory — rev 2)

Risk regen and other **delegated** fanout rows (`attach_risk_regen_delegate_row`, `regeneration_requeued`) must remain causally attached to the originating mutation.

| Verification | Pass criterion |
|--------------|----------------|
| **Authoritative ancestry** | `delegated_origin_correlation_id` on delegate summary matches parent `transition_fanout.correlation_id` |
| **No detached trees** | Delegate `downstream_target` rows reference same `transition_id` or explicit parent row index — no orphan delegate without parent trace |
| **Attributable branches** | `delegated_branch_fingerprint` stable on R2/R3 when §4b collapse applies |
| **C2 handoff** | Delegate observation does not contradict C2 priority/risk readiness unless `partial_convergence_reason` documented (§5b) |

**Artifact:** `d1_delegated_lineage_{slug}.json` — `delegated_lineage_summary[]`: `{ "downstream_target", "delegated_origin_correlation_id", "delegated_branch_fingerprint", "propagation_stage", "parent_transition_id" }`.

**Failure:** **D1-RC-14** = delegated lineage detachment.

##### 10. Governed exclusions and suppression provenance (mandatory)

Every **suppressed**, **blocked**, or **skipped** propagation path must record:

| Field | Requirement |
|-------|-------------|
| `duplicate_suppression_reason` or `activation_reason` | Non-empty governed string |
| `propagation_stage` | Identifies suppression point |
| `propagation_notice` (HTTP) | When route returns deferral — client-visible notice per **L-009** where in scope |
| Lineage | Same `correlation_id` or explicit `transition_id` on parent trace |

**Silent suppression** (row omitted, `enqueue_attempted` ambiguous, or blocked path with empty reason) → **D1-RC-7** — primary failure.

**Artifact:** `d1_suppression_map_{slug}.json` — all suppression/block paths indexed by `propagation_stage` with provenance fields.

##### 10b. Observability-noise stability (mandatory — rev 2)

Stable replay (R2/R3 on D1-M1) must **not** amplify operational noise.

| Delta field | Measures | Pass (R2/R3 vs R1 settled) |
|-------------|----------|----------------------------|
| `observability_noise_delta` | Count of distinct `compliance_fanout` log lines / `transition_downstream_row` debug emissions per correlation | **0** unexplained increase |
| `audit_noise_delta` | New `audit_logs` rows attributable to same `correlation_id` without semantic mutation | **0** |
| `blocked_overlay_noise_delta` | Repeated `merge_rst_core_backbone_activation_into_fanout` overlay churn without state change | **0** |

**Verification must prove stable replay does NOT:**

- spam propagation logs
- duplicate activation overlays on unchanged gate state
- create blocked-state churn (flip-flop `activation_reason` without gate change)
- generate audit amplification (duplicate lifecycle events for identical replay)
- produce false-positive operational noise that implies new propagation when cardinality unchanged (§3b)

**Artifact:** `d1_observability_noise_{slug}.json` — per run: `{ "run", "observability_noise_delta", "audit_noise_delta", "blocked_overlay_noise_delta", "noise_pass": bool }`.

**Failure:** **D1-RC-15** = observability amplification / noise churn.

##### 10c. Suppression determinism (mandatory — rev 3)

D1 verifies **deterministic suppression behaviour** across replay — distinct from suppression **provenance** (§10) and observability **noise** (§10b). **Governance of suppression stability** — **not** suppression-system redesign.

| Requirement | Pass criterion |
|-------------|----------------|
| **Identical replay → identical suppression** | R2 and R3 produce same `suppression_fingerprint` as each other and match R1 settled suppression state |
| **Overlay stability** | `blocked_overlay_noise_delta` = 0 (§10b) and suppression reasons unchanged on unchanged gate |
| **Blocked/suppressed branches replay-stable** | `activation-blocked` and `quiet-suppressed` branches: same `duplicate_suppression_reason` / `activation_reason` on R2/R3 |
| **No inconsistent suppression states** | `suppression_replay_equal=true`; no flip between suppressed vs attempted-without-reason across R2/R3 |

**Capture in** `d1_suppression_determinism_{slug}.json` **and report:**

| Field | Type |
|-------|------|
| `suppression_fingerprint_r1_r2_r3` | `{ "R1": hash, "R2": hash, "R3": hash, "r2_equals_r3": bool }` |
| `suppression_state_matrix[]` | Per branch: `{ "downstream_target", "R1_reason", "R2_reason", "R3_reason", "stable": bool }` |
| `suppression_replay_equal` | bool — **true** on pass |

**Failure:** **D1-RC-18** = suppression inconsistency.

##### 11. Failure taxonomy (mandatory)

Classify staging failures into **one primary branch** (secondary tags allowed):

| Branch | ID | Symptom / detection | Primary authority |
|--------|-----|---------------------|-------------------|
| Propagation amplification | **D1-RC-1** | R2/R3 add unexplained `downstream_rows` or `branch_count` vs R1 | `authority_mutation_fanout`, `requirement_transition_observability` |
| Orphan fanout | **D1-RC-2** | `enqueue_attempted=true` with no queue row and no suppression reason | Fanout attach helpers |
| Lineage divergence | **D1-RC-3** | R2/R3 fanout/lineage fingerprint ≠ R1; forked ancestry | `transition_fanout`, queue correlation index |
| Activation-gated suppression | **D1-RC-4** | Blocked path missing `activation_reason` / overlay | `workflow_runtime_activation_registry` |
| Temporal contradiction | **D1-RC-5** | Fanout claims success but downstream never materializes beyond SLA; impossible stage order | Fanout stages vs C1 queue timeline |
| Cross-tenant bleed | **D1-RC-6** | Control fanout/queue fingerprints change during pilot window | §8 isolation |
| Silent suppression | **D1-RC-7** | Skipped enqueue/block without governed reason in trace or HTTP notice | **L-009**, fanout rows |
| Replay instability | **D1-RC-8** | R2≠R3 fanout or suppression fingerprints | Replay methodology §4 |
| Matrix wiring drift | **D1-RC-9** | Observed fanout contradicts `STREAM_E_MUTATION_FANOUT_MATRIX.md` row for selected mutation | Matrix vs code — **observe**; fix deferred to remediation unit |
| Downstream churn despite stable fanout | **D1-RC-10** | Fanout stable but C2 surfaces drift — escalate to C2/C1 regression, not D1 fanout fix | C2 artifacts |
| Propagation cardinality drift | **D1-RC-11** | `unexpected_branch_count` > 0; R2/R3 cardinality ≠ R1 without documented collapse; missing expected targets | §3b, `d1_branch_cardinality_*` |
| Partial propagation convergence | **D1-RC-12** | `propagation_completion_matrix` shows expected branch fanout-observed but downstream incomplete beyond SLA; `partial_convergence_reason` set | §5b, `d1_partial_convergence_*` |
| Replay collapse inconsistency | **D1-RC-13** | Non-deterministic `replay_collapse_state`; `retained_lineage_visibility=false`; hidden collapsed branches | §4b |
| Delegated lineage detachment | **D1-RC-14** | Delegate rows without `delegated_origin_correlation_id`; detached causal tree | §9b, `d1_delegated_lineage_*` |
| Observability amplification / noise churn | **D1-RC-15** | Non-zero noise deltas on stable replay; log/audit/overlay spam | §10b, `d1_observability_noise_*` |

**C2 cross-reference:** C2-RC-10 (fanout blocked observe-only) findings feed D1 proof requirements but are **not** reclassified as D1 pass/fail unless D1-M5 exercised.

**RC distinction (rev 2):**

| Symptom | Primary RC |
|---------|------------|
| Branch count wrong / extra undeclared branch | **D1-RC-11** |
| Some branches complete, others stall silently | **D1-RC-12** |
| Collapse hides lineage or varies R2 vs R3 | **D1-RC-13** |
| Delegate lost parent correlation | **D1-RC-14** |
| Logs/audits/overlays multiply on replay | **D1-RC-15** |
| `enqueue_attempted=true`, no queue, no reason | **D1-RC-2** (orphan — not partial) |
| Blocked with empty reason | **D1-RC-7** (silent — not partial) |

##### 12. Regression tests required (implementation phase — not yet run)

Extend / add (names indicative); all must pass before **VERIFIED**:

| Test area | File (existing or new) | Assertions |
|-----------|------------------------|------------|
| Fanout phase 4 | `test_requirement_transition_fanout_phase4.py` | Downstream row attachment, backbone gate blocked path |
| Fanout phase 5 / document | `test_requirement_transition_document_fanout_phase5.py` | Document transition fanout health |
| Fanout planning | `test_workflow_requirement_transition_fanout_planning.py` | Normalized fanout context |
| Fanout logging | `test_compliance_fanout_log.py` | Structured fanout extra fields |
| Propagation fingerprint contract | **new** `test_d1_propagation_fingerprint_contract.py` | Stable mock replay → equal fanout hash |
| Replay amplification | **new** `test_d1_replay_no_fanout_amplification.py` | R2=R3 branch count on stable correlation mock |
| Suppression provenance | **new** `test_d1_suppression_provenance_required.py` | Blocked/duplicate paths always carry reason |
| Activation observability | **new** `test_d1_activation_gate_fanout_overlay.py` | `merge_rst_core_backbone_activation_into_fanout` fields present when blocked |
| Cross-tenant isolation | **new** `test_d1_unrelated_fanout_non_mutation.py` | Pilot fanout mock does not mutate control trace |
| Lineage determinism | **new** `test_d1_fanout_lineage_determinism.py` | correlation_id chains to queue mock |
| Propagation cardinality | **new** `test_d1_propagation_cardinality_contract.py` | expected/actual/suppressed/blocked/unexpected counts |
| Partial convergence | **new** `test_d1_partial_propagation_convergence.py` | completion matrix detects incomplete subtrees |
| Replay collapse | **new** `test_d1_replay_collapse_determinism.py` | R2=R3 collapse state; lineage visibility retained |
| Delegated lineage | **new** `test_d1_delegated_lineage_preservation.py` | delegate rows carry `delegated_origin_correlation_id` |
| Observability noise | **new** `test_d1_observability_noise_stable_replay.py` | zero noise deltas on stable replay mock |
| Stream F correlation | `test_stream_f_correlation_propagation_contract.py` | No regression — fanout→score correlation |
| L-009 HTTP (observe) | L-009 propagation_notice suites | Optional gate when D1-M3 returns notice |
| C1 + C2 regression (no regress) | C1 + C2 suites | Still green after any D1 script merge |

**CI:** D1 suite + fanout phase suites + C1/C2 suites green; staging scripts are not a substitute for unit tests.

##### 13. Required artifacts (mandatory)

All under `backend/docs/audit/` with slug `{client_id_8}_{property_id_8}`:

| Artifact | Contents |
|----------|----------|
| `d1_fanout_before_{slug}.json` | Pre-mutation fanout/queue correlation sample for pilot + control baseline |
| `d1_fanout_after_{slug}.json` | Post-R1 settled fanout traces |
| `d1_propagation_replay_{slug}.json` | R1/R2/R3 (+ optional M2) per-run fanout fingerprints |
| `d1_propagation_topology_{slug}.json` | Expected vs observed downstream targets per mutation |
| `d1_lineage_trace_{slug}.json` | Fanout → queue → score history / audit join samples |
| `d1_suppression_map_{slug}.json` | All suppression/block paths with provenance |
| `d1_convergence_fingerprints_{slug}.json` | R1/R2/R3 hashes; `r2_equals_r3` |
| `d1_unrelated_surface_integrity_{slug}.json` | Control tenant delta (§8) |
| `d1_control_selection_{slug}.json` | Control CID/PID + selection reason |
| `d1_verification_report_{slug}.json` | `d1_pass`, `checks{}`, `primary_rc_branch`, `propagation_cardinality_summary[]`, `propagation_completion_matrix[]`, `replay_collapse_state`, `branch_growth_curve[]`, `bounded_growth_pass`, `suppression_replay_equal`, behaviour-class summary, timelines, artifact index |
| `d1_branch_cardinality_{slug}.json` | Per-run expected/actual/suppressed/blocked/unexpected branch counts (§3b) |
| `d1_partial_convergence_{slug}.json` | `expected_vs_completed_branches`, `partial_convergence_reason` (§5b) |
| `d1_delegated_lineage_{slug}.json` | `delegated_lineage_summary[]` (§9b) |
| `d1_observability_noise_{slug}.json` | `observability_noise_delta`, `audit_noise_delta`, `blocked_overlay_noise_delta` (§10b) |

**Proposed scripts (implementation phase — optional):** `scripts/d1_snapshot.py`, `scripts/d1_preflight_capture.py`, `scripts/d1_staging_verification.py` — read-only snapshots + HTTP drivers (mirror C1/C2 pattern).

##### 14. Completion gates

| Gate | Requirement |
|------|-------------|
| **Start `IN_PROGRESS`** | D1 DoD rev 2 **approved**; pilot + control identified; C1/C2 artifacts retained |
| **`IMPLEMENTED_PENDING_VERIFICATION`** | D1 scripts/tests merged (verification only unless separate remediation approved) |
| **`READY_FOR_STAGING_VERIFICATION`** | All §13 artifacts captured on staging |
| **`VERIFIED`** | §1–§11 + §3b, §4b, §5b, §9b, §10b pass on staging report |
| **`DONE`** | §12 tests green; §15 docs updated; remediation deferral list documented |

**D1 cannot move to DONE unless all proven on staging:**

1. Propagation topology matches matrix expectations for selected mutations (§3).
2. **Replay-safe** — R2/R3 fanout fingerprints and branch counts stable on D1-M1 (§4, §9).
3. **Lineage-stable** — no orphan or divergent fanout trees (§5).
4. **Suppression explainable** — no silent suppression (§10).
5. **Cross-tenant isolated** — unrelated fanout delta **0** (§8).
6. **Temporally sane** — no persistent propagation ordering contradiction beyond SLA (§6).
7. **No hidden amplification** — unexplained downstream row growth on replay (§4).
8. Legitimate new-correlation mutation (D1-M2) still propagates when expected (§4).
9. Fanout observation remained **non-mutating** for policy/topology (§7).
10. No notification/scheduler/queue-topology semantics change shipped under D1 guise (§7, §15).
11. **Propagation cardinality stable** — `unexpected_branch_count=0`; R2/R3 cardinality matches R1 or documented collapse (§3b, §4b).
12. **No partial propagation convergence** — `propagation_completion_matrix` complete within SLA (§5b).
13. **Replay collapse deterministic** — `replay_collapse_state` stable R2=R3; `retained_lineage_visibility=true` (§4b).
14. **Delegated lineage preserved** — no detached delegate trees (§9b).
15. **Observability stable under replay** — noise deltas **0** on R2/R3 (§10b).

**Unlock on DONE:** **D2** (legacy bridge review) parallel optional; **E1** DoD drafting — **not** F1, not fanout remediation without separate unit.

##### 15. Boundary clarification and governance updates

**D1 is verification and governance first.** Broad fanout remediation, activation-policy changes, or architecture replacement require a **separate approved remediation unit** (e.g. `D1b`) with its own DoD — not bundled into initial D1 proof.

| Document | Update on D1 **DONE** |
|----------|------------------------|
| `LAUNCH_AUTHORITY_TRACKER.md` | D1 closure evidence; unlock matrix |
| `RUNBOOK_CONTROLLED_BETA_OPERATIONS.md` §12.7 | Add **D1** substeps (fanout snapshots, replay, suppression map) |
| `CLOSED_LOOP_COMPLIANCE_ARCHITECTURE_TRACKER.md` | Stream E row — D1 DONE note |
| `STREAM_E_MUTATION_FANOUT_MATRIX.md` | Cross-ref only if observe findings — **no matrix rewrite** unless remediation approved |
| `GOVERNANCE_INDEX.md` | D1 → E1 handoff cross-ref if needed |
| `runbooks/SCHEDULER_AND_COMPLIANCE_JOBS.md` | Only if lag semantics change in code (**not** expected in D1 verification) |

**Explicit out-of-scope (reaffirmed — rev 2–3 additions remain verification-only):** queue topology redesign; queue suppression redesign; suppression-system redesign; replay-engine redesign; scheduler ownership redesign; `authority_mutation_fanout` architecture replacement; propagation architecture rewrite; event bus redesign; notification overhaul (**F1**); task-system redesign; activation-policy mutation during proof.

**Status:** **DONE** (2026-05-17) — see § **D1 — Closure evidence** below. **No product** route, fanout, queue, scheduler, or notification changes shipped.

##### D1 — Implementation phase note (verification only — 2026-05-16)

| Step | Command |
|------|---------|
| Preflight | `python -m scripts.d1_preflight_capture --client-id CID --property-id PID` |
| Staging | `python -m scripts.d1_staging_verification --artifact-prefix d1b --verification-run d1b_harness_rerun_v3 --client-id CID --property-id PID` |
| Regression | `pytest tests/test_d1_verification_contract.py tests/test_requirement_transition_fanout_phase4.py` |

**Pilot:** `6fd5ac4c-3fd4-4112-ade7-156977deb49f` / `d35a58ae-3c81-491c-9694-1d021dd3b8ad`. **D1-M1 driver:** `enqueue_compliance_recalc_with_fanout` (governed fanout path). Production client HTTP sync uses direct `enqueue_compliance_recalc` — documented in report; not remediated in D1.

---

### D1b — Verification harness refinement (micro-unit)

| Field | Value |
|-------|-------|
| **ID** | D1b |
| **Parent** | **D1** |
| **Priority** | P1 |
| **Trigger** | D1 staging `d1_pass=false` — **D1-RC-15** (overlay baseline false positive) + lineage window contamination from M2 |
| **Scope** | Verification methodology refinement only — `d1_staging_verification.py` + `d1_snapshot.py` noise/lineage windows |
| **Unit status** | **DONE** (2026-05-17) |
| **Verification evidence** | `docs/audit/d1b_verification_report_6fd5ac4c_d35a58ae.json` (`verification_run=d1b_harness_rerun_v3`); full `d1b_*` set; original `d1_*` preserved |

#### D1b — Definition of Done (rev 1 — 2026-05-17; **approved** — **DONE** 2026-05-17)

**Purpose:** Clear **D1-RC-15** and lineage false failures caused by harness methodology — **not** product propagation changes.

| # | Requirement | Pass criterion |
|---|-------------|----------------|
| 1 | **Observability noise baseline** | Compare suppression overlay to **prior replay state** (R2 vs R1, R3 vs R2); R1 establishes baseline — **not** `suppression_fingerprint(None)` |
| 2 | **Lineage windows split** | `lineage_replay_stable` = R2 vs R3 **correlation-attributed propagation** fingerprint (fanout + delegates) **before M2**; M2 uses separate global trace; property-wide history excluded from replay gate |
| 3 | **Preserve D1 artifacts** | All D1b outputs use `d1b_*` prefix; original `d1_*` unchanged |
| 4 | **Re-run staging** | `python -m scripts.d1_staging_verification --artifact-prefix d1b --verification-run d1b_harness_rerun` |
| 5 | **Production path** | Remains **open governance context only** — **no** `routes/properties.py` change |

**Explicitly forbidden:** propagation logic changes; fanout topology; queue semantics; route changes; `_with_fanout` on production HTTP path; notifications/scheduler/E1/F1.

**Closure (2026-05-17):** `d1b_harness_rerun_v3` — `d1_pass=true`; **D1-RC-15** cleared (`noise_pass=true`); `lineage_replay_stable=true` (correlation-attributed propagation fingerprint); M2 observed under separate correlation. Contract tests: 8 passed (`test_d1_verification_contract.py`). D1 parent → **DONE**.

#### D1 — Closure evidence (2026-05-17 — **DONE**)

**Pilot:** `client_id=6fd5ac4c-3fd4-4112-ade7-156977deb49f`, `property_id=d35a58ae-3c81-491c-9694-1d021dd3b8ad`, `pleerity_staging`. **Control:** `04ceda9f-dd72-4b70-a6f5-809bef1b7b6a` / `6d939c70-06ab-4dc8-8b36-204958d2cdb3`.

| Outcome | Result |
|---------|--------|
| **D1b** | **DONE** — verification harness refinement only (noise baseline + split replay/M2 lineage windows) |
| **Authoritative staging** | `verification_run=d1b_harness_rerun_v3` → **`d1_pass=true`**; all `checks{}` green |
| **D1-RC-15** | Cleared as **harness baseline issue** (overlay compared to prior replay state, not null/run-start) |
| **Lineage replay** | **Stable** after split windows — R2/R3 correlation-attributed propagation fingerprint equal **before M2**; M2 legitimate new-correlation propagation observed separately |
| **Propagation instability** | **None found** — R2/R3 fanout fingerprints equal; suppression replay equal; collapse deterministic; delegated lineage intact |
| **Artifact authority** | **`d1b_*` authoritative for closure**; original **`d1_*` preserved** (first run `d1_pass=false`, harness false positives) |
| **Product changes** | **None** — no route, fanout topology, queue semantics, scheduler, or notification changes |

**Authoritative artifacts (`backend/docs/audit/`):** `d1b_verification_report_6fd5ac4c_d35a58ae.json`, `d1b_propagation_replay_*`, `d1b_propagation_topology_*`, `d1b_branch_cardinality_*`, `d1b_branch_behaviour_classes_*`, `d1b_partial_convergence_*`, `d1b_delegated_lineage_*`, `d1b_suppression_determinism_*`, `d1b_observability_noise_*`, `d1b_bounded_growth_*`, `d1b_lineage_trace_replay_*`, `d1b_lineage_trace_m2_*`, `d1b_unrelated_surface_integrity_*`, `d1b_fanout_after_*`. **Preserved (non-authoritative):** full `d1_*` set including `d1_verification_report_*`.

**Regression:** **8 passed** — `tests/test_d1_verification_contract.py`.

**Governance docs:** This tracker; `RUNBOOK_CONTROLLED_BETA_OPERATIONS.md` §12.7 D1; `CLOSED_LOOP_COMPLIANCE_ARCHITECTURE_TRACKER.md` Stream E / launch-unit row.

**Open governance context (not remediated in D1):** Production `POST /api/properties/{property_id}/requirements/sync` uses **direct** `enqueue_compliance_recalc`; D1 verification driver uses `enqueue_compliance_recalc_with_fanout`. Classified as **matrix drift / observability context only** — expected C1-only queue behaviour on production HTTP. **Route alignment requires a separate approved unit** with its own DoD if pursued.

**DONE gates (2026-05-17):** §14 staging proof complete; §12 contract tests green; §15 governance docs updated; remediation deferral list documented (production sync path only).

**Next approved step:** Draft **E1** Definition of Done only. **Do not** start E1 implementation, **F1**, notifications work, scheduler redesign, or fanout/topology remediation without separate approved unit.

---

### D2 — Legacy path and compatibility bridge review

| Field | Value |
|-------|-------|
| **ID** | D2 |
| **Priority** | P2 |
| **Trigger** | Parallel to D1 or after B stable |
| **Scope** | Classify bridges: transitional / deprecated / permanent; retirement conditions; no duplicate runtime authorities |
| **Canonical authority** | [PUBLISHED_REGISTRY_CLIENT_TRUTH_AUDIT.md](../PUBLISHED_REGISTRY_CLIENT_TRUTH_AUDIT.md); `WORKFLOW_BEHAVIOUR_GOVERNANCE.md` |
| **Code areas likely affected** | `REQUIREMENT_GENERATION_SOURCE_DB_RULE`, legacy_readonly paths, order workflow (out of scope for obligations) |
| **Unit status** | **NOT_STARTED** |
| **Verification evidence** | Inventory table in published-registry audit; deprecated paths tagged in tracker |
| **Governance docs after** | `PUBLISHED_REGISTRY_CLIENT_TRUTH_AUDIT.md`; `GOVERNANCE_INDEX.md` TIER_4 list |
| **Regression tests** | N/A unless deprecation removes path |
| **Rollback / safety** | Do not remove legacy_readonly without migration bucket |

---

### E1 — Evidence / document state authority

| Field | Value |
|-------|-------|
| **ID** | E1 |
| **Priority** | P0 |
| **Trigger** | After A–D stable for pilot tenant |
| **Scope** | Upload/verify/reject → authority state; no stale extraction overriding human review (**L-004**) |
| **Canonical authority** | `COMPLIANCE_CLIENT_STATUS_AUTHORITY.md`; `audit/AUTHORITY_WRITE_PATH_RECONCILIATION.md`; **L-004**, **L-005** |
| **Code areas likely affected** | `evidence_review_verify.py`, `document_operational_state.py`, extraction supersession services |
| **Unit status** | **VERIFIED** (2026-05-17) — DoD **rev 3 approved**; **E1a**/**E1b DONE**; authoritative proof `e1b_*`; parent **intentionally not DONE** (deepest truth-authority layer — governance review pause) |
| **Verification evidence** | § **E1 — Closure evidence (VERIFIED)** below; authoritative `e1b_verification_report_6fd5ac4c_d35a58ae.json`; preserved `e1_*`, `e1a_*` |
| **Governance docs after** | This tracker; **L-004** row; `audit/AUTHORITY_WRITE_PATH_RECONCILIATION.md`; `COMPLIANCE_CLIENT_STATUS_AUTHORITY.md`; `RUNBOOK_CONTROLLED_BETA_OPERATIONS.md` §12.7 E1; `CLOSED_LOOP_COMPLIANCE_ARCHITECTURE_TRACKER.md` |
| **Regression tests** | Evidence review / operational-state / authority-sync suites — see E1 §14 |
| **Rollback / safety** | Reconciliation jobs **dry_run** first; no raw Mongo authority edits; no bypass of `sync_requirement_evidence_authority` |

**Unlock (2026-05-17):** D1 **DONE** → E1 DoD **approved** → **IN_PROGRESS** (verification/governance only). **Do not** ship evidence-authority remediation, **F1**, notifications, scheduler redesign, queue/fanout remediation, or document-workflow redesign under E1 without separate approval.

---

#### E1 — Definition of Done (rev 3 — 2026-05-17; **approved**)

**Rev 2 additions (2026-05-17):** authority precedence hierarchy (§3a); replay-idempotent supersession semantics (§4b); authority collapse semantics (§4c); evidence-lineage boundedness (§11b); operational explainability verification (§6b); **E1-RC-16**–**E1-RC-20**; tightened DONE gates (§16).

**Rev 3 additions (2026-05-17):** authority-state cardinality (§3b); replay-stable reconciliation suppression (§3c); human-review immutability (§4d); authority-collapse boundedness (§4e); **E1-RC-21**–**E1-RC-24**; further DONE gate tightening (§16).

**Purpose:** Prove **deterministic evidence and document state authority** behaviour using **existing** governed semantics — principally `requirement_evidence_authority.sync_requirement_evidence_authority` via `authority_mutation_fanout.authority_sync_with_transition_observability`, `document_operational_state`, `evidence_review_state` / Evidence Review V2 lifecycle, extraction supersession and reconciliation, and client runtime projection (`requirement_client_runtime_surface`, `client_requirement_lifecycle`) — aligned to `COMPLIANCE_CLIENT_STATUS_AUTHORITY.md`, `audit/AUTHORITY_WRITE_PATH_RECONCILIATION.md`, and applicable `STREAM_E_MUTATION_FANOUT_MATRIX.md` rows. E1 verifies that governed evidence mutations produce **expected, attributable, replay-stable authority outcomes** — including **authority-state cardinality integrity**, **deterministic authority precedence resolution**, **replay-stable reconciliation suppression**, **human-review immutability**, **cross-layer consistency**, **replay-idempotent supersession**, **authority collapse determinism and boundedness**, **reconciliation convergence**, **bounded evidence lineage**, **operational explainability**, **lineage integrity**, **bounded authority history growth**, **temporally sane ordering**, and **cross-tenant isolation** — without silent suppression, authority amplification, parallel active authority branches, or contradictory evidence states.

**Upstream precondition (accepted):** A1 **DONE**, B1 **DONE**, C1 **DONE**, C2 **DONE**, C2a **DONE**, D1 **DONE**, D1b **DONE** on pilot tenant. Materialisation visibility, queue/recalc replay safety, downstream convergence, and propagation fanout determinism are **already proven**; E1 **consumes** those passes and does **not** re-prove full C1/C2/D1 suites except where evidence authority must chain to queue `correlation_id`, fanout `transition_id`, or downstream convergence samples.

**Pilot tenant (staging verification only):** `client_id=6fd5ac4c-3fd4-4112-ade7-156977deb49f`, `property_id=d35a58ae-3c81-491c-9694-1d021dd3b8ad`, `pleerity_staging`. **Control unrelated** entity pair documented in `e1_control_selection_{slug}.json` (may reuse D1/C2 control `04ceda9f…` / `6d939c70…`). Product logic must remain **tenant-agnostic** (no hardcoded IDs in services/tests).

**One-line boundary:** E1 proves **governed evidence/document authority is cardinality-correct (single active winner), precedence-deterministic, transition-correct, replay-stable (incl. supersession, reconciliation suppression, collapse + collapse-bounded), human-review-immutable, lineage-attributable and lineage-bounded, supersession-explainable, reconciliation-convergent, operationally reconstructable, cross-layer consistent, temporally sane, bounded, audit-stable, and cross-tenant isolated** — verification only within existing authority semantics.

##### 1. Scope and authoritative boundary (mandatory)

**E1 verifies (in scope):**

| Layer | What E1 proves |
|-------|----------------|
| **Evidence authority writer** | `sync_requirement_evidence_authority` outcomes: requirement evidence projection, gap sync side-effects where invoked, transition trace fields, `reconciliation_recommended` flags |
| **Authority entrypoints** | `authority_sync_with_transition_observability` on document verify (v1/v2), evidence review lifecycle, match resolution, extraction supersession paths that call authority sync |
| **Document operational state** | `document_operational_state` derived states vs persisted review/extraction fields — accepted / rejected / superseded / pending / reconciliation-needed semantics |
| **Evidence review state** | `effective_evidence_review_state` / V2 review events — verify, reject, reopen, supersede, external verify, mark-expired |
| **Supersession** | Extraction confirmation superseded by human review; `extraction_confirmation_superseded` / `superseded_by_admin_decision` alignment |
| **Reconciliation** | `evidence_extraction_reconciliation` — historical verified alignment, idempotent skip when aligned, dry_run scan semantics |
| **Client authority projection** | `project_requirement_row_client_runtime`, `client_lifecycle_state` / `evidence_authority` coherence after governed mutations |
| **Replay authority** | Stable re-invocation of same governed authority mutation does not contradict prior settled state |
| **Lineage** | Evidence mutations attributable via `correlation_id`, `transition_id`, document id, requirement id, audit event types |
| **Downstream handoff** | Authority mutation → gap sync / recalc enqueue **observable** where matrix expects (consume D1 fanout proof; do not redesign) |
| **Cross-tenant isolation** | Pilot evidence activity does not mutate control-tenant authority fingerprints |
| **Suppression provenance** | Blocked or deferred authority paths record governed reason — silent suppression is **E1 failure** |
| **Authority precedence** | Conflicting evidence signals resolve per governed precedence — lower authority cannot silently override higher (§3a) |
| **Supersession replay** | Stable replay does not re-supersede or oscillate review outcomes (§4b) |
| **Authority collapse** | Redundant authority writes collapse deterministically on replay with lineage retained (§4c) |
| **Evidence lineage boundedness** | Supersession / override / reconciliation ancestry remains finite on replay (§11b) |
| **Operational explainability** | Satisfied/rejected/superseded/reopened/externally-verified states reconstructable from governed history (§6b) |
| **Authority-state cardinality** | At most one active winning authority state per governed entity window; no parallel winners (§3b) |
| **Reconciliation suppression replay** | Identical replay → identical reconciliation suppression outcomes (§3c) |
| **Human-review immutability** | Human authoritative decisions preserved across replay/reconciliation/collapse (§4d) |
| **Collapse boundedness** | Collapse history and collapsed-lineage depth bounded on replay (§4e) |

**Authoritative evidence state owners (must not be duplicated in E1 proof):**

| Authority | Module / contract | Role |
|-----------|-------------------|------|
| Requirement evidence sync | `services/requirement_evidence_authority.py` — `sync_requirement_evidence_authority` | **Single writer** for evidence-driven requirement authority projection |
| Transition observability | `services/requirement_transition_observability.py` + `authority_mutation_fanout.py` | Wraps authority sync; attaches fanout / activation overlays |
| Document operational projection | `services/document_operational_state.py` | Derived presentation state — must align with review/extraction truth |
| Client runtime projection | `services/requirement_client_runtime_surface.py`, `services/client_requirement_lifecycle.py` | Client-visible status / lifecycle — must align with authority after sync |
| Client status doctrine | `COMPLIANCE_CLIENT_STATUS_AUTHORITY.md` | KPI vs operational-task divergence rules |
| Write-path reconciliation | `audit/AUTHORITY_WRITE_PATH_RECONCILIATION.md` | Canonical paths; optimistic verify promotion visibility (**L-004**) |

**Ownership boundaries (explicit — E1 does not verify):**

| Owner | Remains responsible for | E1 relationship |
|-------|-------------------------|-----------------|
| **D1 (D-layer)** | Propagation fanout topology, branch cardinality, suppression determinism on `transition_fanout` | E1 **consumes** D1 pass; may sample fanout rows after evidence mutations — does **not** re-prove full D1 replay matrix |
| **C1 (C-layer)** | `compliance_recalc_queue` enqueue/worker/reclaim/duplicate suppression | E1 may assert recalc **enqueued or suppressed with reason** after verify — does not re-open C1 unless authority path proves queue contract regression |
| **C2 (C-layer)** | Downstream gaps/risk/tasks/score convergence after recalc | E1 may spot-check post-authority convergence lag — does not re-run full C2 hash suite unless E1-RC implicates downstream churn |
| **F1** | Notifications, `message_logs`, template governance (**L-008**) | **Out of scope** — no notification proof |
| **Scheduler / jobs** | `job_runner`, reconciliation cron ownership, reclaim | **Observe only** — E1 does not redesign cadence |
| **AI extraction assistance** | OCR/extraction models, prompt tuning, enrichment pipelines | **Out of scope** — E1 verifies **governed outcomes** when extraction present (confirm/reject/supersede), not model quality |
| **Document storage** | Blob store, virus scan, upload transport | **Out of scope** — upload success assumed; authority semantics only |
| **Task / Today systems** | `unified_tasks_service`, volatile task ids (C2a watchlist) | **Out of scope** — may observe task deltas as secondary signal only |
| **Fanout / queue topology** | Routing, activation registry policy | **Out of scope** — observe traces only |

**E1 is NOT:** OCR redesign; extraction AI redesign; notification overhaul; workflow UI redesign; queue redesign; scheduler redesign; fanout redesign; storage redesign; broad authority architecture replacement; optimistic-promotion removal (unless separate **L-004** remediation unit); matrix rewrite.

##### 2. Governed evidence mutation sources (verification only)

Mutations must use **production HTTP/admin/service paths** that invoke `sync_requirement_evidence_authority` (directly or via `authority_sync_with_transition_observability`). **No raw Mongo** authority field injection. **No synthetic** evidence rows or fabricated review events in staging proof.

| ID | Endpoint / flow | Matrix row(s) (indicative) | Authority under test | Correlation / idempotency contract |
|----|-----------------|------------------------------|----------------------|-----------------------------------|
| **E1-M1 (primary replay)** | Governed **re-authority sync** on fixed `(requirement_id, document_id)` — e.g. repeat safe admin authority-sync backfill endpoint or duplicate `sync_requirement_evidence_authority` invocation via documented production wrapper | 6–9 | Same settled evidence state; no duplicate review outcomes | **Stable:** per-route correlation (e.g. `AUTHORITY_SYNC:{requirement_id}` or transition-provided id) |
| **E1-M2 (legitimate new evidence)** | Client document upload to requirement (`POST` client compliance evidence / documents upload) | 6–7 | New document row; initial operational state; first authority sync on verify path | **New:** `document_id` |
| **E1-M3 (verify — governed promotion)** | `POST` document verify (v1) or Evidence Review V2 verify (`execute_verify_document_v2`) on pilot-linked document | 6–7 | Authority sync + fanout; optional optimistic promotion marker (**L-004** observe) | `DOCUMENT_VERIFIED:…` / review correlation |
| **E1-M4 (reject / supersede review)** | Evidence Review V2 reject, mark-expired, supersede | 6–7 | Rejected/superseded operational state; authority must not show accepted | Per-handler correlation |
| **E1-M5 (extraction confirmation)** | Apply extraction accept/reject; supersession patch | 6–7 | `extraction_confirmation_superseded`; human review wins | Per document / extraction batch |
| **E1-M6 (evidence match resolution)** | Admin evidence match approve / reject / relink-merge | 6–9 | Match flags; `MATCH_RESOLVED_VERIFICATION_PENDING` vs verify distinction | Per match operation audit |
| **E1-M7 (reconciliation — controlled)** | `evidence_extraction_reconciliation` dry_run scan + **single** apply on pilot document (if fixture exists) | 6–9 | Historical alignment; idempotent skip when aligned | `RECONCILIATION:…` job correlation |
| **E1-M8 (external verify)** | Evidence Review V2 external verify (if pilot fixture) | 6–7 | `EXTERNALLY_VERIFIED` operational semantics | Per external verify event |
| **E1-M9 (blocked backbone observe)** | Same as E1-M3 with `rst_core_backbone_activation.permitted=false` capture **or** read-only blocked trace from audit | — | Authority sync skipped/deferred with explicit activation reason | N/A |

| Forbidden as proof | Reason |
|--------------------|--------|
| Raw Mongo `$set` on `requirements.evidence_*`, `documents.review_*`, or authority projection fields | Bypasses single writer |
| Direct `sync_requirement_evidence_authority` from ad-hoc scripts **not** mirroring production entrypoints | Not operator-reproducible |
| Fleet-wide reconciliation apply without pilot scoping | Amplification / blast radius |
| `requirements/sync` alone as evidence proof | Materialisation — B/C layer |
| Notification send as evidence authority proof | **F1** |
| Re-upload same bytes as “replay” without governed idempotency contract | Ambiguous — use **E1-M1** |

**Replay rule:** Use **E1-M1** only for R2/R3 authority fingerprint comparison on stable correlation. Use **E1-M2** / **E1-M3** once per window for legitimate new-evidence / first-verify proof. Do **not** use **E1-M2** upload for R2/R3 replay-idempotency.

##### 3. Evidence state authority verification (mandatory)

For each governed mutation (R1 and optional M3–M9), capture **authority snapshot** before/after:

| Check | Pass criterion |
|-------|----------------|
| **Authoritative transitions** | `sync_requirement_evidence_authority` outcome / transition trace matches matrix expectation (gap sync attempted or quiet with reason) |
| **Accepted / rejected / reopened** | Review state machine consistent: rejected docs not projected accepted; reopened returns to governed pending/verify path |
| **Supersession** | When human review supersedes extraction, operational state and persisted flags agree (`EVIDENCE_SUPERSEDED`, confirmation superseded) |
| **Reconciliation** | Re-run on aligned doc is no-op; misaligned doc converges in bounded passes |
| **Replay-safe authority** | R2/R3 on **E1-M1**: requirement authority fingerprint + document operational fingerprint **stable** |
| **No contradictory evidence states** | Same document cannot be simultaneously accepted-on-file and rejected without transition between runs |

**Artifact:** `e1_authority_snapshot_{slug}.json` — per run: document operational state, effective review state, requirement authority fields, gap sync summary, transition trace excerpt.

##### 3a. Authority precedence hierarchy (mandatory — rev 2)

When multiple evidence authority signals coexist on the same `(requirement_id, document_id)` window, E1 must verify **governed precedence resolution** — governance verification only; **no** authority-engine redesign.

**Governed precedence order (highest wins — indicative; document in report if code order differs but outcome matches):**

```
human review decision (verify / reject / supersede / reopen)
  → external verification (Evidence Review V2 external verify / EXTERNALLY_VERIFIED)
    → governed reconciliation outcome (historical alignment apply)
      → extraction assistance state (confirmation pending / accepted / rejected)
        → inferred / document heuristics (legacy status, operational inference only)
```

| Requirement | Pass criterion |
|-------------|----------------|
| **Deterministic resolution** | Same input evidence state → same winning authority source on replay |
| **Explainable precedence** | Every conflict records `winning_authority_source` and `overridden_authority_sources[]` |
| **No silent override** | Lower-precedence signal cannot override higher-precedence settled decision without governed transition |
| **Reconciliation subordination** | Reconciliation cannot resurrect rejected human review without governed reopen path |
| **Extraction subordination** | Extraction confirmation cannot override settled human reject without supersession/reopen semantics |

**Report fields (per conflict sample):** `authority_precedence_resolution[]` — `{ "entity_key", "conflicting_sources": [...], "winning_authority_source", "overridden_authority_sources": [...], "resolution_reason", "precedence_pass": bool }`.

**Artifact:** `e1_authority_precedence_{slug}.json`.

**Failure:** **E1-RC-16** = authority precedence violation.

##### 3b. Authority-state cardinality verification (mandatory — rev 3)

E1 must verify **active authority-state cardinality** — governance verification only; **no** authority-writer redesign. Distinct from general history growth (§11) and lineage depth (§11b).

| Field | Definition |
|-------|------------|
| `expected_active_authority_count` | **1** winning active authority state per governed `(requirement_id, document_id)` window after settlement |
| `actual_active_authority_count` | Count of concurrently “winning” terminal/active states observed |
| `unexpected_parallel_authority_count` | Parallel winners, duplicate active terminals, or conflicting active branches |
| `authority_cardinality_pass` | `unexpected_parallel_authority_count == 0` |

**Verification must prove replay/reconciliation cannot create:**

| Failure mode | Pass = absent on R2/R3 |
|--------------|------------------------|
| Duplicate active authority states | ≤1 active winner |
| Multiple simultaneous winning states | Single `winning_authority_source` |
| Parallel supersession winners | One supersession chain head |
| Duplicate externally-verified terminal states | ≤1 EXTERNALLY_VERIFIED terminal |
| Conflicting active authority branches | No forked active branches without governed transition |

**Artifact:** `e1_authority_cardinality_{slug}.json` — per-run counts + `authority_cardinality_pass`.

**Failure:** **E1-RC-21** = authority cardinality drift.

##### 3c. Replay-stable reconciliation suppression semantics (mandatory — rev 3)

E1 verifies reconciliation **convergence** (§3) **and** replay-stable **suppression** behaviour on dry_run/apply — governance semantics only; **not** reconciliation-engine redesign.

| Field | Definition |
|-------|------------|
| `reconciliation_suppression_fingerprint_r1_r2_r3` | Fingerprints of suppression/skip outcome per R1/R2/R3 |
| `reconciliation_replay_equal` | R2=R3 suppression fingerprints on stable replay |
| `reconciliation_suppression_matrix[]` | `{ "run", "dry_run_outcome", "apply_outcome", "suppression_reason", "reopen_suppress_state" }` |

| Requirement | Pass criterion |
|-------------|----------------|
| **Identical replay → identical suppression** | R2/R3 produce same skip/apply/suppress decision on aligned doc |
| **dry_run/apply parity** | dry_run prediction matches apply outcome (no oscillation) |
| **No reopen/suppress oscillation** | Replay does not flip reconciliation reopen vs suppress |
| **Explainable suppression** | Every suppressed/skipped apply has `suppression_reason` |

**Artifact:** `e1_reconciliation_suppression_{slug}.json` (cross-ref `e1_reconciliation_summary_*`).

**Failure:** **E1-RC-22** = reconciliation suppression inconsistency.

##### 4. Evidence replay determinism (mandatory)

| Requirement | Pass criterion | Failure |
|-------------|----------------|---------|
| **Stable replay** | R2/R3 **E1-M1**: `authority_fingerprint_r2 == authority_fingerprint_r3` | **E1-RC-2** |
| **No duplicate authority mutations** | R2/R3 do not create duplicate review events, duplicate gap lifecycle writes, or duplicate authority history entries for same stable correlation | **E1-RC-9** |
| **Reconciliation replay** | Second reconciliation apply on aligned pilot doc: `skipped` / no field churn | **E1-RC-5** |
| **Legitimate new mutation** | **E1-M2** or first **E1-M3** on new doc: new review/audit lineage; downstream propagation observable per D1 matrix | — |
| **Optimistic promotion visibility** | If v1/v2 verify performs pre-authority promotion, fanout/audit carries `pre_authority_optimistic_requirement_promotion` — final state matches post-sync authority (**L-004**) | **E1-RC-1** if final contradicts sync |

**Artifact:** `e1_replay_{slug}.json` — per-run fingerprints, `replay_authority_drift[]` (empty on pass).

##### 4b. Replay-idempotent supersession semantics (mandatory — rev 2)

E1 must verify **supersession consistency** (§3) **and** replay-safe supersession **idempotency** — governance semantics only; **not** reconciliation redesign.

| Requirement | Pass criterion |
|-------------|----------------|
| **No repeated supersede** | R2/R3 on **E1-M1** do not re-apply supersession patches or re-write `extraction_confirmation_superseded` |
| **No reopen/close oscillation** | Stable replay cannot flip rejected ↔ accepted ↔ superseded without governed transition between runs |
| **Reconciliation supersession stable** | Repeat reconciliation on aligned doc does not oscillate supersession outcome |
| **Deterministic supersession chain** | `supersession_state_fingerprint` equal R2=R3 on stable replay |
| **Replay equality** | `supersession_replay_equal=true` when fingerprints match |

**Report fields:** `supersession_replay_equal`, `supersession_state_fingerprint` (per run), `supersession_transition_matrix[]` — `{ "run", "from_state", "to_state", "trigger", "governed": bool }`.

**Artifact:** `e1_supersession_replay_{slug}.json` (includes `e1_supersession_map_{slug}` cross-ref).

**Failure:** **E1-RC-17** = supersession replay oscillation.

##### 4c. Authority collapse semantics (mandatory — rev 2)

Analogous to C1/D1 replay-collapse: stable replay may **collapse** redundant authority writes while retaining lineage visibility — verification only; **not** writer redesign.

| Field | Definition |
|-------|------------|
| `authority_collapse_state` | `collapsed_stable` \| `expanded` \| `inconsistent` |
| `collapsed_authority_mutations[]` | Redundant writes suppressed on R2/R3 with governed reason (e.g. idempotent sync skip, duplicate review outcome suppressed) |
| `retained_authority_visibility` | Collapsed paths remain visible in transition trace / audit — not hidden |

| Requirement | Pass criterion |
|-------------|----------------|
| **Collapse on replay** | R2/R3 may suppress redundant authority writes when already settled |
| **Deterministic collapse** | `authority_collapse_state` identical R2=R3 |
| **Lineage retained** | `retained_authority_visibility=true`; collapsed mutations listed with reason |
| **Explainable collapse** | Each collapsed entry has `collapse_reason` (not silent) |

**Artifact:** `e1_authority_collapse_{slug}.json`.

**Failure:** **E1-RC-18** = authority collapse inconsistency.

##### 4d. Human-review immutability protection (mandatory — rev 3)

E1 must explicitly verify **preservation of human authoritative decisions** across replay, reconciliation, and collapse — verification only; **not** review-workflow redesign. Extends **E1-RC-15** (extraction override) with replay/reconciliation/collapse erosion checks.

| Field | Definition |
|-------|------------|
| `human_review_preservation_pass` | All pilot human-review settlements preserved on R2/R3 |
| `review_override_attempts[]` | Any attempt to downgrade/erase human outcome — must be empty on pass |
| `preserved_human_authority_count` | Count of settled human decisions still authoritative after replay window |

| Requirement | Pass criterion |
|-------------|----------------|
| **Replay cannot erase human outcomes** | R2/R3 do not clear/revert human verify/reject/supersede without governed reopen |
| **Reconciliation cannot downgrade** | Reconciliation apply does not weaken human terminal state |
| **Extraction cannot override preserved review** | Reprocessing does not resurrect extraction over settled human reject |
| **Collapse cannot mutate human lineage** | Collapsed writes do not remove human review events from reconstructable history |

**Artifact:** `e1_human_review_preservation_{slug}.json`.

**Failure:** **E1-RC-23** = human review erosion.

##### 4e. Authority-collapse boundedness (mandatory — rev 3)

Extends §4c collapse **semantics** with replay **boundedness** — governance only; **no** collapse-engine redesign.

| Field | Definition |
|-------|------------|
| `collapse_history_growth` | Δ collapsed-entry count R2 vs R3 (must be **0**) |
| `collapse_growth_pass` | `collapse_history_growth == 0` and depth within cap |
| `collapsed_lineage_depth` | Depth of collapsed-authority ancestry chain |

| Requirement | Pass criterion |
|-------------|----------------|
| **Bounded collapse history** | `collapsed_authority_mutations[]` does not grow on R2/R3 |
| **No inflated collapsed ancestry** | `collapsed_lineage_depth` stable on replay |
| **Collapse lineage replay-stable** | Collapse fingerprint R2=R3 |
| **Metadata growth converges** | Collapse metadata churn Δ **0** on stable replay (or documented watchlist) |

**Artifact:** `e1_collapse_boundedness_{slug}.json` (cross-ref `e1_authority_collapse_*`).

**Failure:** **E1-RC-24** = authority collapse growth instability.

##### 5. Cross-layer authority consistency (mandatory)

After settled authority mutation (post-recalc lag bounds per C2 where recalc enqueued), verify operational consistency across:

| Layer | Sample | Pass criterion |
|-------|--------|----------------|
| **Document** | `document_operational_state` + persisted review fields | Coherent single story |
| **Evidence review** | V2 review events / `effective_evidence_review_state` | Matches operational state |
| **Requirement authority** | `evidence_authority`, semantic fields post-sync | Matches document satisfaction rules |
| **Client-visible** | `project_requirement_row_client_runtime` / `client_lifecycle_state` on pilot requirement | No KPI-authoritative surface contradicts authority (**COMPLIANCE_CLIENT_STATUS_AUTHORITY.md**) |
| **Downstream compliance** | Open gaps / risk signals sample (if triggered) | No gap contradicts accepted evidence without documented exclusion |

**Artifact:** `e1_cross_layer_consistency_{slug}.json` — `cross_layer_matrix[]`: `{ "layer", "entity_key", "fingerprint", "consistent": bool, "notes" }`.

**Failure:** **E1-RC-12** = cross-layer authority inconsistency.

##### 6. Evidence lineage integrity (mandatory)

| Requirement | Pass criterion |
|-------------|----------------|
| **Causal attribution** | Each authority mutation links `requirement_id`, `document_id` (if applicable), `correlation_id`, `transition_id` where produced |
| **Downstream preservation** | Gap sync / recalc samples retain originating correlation where matrix requires |
| **No detached trees** | No orphan `sync_requirement_evidence_authority` outcomes without document/requirement join |
| **No forked ancestry** | R2/R3 stable replay does not fork parallel authority chains for same stable correlation |
| **D1/C2 handoff** | Lineage must not contradict D1 `delegated_lineage_summary[]` or C2 `downstream_lineage_summary[]` on same pilot window |

**Artifacts:** `e1_lineage_trace_{slug}.json`; `e1_delegated_authority_lineage_{slug}.json` (if regen/recalc delegate observed).

**Failures:** **E1-RC-4** (detachment), **E1-RC-13** (orphan mutation).

##### 6b. Operational explainability verification (mandatory — rev 2)

E1 must prove operators can **reconstruct** why a requirement is **satisfied**, **rejected**, **superseded**, **reopened**, or **externally verified** from governed evidence state and history — verification of explainability only; **not** UI redesign.

**Reconstruction sources (all that apply must chain):**

| Source | Minimum sample |
|--------|----------------|
| Evidence lineage | `correlation_id`, document id, requirement id |
| Review actions | V2 review events / effective review state transitions |
| Supersession chain | `supersession_transition_matrix[]` / map |
| Reconciliation history | dry_run + apply summary |
| Propagation lineage | Fanout / queue correlation handoff (D1 sample) |

**Report fields:** `authority_explainability_summary[]` — `{ "requirement_id", "document_id", "operational_outcome", "reconstructable": bool, "sources_used": [...], "gaps": [] }`; `explainability_reconstruction_pass` (all pilot samples reconstructable).

**Artifact:** `e1_authority_explainability_{slug}.json`.

**Failure:** **E1-RC-20** = operational authority opacity (outcome not reconstructable from governed history).

##### 7. Temporal evidence ordering (mandatory)

Capture `evidence_order_timeline[]` ticks after each governed step:

| Expected order (indicative) | Violation |
|-----------------------------|-----------|
| Upload → review pending → verify/reject → authority sync → (optional) gap sync → (optional) recalc enqueue → downstream convergence within C2 lag | Downstream asserts **verified/compliant** before review completes |
| Reconciliation apply only after verify settlement when historical misalignment detected | Reconciliation writes before document review state settled |
| Supersession after extraction confirmation pending | Extraction confirmation re-surfaces after human reject without governed reopen |

**Bounded lag (reuse C2 defaults unless E1 amends):** authority projection immediate; gap/risk within C2 §3; recalc queue terminal within C1 poll bounds.

**Failure:** **E1-RC-8** = temporal contradiction.

**Artifact:** `e1_temporal_ordering_{slug}.json`.

##### 8. Replay amplification / duplication protection (mandatory)

| Check | Pass criterion |
|-------|----------------|
| **No duplicate authority writes** | R2/R3: requirement authority field delta **0** on stable replay |
| **No replay amplification** | Review event count, authority history count, gap lifecycle writes do not grow on R2/R3 |
| **No duplicate review outcomes** | Same verify cannot append second ACCEPTED event without governed reopen |
| **No reconciliation churn** | Repeated dry_run/apply on aligned doc: metadata `updated_at` churn only if documented (B1-style watchlist) |

**Failure:** **E1-RC-9** (amplification), **E1-RC-5** (reconciliation churn).

##### 9. Governed suppression / exclusion semantics (mandatory)

| Path | Must record |
|------|-------------|
| RST core backbone blocked | `activation_reason`, `enqueue_attempted=false` on fanout row |
| Verify blocked by evidence mismatch (409) | Structured error + no silent authority sync |
| Match resolution defer recalc | `propagation_notice` / fanout when backbone defers |
| Quiet gap sync (if invoked) | Matrix-documented quiet — not silent skip |

**Failure:** **E1-RC-7** (silent suppression), **E1-RC-14** (blocked without reason).

##### 10. Cross-tenant isolation (mandatory)

| Check | Pass criterion |
|-------|----------------|
| **Control tenant** | `e1_unrelated_surface_integrity_{slug}.json` — authority fingerprints on control `(CID', PID')` before/after pilot window: delta **0** |
| **No evidence bleed** | Pilot document ids do not appear on control requirements |
| **No review contamination** | Control document review states unchanged |

**Failure:** **E1-RC-6**.

##### 11. Authority cardinality and boundedness (mandatory)

| Metric | Pass criterion |
|--------|----------------|
| **Review events per document** | Bounded; R2/R3 replay does not add events |
| **Authority history growth** | `authority_history_curve[]` flat on R2/R3 |
| **Reconciliation passes** | Converges ≤ configured cap (pilot: document-scoped) |
| **Gap writes per replay** | No unexplained multiplication on **E1-M1** |

**Artifact:** `e1_authority_growth_{slug}.json`.

**Failure:** **E1-RC-11** (general authority growth — distinct from lineage-specific §11b).

##### 11b. Evidence lineage boundedness (mandatory — rev 2)

E1 must verify **evidence-lineage-specific** boundedness — observational/governance only; distinct from general cardinality (§11).

| Metric | Pass criterion |
|--------|----------------|
| `lineage_depth_growth` | Δ **0** on R2/R3 stable replay |
| `supersession_chain_growth` | Chain length stable; no new supersession links on replay |
| `override_chain_growth` | Override/precedence chain does not lengthen on replay |
| `reconciliation_ancestry_growth` | Reconciliation ancestry depth bounded; idempotent on aligned doc |
| `extraction_review_lineage_growth` | Extraction ↔ review lineage finite and stable on replay |
| `lineage_growth_pass` | All growth metrics pass |

**Artifact:** `e1_lineage_boundedness_{slug}.json` — curves + `lineage_growth_pass`.

**Failure:** **E1-RC-19** = unbounded evidence lineage growth.

##### 12. Observability and audit stability (mandatory)

| Check | Pass criterion |
|-------|----------------|
| **Audit noise** | R2/R3 stable replay: `audit_authority_event_delta == 0` for same correlation class |
| **Fanout log noise** | No new `compliance_fanout_extra` storms on replay (count delta 0) |
| **Overlay churn** | Suppression/activation overlays stable on replay (compare prior replay state — D1b pattern) |
| **Explainability** | Every non-zero delta has `governed_reason` |

**Artifact:** `e1_audit_stability_{slug}.json`.

**Failure:** **E1-RC-10**.

##### 13. Failure taxonomy (E1-RC branches)

| RC | Branch | When raised | Primary evidence |
|----|--------|-------------|------------------|
| **E1-RC-1** | Authority divergence | Final requirement/document authority contradicts governed transition outcome | `e1_authority_snapshot_*`, transition trace |
| **E1-RC-2** | Replay instability | `authority_fingerprint_r2 != authority_fingerprint_r3` on **E1-M1** | `e1_replay_*` |
| **E1-RC-3** | Supersession inconsistency | Extraction vs human review flags disagree with operational state | `e1_supersession_map_*` |
| **E1-RC-4** | Lineage detachment | Missing correlation / forked ancestry / broken document-requirement join | `e1_lineage_trace_*` |
| **E1-RC-5** | Reconciliation churn | Repeat apply mutates aligned doc or fails to converge | `e1_reconciliation_summary_*` |
| **E1-RC-6** | Cross-tenant bleed | Control tenant authority delta ≠ 0 | `e1_unrelated_surface_integrity_*` |
| **E1-RC-7** | Silent suppression | Blocked/deferred path without governed reason | fanout / API error body |
| **E1-RC-8** | Temporal contradiction | `evidence_order_timeline[]` violation | `e1_temporal_ordering_*` |
| **E1-RC-9** | Authority amplification | R2/R3 growth in events, history, or writes | `e1_authority_growth_*` |
| **E1-RC-10** | Audit-noise amplification | R2/R3 audit/fanout noise delta ≠ 0 | `e1_audit_stability_*` |
| **E1-RC-11** | Boundedness failure | Unbounded history / reconciliation / gap growth on replay | `e1_authority_growth_*` |
| **E1-RC-12** | Cross-layer inconsistency | Document vs requirement vs client projection disagree | `e1_cross_layer_consistency_*` |
| **E1-RC-13** | Orphan authority mutation | Authority sync without attributable entity keys | lineage trace |
| **E1-RC-14** | Blocked path without reason | Activation/match/verify block missing reason code | fanout row / HTTP |
| **E1-RC-15** | Extraction overrides human review | Stale extraction confirmation surfaces after reject without governed reopen | supersession map + operational state |
| **E1-RC-16** | Authority precedence violation | Lower-precedence signal overrides higher without governed transition | `e1_authority_precedence_*` |
| **E1-RC-17** | Supersession replay oscillation | `supersession_replay_equal=false` or reopen/close flip on R2/R3 | `e1_supersession_replay_*` |
| **E1-RC-18** | Authority collapse inconsistency | Non-deterministic `authority_collapse_state` or `retained_authority_visibility=false` | `e1_authority_collapse_*` |
| **E1-RC-19** | Unbounded evidence lineage growth | `lineage_growth_pass=false` on replay | `e1_lineage_boundedness_*` |
| **E1-RC-20** | Operational authority opacity | `explainability_reconstruction_pass=false` | `e1_authority_explainability_*` |
| **E1-RC-21** | Authority cardinality drift | `authority_cardinality_pass=false`; parallel active winners | `e1_authority_cardinality_*` |
| **E1-RC-22** | Reconciliation suppression inconsistency | `reconciliation_replay_equal=false` or dry_run/apply oscillation | `e1_reconciliation_suppression_*` |
| **E1-RC-23** | Human review erosion | `human_review_preservation_pass=false` | `e1_human_review_preservation_*` |
| **E1-RC-24** | Authority collapse growth instability | `collapse_growth_pass=false` | `e1_collapse_boundedness_*` |

**Primary RC selection order (staging report):** E1-RC-1 → E1-RC-21 → E1-RC-16 → E1-RC-23 → E1-RC-2 → E1-RC-17 → E1-RC-18 → E1-RC-24 → E1-RC-22 → E1-RC-12 → E1-RC-3 → E1-RC-19 → E1-RC-20 → E1-RC-4 → E1-RC-5 → E1-RC-7 → E1-RC-9 → E1-RC-10 → E1-RC-11 → E1-RC-6 → E1-RC-8 → others.

##### 14. Regression suites (mandatory — no product implementation in DoD draft)

**Existing suites (must pass before E1 DONE — baseline):**

| Suite | Role |
|-------|------|
| `tests/test_document_operational_state.py` | Operational state derivation |
| `tests/test_evidence_review_v2_phase1.py` | V2 verify/reject/validation |
| `tests/test_evidence_match_operations_http.py` | Match resolve, verify blocks, propagation notice |
| `tests/test_evidence_extraction_reconciliation.py` | Reconciliation idempotency |
| `tests/test_evidence_extraction_supersession.py` | Supersession patches |
| `tests/test_evidence_review_lifecycle_propagation_notice.py` | Lifecycle + notice |
| `tests/test_l005_evidence_review_v2_guard_contract.py` | V2 guard CI |
| `tests/test_requirement_transition_observability_phase3.py` | Transition traces |
| `tests/test_requirement_transition_fanout_phase4.py` | Fanout shape (handoff to D1) |
| `tests/test_client_compliance_evidence_safety.py` | Upload safety |
| `tests/test_patch_requirement_audit_http.py` | Audit ordering (matrix row 10) |

**Proposed E1 verification-only suites (implement in E1 verification phase — not in this draft):**

| Proposed file | Role |
|---------------|------|
| `tests/test_e1_verification_contract.py` | Mocked fingerprint / replay / supersession contract (mirror `test_d1_verification_contract.py`) |
| `tests/test_e1_authority_replay_determinism.py` | Stable replay → equal authority fingerprint |
| `tests/test_e1_cross_layer_consistency.py` | Document ↔ requirement ↔ client projection matrix |
| `tests/test_e1_supersession_lineage.py` | Human review supersedes extraction deterministically |
| `tests/test_e1_reconciliation_convergence.py` | Aligned skip / misaligned converge |
| `tests/test_e1_authority_precedence_resolution.py` | Precedence hierarchy / conflict resolution (proposed) |
| `tests/test_e1_supersession_replay_determinism.py` | `supersession_replay_equal` on stable replay (proposed) |
| `tests/test_e1_authority_collapse_determinism.py` | Collapse state R2=R3; visibility retained (proposed) |
| `tests/test_e1_lineage_boundedness.py` | Lineage growth metrics on replay (proposed) |
| `tests/test_e1_operational_explainability.py` | Reconstruction from governed history (proposed) |
| `tests/test_e1_authority_cardinality.py` | Single active winner; no parallel authority branches (proposed) |
| `tests/test_e1_reconciliation_suppression_replay.py` | `reconciliation_replay_equal` on stable replay (proposed) |
| `tests/test_e1_human_review_preservation.py` | Human outcomes preserved across replay (proposed) |
| `tests/test_e1_collapse_boundedness.py` | Collapse history growth bounded on replay (proposed) |

**Staging driver (IN_PROGRESS — verification only):** `scripts/e1_preflight_capture.py`, `scripts/e1_staging_verification.py`, `scripts/e1_snapshot.py` (read-only analysis). Governed mutations wired: **E1-M1** (`authority_sync_with_transition_observability`, stable `AUTHORITY_SYNC:{requirement_id}`), **E1-M7 observe** (`reconcile_document_extraction_supersession`, `dry_run=True` only). **E1-M2–M6, M8–M9** not wired in harness v1.

##### 15. Required artifacts (mandatory)

All under `backend/docs/audit/` with slug `6fd5ac4c_d35a58ae` (pilot) unless otherwise noted:

| Artifact | Contents |
|----------|----------|
| `e1_control_selection_{slug}.json` | Pilot + control entity ids |
| `e1_authority_before_{slug}.json` | Preflight authority baseline |
| `e1_authority_snapshot_{slug}.json` | Per-run authority + operational state |
| `e1_replay_{slug}.json` | R1/R2/R3 fingerprints, `replay_authority_drift[]` |
| `e1_supersession_map_{slug}.json` | Extraction vs review supersession decisions |
| `e1_authority_precedence_{slug}.json` | `authority_precedence_resolution[]`, winning/overridden sources (§3a) |
| `e1_authority_cardinality_{slug}.json` | Active authority counts, `authority_cardinality_pass` (§3b) |
| `e1_reconciliation_suppression_{slug}.json` | Suppression fingerprints, `reconciliation_replay_equal` (§3c) |
| `e1_supersession_replay_{slug}.json` | `supersession_replay_equal`, fingerprints, `supersession_transition_matrix[]` (§4b) |
| `e1_authority_collapse_{slug}.json` | `authority_collapse_state`, `collapsed_authority_mutations[]` (§4c) |
| `e1_collapse_boundedness_{slug}.json` | `collapse_growth_pass`, `collapsed_lineage_depth` (§4e) |
| `e1_human_review_preservation_{slug}.json` | `human_review_preservation_pass`, `review_override_attempts[]` (§4d) |
| `e1_reconciliation_summary_{slug}.json` | dry_run + apply outcomes |
| `e1_lineage_trace_{slug}.json` | correlation / transition / audit joins |
| `e1_lineage_boundedness_{slug}.json` | Lineage growth curves, `lineage_growth_pass` (§11b) |
| `e1_authority_explainability_{slug}.json` | `authority_explainability_summary[]`, reconstruction pass (§6b) |
| `e1_cross_layer_consistency_{slug}.json` | Layer consistency matrix |
| `e1_temporal_ordering_{slug}.json` | `evidence_order_timeline[]`, violations |
| `e1_authority_growth_{slug}.json` | Boundedness curves |
| `e1_audit_stability_{slug}.json` | Audit/fanout noise deltas |
| `e1_unrelated_surface_integrity_{slug}.json` | Control tenant before/after |
| `e1_verification_report_{slug}.json` | `e1_pass`, `checks{}`, `primary_rc_branch`, artifact index |

##### 16. Completion gates

| Gate | Requirement |
|------|-------------|
| **Start `IN_PROGRESS`** | E1 DoD **approved**; pilot + control identified; D1/C2 artifacts retained |
| **`IMPLEMENTED_PENDING_VERIFICATION`** | E1 scripts/tests merged (**verification only** unless separate remediation approved) |
| **`READY_FOR_STAGING_VERIFICATION`** | All §15 artifacts captured on staging |
| **`VERIFIED`** | §1–§13 + §3a–§3c, §4b–§4e, §6b, §11b pass on staging report |
| **`DONE`** | §14 tests green; §17 docs updated; deferral list documented |

**E1 cannot move to DONE unless all proven on staging:**

1. Evidence authority transitions are **deterministic** on governed paths (§3).
2. **Replay-safe** — R2/R3 authority fingerprints stable on **E1-M1** (§4).
3. **Lineage-stable** — no orphan or detached authority trees (§6).
4. **Supersession explainable** — human review wins over extraction with visible flags (§3, §9).
5. **Reconciliation convergent** — aligned skip; misaligned bounded converge (§3, §8).
6. **Cross-layer consistent** — document, review, requirement, client surfaces align (§5).
7. **Temporally sane** — `evidence_order_timeline[]` without contradiction (§7).
8. **Cross-tenant isolated** — unrelated authority delta **0** (§10).
9. **Bounded** — no authority amplification on replay (§8, §11).
10. **Audit-stable** — no replay audit/fanout noise (§12).
11. **Suppression explainable** — no silent blocked paths (§9).
12. Legitimate new evidence (**E1-M2** / first **E1-M3**) still propagates when expected (§4).
13. **Authority precedence deterministic** — conflicts resolve per §3a; no silent lower-over-higher override (**E1-RC-16**).
14. **Supersession replay-safe** — `supersession_replay_equal` on R2/R3; no oscillation (**E1-RC-17**).
15. **Authority collapse deterministic** — `authority_collapse_state` stable; `retained_authority_visibility=true` (**E1-RC-18**).
16. **Evidence lineage bounded** — `lineage_growth_pass=true` on replay (**E1-RC-19**).
17. **Operational explainability reconstructable** — `explainability_reconstruction_pass=true` (**E1-RC-20**).
18. **Authority cardinality stable** — `authority_cardinality_pass=true`; no conflicting active authority branches (**E1-RC-21**).
19. **Reconciliation suppression replay-stable** — `reconciliation_replay_equal=true` (**E1-RC-22**).
20. **Human authoritative decisions preserved** — `human_review_preservation_pass=true` (**E1-RC-23**).
21. **Collapse growth bounded** — `collapse_growth_pass=true` (**E1-RC-24**).
22. No notification/scheduler/queue-topology/OCR/storage/event-topology redesign shipped under E1 guise (§1, §17).

**Unlock on VERIFIED (2026-05-17):** **F1** DoD drafting — **not** F1 implementation. Parent E1 **not DONE** until explicit closure. **D2** remains optional parallel.

##### 17. Boundary clarification and governance updates

**E1 is verification and governance first.** Broad evidence-authority remediation, optimistic-promotion removal, workflow redesign, or extraction pipeline changes require a **separate approved remediation unit** (e.g. `E1b`, `L-004` closure) with its own DoD — not bundled into initial E1 proof.

| Document | Update on E1 **DONE** |
|----------|------------------------|
| `LAUNCH_AUTHORITY_TRACKER.md` | E1 closure evidence; unlock **F1** DoD drafting |
| `RUNBOOK_CONTROLLED_BETA_OPERATIONS.md` §12.7 | Add **E1** substeps (authority snapshots, replay, reconciliation) |
| `CLOSED_LOOP_COMPLIANCE_ARCHITECTURE_TRACKER.md` | Stream E / B evidence-authority row |
| `audit/AUTHORITY_WRITE_PATH_RECONCILIATION.md` | Cross-ref staging findings — **no rewrite** unless remediation approved |
| `COMPLIANCE_CLIENT_STATUS_AUTHORITY.md` | Cross-ref only if surface matrix gaps found |
| `STREAM_E_MUTATION_FANOUT_MATRIX.md` | Observe-only row notes — **no matrix rewrite** unless approved |
| **L-004** tracker row | Move toward **REDUCED** / closure only with explicit product decision |

**Explicit out-of-scope (reaffirmed — rev 2–3):** OCR/extraction model work; notification overhaul (**F1**); scheduler redesign; queue topology redesign; fanout routing changes (**D1** consumed); `unified_tasks` architecture; storage layer; admin UI redesign; **authority-engine redesign**; **reconciliation-engine redesign**; **review-workflow redesign**; **collapse-engine redesign**; **extraction pipeline redesign**; **workflow redesign**; **event-topology redesign**; production route alignment (`requirements/sync` → `_with_fanout`) — remains **D1 open governance** unless separate unit.

**Rev 2–3 clarifications (verification only):** §3a–§3c, §4b–§4e, §6b, and §11b are **governance observability** requirements — they do **not** authorize changing `sync_requirement_evidence_authority`, reconciliation algorithms, review state machines, or collapse writers in the E1 unit.

**Status:** **VERIFIED** (2026-05-17) — see § **E1 — Closure evidence (VERIFIED)** below. **Not DONE** in this pass (intentional governance pause). **E1a**/**E1b** micro-units **DONE**.

---

### E1a — Verification harness refinement (micro-unit)

| Field | Value |
|-------|-------|
| **ID** | E1a |
| **Parent** | **E1** |
| **Scope** | Fixture gating, semantic replay fingerprint normalization, vacuous-proof prevention, empty-supersession replay semantics, explainability fixture qualification |
| **Unit status** | **DONE** (2026-05-17) |
| **Verification evidence** | `e1a_verification_report_6fd5ac4c_d35a58ae.json` (`E1a-RC-FIXTURE` — pilot authority-incapable); `e1a_fixture_classification_*`; original `e1_*` preserved |

**Closure:** Pilot had 0 documents / 0 evidence-linked requirements. First `e1_*` run (`E1-RC-2`) reclassified as **fixture/harness insufficiency primary** — not evidence-authority product defect. Harness fail-fast + `e1a_*` authoritative rerun artifacts.

---

### E1b — Authority-capable staging fixture + governed replay proof (micro-unit)

| Field | Value |
|-------|-------|
| **ID** | E1b |
| **Parent** | **E1** |
| **Scope** | Governed staging fixture seed (`e1b_staging_fixture_seed.py`); E1-M1 + E1-M7 dry_run observe only; semantic replay proof |
| **Unit status** | **DONE** (2026-05-17) |
| **Verification evidence** | `e1b_fixture_seed_*`, `e1b_verification_report_6fd5ac4c_d35a58ae.json` (`e1b_pass=true`, `e1_authority_proof_ready=true`) |

**Fixture:** `gas_safety` requirement `c5abaeba-348f-4843-b734-1644bdfb791f` + document `07115f75-3f0b-4dae-aa9c-5bcd22c671db` (marker `E1b_authority_capable_v1`). Classification **authority-capable** before replay.

---

#### E1 — Closure evidence (VERIFIED — 2026-05-17)

**Pilot:** `client_id=6fd5ac4c-3fd4-4112-ade7-156977deb49f`, `property_id=d35a58ae-3c81-491c-9694-1d021dd3b8ad`, `pleerity_staging`. **Control:** `04ceda9f-dd72-4b70-a6f5-809bef1b7b6a` / `6d939c70-06ab-4dc8-8b36-204958d2cdb3`.

##### 1. E1 proof outcome

Governed evidence authority semantics are **proven stable** on an **authority-capable** fixture (`e1b_pass=true`, `primary_rc_branch=null`).

| Proven on E1b fixture | Result |
|------------------------|--------|
| Authority replay determinism (semantic) | **PASS** — `lineage_replay_stable_semantic=true` (R2=R3) |
| Supersession replay stability | **PASS** |
| Reconciliation replay stability (dry_run observe) | **PASS** |
| Authority cardinality integrity | **PASS** |
| Human-review preservation | **PASS** |
| Lineage boundedness | **PASS** |
| Operational explainability | **PASS** |
| Cross-layer consistency | **PASS** |
| Cross-tenant isolation | **PASS** — `unrelated_delta_zero` |

**Governed mutations in proof:** **E1-M1** (`authority_sync_with_transition_observability`); **E1-M7** observe (`reconcile_document_extraction_supersession`, `dry_run=True` only). **No** M2–M9 expansion.

##### 2. Fixture governance history (preserved — do not erase)

| Phase | Artifact authority | Outcome |
|-------|-------------------|---------|
| **Original E1** | `e1_*` preserved | `e1_pass=false`, **E1-RC-2** — pilot **authority-incapable** (0 documents, 0 `evidence_doc_id`) |
| **E1a** | `e1a_*` authoritative rerun | **E1a-RC-FIXTURE** — harness hardening, vacuous-proof prevention; fail-fast |
| **E1b** | `e1b_*` authoritative proof | `e1b_pass=true` — governed seed + semantic replay on **authority-capable** fixture |

Earlier RC classifications remain in preserved artifacts for audit.

##### 3. Replay normalization boundary (operational documentation)

| Normalized (verification only) | Not normalized |
|--------------------------------|----------------|
| `evidence_last_updated_at`, `evidence_last_verified_at` stripped from **semantic replay fingerprint** compare | Semantic authority state |
| Reconciliation suppression fingerprint excludes per-run `run`/`dry_run` labels | Precedence resolution |
| Empty supersession fingerprint: equality without truthiness gate | Lineage depth / supersession state |
| | Human-review state |

**Raw** authority fingerprint may still drift on timestamp churn (`lineage_replay_stable_raw_observability_only=false` on E1b) — recorded as **observability only**, not a verification failure.

##### 4. No remediation conclusion

| Item | Conclusion |
|------|------------|
| Evidence-authority product defect | **Not confirmed** |
| Authority-writer redesign | **Not required** (this pass) |
| Reconciliation redesign | **Not required** (this pass) |
| Extraction redesign | **Not required** (this pass) |
| Workflow redesign | **Not required** (this pass) |

##### 5. Remaining watchlist

- **Raw observability timestamp drift** may still occur on `sync_requirement_evidence_authority` replay (E1b: `timestamp_only_drift=true` on raw fingerprint).
- Normalization applies **only** to semantic replay proof gates — not to product writers.
- **No** product suppression/writer optimization performed under E1/E1a/E1b.
- E1b fixture is a **governed staging seed** (`E1b_authority_capable_v1`) — not a claim that all pilot properties have native evidence uploads.
- **DONE** gates (§14 full baseline suites, §17 doc sweep) intentionally deferred until explicit **DONE** approval.

##### 6. Governance posture — VERIFIED vs DONE

**E1 VERIFIED** means: evidence authority integrity is **proven under governed replay conditions** on an authority-capable fixture; parent unit **paused before DONE** for review discipline (deepest truth-authority layer in programme).

**E1 is not DONE** in this pass.

##### 7. Authoritative artifacts

| Set | Role |
|-----|------|
| **`e1b_*`** | **Authoritative for E1 VERIFIED** — `e1b_verification_report_6fd5ac4c_d35a58ae.json`, `e1b_replay_*`, full matrix |
| **`e1a_*`** | Harness refinement record |
| **`e1_*`** | First-run history (`E1-RC-2`, authority-incapable pilot) |

**Regression (harness):** `tests/test_e1_verification_contract.py`, `tests/test_e1a_verification_contract.py` — green.

**Unlock on VERIFIED:** **F1** Definition of Done **drafting only** — **not** F1 implementation.

**Next approved step (historical — superseded):** F1 staging → **VERIFIED** achieved 2026-05-17 via **F1a** authoritative rerun.

---

### F1 — Notification governance

| Field | Value |
|-------|-------|
| **ID** | F1 |
| **Priority** | P2 (pilot) |
| **Trigger** | **Only after A–E pass** |
| **Scope** | Eligibility; `NOTIFICATION_DISPATCH` global flag; orchestrator vs obligation health separation |
| **Canonical authority** | `audit/NOTIFICATION_GOVERNANCE_INVENTORY.json`; **L-008** |
| **Code areas likely affected** | `notification_orchestrator.py`, `jobs.py` — **not** materialisation |
| **Unit status** | **DONE** (2026-05-17) — DoD **rev 2**; governed **F1-M1** replay proof complete; **F1a DONE**; historical `f1_*` + **F1-RC-15** preserved |
| **Verification evidence** | **Authoritative:** `f1a_verification_report_6fd5ac4c_d35a58ae.json` (`f1a_harness_refinement_rerun_v1`, no critical stop, `failure_classification=governed_replay_proof_candidate`). **Preserved:** `f1_*` (first run, **F1-RC-15**). Harness: `f1a_snapshot.py`, `f1a_preflight_capture.py`, `f1a_staging_verification.py`; `test_f1_*` / `test_f1a_*` contract tests |
| **Governance docs after** | This tracker; `audit/NOTIFICATION_GOVERNANCE_INVENTORY.json`; `RUNBOOK_CONTROLLED_BETA_OPERATIONS.md` §12.7 F1; **L-008** cross-ref |
| **Regression tests** | L-008 + notification orchestrator suites — see F1 §8 |
| **Rollback / safety** | Do not globally activate `NOTIFICATION_DISPATCH` without program sign-off; no provider/template/queue changes under F1 guise |

**Unlock (2026-05-17):** F1 **DONE** — F-layer replay-governance proof complete for approved **F1-M1** scope. **G1/G2** continuous improvement unlocked. Future notification work requires **new governed verification units** or **explicitly approved remediation units** — **do not** silently extend F1 scope.

---

#### F1 — Definition of Done (rev 2 — 2026-05-17; **approved** — **DONE** 2026-05-17)

**Rev 2 additions (2026-05-17):** delivery authority precedence semantics (§4a); acknowledgement ambiguity handling (§4b); replay-visible user impact boundedness (§3k); notification lineage boundedness (§3l); **F1-RC-14**–**F1-RC-17**; tightened DONE gates (§9).

**Purpose:** Prove **truthful operational communication under replay and propagation conditions** using **existing** notification governance semantics — principally `services.notification_orchestrator`, `message_logs`, template/idempotency contracts (**L-008**, **L-008d/e**), preference enforcement, and governed send entrypoints aligned to `audit/NOTIFICATION_GOVERNANCE_INVENTORY.json` and `STREAM_E_MUTATION_FANOUT_MATRIX.md` (observe-only delegate rows). F1 verifies that governed notification paths produce **expected, attributable, replay-stable delivery observability** — including **truthful delivery-state semantics**, **delivery-authority precedence**, **acknowledgement ambiguity governance**, **dedupe determinism**, **lineage continuity and boundedness**, **replay-visible user impact boundedness**, **suppression replay stability**, **bounded retry/replay growth**, and **operational explainability** — without cross-tenant bleed, false “delivered” implication, authority precedence violations, or notification saturation.

**F1 governs truthfulness and determinism — not delivery success guarantees.** Provider acceptance, SMTP/API handoff, and end-user inbox receipt remain **observed** layers; no surface may claim **delivered** from enqueue or provider acceptance alone.

**Upstream precondition (accepted):** A1 **DONE**, B1 **DONE**, C1 **DONE**, C2 **DONE**, C2a **DONE**, D1 **DONE**, E1 **VERIFIED** on pilot tenant. Queue/recalc, propagation fanout, and evidence authority are **consumed**; F1 does **not** re-prove full C1/C2/D1/E1 suites except where notification lineage must chain to `correlation_id`, fanout delegate rows, or authority transitions.

**Pilot tenant (staging verification only):** `client_id=6fd5ac4c-3fd4-4112-ade7-156977deb49f`, `property_id=d35a58ae-3c81-491c-9694-1d021dd3b8ad`, `pleerity_staging`. **Control unrelated** tenant/property documented in `f1_control_selection_{slug}.json`. Product logic must remain **tenant-agnostic** (no hardcoded IDs in services/tests).

**One-line boundary:** F1 proves **governed notification observability is delivery-truthful, delivery-authority-correct, acknowledgement-ambiguity-explainable, dedupe-deterministic, replay-stable (incl. suppression and visible user impact), lineage-attributable and lineage-bounded, suppression-explainable, temporally sane, cross-tenant isolated, and operationally reconstructable** — verification only within existing notification semantics.

##### 1. Scope and authoritative boundary (mandatory)

**Layer separation (explicit):**

| Layer | Owner semantics | F1 proves |
|-------|-----------------|-----------|
| **Notification generation** | Orchestrator/template selection, semantic family, idempotency key construction | Generation produces **governed** intent records; no orphan intent without lineage |
| **Notification enqueue** | Internal queue/batch scheduling before provider handoff | Enqueue ≠ delivered; state labelled **queued** / **intended_to_send** only |
| **Provider delivery** | SMTP/API/provider adapters (`notification_orchestrator` internal) | **attempted** / **provider_accepted** distinct from **delivered** / **observed** |
| **Operational observability** | `message_logs`, audit samples, orchestrator outcomes | Truthful states; replay does not amplify noise |
| **User-visible communication state** | Client/admin surfaces, digests, alerts copy | No false delivery implication; blocked/suppressed visible with reason |

**F1 verifies (in scope):**

| Theme | What F1 proves |
|-------|----------------|
| **Notification truthfulness** | Recorded delivery states match governed semantics — no false “sent/delivered” from enqueue alone |
| **Replay-safe delivery semantics** | R2/R3 on stable correlation: notification intent fingerprint stable; no duplicate live sends |
| **Dedupe determinism** | Idempotency keys (`L-008d` reminders/alerts) — identical inputs → identical dedupe outcome |
| **Lineage / correlation propagation** | `correlation_id` / `transition_id` / `client_id` / `property_id` joinable across fanout → orchestrator → `message_logs` |
| **Operational explainability** | Operator can reconstruct why notified, suppressed, blocked, or deduped from governed history |
| **Delivery boundedness** | Retry/replay cycles do not grow unbounded notification rows or attempts |
| **Cross-tenant isolation** | Pilot notification activity does not mutate control-tenant `message_logs` fingerprints |
| **Suppression explainability** | Every suppressed/blocked path has governed reason — silent suppression is **F1 failure** |
| **Notification replay behaviour** | Branches classified: replay-collapsible, replay-regenerative, idempotent, etc. (§5) |
| **Delivery observability integrity** | `message_logs` + orchestrator outcomes internally consistent |
| **Delivery authority precedence** | No lower-trust source overrides higher-trust delivery truth (§4a) |
| **Acknowledgement ambiguity** | Ambiguous ack states explainable; no silent certainty upgrade on replay (§4b) |
| **Replay-visible user impact** | User-visible notification churn bounded on replay (§3k) |
| **Notification lineage boundedness** | Lineage depth/growth finite; collapse deterministic (§3l) |

**Ownership boundaries (explicit — F1 does not verify):**

| Owner | Remains responsible for | F1 relationship |
|-------|-------------------------|-----------------|
| **C1** | Recalc queue/worker | F1 may observe post-recalc notification triggers — does not re-prove queue |
| **D1** | Propagation fanout | F1 may sample notification delegate rows — does not re-prove fanout matrix |
| **E1** | Evidence authority | F1 may chain lineage — does not re-prove authority replay |
| **Scheduler / jobs** | `job_runner`, digest cron, retry reclaim | **Observe only** — no cadence redesign |
| **Provider SLA** | External email/SMS delivery success | **Out of scope** — observability truth only |

**F1 is NOT:** notification architecture rewrite; provider redesign; scheduler redesign; queue topology redesign; fanout redesign; event-bus redesign; workflow redesign; authority redesign; task-system redesign; template-system rewrite; global `NOTIFICATION_DISPATCH` activation without program sign-off.

##### 2. Governed mutation sources (verification only — do not widen yet)

Mutations must use **production orchestrator / documented HTTP paths**. **No raw Mongo** `message_logs` injection. **No synthetic** delivery fixtures in staging proof unless governed seed unit approved separately.

| ID | Source (examples) | F1 proves | Correlation contract |
|----|-------------------|-----------|----------------------|
| **F1-M1 (primary replay)** | Governed notification intent after **stable** upstream event — e.g. duplicate-safe compliance alert fingerprint path (**L-008d**) or orchestrator replay probe on fixed template + tenant scope | R2/R3 dedupe/suppression fingerprint stable | **Stable:** per governed idempotency key / `correlation_id` |
| **F1-M2** | Authority transition observable path (post-E1) — notification delegate row after `authority_sync` / verify | Lineage joins authority `correlation_id` | `AUTHORITY_SYNC:{requirement_id}` or route correlation |
| **F1-M3** | Propagation event — fanout notification delegate after D1-class mutation | Delegate row → orchestrator sample | `REQUIREMENTS_SYNC:{property_id}` or transition correlation |
| **F1-M4** | Notification retry path — governed retry/requeue observe | Retry bounded; no amplification on replay | Per retry job correlation |
| **F1-M5** | Digest generation (monthly/operational digest job) | Batch-scoped; bounded recipient cardinality | Per digest batch id |
| **F1-M6** | Escalation alert (SLA/risk monitor cluster) | Suppression + idempotency on replay | Per monitor fingerprint |
| **F1-M7** | Suppression overlay — preference off, duplicate_ignored, activation-blocked | Explicit suppression reason | N/A |
| **F1-M8** | Activation-blocked path — `NOTIFICATION_DISPATCH` off / workflow gate | **blocked** state with reason — not silent skip | N/A |

| Forbidden as proof | Reason |
|--------------------|--------|
| Raw Mongo insert into `message_logs` | Bypasses orchestrator |
| Direct deprecated `EmailService` send | **L-008** bypass risk |
| Fleet batch / marketing sends | Out of pilot scope |
| C1-M2 for replay-idempotency notification proof | New correlation by design |
| Claiming inbox delivery without observed layer | False delivery implication |

**Replay rule:** Use **F1-M1** only for R2/R3 notification fingerprint comparison on stable idempotency key. Use **F1-M5** / **F1-M6** once per window for legitimate batch/regenerative proof.

##### 3. Mandatory verification themes

###### 3a. Replay-safe notification semantics (mandatory)

| Check | Pass criterion |
|-------|----------------|
| **Stable replay** | R2/R3 **F1-M1**: notification intent fingerprint == prior settled state |
| **No duplicate live sends** | R2/R3 do not create additional `message_logs` rows with `status` implying send for same idempotency scope |
| **Suppression stable** | `duplicate_ignored` / `suppressed` outcomes identical on R2/R3 |

**Artifact:** `f1_notification_replay_{slug}.json` — per-run fingerprints, `replay_notification_drift[]` (empty on pass).

**Failure:** **F1-RC-1** = notification replay drift; **F1-RC-2** = replay amplification.

###### 3b. Duplicate suppression determinism (mandatory)

| Field | Definition |
|-------|------------|
| `expected_dedupe_outcome` | `sent` \| `duplicate_ignored` \| `suppressed` \| `blocked` per governed contract |
| `actual_dedupe_outcome` | Observed orchestrator + `message_logs` outcome |
| `dedupe_deterministic` | R2/R3 outcomes equal on stable key |

**Failure:** **F1-RC-3** = duplicate delivery drift.

###### 3c. Lineage / correlation continuity (mandatory)

| Check | Pass criterion |
|-------|----------------|
| **Joinable lineage** | Sample rows chain: upstream event → orchestrator call → `message_logs` with same `client_id` / `correlation_id` where applicable |
| **No detached notifications** | No `message_logs` without attributable upstream trigger class |
| **Delegate continuity** | Fanout notification delegate rows (if present) reference same correlation as parent transition |

**Artifacts:** `f1_lineage_trace_{slug}.json`; `f1_correlation_matrix_{slug}.json`. **Lineage growth boundedness:** §3l.

**Failure:** **F1-RC-4** = lineage detachment.

###### 3d. Truthful delivery states (mandatory)

See §4 delivery truth model. **Failure:** **F1-RC-5** = false delivery implication.

###### 3e. Notification boundedness (mandatory)

| Metric | Pass |
|--------|------|
| `message_logs_growth_on_replay` | 0 semantic growth R2/R3 on F1-M1 |
| `retry_attempt_growth` | 0 unbounded growth on replay window |
| `recipient_cardinality` | Within documented batch bounds for digests |

**Artifact:** `f1_delivery_boundedness_{slug}.json`.

**Failures:** **F1-RC-6** = notification saturation; **F1-RC-12** = unbounded retry growth.

###### 3f. Suppression replay stability (mandatory)

| Field | Definition |
|-------|------------|
| `suppression_fingerprint_r1_r2_r3` | Fingerprint of suppression/blocked outcomes per run |
| `suppression_replay_equal` | R2 == R3 on stable replay |

**Artifact:** `f1_suppression_replay_{slug}.json`.

**Failure:** **F1-RC-7** = suppression inconsistency.

###### 3g. Operational explainability (mandatory)

| Check | Pass criterion |
|-------|----------------|
| **Reconstructable** | From `message_logs` + orchestrator metadata: why sent, suppressed, blocked, or deduped |
| **No opacity** | `explainability_reconstruction_pass=true` |

**Artifact:** `f1_notification_explainability_{slug}.json`.

**Failure:** **F1-RC-13** = delivery-state opacity.

###### 3h. Temporal ordering sanity (mandatory)

`notification_order_timeline[]` — no `attempted` before `queued`, no `delivered` before `attempted` without documented async lag class.

**Artifact:** `f1_temporal_ordering_{slug}.json`.

**Failure:** **F1-RC-8** = temporal contradiction.

###### 3i. Unrelated tenant isolation (mandatory)

Control tenant `message_logs` / notification fingerprint delta **0** on pilot replay window.

**Artifact:** `f1_unrelated_surface_integrity_{slug}.json`.

**Failure:** **F1-RC-9** = cross-tenant bleed.

###### 3j. Audit-noise boundedness (mandatory)

Audit/orchestrator log deltas on R2/R3 replay **0** for notification-scoped events (aligned to D1/E1 observability discipline).

**Artifact:** `f1_audit_stability_{slug}.json`.

**Failure:** **F1-RC-10** = observability noise amplification.

###### 3k. Replay-visible user impact boundedness (mandatory — rev 2)

F1 must verify **user-visible** communication impact boundedness — not only internal queue depth or `message_logs` row counts.

| Field | Definition |
|-------|------------|
| `visible_notification_delta` | Count/fingerprint delta of user-visible notification surfaces (client inbox indicators, digest rows shown, alert banners) on replay window |
| `visible_replay_growth_curve[]` | Per-run (R1/R2/R3) visible impact metrics |
| `user_visible_notification_fingerprint` | Semantic fingerprint of what the user would see |
| `replay_visible_impact_pass` | R2/R3 produce **no** unbounded visible churn; duplicate suppressions user-stable |

**Verification must prove:**

| Requirement | Failure signal |
|-------------|----------------|
| Replay does not create unbounded **visible** communication churn | Visible delta grows R2→R3 without legitimate regenerative class |
| Duplicate suppressions remain **user-stable** | User sees repeat of suppressed item as new alert |
| Replay-regenerative paths operationally bounded | Legitimate new sends within documented cardinality |
| Replay cannot create notification storms visible to end users | Spike in visible fingerprint without upstream regenerative correlation |

**Artifact:** `f1_visible_impact_{slug}.json`.

**Failure:** **F1-RC-16** = replay-visible notification amplification.

**Clarification:** Verification/governance only — **not** retry-system or provider redesign.

###### 3l. Notification lineage boundedness (mandatory — rev 2)

F1 verifies lineage **continuity** (§3c) **and** lineage **growth boundedness** — governance observability only.

| Field | Definition |
|-------|------------|
| `notification_lineage_depth` | Max attributable ancestry depth per notification window |
| `lineage_growth_curve[]` | Depth/count deltas across R1/R2/R3 and chain types |
| `lineage_growth_pass` | Growth == 0 on stable replay (R2/R3 vs settled R1) unless documented regenerative class |
| `lineage_collapse_state` | `collapsed_stable` \| `expanded` \| `inconsistent` on replay collapse |

**Bounded chain types (must prove finite growth on replay):**

| Chain type | Bounded on R2/R3 replay |
|------------|-------------------------|
| Retry lineage chains | Yes — no unbounded retry ancestry |
| Delegated notification chains | Yes — fanout delegate depth reconstructable |
| Replay-regenerative chains | Yes — only on new correlation |
| Escalation chains | Yes — escalation depth capped in window |
| Digest lineage | Yes — batch-scoped |
| Suppression lineage overlays | Yes — suppression reason stack bounded |

**Verification must prove:** lineage growth operationally finite; replay cannot create unbounded notification ancestry; delegated chains reconstructable; lineage collapse deterministic (aligned to D1/E1 collapse discipline).

**Artifact:** `f1_lineage_boundedness_{slug}.json`.

**Failure:** **F1-RC-17** = unbounded notification lineage growth.

##### 4. Delivery truth model (mandatory)

**Governed delivery states (taxonomy — verification only):**

| State | Meaning | May imply user received? |
|-------|---------|---------------------------|
| `intended_to_send` | Orchestrator accepted intent | **No** |
| `queued` | Accepted for internal queue/batch | **No** |
| `attempted` | Provider handoff tried | **No** |
| `provider_accepted` | Provider API accepted | **No** (unless programme defines observed sync) |
| `delivered` | Governed **observed** delivery signal only | **Yes** (only with observed layer) |
| `observed` | Tracking/webhook confirmed | **Yes** (within observed semantics) |
| `acknowledged` | User/system ack recorded | Contextual |
| `suppressed` | Governed skip (preference, policy) | N/A — must show reason |
| `blocked` | Activation/policy block | N/A — must show reason |
| `replay-collapsed` | Replay produced no new send (idempotent) | N/A |

**Hard rule:** No UI, digest, admin surface, or `message_logs` consumer may map `queued` or `provider_accepted` → user-visible **“Delivered”** without `observed` or programme-approved equivalent.

**Artifact:** `f1_delivery_truth_matrix_{slug}.json` — per sample: `{ "surface", "recorded_state", "implied_user_state", "truthful": bool }`.

##### 4a. Delivery authority semantics (mandatory — rev 2)

The delivery truth model (§4) separates states; **§4a** governs **who or what may assert** communication truth. **Governance classification only** — **not** provider-semantics redesign.

**Delivery authority sources (precedence hierarchy — highest trust wins):**

| Rank | Authority source | May assert |
|------|------------------|------------|
| 1 (highest) | **User-visible authority** | User-facing “received/read/acknowledged” only when programme rules allow |
| 2 | **Observed authority** | Webhook/tracking/observed delivery signals |
| 3 | **Platform authority** | `message_logs` / orchestrator governed platform record |
| 4 | **Provider authority** | SMTP/API acceptance, provider callbacks |
| 5 (lowest) | **Operational observability authority** | Internal logs, debug, operator dashboards |
| — | **Inferred/derived authority** | **Never** upgrades certainty above source; must cite parent authority |

**Verification must prove:**

| Requirement | Pass |
|-------------|------|
| No lower-trust authority overrides higher-trust delivery truth | **Yes** |
| Inferred states cannot silently upgrade delivery certainty | **Yes** |
| Replay does not alter authority precedence | R2/R3 `delivery_truth_resolution[]` stable |
| User-visible delivery claims remain authority-correct | No UI upgrade from enqueue/provider alone |

**Required report fields (per sample/window):**

| Field | Definition |
|-------|------------|
| `delivery_authority_source` | Winning authority source for the asserted delivery claim |
| `delivery_authority_precedence[]` | Ordered list of coexisting authority signals |
| `overridden_delivery_authorities[]` | Lower-trust sources explicitly overridden |
| `delivery_truth_resolution[]` | Per-surface: `{ "surface", "winning_source", "overridden", "precedence_pass" }` |

**Artifact:** `f1_delivery_authority_{slug}.json`.

**Failure:** **F1-RC-14** = delivery authority precedence violation.

##### 4b. Acknowledgement ambiguity handling (mandatory — rev 2)

`acknowledged` in §4 is **not** sufficient without governed ambiguity semantics. **Governance verification only** — **not** acknowledgement-system redesign.

**Ambiguous acknowledgement classes (must be classifiable):**

| Class | Operational meaning |
|-------|---------------------|
| `observed_not_acknowledged` | Delivery observed; no ack signal |
| `acknowledged_without_confirmed_human` | System ack without confirmed human interaction |
| `partial_acknowledgement` | Incomplete ack scope |
| `inferred_acknowledgement` | Derived ack — lowest certainty |
| `delayed_acknowledgement` | Ack after lag window |
| `stale_acknowledgement` | Ack no longer valid for current state |

**Verification must prove:**

| Requirement | Pass |
|-------------|------|
| Ambiguous acknowledgement states operationally explainable | `acknowledgement_state_resolution[]` populated |
| Replay does not silently upgrade acknowledgement certainty | `acknowledgement_replay_equal` on R2/R3 |
| Acknowledgement ambiguity bounded and reconstructable | `acknowledgement_confidence` stable on replay |

**Required report fields:**

| Field | Definition |
|-------|------------|
| `acknowledgement_state_resolution[]` | Per notification: class, sources, resolution reason |
| `acknowledgement_confidence` | `high` \| `medium` \| `low` \| `ambiguous` |
| `acknowledgement_replay_equal` | R2/R3 acknowledgement fingerprint equal on stable replay |
| `acknowledgement_ambiguity_reason` | Governed reason when not `high` confidence |

**Artifact:** `f1_acknowledgement_semantics_{slug}.json`.

**Failure:** **F1-RC-15** = acknowledgement certainty drift.

##### 5. Replay semantics — notification branch classes (mandatory)

Each observed notification branch on replay must be classified:

| Class | Definition | R2/R3 expectation |
|-------|------------|-------------------|
| `replay-collapsible` | Duplicate upstream replay → no new send | Stable fingerprint |
| `replay-regenerative` | Legitimate new upstream correlation → new send allowed | New row with new correlation |
| `idempotent` | Explicit duplicate_ignored | Stable outcome |
| `suppression-stable` | Suppressed/blocked with same reason | Same suppression fingerprint |
| `activation-blocked` | `NOTIFICATION_DISPATCH` / workflow gate | Stable blocked reason |
| `delegated-regenerative` | Fanout delegate triggers new notification path | Documented once per new correlation |

**Artifact:** `f1_notification_branch_behaviour_{slug}.json` — `notification_behaviour_classes[]`.

**Failure:** **F1-RC-11** = replay collapse inconsistency.

##### 6. Failure taxonomy (F1-RC-*)

| RC | Name | Trigger |
|----|------|---------|
| **F1-RC-1** | Notification replay drift | R2≠R3 intent fingerprint on stable key |
| **F1-RC-2** | Replay amplification | Extra sends/attempts on replay |
| **F1-RC-3** | Duplicate delivery drift | Dedupe outcome non-deterministic |
| **F1-RC-4** | Lineage detachment | Orphan or unjoinable `message_logs` |
| **F1-RC-5** | False delivery implication | Surface implies delivered from enqueue/accept only |
| **F1-RC-6** | Notification saturation | Unbounded rows/attempts in window |
| **F1-RC-7** | Suppression inconsistency | R2/R3 suppression fingerprint differs |
| **F1-RC-8** | Temporal contradiction | Ordering violations in timeline |
| **F1-RC-9** | Cross-tenant bleed | Control tenant delta ≠ 0 |
| **F1-RC-10** | Observability noise amplification | Audit/log churn on replay |
| **F1-RC-11** | Replay collapse inconsistency | Collapse class unstable R2/R3 |
| **F1-RC-12** | Unbounded retry growth | Retry counters grow on replay |
| **F1-RC-13** | Delivery-state opacity | Outcome not reconstructable |
| **F1-RC-14** | Delivery authority precedence violation | Lower-trust source wins or inferred upgrade |
| **F1-RC-15** | Acknowledgement certainty drift | Ack certainty changes on R2/R3 without governed transition |
| **F1-RC-16** | Replay-visible notification amplification | Unbounded user-visible churn on replay |
| **F1-RC-17** | Unbounded notification lineage growth | Lineage depth/count grows without regenerative class |

`detect_primary_rc` order documented in verification harness (lowest index wins for reporting). Suggested priority after fixture gate: **F1-RC-14** → **F1-RC-15** → **F1-RC-16** → **F1-RC-17** → **F1-RC-1** … (full order in harness spec on implementation).

**Rev 2 RC quick reference:** **F1-RC-14** delivery authority; **F1-RC-15** acknowledgement; **F1-RC-16** visible impact; **F1-RC-17** lineage growth.

##### 7. Required artifacts (mandatory)

All under `backend/docs/audit/` with slug `6fd5ac4c_d35a58ae` (pilot) unless noted:

| Artifact | Contents |
|----------|----------|
| `f1_control_selection_{slug}.json` | Pilot + control ids |
| `f1_notification_before_{slug}.json` | Preflight `message_logs` counts / fingerprints |
| `f1_notification_replay_{slug}.json` | R1/R2/R3 replay fingerprints |
| `f1_dedupe_determinism_{slug}.json` | Idempotency key outcomes |
| `f1_lineage_trace_{slug}.json` | correlation / transition joins |
| `f1_correlation_matrix_{slug}.json` | Cross-layer correlation consistency |
| `f1_delivery_truth_matrix_{slug}.json` | Truth model per surface |
| `f1_delivery_authority_{slug}.json` | Authority precedence + `delivery_truth_resolution[]` (§4a) |
| `f1_acknowledgement_semantics_{slug}.json` | Ack ambiguity + `acknowledgement_replay_equal` (§4b) |
| `f1_visible_impact_{slug}.json` | User-visible replay impact (§3k) |
| `f1_lineage_boundedness_{slug}.json` | Lineage depth/growth/collapse (§3l) |
| `f1_delivery_boundedness_{slug}.json` | Internal growth curves |
| `f1_suppression_replay_{slug}.json` | Suppression fingerprints |
| `f1_notification_branch_behaviour_{slug}.json` | Behaviour classes |
| `f1_notification_explainability_{slug}.json` | Reconstruction pass |
| `f1_temporal_ordering_{slug}.json` | Timelines |
| `f1_audit_stability_{slug}.json` | Noise deltas |
| `f1_unrelated_surface_integrity_{slug}.json` | Control tenant before/after |
| `f1_verification_report_{slug}.json` | `f1_pass`, `checks{}`, `primary_rc_branch`, artifact index |

**Staging driver:** `f1_*` first run (`f1_first_governed_staging_run_v1`) + **F1a** authoritative rerun (`f1a_harness_refinement_rerun_v1`). Scripts: `f1_snapshot.py`, `f1_preflight_capture.py`, `f1_staging_verification.py`, `f1a_snapshot.py`, `f1a_preflight_capture.py`, `f1a_staging_verification.py`. **F1-M1** + **F1-M8** observe only.

#### F1a — Harness refinement (micro-unit)

| Field | Value |
|-------|-------|
| **ID** | F1a |
| **Parent** | **F1** |
| **Scope** | Replay-pair acknowledgement semantics; replay fingerprint field alignment; vacuous replay prevention; population ambiguity excluded from **F1-RC-15** critical stop |
| **Unit status** | **DONE** (2026-05-17) |
| **Verification evidence** | `f1a_verification_report_6fd5ac4c_d35a58ae.json` (`f1a_rc15_cleared=true`, exit 0); `f1a_acknowledgement_semantics_*` (replay-pair); original `f1_*` preserved |

**Closure:** First `f1_*` run stopped on **F1-RC-15** (population acknowledgement compare — **harness methodology**, not notification replay instability). F1a corrected: replay-pair question = *did R2/R3 alter acknowledgement certainty on M1 idempotency row?*; M1 probe fingerprints aligned into `replay_notification_comparison_f1a`; vacuous `null==null` semantic pass prevented.

---

#### F1 — Closure evidence (VERIFIED — 2026-05-17)

**Pilot:** `client_id=6fd5ac4c-3fd4-4112-ade7-156977deb49f`, `property_id=d35a58ae-3c81-491c-9694-1d021dd3b8ad`, `pleerity_staging`. **Control:** `04ceda9f-dd72-4b70-a6f5-809bef1b7b6a` / `6d939c70-06ab-4dc8-8b36-204958d2cdb3`.

##### 1. F1 proof outcome (governed **F1-M1** replay path)

Notification governance replay semantics are **materially proven stable** on a **notification-replay-capable** pilot fixture (`f1a` rerun: no critical stop, `failure_classification=governed_replay_proof_candidate`).

| Proven on F1a authoritative rerun | Result |
|-----------------------------------|--------|
| No replay-visible amplification | **PASS** — `message_log_count` 49 constant R1–R3 |
| Deterministic duplicate suppression (**F1-M1**) | **PASS** — R2/R3 `duplicate_ignored`; `dedupe_deterministic=true` |
| Visible notification fingerprints stable | **PASS** — `replay_visible_impact_stable=true` |
| Suppression replay stable | **PASS** — `suppression_replay_equal=true` |
| Lineage bounded | **PASS** — `lineage_growth_pass=true`; depth 2 stable |
| Cross-tenant isolation | **PASS** — `unrelated_delta_zero=true`; control `message_logs` unchanged |
| Acknowledgement replay semantics (replay-pair) | **PASS** — `acknowledgement_replay_equal=true`; **no** certainty escalation on replay |
| Semantic notification replay | **PASS** — R2/R3 semantic + raw fingerprints aligned (`af8be64b…` / `3d8d55a7…`) |
| Delivery-authority precedence (sample) | **PASS** — `delivery_authority_precedence_pass=true` |
| Delivery truth on replay probe row | **PASS** — `false_delivery_implication_on_replay_probe=false` |

**Governed mutations in proof:** **F1-M1** (idempotency replay probe on stable key); **F1-M8** observe (`NOTIFICATION_DISPATCH` off per inventory). **F1-M2–M7** **not** proven in this unit.

##### 2. Classification history (preserved — do not erase)

| Phase | Artifact set | Outcome | Programme interpretation |
|-------|----------------|---------|---------------------------|
| **Original F1** | `f1_*` preserved | Critical stop **F1-RC-15**; `acknowledgement_replay_equal=false` on **population** compare | **Harness methodology issue** — not proven notification-governance instability |
| **F1a** | `f1a_*` authoritative | `f1a_rc15_cleared=true`; replay-pair ack stable; exit 0 | **Governed replay proof candidate** → **VERIFIED** basis |

Original **F1-RC-15** classification and artifacts remain for audit. **Do not rewrite** `f1_verification_report_*`.

##### 3. Replay methodology corrections (F1a — authoritative for VERIFIED)

| Correction | Detail |
|------------|--------|
| **Replay-pair vs population** | Acknowledgement RC applies to **R2/R3 on M1 idempotency row** only; historical `inferred_acknowledgement` population does **not** trigger **F1-RC-15** |
| **Fingerprint alignment** | `replay_notification_comparison_f1a` merges M1 probe `notification_intent_fingerprint_*_after` into R2/R3 |
| **Vacuous pass prevention** | `null==null` semantic stability rejected; `vacuous_semantic_comparison_prevented` explicit |
| **Critical-stop discipline** | On true replay defect signals: preserve artifacts, classify RC, stop — **no** remediation under F1/F1a |

##### 4. VERIFIED interpretation

**F1 VERIFIED means:**

- Governed **F1-M1** replay proof **succeeded** on staging pilot.
- Replay semantics behaved **deterministically** (idempotent collapse, no amplification, visible impact stable).
- **No** true notification replay instability established on the proven path.
- **No** replay-visible communication storm observed.
- **No** semantic delivery-authority escalation on replay probe.

**F1 VERIFIED does NOT mean:**

- All historical notification ambiguity is resolved.
- Provider certainty is perfect or inbox delivery is guaranteed.
- Acknowledgement ambiguity no longer exists in `message_logs` history.
- Notification architecture is complete.
- **F1-M2–M7** mutation paths are proven.
- Global `NOTIFICATION_DISPATCH` activation is approved.

##### 5. No remediation conclusion

| Item | Conclusion |
|------|------------|
| Notification product defect (replay path) | **Not confirmed** |
| `notification_orchestrator` redesign | **Not indicated** |
| Provider redesign | **Not indicated** |
| Retry redesign | **Not indicated** |
| Queue / scheduler redesign | **Not indicated** |
| Template remediation | **Not indicated** |
| `message_logs` semantic rewrite | **Not authorized** |

##### 6. Remaining watchlist (explicit)

- **Operational population ambiguity** exists (`population_operational_ambiguity_present=true` on F1a rerun) — `inferred_acknowledgement` / `ambiguous` on historical **DELIVERED** rows without observed/ack signals; **not** a replay failure.
- **Raw timestamp drift** may still be observable on non-replay windows; **only semantic replay** gates were normalized (observational keys + run labels).
- Proof scope is **F1-M1 + F1-M8 observe** only — digest (**M5**), escalation (**M6**), authority-transition notify (**M2**), fanout delegate (**M3**), retry observe (**M4**), suppression overlay proof (**M7**) remain **unproven**.
- **`NOTIFICATION_DISPATCH`** remains globally **off** per `NOTIFICATION_GOVERNANCE_INVENTORY.json`.
- §8 **DONE** baseline suites (`test_notification_*` full matrix) not yet closed for **DONE**.
- Do **not** reinterpret provider **SENT** / platform **DELIVERED** as guaranteed user receipt.

##### 7. Governance posture — VERIFIED vs DONE

**F1 VERIFIED** (2026-05-17) = governed notification replay truthfulness **proven on F1-M1** under existing orchestrator semantics.

**F1 DONE** (2026-05-17) = F-layer replay-governance proof **operationally complete** for the approved scope. Programme closure; **not** notification architecture finality.

**Authoritative artifacts:**

| Set | Role |
|-----|------|
| **`f1a_*`** | **Authoritative for F1 VERIFIED/DONE proof** — `f1a_verification_report_6fd5ac4c_d35a58ae.json`, `f1a_notification_replay_*`, `f1a_acknowledgement_semantics_*` |
| **`f1_*`** | **Permanent history** — first run, **F1-RC-15** (harness methodology — **do not delete or rewrite**) |

**Regression (harness):** `tests/test_f1_verification_contract.py`, `tests/test_f1a_verification_contract.py` — green.

**Unlock on DONE:** **G1/G2** per programme sequence. **No** silent F1 scope extension. New paths (**F1-M2–M7**, provider ack, dispatch activation) require **separate units**.

---

#### F1 — Closure evidence (DONE — 2026-05-17)

**Pilot:** `client_id=6fd5ac4c-3fd4-4112-ade7-156977deb49f`, `property_id=d35a58ae-3c81-491c-9694-1d021dd3b8ad`. **Control:** `04ceda9f-dd72-4b70-a6f5-809bef1b7b6a` / `6d939c70-06ab-4dc8-8b36-204958d2cdb3`.

##### 1. F-layer proof posture (operationally complete)

For the governed **F1-M1** replay-notification proof scope, F1 is **DONE**:

| Proven capability | Evidence |
|-------------------|----------|
| Replay-visible communication boundedness | `message_log_count` stable R1–R3; `replay_visible_impact_stable=true` |
| Deterministic duplicate suppression | R2/R3 `duplicate_ignored`; `dedupe_deterministic=true` |
| Replay-collapsible notification semantics | `replay_branch_hint=replay-collapsible` |
| Stable visible notification fingerprints | `499d420f…` constant across runs |
| Stable suppression replay | `suppression_replay_equal=true` |
| Bounded notification lineage | `lineage_growth_pass=true` |
| Replay-pair acknowledgement stability | `f1a_rc15_cleared=true`; no escalation on replay |
| Delivery-authority operational coherence | `delivery_authority_precedence_pass=true` (sample) |
| Cross-tenant isolation | `unrelated_delta_zero=true` |
| No replay-visible notification storms | No amplification on **F1-M1** window |

##### 2. Preserved RC chronology (permanent — no retroactive rewrite)

| Phase | Artifacts | RC / outcome | Final interpretation |
|-------|-----------|--------------|----------------------|
| **F1 first run** | `f1_*` | **F1-RC-15** critical stop | **Harness methodology** — population ack compare; **not** notification instability |
| **F1a refinement** | `f1a_*` | No critical stop; `f1a_rc15_cleared=true` | Replay-pair ack + fingerprint alignment |
| **F1 programme** | Tracker + runbook | **VERIFIED** → **DONE** | Governed **F1-M1** replay proof accepted |

**Methodology-evolution trail (preserved):** observational-only normalization (timestamps, run labels); **never** normalize delivery authority, visible impact, ack certainty on replay pair, suppression, lineage, amplification.

##### 3. DONE scope limits (mandatory)

**F1 DONE does NOT mean:**

- Provider delivery, human-read, or inbox guarantees
- Full notification-path coverage or **F1-M2–M7** proof
- `NOTIFICATION_DISPATCH` global activation
- Perfect historical acknowledgement certainty
- Complete notification architecture finality

##### 4. Explicit non-conclusions (recorded)

| Item | Conclusion |
|------|------------|
| Notification defect on governed replay path | **Not confirmed** |
| Provider / retry / scheduler / queue redesign | **Not indicated** |
| `notification_orchestrator` redesign | **Not indicated** |
| Template remediation | **Not indicated** |
| `message_logs` semantic rewrite | **Not authorized** |

##### 5. Remaining watchlist (visible — not hidden debt)

- **Historical `inferred_acknowledgement`** population ambiguity (`f1a_acknowledgement_population_ambiguity_*`)
- **Raw timestamp drift** on observational fingerprints (non-blocking; semantic replay gates only)
- **F1-M2–M7** mutation paths **unproven** (authority notify, fanout delegate, retry, digest, escalation, suppression overlay)
- **Provider vs user acknowledgement** distinction remains governed — platform **DELIVERED** ≠ inbox receipt
- **`NOTIFICATION_DISPATCH`** globally **off** (inventory policy)
- §8 **L-008** CI: harness + core notification suites owned by programme CI; one pre-existing `test_notification_preferences_enforcement` SMS case may fail outside F1 scope — **no fix authorized under F1**

##### 6. Programme posture after DONE

F-layer **replay-governance proof is complete** for the approved scope. Future notification work must split into:

- **New governed verification units** (e.g. F1-M2–M7 expansion), or
- **Explicitly approved remediation units**

**Do not** silently extend F1. **Do not** start F2, provider redesign, or notification architecture rewrite under F1 guise.

##### 7. Authoritative references

| Document | Update |
|----------|--------|
| `LAUNCH_AUTHORITY_TRACKER.md` | This § F1 DONE closure |
| `CLOSED_LOOP_COMPLIANCE_ARCHITECTURE_TRACKER.md` | F1 row **DONE** |
| `RUNBOOK_CONTROLLED_BETA_OPERATIONS.md` | §12.7 F1 — DONE posture |
| `audit/NOTIFICATION_GOVERNANCE_INVENTORY.json` | Canonical send authority (unchanged) |

##### 8. Regression suites

**Existing suites (must pass before F1 DONE — baseline):**

| Suite | Role |
|-------|------|
| `tests/test_notification_bypass_governance.py` | **L-008** — no bypass sends |
| `tests/test_notification_orchestrator.py` | Orchestrator core |
| `tests/test_notification_compliance_alert_idempotency.py` | **L-008d** alert dedupe |
| `tests/test_notification_reminder_idempotency.py` | Reminder batch idempotency |
| `tests/test_notification_preferences_enforcement.py` | Preference suppression |
| `tests/test_enterprise_notification.py` | Enterprise paths |
| `tests/test_notification_template_seed_definitions.py` | **L-008e** template registry |
| `tests/test_work_order_contractor_routing_notifications.py` | WO routing observe |

**Proposed F1 verification-only suites (implement in F1 verification phase — not in this draft):**

| Proposed file | Role |
|---------------|------|
| `tests/test_f1_verification_contract.py` | **Implemented** — mocked replay/dedupe/truth-model contract |
| `tests/test_f1a_verification_contract.py` | **Implemented** — replay-pair ack + vacuous prevention |
| `tests/test_f1_notification_replay_determinism.py` | Stable replay → equal intent fingerprint |
| `tests/test_f1_delivery_truth_semantics.py` | No false delivered implication |
| `tests/test_f1_suppression_replay.py` | Suppression fingerprint R2=R3 |
| `tests/test_f1_lineage_continuity.py` | Correlation join matrix |

##### 9. Completion gates

| Gate | Requirement |
|------|-------------|
| **Start `IN_PROGRESS`** | F1 DoD **approved**; pilot + control identified; E1 **VERIFIED** |
| **`IMPLEMENTED_PENDING_VERIFICATION`** | F1 scripts/tests merged (**verification only**) |
| **`READY_FOR_STAGING_VERIFICATION`** | All §7 artifacts captured on staging |
| **`VERIFIED`** | §1–§6 + §3 themes + §4a–§4b pass on staging report |
| **`DONE`** | §8 tests green; §10 docs updated; deferral list documented |

**F1 cannot move to DONE unless all proven on staging:**

1. **Deterministic replay** on F1-M1 stable keys.
2. **Truthful delivery semantics** — no false delivery implication (**F1-RC-5**).
3. **Delivery authority precedence deterministic** — no lower-trust override (**F1-RC-14**).
4. **Acknowledgement ambiguity replay-stable** — no silent certainty upgrade (**F1-RC-15**).
5. **Visible replay impact bounded** — no user-visible notification storms (**F1-RC-16**).
6. **Notification lineage bounded** — finite ancestry; collapse deterministic (**F1-RC-17**).
7. **Bounded retry/replay growth** (**F1-RC-6**, **F1-RC-12**).
8. **Suppression stability** on replay (**F1-RC-7**).
9. **Lineage continuity** (**F1-RC-4**).
10. **Cross-tenant isolation** (**F1-RC-9**).
11. **Operational explainability** (**F1-RC-13**).
12. **Bounded observability noise** (**F1-RC-10**).
13. **No replay-visible notification storms** (visible + internal boundedness).
14. No notification/queue/scheduler/template/provider/acknowledgement redesign shipped under F1 guise (§10).

##### 10. Boundary reaffirmation (explicit NOT — rev 2)

**F1 is verification and governance first.** Notification architecture remediation, provider migration, acknowledgement-system redesign, retry-system redesign, scheduler cadence changes, queue topology changes, fanout routing changes, workflow redesign, authority redesign, task-system redesign, event-bus redesign, template-system rewrite, or global `NOTIFICATION_DISPATCH` activation require **separate approved units** with their own DoD — not bundled into initial F1 proof.

| Explicitly out of scope (reaffirmed rev 2) | |
|--------------------------------------------|--|
| Notification architecture rewrite | |
| Provider redesign / provider semantics redesign | |
| Acknowledgement system redesign | |
| Retry system redesign | |
| Scheduler redesign | |
| Queue redesign | |
| Event-bus redesign | |
| Template-system redesign | |
| Fanout topology redesign | |
| Workflow redesign | |
| Authority / evidence systems (E-layer) | |
| Task systems (C2) | |

**Rev 2 clarifications (verification only):** §4a delivery authority, §4b acknowledgement ambiguity, §3k visible impact, and §3l lineage boundedness are **governance observability** requirements — they do **not** authorize changing provider callbacks, ack pipelines, retry writers, or orchestrator routing in the F1 unit.

**Status:** **DONE** (2026-05-17) — see § **F1 — Closure evidence (VERIFIED)** and § **F1 — Closure evidence (DONE)**. **F1a DONE**. Staging JSON retains `f1_pass: null` / `classification_deferred: true` in preserved artifacts; programme **DONE** is tracker-authoritative.

---

### G1 — Launch Governance Surveillance (LGS) (continuous)

| Field | Value |
|-------|-------|
| **ID** | G1 |
| **Role** | **Launch Governance Surveillance (LGS)** — observational oversight of launch truth; **not** a constitutional operating system |
| **Priority** | P1 (programme) |
| **Trigger** | **Only after A–F proof domains complete** — B1 **DONE**, C1/C2/C2a **DONE**, D1 **DONE**, E1 **VERIFIED**, F1 **DONE** |
| **Scope** | Read-only surveillance of **product truth**, **launch scope honesty**, **anti-self-validation**, and **launch-surface explainability** — **not** re-proof of B–F; **not** normative governance authority |
| **Canonical authority** | This tracker; `CLOSED_LOOP_COMPLIANCE_ARCHITECTURE_TRACKER.md`; `GOVERNANCE_INDEX.md`; `RUNBOOK_CONTROLLED_BETA_OPERATIONS.md`; **Tier-0** `audit/*_{slug}.json` from B–F units |
| **Code areas likely affected** | **Verification/governance scripts only** when approved — read-only surveillance; **not** production writers |
| **Unit status** | **IN_PROGRESS** (2026-05-17) — **Tranche T1 harness only**; surveillance execution **not** authorised |
| **Implementation scope** | T1 read-only harness scaffolding only — see § **G1 — Programme sign-off** and §11 |
| **Verification evidence** | On **VERIFIED** (future): six mandatory `g1_*` artefacts; `g1_launch_readiness_*` sole pass/fail index |
| **Governance docs after** | This tracker; `CLOSED_LOOP_COMPLIANCE_ARCHITECTURE_TRACKER.md`; `RUNBOOK_CONTROLLED_BETA_OPERATIONS.md` §12.7 G1 |
| **Regression tests** | `tests/test_g1_verification_contract.py` — **T1 subset only** until separate T2/T3 approval |
| **Rollback / safety** | Surveillance-only; no auto-repair; no proof rewrite; no silent RC reclassification; **G1 cannot redefine B–F DONE/VERIFIED** |

**Unlock (2026-05-17):** F1 **DONE** → G1 recovery DoD → **programme sign-off** (2026-05-17) → **IN_PROGRESS** (T1 harness only).

**Relationship to prior G1 label (“support recovery”):** `RUNBOOK`, admin explain, and support views remain **operational inputs (Tier-2)**. G1 **does not** replace them and **does not** become sovereign over programme semantics.

**Dual sovereignty (mandatory):** Unit closure (B–F) decides **what was proven in staging**. G1 decides whether **launch narrative still matches Tier-0 + closure**. Programme launch authority decides **whether to ship** (outside G1). G1 **non-VERIFIED** does **not** retroactively un-DONE a unit; it flags **launch governance risk** and blocks **G1 DONE** only.

---

#### G1 — Programme sign-off (formal — 2026-05-17)

**Pre-signoff outcome:** Hardened recovery DoD passed pre-signoff review. Rev 5 constitutional re-entry vectors (manifest prestige, degraded pass leakage, array mass bypass, retired-artefact influence, tracker-only loops, tag elevation, narrative gates, critical-path masking) were **addressed in documentation**.

**Approval:** LGS recovery is **approved for controlled harness implementation readiness** — **not** for surveillance execution, remediation, proof rewriting, or governance mutation.

| Signoff field | Value |
|---------------|-------|
| `signoff_timestamp` | **2026-05-17** |
| `signoff_scope` | Hardened **Launch Governance Surveillance (LGS)** recovery DoD — `LAUNCH_AUTHORITY_TRACKER.md` § G1 |
| `approved_tranche` | **T1** |
| `governance_posture` | **ANTI_EXPANSION** |
| `implementation_authority` | **READ_ONLY_SURVEILLANCE_ONLY** |

**Explicitly authorised by this signoff:**

| Authorised | Not authorised |
|------------|----------------|
| Tranche **T1** harness work only | Tranche T2/T3 (separate approval required) |
| Read-only surveillance **harness scaffolding** | Staging surveillance **execution** |
| `launch_baseline_manifest_{slug}_v1` capture at T1 start | `READY_FOR_STAGING_SURVEILLANCE` / **VERIFIED** / **DONE** |
| Contract tests for **T1 RC subset** only | Full RC matrix implementation |
| Manifest integrity, degraded enforcement, critical authoritative checks | Remediation, proof rewrite, governance mutation |

**State transition:** **NOT_STARTED** → **IN_PROGRESS** (constrained). **No** promotion to **`IMPLEMENTED_PENDING_VERIFICATION`** without separate programme approval after T1 harness merge review.

**Surveillance execution:** **Still pending** — no pilot staging surveillance run authorised by this signoff.

---

#### G1 — Definition of Done (recovery — simplified + pre-signoff hardening; 2026-05-17)

**Supersedes:** G1 DoD **rev 1–5 draft** constitutional meta-layer (23 RCs, 21+ artefact families, 28 gates). Rev 1–4 operational intent is **preserved** where not listed in §12 deprecation.

**Recovery principle:** Smallest **falsifiable** governance surface that protects launch truth **without** self-preserving constitutional infrastructure.

**Four constitutional pillars (only)** — namespace **`Pillar P1`–`Pillar P4`** (not `G1-P#`):

| Constitutional pillar | G1 proves |
|-----------------------|-----------|
| **Pillar P1 — Product truth preservation** | B–F authoritative staging evidence still supports unit closure claims |
| **Pillar P2 — Anti-silent reinterpretation** | Proof scope, normalization, deferred risks, and watchlists were not silently rewritten |
| **Pillar P3 — Anti-self-validation** | Launch claims ground in Tier-0/Tier-1 with **no** normative G1-on-G1 or tracker-only product loops |
| **Pillar P4 — Launch decision explainability** | Tracker, CLOSED_LOOP, and RUNBOOK do not assert what Tier-0 refutes |

**Governance namespace map (mandatory — no symbolic overlap):**

| Symbol | Meaning |
|--------|---------|
| **Pillar P1–P4** | Constitutional intent pillars (this table) |
| **G1-P1–G1-P10** | Primary surveillance failure codes (§8) |
| **G1-RC-21–G1-RC-27** | Reissued LGS hardening failure codes (§8b); **not** rev 5 draft semantics |
| **TAG_*** | Advisory tags only (§8); never primary |

**One-line boundary:** G1 proves **launch truth remains Tier-0-grounded, scope-honest, non-self-validating, and launch-explainable** — observational surveillance only.

##### 1. What G1 is and is not (mandatory)

**G1 is:**

| Capability | Mechanism |
|------------|-----------|
| Launch governance surveillance | Read-only comparison vs frozen **launch baseline manifest** |
| Product-truth drift detection | Fingerprints vs authoritative `*b_*` / `d1b_*` / `e1b_*` / `f1a_*` |
| Anti-silent reinterpretation | Scope registry + proof-context constraints |
| Anti-self-validation | Tier breakers (§4) |
| Launch-surface coherence | Governance-surface join (§6 artefact 4) |
| Bounded surveillance mass | P10 caps (§9) |

**G1 is NOT:**

| Excluded | Reason |
|----------|--------|
| Constitutional operating system | No normative legitimacy engine |
| Semantic authority / reinterpretation engine | No approval of normalization or scope changes |
| Governance sovereign over B–F | Cannot un-DONE units |
| Narrative-completeness gate | No blocking on prose density |
| Remediation / auto-healing / proof rewrite | Separate units |
| Re-proof of C1/D1/E1/F1 full staging | Upstream units own first proof |

##### 2. Upstream consumed proof domains (mandatory)

G1 **consumes** B–F **Tier-0** artefacts — does **not** re-prove:

| Domain | Authoritative Tier-0 families (examples) | Surveillance question |
|--------|------------------------------------------|------------------------|
| **B** | `b1_*` | Visibility claims still aligned? |
| **C** | `c1_*`, `c2_*`, `c2a_*` | Replay-confidence decayed? |
| **D** | `d1b_*` authoritative; `d1_*` historical | Fanout lineage credible? |
| **E** | `e1b_*` authoritative; `e1_*` historical | Authority replay semantics stable? |
| **F** | `f1a_*` authoritative; `f1_*` historical | Notification replay-confidence stable? |

**Launch baseline manifest (mandatory at `IN_PROGRESS`):** `launch_baseline_manifest_{slug}_v{N}.json`

| Manifest rule | Requirement |
|---------------|-------------|
| **Tier classification** | `manifest_tier_classification="T1_INDEX_ONLY"` — **Tier-1 index metadata only**; **never** normative product truth |
| **Grounding** | `manifest_grounding_requirements[]` — every row must cite Tier-0 `path`, `sha256`, `authoritative_label`; **no** independent governance assertions |
| **Capture** | Derived **exclusively** from Tier-0 hashes/paths captured at **`IN_PROGRESS`**; manifest convenience must **never** become constitutional authority |
| **Surveillance use** | Compare current Tier-0 state to manifest vN — **not** to prior `g1_*` (B4) |

**Failure branch:** **G1-RC-21** = manifest authority escalation (manifest treated as product ground, missing Tier-0 derivation, or normative assertions in manifest body).

**Per-unit closure (operational, not constitutional DONE):** `acceptance_rationale_ref` (tracker § + artefact IDs) — presence check only; missing → `TAG_LEGITIMACY_INCOMPLETE` (advisory).

##### 3. Core governance themes (essential only)

| # | Theme | Pillar |
|---|-------|--------|
| 3a | Tier-0 artifact integrity | Pillar P1 |
| 3b | Product replay-confidence | Pillar P1 |
| 3c | Normalization / scope stability | Pillar P1, Pillar P2 |
| 3d | Proof-context / scope registry | Pillar P2 |
| 3e | Deferred-risk + watchlist visibility | Pillar P2 |
| 3f | Cross-layer operational consistency | Pillar P1 |
| 3g | Launch-surface truthfulness | Pillar P4 |
| 3h | Anti-self-validation (tier breakers) | Pillar P3 |
| 3i | Surveillance mass boundedness | G1-P10 |

**Advisory only (secondary tags — never sole VERIFIED block):** succession gaps, semantic drift, concentration, replay-narrative gaps, partial knowledge, visible contradictions, legitimacy prose incomplete. See §8 secondary tags.

##### 4. Tier model and anti-recursion breakers (mandatory)

| Tier | Sources | May ground **product launch truth**? |
|------|---------|-------------------------------------|
| **T0** | B–F `audit/*_{slug}.json`; authoritative rerun reports; read-only staging fingerprints | **Yes** |
| **T1** | Unit closure sections (this tracker); CLOSED_LOOP rows; `launch_baseline_manifest_*` (**index only**) | **Yes, only if T0-linked per §4a** |
| **T2** | RUNBOOK, GOVERNANCE_INDEX operational narrative | **No** (operations only) |
| **T3** | `g1_*` surveillance outputs | **Never normative** |

**Hard breakers (validation must fail → P7 or P1 as applicable):**

| Breaker | Rule |
|---------|------|
| **B1 — No G1-on-G1 normative grounding** | T3 paths must not justify P1–P6 product conclusions |
| **B2 — No tracker-only product truth** | T1-only loops without T0 edge → P7 |
| **B3 — No T3→T3 legitimacy** | Surveillance snapshots cannot anchor further surveillance |
| **B4 — No prestige baseline** | Baseline is `launch_baseline_manifest_vN`, not prior `g1a_*` |
| **B5 — Superseded is non-authoritative** | `historical_only=true` / `non_authoritative=true` artefacts excluded from grounding |

###### 4a. Tier-0 linkage predicate (mandatory)

Tracker prose alone is **never** constitutional product truth. Every launch/product claim in `tracker_claims[]` must resolve via `tier0_link_resolution[]`:

| Required resolution field | Purpose |
|---------------------------|---------|
| `tier0_artifact_path` | Audit JSON path |
| `tier0_artifact_sha256` | Hash at manifest capture |
| `replay_lineage_ref` | Authoritative rerun label (e.g. `f1a_*`, `d1b_*`) where applicable |
| `normalization_boundary_ref` | Omit-key / scope boundary ID where applicable |

**Outputs (in `g1_governance_surface_*` / `g1_self_validation_check_*`):** `tier0_link_resolution[]`, `unresolved_tracker_claims[]` (must be **empty** on pass), `tracker_truth_binding_pass`.

**Failure branch:** **G1-RC-24** = tracker self-validation loop (T1-only product claim or unresolved tracker claim).

##### 5. Surveillance modes (mandatory)

| Mode | `degraded_mode` | VERIFIED allowed? | G1 DONE allowed? |
|------|-----------------|-------------------|------------------|
| **SURVEILLANCE_FULL** | `false` | Yes, if G1-P1–P9 + hardening RCs clear; `g1_pass=true` permitted | Yes, if §10 conditions pass |
| **SURVEILLANCE_DEGRADED** | `true` | **No** — `g1_pass` **must be false** | **No** |
| **SURVEILLANCE_BLOCKED** | n/a (hard fail) | **No** — `g1_pass` **must be false** | **No** |

**Pass prohibition (mandatory):** If `degraded_mode=true` **OR** `surveillance_mode≠SURVEILLANCE_FULL` → `g1_pass=false`; **VERIFIED prohibited**; **DONE prohibited**. Degraded reconstruction may emit observational artefacts but **never** implies constitutional adequacy.

**Degraded triggers (any applies):**

| Trigger | Mode |
|---------|------|
| Tier-0 availability below manifest `min_tier0_coverage` (default **≥95%** paths present and hash-valid) | DEGRADED |
| **Critical authoritative omission** (below) | DEGRADED or BLOCKED |

**Critical-path rule (mandatory — not statistical):** Missing **any** authoritative rerun artefact in `critical_authoritative_artifact_inventory[]` forces **SURVEILLANCE_DEGRADED** or **SURVEILLANCE_BLOCKED** regardless of coverage percentage.

| Unit | Critical authoritative families (pilot) |
|------|----------------------------------------|
| **D** | `d1b_*` verification report + authoritative rerun set listed in manifest |
| **E** | `e1b_*` verification report |
| **F** | `f1a_*` verification report |

**Outputs:** `critical_authoritative_artifact_inventory[]`, `missing_critical_authoritative_artifacts[]` in `g1_upstream_integrity_*`. **Failure branch:** **G1-RC-27** = critical-proof omission masking (critical artefact missing but surveillance treated as FULL).

**Degraded observational only:** May emit `partial_reconstruction_summary` in `g1_launch_readiness_*`. Tag: `TAG_PARTIAL_KNOWLEDGE`. **Must not** claim product truth or constitutional legitimacy.

##### 6. Governed surveillance sources (when implemented)

| ID | Source | Observes |
|----|--------|----------|
| **G1-S1** | Tier-0 manifest + audit filesystem | P1, P2 (tamper, hash) |
| **G1-S2** | Read-only pilot fingerprints | P1 (replay-confidence) |
| **G1-S3** | Tracker + CLOSED_LOOP + RUNBOOK | P4, P8 |
| **G1-S4** | Scope/deferred/watchlist registry | P2, P5 |
| **G1-S5** | Tier graph builder | P3, P7 |

**No production mutations** in G1 scope.

##### 7. Mandatory artefacts (6 + optional handoff)

All under `backend/docs/audit/`. Pilot slug default: `6fd5ac4c_d35a58ae`.

**Constitutional mass cap:** **6 mandatory** artefacts per run; accounting mode **`constitutional_mass_accounting_mode="FIELD_PLUS_ELEMENT"`** — **each array element counts** toward mass; **≤120** total field+element units; per-field `max_allowed_array_elements[]` enforced; arrays may **not** become hidden governance registries. Excess → **G1-P10** or **G1-RC-22**. Optional handoff does not count toward cap.

| Artefact | Schema (mandatory fields) | Pillar |
|----------|---------------------------|--------|
| `g1_upstream_integrity_{slug}.json` | `manifest_version`, `tier0_manifest_ref`, `manifest_tier_classification`, `manifest_grounding_requirements[]`, `tier0_entries[]` (max elements = manifest row count), `critical_authoritative_artifact_inventory[]`, `missing_critical_authoritative_artifacts[]`, `tamper_detected`, `missing_tier0[]`, `retroactive_rewrite_detected` | Pillar P1 |
| `g1_product_surveillance_{slug}.json` | `unit_fingerprints[]`, `normalization_omit_keys[]`, `cross_layer_contradictions[]`, `normalization_drift_detected`, `predicate_binding_refs[]` | Pillar P1/P2; G1-P3/P6 |
| `g1_launch_scope_registry_{slug}.json` | `proof_context_snapshot[]`, `accepted_scope_limitations[]`, `deferred_risk_inventory[]`, `watchlist_inventory[]`, `silently_removed[]` (empty on pass), `proof_interpretation_constraints[]` | Pillar P2 |
| `g1_governance_surface_{slug}.json` | `tracker_claims[]`, `tier0_link_resolution[]`, `unresolved_tracker_claims[]`, `tracker_truth_binding_pass`, `artifact_claims[]`, `surface_mismatches[]`, `launch_surface_falsehood_detected` | Pillar P4 |
| `g1_self_validation_check_{slug}.json` | `tier_edges[]`, `normative_loops[]` (empty on pass), `tracker_only_product_claims[]`, `self_validating_loop_detected`, `tier_breakers_triggered[]`, `retired_artifact_read_policy[]`, `retired_artifact_usage_violations[]` (empty on pass) | Pillar P3 |
| `g1_launch_readiness_{slug}.json` | `surveillance_mode`, `degraded_mode`, `g1_pass` (**must be false** if `degraded_mode=true` or `surveillance_mode≠SURVEILLANCE_FULL`), `primary_rc` (one **G1-P***, **G1-RC-21–27**, or null), `secondary_tags[]`, `advisory_tag_elevation_attempts[]`, `tag_governance_boundary_pass`, `tier0_grounding[]` (T0 paths only; **no T3**), `predicate_binding_inventory[]`, `non_falsifiable_language_inventory[]` (empty on pass), `advisory_only_governance_language[]`, `constitutional_mass` (`artefact_count`, `field_count`, `element_count`, `constitutional_mass_element_budget`, `max_allowed_array_elements[]`), `challenge_refs[]`, `artifact_index[]` (T3 observational only) | Index |

**Optional (event-triggered only):** `g1_handoff_record_{slug}.json` — `stewardship_transition`, `from_steward`, `to_steward`, `handoff_at`, `inherited_scope_refs[]`. Emits tag `TAG_SUCCESSION_GAP` if required handoff missing; **never** primary RC alone.

**Prefix rule:** First run `g1_*`; reruns `g1a_*`, `g1b_*`. **Never** overwrite upstream B–F artefacts. **T3 is observational:** `g1_*` never listed in `tier0_grounding[]` for product claims.

**Staging drivers (after approval):** `scripts/g1_snapshot.py`, `scripts/g1_preflight_capture.py`, `scripts/g1_staging_surveillance.py` (read-only).

##### 8. Primary RC model (G1-P1–P10) + secondary tags

**Single-primary enforcement:** Each surveillance run sets exactly **one** `primary_rc` ∈ {`G1-P1`…`G1-P10`, `G1-RC-21`…`G1-RC-27`} or `null` if pass. `secondary_tags[]` may list multiple advisories.

**Core primary RCs (launch-blocking on FULL VERIFIED):**

| RC | Name | Falsifiable trigger (contract-bound) | Absorbs (rev 1–5 draft) |
|----|------|-----------------------------------|-------------------------|
| **G1-P1** | Historical tampering | Tier-0 missing, hash mismatch, RC/artefact rewrite | G1-RC-2 |
| **G1-P2** | Silent scope / normalization expansion | Omit-keys or proof scope widened without `approving_unit_ref` | G1-RC-4 |
| **G1-P3** | Product replay-confidence erosion | `semantic_drift=true` per `test_g1_verification_contract` predicate | G1-RC-3 |
| **G1-P4** | Silent proof reinterpretation | Constraint violation per registry diff predicate | G1-RC-11 |
| **G1-P5** | Deferred / watchlist erasure | `silently_removed[]` non-empty | G1-RC-10, G1-RC-12 |
| **G1-P6** | Cross-layer operational contradiction | `cross_layer_contradictions[]` non-empty without `documented_cause_ref` | G1-RC-5 |
| **G1-P7** | Self-validating governance loop | `normative_loops[]` non-empty or `self_validating_loop_detected=true` | rev5-RC-23 (void) |
| **G1-P8** | Launch surface falsehood | `launch_surface_falsehood_detected=true` | G1-RC-1, G1-RC-9 |
| **G1-P9** | Hidden remediation coupling | `remediation_coupling_detected=true` per change-log predicate | G1-RC-8 |
| **G1-P10** | Governance surveillance saturation | Artefact >6 or mass budget exceeded (aggregate) | G1-RC-14 |

##### 8b. LGS hardening RCs (G1-RC-21–27 reissued)

**Number reissue:** **G1-RC-21–27** are **reissued for LGS hardening** (2026-05-17). Rev 5 **draft** meanings of these IDs are **void**. Historical references use prefix **rev5-** in tag tables only.

| RC | Name | Falsifiable trigger |
|----|------|---------------------|
| **G1-RC-21** | Manifest authority escalation | `manifest_tier_classification≠T1_INDEX_ONLY` or manifest row lacks Tier-0 hash/path derivation |
| **G1-RC-22** | Constitutional mass bypass | `constitutional_mass_accounting_mode` violated or array element exceeds `max_allowed_array_elements[]` |
| **G1-RC-23** | Retired-constitutional reintroduction | Any `retired_artifact_usage_violations[]` non-empty (retired §12 artefact used for pass/fail) |
| **G1-RC-24** | Tracker self-validation loop | `tracker_truth_binding_pass=false` or `unresolved_tracker_claims[]` non-empty |
| **G1-RC-25** | Advisory-tag constitutional escalation | `tag_governance_boundary_pass=false` or `advisory_tag_elevation_attempts[]` non-empty |
| **G1-RC-26** | Non-falsifiable governance predicate | `non_falsifiable_language_inventory[]` non-empty (narrative gate without harness binding) |
| **G1-RC-27** | Critical-proof omission masking | `missing_critical_authoritative_artifacts[]` non-empty while `surveillance_mode=SURVEILLANCE_FULL` |

**Secondary tags (advisory — never alone block VERIFIED/DONE):**

| Tag | Notes |
|-----|-------|
| `TAG_LEGITIMACY_INCOMPLETE` | Missing `acceptance_rationale_ref` at closure |
| `TAG_SEMANTIC_DRIFT` | Vocabulary shift; review |
| `TAG_SUCCESSION_GAP` | Handoff not documented |
| `TAG_CONCENTRATION` | Operator concentration |
| `TAG_REPLAY_NARRATIVE_GAP` | Narrative gap; not product-false |
| `TAG_PARTIAL_KNOWLEDGE` | Degraded mode |
| `TAG_CONTRADICTION_VISIBLE` | Known supersession visible |
| `TAG_AUTHORITY_INCONSISTENT` | Sign-off index gap |

**Tag anti-elevation (mandatory):** `TAG_*` entries are **advisory only**. Tags **must never** independently block VERIFIED or DONE. Policy elevation of any tag to a launch gate requires a **separate approved launch unit** (not G1 amendment), explicit governance amendment record, and new RC lineage — recorded in `advisory_tag_elevation_attempts[]`; violation → **G1-RC-25**.

**Predicate binding (mandatory):** All constitutional conditions in §10 must bind to harness predicates in §14 or `predicate_binding_inventory[]`. Narrative terms without binding → `advisory_only_governance_language[]` only; if used as gate → **G1-RC-26**. Narrative legitimacy cannot substitute for falsifiable legitimacy.

**Precedence (mandatory — `detect_primary_rc`):**

1. **G1-RC-27** → **G1-RC-21** → **G1-P1** → **G1-RC-24** → **G1-P7** → **G1-RC-23** → **G1-P2** → **G1-RC-22** → **G1-P3** → **G1-P4** → **G1-P5** → **G1-P6** → **G1-P8** → **G1-RC-26** → **G1-RC-25** → **G1-P9** → **G1-P10**
2. **G1-P1 / G1-P2 / G1-P3** defeat all secondary tags for VERIFIED.
3. **G1-P7 / G1-RC-24** defeat legitimacy-completeness interpretations.
4. Secondary tags **cannot** block VERIFIED or DONE.

**RC collision resolution:** Suppressed candidates in `g1_launch_readiness_*.secondary_rc_candidates[]` (observational).

##### 9. Falsifiability — launch challenge path (mandatory)

**Purpose:** Cheap, bounded dispute without invalidating entire governance history.

| Field | Rule |
|-------|------|
| `launch_challenge_record` | Tracker appendix entry: `challenge_id`, `tier0_refs[]`, `disputed_claim`, `requested_checks[]` ⊆ {G1-P1,G1-P2,G1-P3,G1-P4,G1-P8,G1-P7} |
| Scope | **Bounded** — max 3 Tier-0 refs per challenge |
| Effect | Triggers **targeted re-surveillance** of listed checks only; no recursive artefact expansion |
| Outcome | Updates `g1_launch_readiness_*.challenge_refs[]`; may elevate primary RC; **does not** delete history |

##### 10. Completion gates and DONE conditions (≤12)

| Gate | Requirement |
|------|-------------|
| **Start `IN_PROGRESS`** | Recovery DoD **signed off** (2026-05-17); T1 harness scope only; `launch_baseline_manifest_{slug}_v1` capture **in progress** |
| **`IMPLEMENTED_PENDING_VERIFICATION`** | Read-only scripts + `test_g1_verification_contract.py` merged |
| **`READY_FOR_STAGING_SURVEILLANCE`** | Six mandatory artefacts emitted; `g1_pass=false` if DEGRADED/BLOCKED |
| **`VERIFIED`** | `surveillance_mode=SURVEILLANCE_FULL`; `g1_pass=true`; no G1-P1–P9; no G1-RC-21–27; `degraded_mode=false` |
| **`DONE`** | §10 constitutional conditions 1–12 only (see programme-process note below) |

**Programme-process maintenance (outside constitutional DONE):** Tracker hygiene, RUNBOOK §12.7 updates, and watchlist registry currency are **operational housekeeping** — **not** constitutional legitimacy and **not** G1 DONE conditions. Operational maintenance ≠ constitutional adequacy.

**G1 cannot reach DONE unless (12 constitutional conditions — each maps to §14 predicate):**

1. Tier-0 manifest integrity-checked — **G1-P1** / **G1-RC-21** clear.
2. No silent normalization/scope expansion — **G1-P2** clear.
3. No product semantic drift — **G1-P3** predicate clear.
4. Proof-context registry constraints satisfied — **G1-P4** predicate clear.
5. No deferred/watchlist erasure — **G1-P5** clear.
6. No cross-layer contradiction without `documented_cause_ref` — **G1-P6** predicate clear.
7. No self-validating governance loop — **G1-P7** / **G1-RC-24** clear.
8. Launch surfaces match Tier-0 — **G1-P8** clear.
9. No hidden remediation coupling — **G1-P9** predicate clear (or advisory-only if change-log unavailable per §14).
10. Surveillance mass within caps — **G1-P10** / **G1-RC-22** clear.
11. `surveillance_mode=SURVEILLANCE_FULL` and `g1_pass=true`.
12. No remediation or proof rewrite under G1 guise.

**VERIFIED prohibition:** Any **G1-P1–P9**; any **G1-RC-21–27**; `degraded_mode=true`; `g1_pass=false`; `surveillance_mode≠SURVEILLANCE_FULL`; secondary tags alone.

##### 11. Phased surveillance tranches (mandatory for first implementation)

| Tranche | Status | Primary RCs | Artefacts |
|---------|--------|-------------|-----------|
| **T1** | **APPROVED** (signoff 2026-05-17) | **G1-P1**, **G1-P2**, **G1-P5**, **G1-RC-21**, **G1-RC-27** | `g1_upstream_integrity_*`, `g1_launch_scope_registry_*`, `g1_launch_readiness_*` |
| **T2** | **Blocked** — separate approval | + G1-P3, G1-P6, G1-P8; G1-RC-24 | + `g1_product_surveillance_*`, `g1_governance_surface_*` |
| **T3** | **Blocked** — separate approval | + G1-P7, G1-P9, G1-P10; G1-RC-22, G1-RC-23, G1-RC-25, G1-RC-26 | + `g1_self_validation_check_*`; full cap enforcement |

**DONE requires T3 complete** — **not** implied by T1 signoff.

###### 11a. Tranche T1 scope (approved — harness only)

**T1 implements only:**

| Work package | Covers |
|--------------|--------|
| Harness scaffolding | `scripts/g1_snapshot.py`, `g1_preflight_capture.py`, `g1_staging_surveillance.py` skeleton — **read-only** |
| Manifest integrity | Tier-0 manifest capture; **G1-RC-21** / **G1-P1** predicates |
| Degraded-state enforcement | `g1_pass=false` when degraded; mode gates in contract tests |
| Critical authoritative verification | `d1b_*`, `e1b_*`, `f1a_*` presence — **G1-RC-27** |
| Registry / erasure checks | Deferred + watchlist registry diff — **G1-P5** |
| Scope / normalization delta (manifest-bound) | **G1-P2** |

**T1 explicitly does NOT implement:**

| Excluded from T1 |
|------------------|
| Full RC matrix (G1-P3–P10 except as listed above) |
| Semantic reinterpretation drift surveillance |
| Institutional survivability simulation |
| Governance succession modelling |
| Anti-fragility expansion |
| Replay archaeology / full replayability narrative |
| Historical contradiction simulation |
| Staging surveillance **execution** (harness run against live pilot) |
| Promotion beyond **`IMPLEMENTED_PENDING_VERIFICATION`** |

##### 12. Deprecated rev 5 structures (retirement — mandatory)

The following are **retired** as normative launch-blocking structures. Historical files in `audit/` remain **queryable** with metadata:

| Deprecated artefact / RC | Retirement flags | `superseded_by` |
|--------------------------|------------------|-----------------|
| `g1_governance_legitimacy_*` | `archived=true`, `non_authoritative=true`, `historical_only=true` | `g1_launch_scope_registry_*` + closure `acceptance_rationale_ref` |
| `g1_bounded_reinterpretation_*` | same | `g1_product_surveillance_*` (P2) |
| `g1_anti_authoritarian_drift_*` | same | `g1_self_validation_check_*` (P7) |
| `g1_governance_replayability_*` | same | `g1_upstream_integrity_*` + manifest |
| `g1_institutional_memory_antifragility_*` | same | tag `TAG_CONCENTRATION` |
| `g1_historical_contradictions_*` | same | `g1_launch_scope_registry_*` |
| `g1_governance_succession_*` | same | `g1_handoff_record_*` (optional) |
| `g1_partial_knowledge_survivability_*` | same | `g1_launch_readiness_*.degraded_mode` |
| `g1_interpretation_drift_*` | same | tag `TAG_SEMANTIC_DRIFT` |
| `g1_governance_authority_*` (full chains) | same | T1 sign-off index in manifest |
| **G1-RC-1 … G1-RC-20** (rev 5 draft IDs) | `historical_only=true` | **G1-P1 … G1-P10** per §8 |
| **G1-RC-21 … G1-RC-27** (rev 5 draft semantics) | `historical_only=true` (draft meaning void) | **Reissued** LGS hardening meanings per §8b |

**Retired artefacts MUST NOT:** participate in launch grounding, satisfy RC checks, satisfy VERIFIED, satisfy DONE, appear in `tier0_grounding[]`, serve as normalization derivation inputs, replay comparison baselines, or legitimacy justification.

**Retired-artifact read prohibition (mandatory — harness):**

| Policy | Rule |
|--------|------|
| `retired_artifact_read_policy[]` | `PASS_FAIL_INPUT=FORBIDDEN`; `VERIFIED_INPUT=FORBIDDEN`; `BASELINE_INPUT=FORBIDDEN`; `HISTORY_QUERY=ALLOWED` |
| Violations | Any read of §12 artefact families for pass/fail → `retired_artifact_usage_violations[]` → **G1-RC-23** |

Compression of retired JSON is **not** simplification if it still influences surveillance outcomes.

##### 13. Boundary reaffirmation (explicit NOT)

| Out of scope |
|--------------|
| Political / org / permissions redesign |
| Governance freezing (safe-harbour clarifications with `approving_unit_ref` remain allowed) |
| Decentralization mandates |
| Auto-remediation, proof rewriting, architecture mutation |
| Re-proof of B–F full staging suites |
| Normative authority from `g1_*` (Tier T3) |
| Tag elevation to launch gates without separate unit | G1-RC-25 |

##### 14. Validation logic (normative — harness contract)

The verification harness **must** implement, without placeholder branches:

| Check | RC | Inputs |
|-------|-----|--------|
| Tier-0 manifest match | G1-P1 | `g1_upstream_integrity_*` |
| Manifest T1 index only | G1-RC-21 | manifest fields |
| Omit-key / scope delta | G1-P2 | `g1_product_surveillance_*`, manifest |
| Semantic fingerprint compare | G1-P3 | `g1_product_surveillance_*` |
| Context constraint violation | G1-P4 | `g1_launch_scope_registry_*` |
| Registry diff | G1-P5 | `g1_launch_scope_registry_*` |
| Cross-layer contradiction | G1-P6 | `g1_product_surveillance_*` |
| Tier graph / normative loops | G1-P7 | `g1_self_validation_check_*` |
| Tracker T0 binding | G1-RC-24 | `g1_governance_surface_*` |
| Surface claim vs Tier-0 | G1-P8 | `g1_governance_surface_*` |
| Remediation coupling | G1-P9 | change log + G1-P3 |
| Mass counter (field+element) | G1-P10 / G1-RC-22 | `g1_launch_readiness_*.constitutional_mass` |
| Retired artefact read guard | G1-RC-23 | `retired_artifact_usage_violations[]` |
| Tag elevation guard | G1-RC-25 | `tag_governance_boundary_pass` |
| Predicate binding audit | G1-RC-26 | `non_falsifiable_language_inventory[]` |
| Critical authoritative presence | G1-RC-27 | `missing_critical_authoritative_artifacts[]` |
| Single `primary_rc` | all | `g1_launch_readiness_*` |
| Pass prohibition if degraded | §5 | `g1_pass`, `surveillance_mode`, `degraded_mode` |
| T3 exclusion from `tier0_grounding` | B1 | `g1_launch_readiness_*` |

##### 15. Anti-expansion constitutional posture (mandatory)

**Recovery success criteria (why simplification succeeded):**

| Reduced | Mechanism |
|---------|-----------|
| Authority | G1-P1–P10 + reissued RC-21–27 only; no rev 5 constitutional trilogy |
| Recursion | T0–T3 tiers; B1–B5 breakers; manifest not `g1a_*` baseline |
| Interpretive surfaces | Six artefacts; field+element cap; predicate binding |
| Hidden legitimacy vectors | Manifest T1-only; retired read ban; tag anti-elevation |
| Constitutional mass | P10 / RC-22; ≤6 artefacts; ≤120 field+element units |

**Future G1 evolution requires:** demonstrated necessity; bounded mass impact; explicit falsifiability; independent signoff lineage; anti-recursion review.

**Programme warning (mandatory):** *Governance sophistication alone is not evidence of governance quality.*

**G1 still does NOT authorize (reaffirmed at signoff):** remediation orchestration; governance restructuring; automatic replay reinterpretation; proof rewriting; topology / queue / scheduler / fanout redesign; policy elevation of advisory tags; self-authorizing governance growth; normative authority from `g1_*` (T3).

**Status:** Recovery DoD **signed off** (2026-05-17). **IN_PROGRESS** — Tranche **T1** harness only. **Surveillance execution pending.** **No** T2/T3 authority implied.

**Next step:** Implement T1 harness scaffolding + `test_g1_verification_contract.py` **T1 subset** → separate approval for **`IMPLEMENTED_PENDING_VERIFICATION`** → later T2/T3 approval → staging surveillance execution.

---

### G2 — Operational observability hardening

| Field | Value |
|-------|-------|
| **ID** | G2 |
| **Priority** | P2 |
| **Trigger** | Parallel G1; after A1 proves explain endpoint |
| **Scope** | Diagnose materialisation, visibility, queue, fanout, activation, exclusions **without** Mongo for routine ops |
| **Canonical authority** | `GOVERNANCE_INDEX.md`; admin explain + provisioning GET + automation centre |
| **Code areas likely affected** | Observability routes, admin dashboard signals |
| **Unit status** | **NOT_STARTED** |
| **Verification evidence** | Operator flow tested; explain documented in RUNBOOK |
| **Governance docs after** | RUNBOOK §12.7; `GOVERNANCE_INDEX.md` |
| **Regression tests** | N/A |
| **Rollback / safety** | Additive admin fields only |

---

### Implementation sequence (mandatory)

```
A1 → (A2 | A3 as triggered) → (B1 → B2 as triggered) → B3
  → C1 → C2 → D1 (+ D2 in parallel) → E1 → F1 **DONE** → G1/G2 continuous
```

**Next approved step:** G1 T1 harness implementation (read-only scaffolding). **Do not** run staging surveillance or expand to T2/T3 without separate approval. **D2** optional parallel. **B2** BLOCKED (product); **B3** BLOCKED/deferred.

---

### TRUST-01 — operational coherence remediation (2026-05-16)

**Status:** **IMPLEMENTED** — frontend remediation verified through OPS-VERIFY-01 Journey A re-submit (2026-05-18) and Journey C supporting-vs-authoritative copy (2026-05-20).

**Scope:** Product-path read/write coherence only — persisted guided compliance evidence records (CER) are human-inspectable in **Requirement details**; supporting-file upload success is separated from authoritative `POST /compliance-evidence` completion; no authority, fanout, lifecycle, or governance expansion.

**Surfaces:** `GET /client/properties/{pid}/requirements/{rid}/compliance-evidence` (existing); `RequirementSubmissionInspectPanel` in `RequirementIntelligenceModal`; truthful guided-submit summary from returned `evidence_record`; presentation-layer lifecycle truthfulness when CER exists (`clientPersistedSubmissionPresentation`); requirements load-failure visibility; dev CORS parity for `127.0.0.1:3000`.

**Out of scope:** E1/F1/G1 reopening; new governance RCs; replay/lineage archaeology.

---

### OPS-VERIFY-01 — client evidence journey operational closure (COMPLETE — A/B/C/D)

**Scope:** Staging walkthrough + DB + async convergence for real client journeys (guided submit, primary upload, supporting-only, document-primary verify/review). **Not** D1/E1/C1/C2/F1 replacement.

**Rule:** Infrastructure replay proof ≠ operational closure proof.

**Unit status:** **COMPLETE** for pilot evidence journeys **A/B/C/D** on `6fd5ac4c` / `d35a58ae`. Reject/resubmit and structured CER review path remain **watchlist**, not blockers.

| Journey | Status |
|---------|--------|
| **A** guided structured evidence submit | **VERIFIED_OPERATIONALLY** — existing-CER **re-submit** on pilot `occupation_contract` (`488269bb-…`) via browser `?open=resolve` (`proof_mode: operational_browser`); bundle `docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/`. |
| **A** clean first-submit | **Watchlist** — no greenfield guided requirement on pilot property; first-time modal submit not attested. |
| **B** primary document upload | **VERIFIED_OPERATIONALLY** — **fire_alarm** `69fc66fe-…` primary document upload via `/documents` deeplink. |
| **C** supporting-upload-only | **VERIFIED_OPERATIONALLY** — supporting upload only; `cer_delta=0`; truthful UI after TRUST remediation (2026-05-20). |
| **D** verify/review | **VERIFIED_OPERATIONALLY** — document-primary admin verify/override on Journey B `fire_alarm` doc `a9fd10d8-…`; linked DOCUMENT_UPLOAD CER review-state alignment; browser attestation (2026-05-21). |
| **D** reject/resubmit | **Watchlist** — not exercised on pilot. |
| **D** structured CER review path | **Watchlist** — occupation_contract CER `cer_979c…` structured review path not attested. |

**Harness:** Read-only capture/classify scripts `backend/scripts/ops_verify_01_{capture,manifest,classify,snapshot}.py`; evidence bundles under `docs/audit/ops_verify_01_{slug}/`. Classifier run per journey against journey-appropriate capture snapshots; roll-up `ops_verify_01_classifications.json` lists A–D `VERIFIED_OPERATIONALLY`.

**Done when:** Evidence bundles under `audit/ops_verify_01_*` and classifications A–D `VERIFIED_OPERATIONALLY` (or signed waiver) — **met** (2026-05-21).

**Out of scope:** Governance expansion, architecture redesign, new RC systems.

---

### CONDITION_STANDARD_ACTIVE_STANDARD — Phase 1 foundation (2026-05-20)

**Status:** **IMPLEMENTED** (runtime foundation). **`repairing_standard`:** **`VERIFIED_OPERATIONALLY`**. **`fitness_for_human_habitation`:** **`VERIFIED_OPERATIONALLY`** (2026-05-23 after staging registry remediation). **NOT** launch-ready.

**Scope:** Bounded pilot materialisation for `fitness_for_human_habitation` / `repairing_standard`; operational convergence read-model (`active_standard_status_summary`); authority/lifecycle hardening; truthful UX + inspect panel; OPS readiness helpers. **No** upload-primary closure; **no** global planner materialisation; **no** asset-authoritative synthesis.

**Surfaces:** `services/condition_standard_pilot_materialisation.py` (`evaluate_condition_standard_pilot_runtime_legitimacy`); `services/requirement_client_runtime_surface.py` (bounded pilot pass); `services/ops_condition_standard_readiness.py`; admin `POST …/condition-standard-pilot-materialise`; `ConditionStandardOperationalInspectPanel`; `docs/audit/CONDITION_STANDARD_ACTIVE_STANDARD_OPS.md`.

**Pilot allowlist:** England FFHH `6bcc43c0…` / `3a69dcbd…`; Scotland RS `ec0b091b…` / `def23b30…` — rows exist only after explicit admin materialise invoke.

**OPS programme:** `PRELAUNCH-OPS-VERIFY-CONDITION-STANDARD-01` — **`repairing_standard`** and **`fitness_for_human_habitation`** each **`VERIFIED_OPERATIONALLY`** in independent same-run browser OPS. FFHH required staging publish of `FITNESS_FOR_HUMAN_HABITATION|ENGLAND` (published v24) before runtime legitimacy passed — **not** a legitimacy bypass.

**Watchlist:** Pilot-only posture retained; no fleet rollout; no launch authorization.

**Done when:** OPS bundles per obligation classify `VERIFIED_OPERATIONALLY` in same run — **met for both allowlisted obligations**.

---

### PRELAUNCH-OPS-RUNTIME-VERIFY-01 — operational domain runtime closure (DEFINED — hardened charter)

**Status:** **IN_PROGRESS** — F1 `VERIFIED_OPERATIONALLY` (2026-05-23 rerun post G9 fix). F2+ pending.

**Charter:** [`docs/PRELAUNCH_OPS_RUNTIME_VERIFICATION.md`](../../../docs/PRELAUNCH_OPS_RUNTIME_VERIFICATION.md)

**Scope:** Real browser + async + DB verification for **operations runtime domains** only: issues, work orders, contractor portal, risk signals, client sync, rent ops (browser runtime), tenant portal visibility, cross-domain integration chain.

**Core governance additions (rev 2):**

| Mechanism | Purpose |
|-----------|---------|
| **Operational ownership model** | One authoritative family per mutation origin; no duplicate lifecycle verification |
| **G9 Idempotency** | Repeat click / refresh / retry / async fanout duplicate protection |
| **G10 Authority integrity** | Role-based mutation legitimacy; monotonic lifecycle; forbidden transitions |
| **Family 8 anti-duplication** | Integration-only; references owner `07_classification.json` bundles |
| **TRUST_RISK_PRESENT** | Blocks silent upgrade; tenant misinformation + false completion semantics |
| **Rent Family 6 rule** | Prior `RENT-OPS-OPERATIONAL-VERIFY-01` = baseline system integrity only; browser rerun required for `VERIFIED_OPERATIONALLY` |

**Operational ownership map:**

| Mutation origin | Authoritative family | Slug |
|-----------------|----------------------|------|
| Issue lifecycle | 1 | `ops_runtime_01_issues` |
| WO / job lifecycle | 2 | `ops_runtime_02_work_orders` |
| Contractor sync | 3 | `ops_runtime_03_contractor` |
| Risk propagation | 4 | `ops_runtime_04_risk_signals` |
| Cross-surface convergence | 5 | `ops_runtime_05_client_sync` |
| Rent lifecycle | 6 | `ops_runtime_06_rent_ops` |
| Tenant-originated maintenance | 7 | `ops_runtime_07_tenant_portal` |
| Full-chain integrity (integration only) | 8 | `ops_runtime_08_cross_domain` |

**Family status:**

| Family | Slug | Status | Classification |
|--------|------|--------|----------------|
| Issues | `ops_runtime_01_issues` | VERIFIED_OPERATIONALLY | Post-G9 remediation rerun `20260523T113129Z`; bundle `ops_runtime_01_issues_6fd5ac4c_d35a58ae` |
| Work orders | `ops_runtime_02_work_orders` | NOT_STARTED | — |
| Contractor | `ops_runtime_03_contractor` | NOT_STARTED | — |
| Risk signals | `ops_runtime_04_risk_signals` | NOT_STARTED | — |
| Client sync | `ops_runtime_05_client_sync` | NOT_STARTED | — |
| Rent ops | `ops_runtime_06_rent_ops` | NOT_STARTED | RENT-OPS baseline system integrity only; browser pending |
| Tenant portal | `ops_runtime_07_tenant_portal` | NOT_STARTED | — |
| Cross-domain | `ops_runtime_08_cross_domain` | NOT_STARTED | BLOCKED until upstream owner bundles exist |

**Related baseline (does not confer runtime VERIFIED_OPERATIONALLY):**

| Programme | Status |
|-----------|--------|
| `RENT-OPS-OPERATIONAL-VERIFY-01` | Baseline system integrity — `backend/docs/audit/rent_ops_verify_01/REPORT.md` |

**Done when:** Each in-scope family `VERIFIED_OPERATIONALLY` or signed `WATCHLIST` with owner; no open `TRUST_RISK_PRESENT` without remediation plan; Family 8 references upstream owner bundles (no duplicate lifecycle proof).

**Out of scope:** Launch authorization · UK rollout · asset-native synthesis · accounting certification · compliance authority redesign · planner redesign · AI ops orchestration · merging with OPS-VERIFY-01.

---

*Maintainers: **L-00x** rows use **§ Finishable unit contract**; **A1–G2** rows use **§ Recovery unit implementation contract** (end-to-end, status lifecycle, ten DONE gates). After each pass: update statuses (never skip `IMPLEMENTED_PENDING_VERIFICATION` → `VERIFIED` → `DONE`), paste closure evidence, unlock next unit. Do not declare wider launch without updating this file and the ten-gate table.*
