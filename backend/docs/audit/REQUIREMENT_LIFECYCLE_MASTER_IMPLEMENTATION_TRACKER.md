# Requirement Lifecycle — Master Implementation Tracker

**Authority:** `ADR_REQUIREMENT_LIFECYCLE_SEMANTICS.md`, `REQUIREMENT_LIFECYCLE_PHASE2_IMPLEMENTATION_DESIGN_01.md`  
**Maintained:** Programme / lifecycle workstream  
**Last updated:** 2026-06-02  
**Purpose:** Single source of truth for phases, slices, PRs, commits, gates, and remaining work.

---

## Phase 3 status: **IN PROGRESS** — S3.2 + S3.3 complete on branch (2026-06-02)

| Phase 3 slice | Status | Branch | PR | Merge SHA |
|---------------|--------|--------|-----|-----------|
| **S3.1** — scoring flag infrastructure | **Complete** | — | [#9](https://github.com/Pleeriyenterprise/Pleerity-enterprise/pull/9) | `f29e066d` |
| **S3.2** — shadow scoring telemetry | **Complete (branch)** | `feature/lifecycle-phase3-s32-s33-scoring-gates` | — | — |
| **S3.3** — active penalty gates | **Complete (branch)** | `feature/lifecycle-phase3-s32-s33-scoring-gates` | — | — |

**`develop` tip:** `f29e066d` (S3.1 merged)  
**Staging deploy:** pending S3.2/S3.3 merge  
**`main` / production:** `60c1dbbe` — **untouched**

---

Phase 2 (confirm + extraction) is **closed**. All planned Phase 2 implementation slices are merged to `develop` and deployed to staging in **shadow** governance. No further Phase 2 feature slices should be added except critical bug fixes. Remaining lifecycle programme work belongs to Phases 3–7.

| Phase 2 slice | Status | PR | Merge SHA |
|---------------|--------|-----|-----------|
| Phase 1 — resolver/shadow | **Complete** | [#3](https://github.com/Pleeriyenterprise/Pleerity-enterprise/pull/3) | `a4dd04c5` |
| Phase 2 S1–S3 — profiles/contracts | **Complete** | [#4](https://github.com/Pleeriyenterprise/Pleerity-enterprise/pull/4) | `5462d2b0` |
| Phase 2 S4 — shadow validation | **Complete** | [#5](https://github.com/Pleeriyenterprise/Pleerity-enterprise/pull/5) | `46a3c74e` |
| Phase 2 S5.1–S5.3 — persistence + UI | **Complete** | [#6](https://github.com/Pleeriyenterprise/Pleerity-enterprise/pull/6) | `757f328f` |
| Phase 2 S5.4 — preview-only confirm enforcement | **Complete** | [#7](https://github.com/Pleeriyenterprise/Pleerity-enterprise/pull/7) | `b6d79641` |
| Phase 2 S5-extract — profile-aware extraction shadow | **Complete** | [#8](https://github.com/Pleeriyenterprise/Pleerity-enterprise/pull/8) | `d017a084` |

**`develop` tip:** `d017a084366d38b9de2bb44f239505df5b471c5a`  
**Staging deploy:** `d017a084` @ `pleerity-enterprise.onrender.com` — `environment=staging`, health **healthy**  
**`main` / production:** `60c1dbbe` — **untouched**

---

## Phase 2 Operational Observations

Recorded for Phase 3+ planning. **None block Phase 2 completion.**

| Observation | Classification | Notes |
|-------------|----------------|-------|
| Staging shadow intentionally executes **dual extraction** (legacy + profile LLM) when `LIFECYCLE_AWARE_EXTRACTION=shadow` | Operational | Expected temporary increase in LLM usage/cost while extraction shadow is enabled; legacy response remains authoritative |
| Runtime evidence campaign (48h shadow log measurement) still **pending** | Operational | RUNTIME-EVIDENCE-GATE-01; no measured production of `lifecycle_extract_shadow_*` counts on staging yet |
| Admin confirm fixture (`test_document_extraction.py`) requires update following S5.4 enforcement wiring | Future-phase / test hygiene | Stale fixture under active confirm mode; S5.4 fallout, not S5-extract |
| `deployment-governance` CI fail on unrelated frontend staging URL in test files | Operational | Pre-existing; unrelated to lifecycle logic |
| Design S7 admin UI confirm parity | Future-phase | Backend wired in S5.4; admin UI still cert-field oriented |
| Design S8 preview active soak (V2-U1–U10) | Future-phase | Deferred; preview `active` not enabled on staging/production |
| Design S9 pipeline convergence (optional) | Future-phase | Not started; not required for Phase 2 closeout |

---

## 1. Original roadmap (ADR initiative phases)

| Phase | Name | Deliverable | Feature flag | Customer impact when off |
|-------|------|-------------|--------------|--------------------------|
| **0** | ADR promotion | `ADR_REQUIREMENT_LIFECYCLE_SEMANTICS.md` | — | None |
| **1** | Resolver + registry backfill | `lifecycle_semantics_resolver.py`, shadow logging | `LIFECYCLE_SEMANTICS_MODE` | None (observe-only) |
| **2** | Confirm + extraction | Profiles, confirm contract, enforcement | `LIFECYCLE_AWARE_CONFIRM`, `LIFECYCLE_AWARE_EXTRACTION` | Cert-centric confirm/extraction unchanged |
| **3** | Scoring gates | Penalty eligibility via `field_contract` | `LIFECYCLE_AWARE_SCORING` (planned) | Legacy scoring |
| **4** | Reminders + gaps | `attention_kind` templates | `LIFECYCLE_AWARE_REMINDERS` (planned) | Legacy reminder subjects |
| **5** | Dashboard KPIs | Split widgets / lifecycle-aware buckets | `LIFECYCLE_AWARE_KPIS` (planned) | Legacy KPI counts |
| **6** | Reports + digest | Section language / human-language alignment | — | Legacy report copy |
| **7** | Legacy deprecation | Remove independent expiry inference | — | — |

---

## 2. Expanded roadmap — Phase 2 slices

| Expanded slice | Maps to | Summary | Status |
|----------------|---------|---------|--------|
| **Phase 1 — resolver/shadow** | Phase 1 | Observe-only semantics resolver, registry loader, HMO reconciliation, shadow validation | **Merged** |
| **Phase 2 S1** | Phase 2 | Extraction profile registry + resolver | **Merged** (PR #4) |
| **Phase 2 S2** | Phase 2 | HMO registry/spec reconciliation | **Merged** (PR #4) |
| **Phase 2 S3** | Phase 2 | `lifecycle_confirm_contract` on GET extraction (shadow attach) | **Merged** (PR #4) |
| **Phase 2 S4** | Phase 2 | Shadow confirm validation (observe-only, no block) | **Merged** (PR #5) |
| **Phase 2 S5.1** | Phase 2 | Active-plan persistence builders (`lifecycle_confirm_apply.py`) | **Merged** (PR #6) |
| **Phase 2 S5.2** | Phase 2 | Shadow persistence telemetry (`would_skip_persistence`) | **Merged** (PR #6) |
| **Phase 2 S5.3** | Phase 2 | Frontend `LifecycleAwareConfirm` + `DocumentsPage` wiring | **Merged** (PR #6) |
| **Phase 2 S5.4** | Phase 2 | Preview-only **active** confirm enforcement + persistence gating + 422 UX | **Merged** (PR #7) |
| **S5-extract** | Phase 2 | Profile-aware LLM extraction + EXTRACTED rules (shadow) | **Merged** (PR #8) |
| **Design S7** (admin confirm parity) | Phase 2+ | Admin extraction queue semantic confirm UX | **Partial** — deferred |
| **Design S8** (staging gate V2-U1–U10) | Phase 2+ gate | 48h shadow + preview active + regression | **Deferred** |
| **Design S9** (pipeline convergence) | Phase 2 optional | Client upload → `enqueue_extraction` | **Not started** |
| **Phase 3 scoring** | Phase 3 | `LIFECYCLE_AWARE_SCORING` | **S3.1 merged; S3.2/S3.3 on branch** |
| **Phase 4 reminders** | Phase 4 | `LIFECYCLE_AWARE_REMINDERS` | **Not started** |
| **Phase 5 KPIs** | Phase 5 | Dashboard widget split | **Not started** |
| **Phase 6 reports** | Phase 6 | Report/digest language | **Not started** |

---

## 3. Status table

| Item | Status | Branch | PR | Merge SHA | Merged | Staging | Production |
|------|--------|--------|-----|-----------|--------|---------|------------|
| Phase 1 resolver/shadow | **Complete** | `feature/lifecycle-semantics-phase1` | #3 | `a4dd04c5` | Yes | On develop lineage | Untouched |
| Phase 2 S1–S3 | **Complete** | `feature/lifecycle-phase2-s1-s3` | #4 | `5462d2b0` | Yes | On develop lineage | Untouched |
| Phase 2 S4 | **Complete** | `feature/lifecycle-phase2-s4-validation` | #5 | `46a3c74e` | Yes | On develop lineage | Untouched |
| Phase 2 S5.1–S5.3 | **Complete** | `feature/lifecycle-phase2-s5-enforcement` | #6 | `757f328f` | Yes | On develop lineage | Untouched |
| Phase 2 S5.4 | **Complete** | `feature/lifecycle-phase2-s54-enforcement` | #7 | `b6d79641` | Yes | Deployed | Untouched |
| S5-extract | **Complete** | `feature/lifecycle-phase2-s5-extract` | #8 | `d017a084` | Yes | Deployed @ `d017a084` | Untouched |
| Phase 3 S3.1 | **Complete** | — | #9 | `f29e066d` | Yes | Deployed lineage | Untouched |
| Phase 3 S3.2–S3.3 | **Complete (branch)** | `feature/lifecycle-phase3-s32-s33-scoring-gates` | — | — | No | — | Untouched |
| Phase 4–7 | **Not started** | — | — | — | No | — | Untouched |

**Branch heads (2026-06-25):**

| Branch | HEAD |
|--------|------|
| `develop` | `9730a0c6` (tracker doc) / Phase 2 code `d017a084` |
| `main` | `60c1dbbe` |

**Staging configuration:** `render.staging.yaml` → `DEPLOYMENT_TIER=staging`, `LIFECYCLE_AWARE_CONFIRM=shadow`, `LIFECYCLE_AWARE_EXTRACTION=shadow`, `LIFECYCLE_AWARE_SCORING=shadow` (S3.1).  
**Production configuration:** `render.production.yaml` — no lifecycle `active` flags.

---

## 4. Phase 2 scope delivered

Phase 2 now contains **only** the following (all merged):

- Resolver (Phase 1 foundation used by Phase 2)
- Shadow observe-only semantics and confirm validation
- Extraction profile registry (11 profiles) + resolver
- Lifecycle confirm contract (GET attach)
- Confirm validation (shadow + preview-only active enforcement code)
- Persistence authority builders (`structured_declaration` for non-EXPIRY active path)
- Frontend lifecycle-aware confirm UX + 422 field errors
- Preview-only confirm enforcement (tier-guarded; not enabled on staging/production)
- Profile-aware extraction (shadow dual-run; legacy authoritative in off/shadow)

**Not implemented (Phase 3+):**

- Lifecycle-aware scoring
- Lifecycle-aware reminders
- Lifecycle-aware KPIs / dashboards
- Lifecycle-aware reports / customer wording
- Legacy expiry deprecation (Phase 7)

---

## 5. Feature flags and safety (Phase 2 + Phase 3 S3.1)

| Flag | Default | Staging | Production effective |
|------|---------|---------|----------------------|
| `LIFECYCLE_SEMANTICS_MODE` | observe (Phase 1) | Per Phase 1 deploy | Per Phase 1 deploy |
| `LIFECYCLE_AWARE_CONFIRM` | `off` | `shadow` | `off` if raw `active` |
| `LIFECYCLE_AWARE_EXTRACTION` | `off` | `shadow` | `off` if raw `active` |
| `LIFECYCLE_AWARE_SCORING` | `off` | `shadow` (S3.1) | `off` if raw `active` |

**Safety mechanisms:**

- Deployment tier guards: staging raw `active` → effective `shadow`; production raw `active` → effective `off`
- Boot validation: `validate_lifecycle_confirm_boot()`, `validate_lifecycle_extraction_boot()`, `validate_lifecycle_scoring_boot()`
- CI governance: rejects `LIFECYCLE_AWARE_CONFIRM=active`, `LIFECYCLE_AWARE_EXTRACTION=active`, and `LIFECYCLE_AWARE_SCORING=active` in production blueprints
- Shadow modes: legacy confirm/extraction responses authoritative; profile paths observe-only
- Rollback: set flags to `off` for instant cert-centric behaviour

---

## 6. Test inventory (2026-06-25)

| Suite | Count |
|-------|-------|
| Full `test_lifecycle_*.py` | **219** (208 pre-S3.2/S3.3 + 11 S3.2/S3.3) |
| `test_lifecycle_extraction_s5_extract.py` | **46** (subset of 199) |
| Frontend `LifecycleAwareConfirm` | **12** |

Historical counts: **153** = pre-S5-extract lifecycle suite; **121** = pre-S5.4.

---

## 7. Dependency map (post Phase 2)

```
Phase 1 + Phase 2 (COMPLETE on develop)
    └── Phase 3 scoring (LIFECYCLE_AWARE_SCORING)
            └── Phase 4 reminders
                    └── Phase 5 dashboard KPIs
                            └── Phase 6 reports
                                    └── Phase 7 legacy deprecation
```

Preview active confirm/extraction soak and runtime evidence campaign are **operational gates** for future promotion — not Phase 2 implementation blockers.

---

## 8. Go / no-go gates (updated)

| Gate | Current |
|------|---------|
| **Phase 2 feature-complete on `develop`** | **PASS** — PRs #3–#8 merged |
| **Phase 3 S3.1 on `develop`** | **PASS** — PR #9 @ `f29e066d` |
| **Phase 3 S3.2/S3.3** | **READY FOR PR** — shadow + active gates on branch |
| **Staging shadow (confirm + extraction + scoring)** | **ACTIVE** (scoring shadow observe on staging) |
| **Preview active soak** | **NOT STARTED** — deferred to Phase 3 planning |
| **Staging active** | **BLOCKED** by policy |
| **Production promotion** | **BLOCKED** — `main` untouched |

---

## 9. Key documents

| Document | Path |
|----------|------|
| ADR | `backend/docs/architecture/ADR_REQUIREMENT_LIFECYCLE_SEMANTICS.md` |
| Phase 2 design | `backend/docs/audit/REQUIREMENT_LIFECYCLE_PHASE2_IMPLEMENTATION_DESIGN_01.md` |
| Phase 2 readiness | `backend/docs/audit/REQUIREMENT_LIFECYCLE_PHASE2_READINESS_01.md` |
| S5.4 preview runbook (contingency) | `backend/docs/audit/LIFECYCLE_PHASE2_S54_RENDER_PREVIEW_RUNBOOK.md` |
| S1–S3 shadow validation | `backend/docs/audit/LIFECYCLE_PHASE2_S1_S3_SHADOW_VALIDATION_01.json` |

---

## 10. Next recommended action

**Open PR for S3.2/S3.3** → merge to `develop` → verify staging shadow scoring telemetry. Preview active soak for scoring deferred.

**Tracker verdict:** `PHASE3_S3_2_S3_3_BRANCH_COMPLETE`
