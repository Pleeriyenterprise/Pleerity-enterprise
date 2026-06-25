# Requirement Lifecycle — Master Implementation Tracker

**Authority:** `ADR_REQUIREMENT_LIFECYCLE_SEMANTICS.md`, `REQUIREMENT_LIFECYCLE_PHASE2_IMPLEMENTATION_DESIGN_01.md`  
**Maintained:** Programme / lifecycle workstream  
**Last updated:** 2026-06-02 (Phase 5 P5-S4/S5 in progress on `feature/lifecycle-phase5-p5-s4-s5-kpi-exposure`; develop @ `9f356509`)  
**Purpose:** Single source of truth for phases, slices, PRs, commits, gates, and remaining work.

---

## Phase 5 status: **IN PROGRESS** (P5-S1–S3 merged; P5-S4/S5 in progress — 2026-06-02)

Phase 5 (lifecycle-aware dashboard KPIs) is underway. **P5-S1**, **P5-S2**, and **P5-S3** are merged to `develop` and deployed to staging in **shadow** governance (`LIFECYCLE_AWARE_KPIS=shadow`). **P5-S5** (additive API `lifecycle_kpi_breakdown`) and **P5-S4** (dashboard attention strip) are **in progress** on branch `feature/lifecycle-phase5-p5-s4-s5-kpi-exposure`.

| Phase 5 slice | Status | PR | Merge SHA |
|---------------|--------|-----|-----------|
| **P5-S1** — KPI flag infrastructure | **Complete** | [#14](https://github.com/Pleeriyenterprise/Pleerity-enterprise/pull/14) | `10ef1733` |
| **P5-S2** — shadow KPI telemetry (`lifecycle_kpi_shadow_*`) | **Complete** | [#15](https://github.com/Pleeriyenterprise/Pleerity-enterprise/pull/15) | `acd7d675` |
| **P5-S3** — active KPI authority switch (preview-only) | **Complete** | [#16](https://github.com/Pleeriyenterprise/Pleerity-enterprise/pull/16) | `4fd1d3e1` |
| **P5-S5** — additive API `lifecycle_kpi_breakdown` | **In progress** | — | — |
| **P5-S4** — dashboard attention strip | **In progress** | — | — |
| **P5-S4b** — portfolio/requirements straggler convergence | **Deferred** | — | — |
| **P5-S6** — reports / digest / exports | **Not started** | — | — |
| **P5-S7** — legacy deprecation | **Not started** | — | — |

**`develop` tip:** `9f356509` (P5-S3 governance closeout)  
**Feature branch:** `feature/lifecycle-phase5-p5-s4-s5-kpi-exposure` (P5-S4/S5)  
**Staging deploy:** `4fd1d3e1` @ `pleerity-enterprise.onrender.com` — `environment=staging`, `/api/health` **healthy**, `/api/version` confirms SHA  
**`main` / production:** `60c1dbbe` — **untouched**

**P5-S3 dependencies:** P5-S1 (`lifecycle_aware_kpis_config.py`), P5-S2 (`lifecycle_kpi_gates.py` shadow telemetry).

**P5-S3 active authority switch:** `compute_client_portal_requirement_stats` in `requirement_client_runtime_surface.py` — single choke point; **off/shadow** → legacy; **active (preview)** → lifecycle via `lifecycle_stats_authoritative_payload(compute_lifecycle_kpi_stats(...))`.

**P5-S5 additive API:** `stats.lifecycle_kpi_breakdown` on compliance-score path only; 8-key KPI contract unchanged.

**P5-S4 dashboard:** supplemental `LifecycleKpiAttentionStrip` below headline KPI tiles; tiles remain authoritative from 8-key `stats`.

**Next slice after P5-S4/S5:** **P5-S4b** — portfolio/requirements straggler convergence; then **P5-S6** reports.

---

## Phase 4 status: **COMPLETE** (2026-06-02)

Phase 4 (lifecycle-aware reminders) is **closed**. All planned slices (S4.1–S4.4) are merged to `develop` and deployed to staging in **shadow** governance. No further Phase 4 feature slices should be added except critical bug fixes. **Next programme work: Phase 5 (dashboard KPIs).**

| Phase 4 slice | Status | PR | Merge SHA |
|---------------|--------|-----|-----------|
| **S4.1** — reminder flag infrastructure | **Complete** | [#11](https://github.com/Pleeriyenterprise/Pleerity-enterprise/pull/11) | `4a15747a` |
| **S4.2** — shadow reminder telemetry | **Complete** | [#12](https://github.com/Pleeriyenterprise/Pleerity-enterprise/pull/12) | `906e67b6` |
| **S4.3** — active eligibility gates + template routing | **Complete** | [#12](https://github.com/Pleeriyenterprise/Pleerity-enterprise/pull/12) | `906e67b6` |
| **S4.4** — dedicated `attention_kind` email/SMS templates | **Complete** | [#13](https://github.com/Pleeriyenterprise/Pleerity-enterprise/pull/13) | `c58616e2` |

**`develop` tip:** `c58616e2` (S4.4 merge); governance closeout commit `ac0357f9` local ahead of `origin/develop`  
**Staging deploy:** `c58616e2` @ `pleerity-enterprise.onrender.com` — `environment=staging`, `/api/health` **healthy**, `/api/version` confirms SHA  
**`main` / production:** `60c1dbbe` — **untouched**

---

## Phase 3 status: **COMPLETE** (2026-06-25)

Phase 3 (lifecycle-aware scoring) is **closed**. All planned slices (S3.1–S3.3) are merged to `develop` and deployed to staging in **shadow** governance. No further Phase 3 feature slices should be added except critical bug fixes. **Next programme work: Phase 4 (reminders).**

| Phase 3 slice | Status | PR | Merge SHA |
|---------------|--------|-----|-----------|
| **S3.1** — scoring flag infrastructure | **Complete** | [#9](https://github.com/Pleeriyenterprise/Pleerity-enterprise/pull/9) | `f29e066d` |
| **S3.2** — shadow scoring telemetry | **Complete** | [#10](https://github.com/Pleeriyenterprise/Pleerity-enterprise/pull/10) | `e07f8fd0` |
| **S3.3** — active penalty gates | **Complete** | [#10](https://github.com/Pleeriyenterprise/Pleerity-enterprise/pull/10) | `e07f8fd0` |

**`develop` tip:** `906e67b65ae6c04316ecf53a82a7e2b8c20faeac`  
**Staging deploy:** `906e67b6` @ `pleerity-enterprise.onrender.com` — `environment=staging`, health **healthy**  
**`main` / production:** `60c1dbbe` — **untouched**

---

## Phase 2 status: **FEATURE-COMPLETE** (frozen)

Phase 2 (confirm + extraction) is **closed** and frozen. See Phase 2 slice table below.

| Phase 2 slice | Status | PR | Merge SHA |
|---------------|--------|-----|-----------|
| Phase 1 — resolver/shadow | **Complete** | [#3](https://github.com/Pleeriyenterprise/Pleerity-enterprise/pull/3) | `a4dd04c5` |
| Phase 2 S1–S3 — profiles/contracts | **Complete** | [#4](https://github.com/Pleeriyenterprise/Pleerity-enterprise/pull/4) | `5462d2b0` |
| Phase 2 S4 — shadow validation | **Complete** | [#5](https://github.com/Pleeriyenterprise/Pleerity-enterprise/pull/5) | `46a3c74e` |
| Phase 2 S5.1–S5.3 — persistence + UI | **Complete** | [#6](https://github.com/Pleeriyenterprise/Pleerity-enterprise/pull/6) | `757f328f` |
| Phase 2 S5.4 — preview-only confirm enforcement | **Complete** | [#7](https://github.com/Pleeriyenterprise/Pleerity-enterprise/pull/7) | `b6d79641` |
| Phase 2 S5-extract — profile-aware extraction shadow | **Complete** | [#8](https://github.com/Pleeriyenterprise/Pleerity-enterprise/pull/8) | `d017a084` |

---

---

## Phase 4 Operational Observations

Recorded for Phase 5+ planning. **None block Phase 4 completion.**

| Observation | Classification | Notes |
|-------------|----------------|-------|
| Runtime evidence campaign (48h) for **reminder** shadow logs | Operational | Pending measured `lifecycle_reminder_shadow_*` on staging @ `c58616e2` |
| Preview active reminder soak not started | Operational | `LIFECYCLE_AWARE_REMINDERS=active` preview-tier only |
| Staging shadow dual reminder evaluate when flag=shadow | Operational | Legacy eligibility authoritative; lifecycle path observe-only |
| `jobs.py` email payload still uses `get_effective_expiry_date()` after truth | Carry-forward | Preview-active display edge case only |

---

## Phase 3 Operational Observations

Recorded for Phase 4+ planning. **None block Phase 3 completion.**

| Observation | Classification | Notes |
|-------------|----------------|-------|
| Runtime evidence campaign (48h shadow log measurement) for **scoring** still **pending** | Operational | No measured `lifecycle_scoring_shadow_*` counts on staging yet; RUNTIME-EVIDENCE-GATE-01 |
| Preview active scoring soak not started | Operational | `LIFECYCLE_AWARE_SCORING=active` preview-tier only; staging/production remain shadow/off |
| Staging shadow executes dual scoring compute when flag=shadow | Operational | Legacy fractions authoritative; lifecycle path observe-only |
| Phase 2 operational observations (extraction dual-LLM, confirm fixture, S7/S8/S9) | Carry-forward | See Phase 2 table below; still open where noted |

---

## Phase 2 Operational Observations

| Observation | Classification | Notes |
|-------------|----------------|-------|
| Staging shadow **dual extraction** when `LIFECYCLE_AWARE_EXTRACTION=shadow` | Operational | Legacy authoritative; expected LLM cost increase |
| Runtime evidence campaign (48h) for confirm/extraction shadow | Operational | Pending measured `lifecycle_extract_shadow_*` on staging |
| Admin confirm fixture (`test_document_extraction.py`) stale under active confirm | Test hygiene | S5.4 fallout |
| `deployment-governance` CI staging URL in frontend tests | **Resolved** | Fixed in PR #10 (`api.example.test` fixtures) |
| Design S7 admin UI confirm parity | Deferred | Not Phase 3 scope |
| Design S8 preview active soak (V2-U1–U10) | Deferred | Cross-phase promotion gate |
| Design S9 pipeline convergence | Deferred | Optional |

---

## 1. Original roadmap (ADR initiative phases)

| Phase | Name | Deliverable | Feature flag | Status |
|-------|------|-------------|--------------|--------|
| **0** | ADR promotion | `ADR_REQUIREMENT_LIFECYCLE_SEMANTICS.md` | — | Complete |
| **1** | Resolver + registry backfill | `lifecycle_semantics_resolver.py` | `LIFECYCLE_SEMANTICS_MODE` | Complete |
| **2** | Confirm + extraction | Profiles, confirm contract | `LIFECYCLE_AWARE_CONFIRM`, `LIFECYCLE_AWARE_EXTRACTION` | Complete |
| **3** | Scoring gates | Penalty eligibility via `field_contract` | `LIFECYCLE_AWARE_SCORING` | **Complete** |
| **4** | Reminders + gaps | `attention_kind` templates | `LIFECYCLE_AWARE_REMINDERS` | **Complete** |
| **5** | Dashboard KPIs | Split widgets | `LIFECYCLE_AWARE_KPIS` | **IN PROGRESS** (P5-S3 complete; P5-S4 next) |
| **6** | Reports + digest | Section language | — | Not started |
| **7** | Legacy deprecation | Remove independent expiry inference | — | Not started |

---

## 2. Expanded roadmap — implementation slices

| Slice | Phase | Summary | Status |
|-------|-------|---------|--------|
| Phase 1 — resolver/shadow | 1 | Observe-only semantics resolver | **Merged** |
| Phase 2 S1–S5-extract | 2 | Confirm + extraction programme | **Merged** |
| Design S7–S9 | 2+ | Admin UI, soak gate, pipeline convergence | **Deferred** |
| **Phase 3 S3.1** | 3 | `LIFECYCLE_AWARE_SCORING` flag + boot + CI | **Merged** PR #9 |
| **Phase 3 S3.2** | 3 | Shadow scoring telemetry (`lifecycle_scoring_shadow_*`) | **Merged** PR #10 |
| **Phase 3 S3.3** | 3 | Active penalty gates + projector overlay | **Merged** PR #10 |
| **Phase 4 S4.1** | 4 | `LIFECYCLE_AWARE_REMINDERS` flag + boot + CI | **Merged** PR #11 |
| **Phase 4 S4.2** | 4 | Shadow reminder telemetry (`lifecycle_reminder_shadow_*`) | **Merged** PR #12 |
| **Phase 4 S4.3** | 4 | Active eligibility gates + template routing authority | **Merged** PR #12 |
| **Phase 4 S4.4** | 4 | Dedicated `attention_kind` email/SMS templates | **Merged** PR #13 |
| **Phase 5 P5-S1** | 5 | `LIFECYCLE_AWARE_KPIS` flag + boot + CI | **Merged** PR #14 |
| **Phase 5 P5-S2** | 5 | Shadow KPI telemetry (`lifecycle_kpi_shadow_*`) | **Merged** PR #15 |
| **Phase 5 P5-S3** | 5 | Active KPI authority switch (preview-only) | **Merged** PR #16 |
| Phase 5 P5-S5 | 5 | Additive API `lifecycle_kpi_breakdown` | **In progress** |
| Phase 5 P5-S4 | 5 | Dashboard attention strip | **In progress** |
| Phase 5 P5-S4b | 5 | Portfolio/requirements straggler convergence | Deferred |
| Phase 6 reports | 6 | Report/digest language | Not started |
| Phase 7 legacy deprecation | 7 | Remove independent expiry inference | Not started |

---

## 3. Status table

| Item | Status | PR | Merge SHA | Merged | Staging | Production |
|------|--------|-----|-----------|--------|---------|------------|
| Phase 1 | Complete | #3 | `a4dd04c5` | Yes | Lineage | Untouched |
| Phase 2 (all slices) | Complete | #4–#8 | `d017a084` | Yes | Deployed | Untouched |
| Phase 3 S3.1 | Complete | #9 | `f29e066d` | Yes | Deployed | Untouched |
| Phase 3 S3.2–S3.3 | Complete | #10 | `e07f8fd0` | Yes | Deployed @ `e07f8fd0` | Untouched |
| Phase 4 S4.1 | Complete | #11 | `4a15747a` | Yes | Deployed | Untouched |
| Phase 4 S4.2–S4.3 | Complete | #12 | `906e67b6` | Yes | Deployed @ `906e67b6` | Untouched |
| Phase 4 S4.4 | Complete | #13 | `c58616e2` | Yes | Deployed @ `c58616e2` | Untouched |
| Phase 5 P5-S1 | Complete | #14 | `10ef1733` | Yes | Deployed @ `10ef1733` | Untouched |
| Phase 5 P5-S2 | Complete | #15 | `acd7d675` | Yes | Deployed @ `acd7d675` | Untouched |
| Phase 5 P5-S3 | Complete | #16 | `4fd1d3e1` | Yes | Deployed @ `4fd1d3e1` | Untouched |
| Phase 5 P5-S5 | In progress | — | — | No | — | Untouched |
| Phase 5 P5-S4 | In progress | — | — | No | — | Untouched |
| Phase 5 P5-S4b / S6–S7 | Not started | — | — | No | — | Untouched |

**Branch heads (2026-06-02):**

| Branch | HEAD |
|--------|------|
| `develop` | `9f356509` |
| `feature/lifecycle-phase5-p5-s4-s5-kpi-exposure` | P5-S4/S5 (in progress) |
| `main` | `60c1dbbe` |

**Staging configuration:** `DEPLOYMENT_TIER=staging`, `LIFECYCLE_AWARE_CONFIRM=shadow`, `LIFECYCLE_AWARE_EXTRACTION=shadow`, `LIFECYCLE_AWARE_SCORING=shadow`, `LIFECYCLE_AWARE_REMINDERS=shadow`, `LIFECYCLE_AWARE_KPIS=shadow` — all shadow-only @ `4fd1d3e1`.  
**Production configuration:** `render.production.yaml` — **no lifecycle flags** (including no `LIFECYCLE_AWARE_KPIS`).

---

## 4. Phase 3 scope delivered

- `lifecycle_aware_scoring_config.py` — flag, tier guards, boot validation
- `lifecycle_scoring_gates.py` — resolver context, shadow observe, projector gate helper
- `compliance_scoring_v2.py` — dual-run shadow; active gates via `requires_expiry_date`; suppress non-`EXPIRY_BASED` `due_date` penalties
- `customer_status_projector_v2.py` — `EXPIRY_DATE_NEEDED` gated when scoring active
- CI governance for production blueprint
- STREAM_B §5b scoring authority inventory

**In progress (Phase 5 P5-S4/S5):** additive KPI API field `lifecycle_kpi_breakdown` (compliance-score path); dashboard attention strip (`LifecycleKpiAttentionStrip`).

**Not implemented (Phase 5 P5-S4b / S6–S7 per ADR):** portfolio/requirements straggler convergence, reports/digest/exports language, legacy deprecation.

---

## 5a. Phase 5 P5-S1 scope delivered (merged PR #14)

- `lifecycle_aware_kpis_config.py` — flag, tier guards, boot validation (`validate_lifecycle_kpi_boot`)
- `server.py` — boot guard registration (after reminders)
- `deployment_governance_ci_gate.py` — reject `LIFECYCLE_AWARE_KPIS=active` in production blueprints
- `render.staging.yaml` — `LIFECYCLE_AWARE_KPIS=shadow`
- `test_lifecycle_kpis_p5_s1.py` — flag/tier/CI tests
- STREAM_B §5d KPI authority inventory

**Explicitly not in P5-S1:** KPI calculations, dashboard widgets, dashboard APIs, reporting, reminder/scoring/confirm/extraction semantics, production config changes.

---

## 5b. Phase 5 P5-S2 scope delivered (merged PR #15)

- `lifecycle_kpi_gates.py` — resolver context, shadow `lifecycle_kpi_shadow_*` logs, `attention_kind` bucket aggregation
- `requirement_client_runtime_surface.py` — dual-run shadow in `compute_client_portal_requirement_stats`; legacy stats authoritative
- `test_lifecycle_kpis_p5_s2.py` — shadow divergence, legacy authority tests

**Staging behaviour:** `LIFECYCLE_AWARE_KPIS=shadow` — legacy `compute_client_portal_requirement_stats` authoritative; lifecycle path observe-only.

**Not in P5-S2:** dashboard widget/API changes, active KPI gates (P5-S3), reports, production config.

---

## 5c. Phase 5 P5-S3 scope delivered (merged PR #16)

- `lifecycle_kpi_gates.py` — explicit semantics→bucket map (no `CERTIFICATE_EXPIRING` fallback); `lifecycle_stats_authoritative_payload`
- `requirement_client_runtime_surface.py` — authority switch in `compute_client_portal_requirement_stats`: **off/shadow** → legacy; **active** → lifecycle
- `test_lifecycle_kpis_p5_s3.py` — active/shadow/legacy, semantics, tier guards, rollback
- `test_lifecycle_kpis_p5_s3_authority_regression.py` — atomic authority guards, payload contract, single entry-point regression

**Active authority switch:** `compute_client_portal_requirement_stats` — single KPI choke point.

**Preview behaviour:** `LIFECYCLE_AWARE_KPIS=active` + preview tier → lifecycle-gated counts returned (8-key payload unchanged).

**Staging/production:** raw `active` downgraded (shadow / off); staging remains legacy authoritative.

**Not in P5-S3:** dashboard widgets (P5-S4), additive API fields / `lifecycle_kpi_breakdown` (P5-S5), reports (P5-S6), frontend, production config.

**Next slice:** P5-S4/S5 — dashboard exposure + additive API (in progress).

## 5d. Phase 5 P5-S5 scope (in progress)

- `lifecycle_kpi_gates.py` — `lifecycle_kpi_breakdown_api_payload`, `lifecycle_kpi_breakdown_for_portal_rows`, `LIFECYCLE_KPI_BREAKDOWN_KEYS`
- `compliance_score.py` — additive `stats.lifecycle_kpi_breakdown` + `stats.lifecycle_kpi_effective_mode` when flag ≠ off
- `routes/client.py` — `server_feature_flags.lifecycle_aware_kpis_effective_mode` on dashboard response
- `test_lifecycle_kpis_p5_s5.py` — breakdown payload, mode gating, authority regression guards

**Additive only:** 8-key KPI contract (`total_requirements`, `compliant`, `satisfied`, `status_valid`, `pending`, `missing_evidence`, `expiring_soon`, `overdue`) unchanged.

**Breakdown keys:** `certificate_expiring`, `review_due`, `event_action_required`, `tenancy_term_ending`, `occupancy_review_due`, `operational_action_required`.

**Not in P5-S5:** reports, digest, exports, portfolio/requirements stragglers (P5-S4b), production config.

## 5e. Phase 5 P5-S4 scope (in progress)

- `frontend/src/utils/lifecycleKpiBreakdown.js` — parse/normalize breakdown from dashboard API
- `frontend/src/components/dashboard/LifecycleKpiAttentionStrip.jsx` — supplemental attention strip below headline KPI tiles
- `frontend/src/pages/ClientDashboard.js` — strip wired; headline tiles unchanged (`expiring_soon` from 8-key field)

**Off mode:** no breakdown in API; strip hidden.

**Shadow mode:** legacy tiles authoritative; supplemental strip visible when breakdown buckets non-zero.

**Active mode (preview):** lifecycle authority on 8-key stats; strip visible.

**Not in P5-S4:** portfolio/requirements straggler convergence (P5-S4b), reports (P5-S6), production config.

## 4b. Phase 4 S4.2/S4.3 scope delivered (merged PR #12)

- `lifecycle_reminder_gates.py` — resolver context, shadow `lifecycle_reminder_shadow_*` logs, active certificate-expiry pipeline gates, template routing authority
- `reminder_truth_service.py` — dual-run shadow; active uses lifecycle eligibility (legacy authoritative on staging shadow)
- `jobs.py` — `resolve_lifecycle_reminder_template_key` for email/SMS sends; `lifecycle_attention_kind` on reminder items
- `test_lifecycle_reminders_s42_s43.py` — shadow divergence, active gates, template routing

**Staging behaviour:** `LIFECYCLE_AWARE_REMINDERS=shadow` keeps legacy eligibility authoritative; lifecycle path observe-only.

**Active (preview-tier only):** suppresses non-`EXPIRY_BASED` requirements from `DAILY_COMPLIANCE_EXPIRY_*` pipeline.

**Not in S4.2/S4.3:** scheduler registration changes, email/SMS template body changes, customer wording changes, scoring/dashboard/report changes.

---

## 4c. Phase 4 S4.4 scope delivered (merged PR #13)

- `lifecycle_reminder_template_registry.py` — 12 templates (6 EMAIL + 6 SMS), kind-specific copy, seed rows
- `lifecycle_reminder_gates.py` — planned `LIFECYCLE_REMINDER_*` routing (active preview only)
- `email_service.py` / `notification_orchestrator.py` — code-built lifecycle reminder render path
- `jobs.py` — resolved template keys in idempotency; lifecycle subjects when active
- `test_lifecycle_reminders_s44.py` — registry, routing, copy tests

**Staging behaviour:** `LIFECYCLE_AWARE_REMINDERS=shadow` — legacy `COMPLIANCE_EXPIRY_*` templates authoritative; planned lifecycle routing logged only.

**Active (preview-tier only):** sends `LIFECYCLE_REMINDER_*` per `attention_kind`; not enabled on staging or production.

**Not in S4.4:** scheduler registration, scoring, dashboard, report, production config changes.

---

## 4a. Phase 4 S4.1 scope delivered (infrastructure only)

- `lifecycle_aware_reminders_config.py` — flag, tier guards, boot validation (`validate_lifecycle_reminder_boot`)
- `server.py` — boot guard registration (after scoring)
- `deployment_governance_ci_gate.py` — reject `LIFECYCLE_AWARE_REMINDERS=active` in production blueprints
- `render.staging.yaml` — `LIFECYCLE_AWARE_REMINDERS=shadow`
- `test_lifecycle_reminders_s4.py` — flag/tier/CI tests
- STREAM_B §5c reminder authority inventory

**Explicitly not in S4.1:** `reminder_truth_service.py`, jobs, scheduler, email/SMS templates, notification services, attention-date calculations, effective reminder dates, `get_effective_expiry_date()` consumers.

---

## 5. Feature flags and safety

| Flag | Default | Staging | Production effective |
|------|---------|---------|----------------------|
| `LIFECYCLE_SEMANTICS_MODE` | observe | Per Phase 1 | Per Phase 1 |
| `LIFECYCLE_AWARE_CONFIRM` | `off` | `shadow` | `off` if raw `active` |
| `LIFECYCLE_AWARE_EXTRACTION` | `off` | `shadow` | `off` if raw `active` |
| `LIFECYCLE_AWARE_SCORING` | `off` | `shadow` | `off` if raw `active` |
| `LIFECYCLE_AWARE_REMINDERS` | `off` | `shadow` | `off` if raw `active` |
| `LIFECYCLE_AWARE_KPIS` | `off` | `shadow` | `off` if raw `active` |
| `LIFECYCLE_AWARE_REMINDER_PREVIEW_OVERRIDE` | unset | unset (staging) | **never** enables active on production |
| `LIFECYCLE_AWARE_KPIS_PREVIEW_OVERRIDE` | unset | unset (staging) | **never** enables active on production |

**Preview override env vars:** `LIFECYCLE_AWARE_CONFIRM_PREVIEW_OVERRIDE`, `LIFECYCLE_AWARE_EXTRACTION_PREVIEW_OVERRIDE`, `LIFECYCLE_AWARE_SCORING_PREVIEW_OVERRIDE`, `LIFECYCLE_AWARE_REMINDER_PREVIEW_OVERRIDE`, `LIFECYCLE_AWARE_KPIS_PREVIEW_OVERRIDE` — allow raw `active` on non-production tiers only.

**Safety:** tier guards, boot validation, CI production blueprint gate, shadow modes keep legacy authoritative on staging.

---

## 4d. Phase 4 programme scope delivered (S4.1–S4.4)

- `lifecycle_aware_reminders_config.py` — flag, tier guards, boot validation
- `lifecycle_reminder_gates.py` — shadow telemetry, active eligibility gates, template routing
- `reminder_truth_service.py` — dual-run shadow; active lifecycle eligibility (preview only)
- `lifecycle_reminder_template_registry.py` — 12 `LIFECYCLE_REMINDER_*` templates (EMAIL+SMS per `attention_kind`)
- `jobs.py` / `email_service.py` / `notification_orchestrator.py` — send path, code-built render, idempotency keys
- CI governance for production blueprint; `render.staging.yaml` shadow flag
- STREAM_B §5c reminder authority inventory

**Staging behaviour:** `LIFECYCLE_AWARE_REMINDERS=shadow` — legacy eligibility and `COMPLIANCE_EXPIRY_*` templates authoritative.

**Active (preview-tier only):** lifecycle-gated eligibility and `LIFECYCLE_REMINDER_*` sends; not enabled on staging or production.

**Not in Phase 4 (ADR Phases 5–7):** dashboard KPIs, reports/digest, legacy deprecation, scheduler registration changes.

---

## 6. Test inventory (2026-06-02)

| Suite | Count |
|-------|-------|
| Full `test_lifecycle_*.py` on `develop` + P5-S3 branch | **296** |
| `test_lifecycle_kpis_p5_s1.py` | **11** |
| `test_lifecycle_kpis_p5_s2.py` | **5** |
| `test_lifecycle_kpis_p5_s3.py` | **19** |
| `test_lifecycle_kpis_p5_s3_authority_regression.py` | **12** |
| `test_lifecycle_scoring_s31.py` | **9** |
| `test_lifecycle_scoring_s32_s33.py` | **11** |
| `test_lifecycle_reminders_s4.py` | **11** |
| `test_lifecycle_reminders_s42_s43.py` | **10** |
| `test_lifecycle_reminders_s44.py` | **11** |
| Phase 4 reminder suites (S4.1–S4.4) | **32** |
| `test_lifecycle_extraction_s5_extract.py` | **46** |
| Frontend `LifecycleAwareConfirm` | **12** |

---

## 7. Dependency map

```
Phase 1 + Phase 2 + Phase 3 + Phase 4 (COMPLETE on develop)
    └── Phase 5 dashboard KPIs (LIFECYCLE_AWARE_KPIS)  ← P5-S1/S2/S3 MERGED; P5-S4/S5 IN PROGRESS
            ├── P5-S5 additive API lifecycle_kpi_breakdown (in progress)
            ├── P5-S4 dashboard attention strip (in progress)
            ├── P5-S4b portfolio/requirements stragglers (deferred)
            ├── P5-S6 reports / digest / exports (not started)
            └── P5-S7 legacy deprecation (not started)
```

---

## 8. Go / no-go gates

| Gate | Current |
|------|---------|
| **Phase 3 feature-complete on `develop`** | **PASS** — PRs #9–#10 merged |
| **Phase 4 feature-complete on `develop`** | **PASS** — PRs #11–#13 merged |
| **Staging shadow (confirm + extraction + scoring + reminders + KPIs)** | **ACTIVE** @ `4fd1d3e1` |
| **KPI shadow runtime evidence** | **PENDING** — operational (non-blocking) |
| **Reminder shadow runtime evidence** | **PENDING** — operational (non-blocking) |
| **Preview active reminder soak** | **NOT STARTED** |
| **Scoring shadow runtime evidence** | **PENDING** — operational |
| **Preview active scoring soak** | **NOT STARTED** |
| **Staging active** | **BLOCKED** by policy |
| **Production promotion** | **BLOCKED** — `main` untouched |

---

## 9. Key documents

| Document | Path |
|----------|------|
| ADR | `backend/docs/architecture/ADR_REQUIREMENT_LIFECYCLE_SEMANTICS.md` |
| STREAM_B scoring matrix | `backend/docs/STREAM_B_SCORING_AUTHORITY_MATRIX.md` |
| Phase 2 design | `backend/docs/audit/REQUIREMENT_LIFECYCLE_PHASE2_IMPLEMENTATION_DESIGN_01.md` |

---

## 10. Next recommended action

**Next:** Complete **P5-S4/S5** PR review and merge; then **P5-S4b** portfolio/requirements straggler convergence. Run KPI shadow runtime evidence campaign on staging @ `4fd1d3e1` in parallel (operational, non-blocking).

**Tracker verdict:** `P5_S4_S5_IN_PROGRESS`
