# Compliance Vault Pro — Launch Authority Tracker

**Program:** Compliance Vault Pro Launch Authority Program  
**Role:** Single source of truth for launch blockers, stabilization, deferred/accepted risks, and governance status.  
**Baseline:** PRE-LAUNCH GOVERNANCE AUDIT (Directions A — Product Hardening, B — User Trust UX, C — Commercial Readiness). *If the audit lives outside this repository, link the canonical export here when available.*

**Allowed status values only:** `READY` | `PARTIAL` | `BLOCKED` | `DEFERRED_FOR_POST_LAUNCH` | `ACCEPTED_LAUNCH_RISK`

**Last tracker update:** 2026-05-16 (C1 **DONE** — administrative closure; C2 DoD drafting only)

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
| **C** | Scheduler / queue | [runbooks/SCHEDULER_AND_COMPLIANCE_JOBS.md](../runbooks/SCHEDULER_AND_COMPLIANCE_JOBS.md); **L-006** | `job_runs`, `compliance_recalc_queue`, `scheduler_heartbeat` | Platform ops | **LAUNCH_CRITICAL** | **DONE** (unit **C1** 2026-05-16) | Pilot queue replay + M2; see C1 closure evidence |
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
| **C2** | **BLOCKED** (DoD **not drafted**) | **Unlocked:** DoD drafting only — no implementation |
| **C3+** | **BLOCKED** | After C2 |

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
| **Unit status** | **BLOCKED** (implementation) — **UNLOCKED for DoD drafting only** after C1 **DONE**; DoD **not drafted** |
| **Verification evidence** | No stale conflicting state across surfaces; timestamps/audit align; bounded lag documented |
| **Governance docs after** | Closed-loop tracker stream notes; gap analysis cross-ref |
| **Regression tests** | Stream E fanout tests; gap sync tests |
| **Rollback / safety** | Use validate-compliance-score diagnose before fix |

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
| **Unit status** | **BLOCKED** (pending C) |
| **Verification evidence** | Fanout trace on governed mutation; blocked case has `propagation_notice` / activation reason |
| **Governance docs after** | **L-009** inventory if new route; AUTHORITY_WRITE_PATH |
| **Regression tests** | `test_requirement_transition_fanout_phase4.py`, L-009 HTTP suites |
| **Rollback / safety** | Do not bypass activation registry |

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
| **Unit status** | **BLOCKED** (pending D) |
| **Verification evidence** | Verify changes requirement projection; gap sync follows; audit event |
| **Governance docs after** | **L-004** row; AUTHORITY_WRITE_PATH |
| **Regression tests** | Evidence review HTTP suites; operational state tests |
| **Rollback / safety** | Reconciliation job dry_run first |

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
| **Unit status** | **BLOCKED** (pending E) |
| **Verification evidence** | `message_logs`; blocked sends have governed reason; **no** notification as obligation-creation proof |
| **Governance docs after** | JSON inventory if policy changes |
| **Regression tests** | L-008 contract tests |
| **Rollback / safety** | Do not globally activate NOTIFICATION_DISPATCH without program sign-off |

---

### G1 — Support / admin operational recovery

| Field | Value |
|-------|-------|
| **ID** | G1 |
| **Priority** | P1 |
| **Trigger** | After A–F; continuous improvement |
| **Scope** | Admin explain tools; support playbook; safe sync/retry; classify A/B/C from UI/runbook |
| **Canonical authority** | `RUNBOOK_CONTROLLED_BETA_OPERATIONS.md`; `SUPPORT_REMEDIATION_CORRELATION_VIEW_V1.md` |
| **Code areas likely affected** | Admin SPA provisioning panel, explain endpoint discoverability |
| **Unit status** | **NOT_STARTED** |
| **Verification evidence** | Support drill: classify failure without Mongo; closure in tracker |
| **Governance docs after** | RUNBOOK §12.6–§12.7 |
| **Regression tests** | N/A |
| **Rollback / safety** | Correlation view remains non-authoritative |

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
  → C1 → C2 → D1 (+ D2 in parallel) → E1 → F1 → G1/G2 continuous
```

**Next approved step:** Draft **C2** Definition of Done only (downstream convergence). **C2 implementation BLOCKED** until C2 DoD approved. **B2** BLOCKED (product); **B3** BLOCKED/deferred.

---

*Maintainers: **L-00x** rows use **§ Finishable unit contract**; **A1–G2** rows use **§ Recovery unit implementation contract** (end-to-end, status lifecycle, ten DONE gates). After each pass: update statuses (never skip `IMPLEMENTED_PENDING_VERIFICATION` → `VERIFIED` → `DONE`), paste closure evidence, unlock next unit. Do not declare wider launch without updating this file and the ten-gate table.*
