# Requirement Lifecycle — Master Implementation Tracker

**Authority:** `ADR_REQUIREMENT_LIFECYCLE_SEMANTICS.md`, `REQUIREMENT_LIFECYCLE_PHASE2_IMPLEMENTATION_DESIGN_01.md`  
**Maintained:** Programme / lifecycle workstream  
**Last updated:** 2026-06-25 (Phase 4 S4.2/S4.3 closeout — PR #12)  
**Purpose:** Single source of truth for phases, slices, PRs, commits, gates, and remaining work.

---

## Phase 4 status: **IN PROGRESS** (S4.1–S4.3 complete — 2026-06-25)

| Phase 4 slice | Status | PR | Merge SHA |
|---------------|--------|-----|-----------|
| **S4.1** — reminder flag infrastructure | **Complete** | [#11](https://github.com/Pleeriyenterprise/Pleerity-enterprise/pull/11) | `4a15747a` |
| **S4.2** — shadow reminder telemetry | **Complete** | [#12](https://github.com/Pleeriyenterprise/Pleerity-enterprise/pull/12) | `906e67b6` |
| **S4.3** — active eligibility gates + template routing | **Complete** | [#12](https://github.com/Pleeriyenterprise/Pleerity-enterprise/pull/12) | `906e67b6` |
| **S4.4+** — dedicated `attention_kind` email/SMS templates | **Not started** | — | — |

**`develop` tip:** `906e67b65ae6c04316ecf53a82a7e2b8c20faeac`  
**Staging deploy:** `906e67b6` @ `pleerity-enterprise.onrender.com` — `environment=staging`, `/api/health` **healthy**, `/api/version` confirms SHA  
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

Recorded for S4.4+ planning. **None block S4.2/S4.3 closeout.**

| Observation | Classification | Notes |
|-------------|----------------|-------|
| Runtime evidence campaign (48h) for **reminder** shadow logs | Operational | Pending measured `lifecycle_reminder_shadow_*` on staging @ `906e67b6` |
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
| **4** | Reminders + gaps | `attention_kind` templates | `LIFECYCLE_AWARE_REMINDERS` | **IN PROGRESS** (S4.4+ next) |
| **5** | Dashboard KPIs | Split widgets | `LIFECYCLE_AWARE_KPIS` | Not started |
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
| **Phase 4 S4.4+** | 4 | Dedicated `attention_kind` email/SMS templates | **Not started** |
| Phase 5 KPIs | 5 | Dashboard widget split | Not started |
| Phase 6 reports | 6 | Report/digest language | Not started |

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
| Phase 4 S4.4+ | Not started | — | — | No | — | Untouched |
| Phase 5–7 | Not started | — | — | No | — | Untouched |

**Branch heads (2026-06-25):**

| Branch | HEAD |
|--------|------|
| `develop` | `906e67b6` |
| `main` | `60c1dbbe` |

**Staging configuration:** `DEPLOYMENT_TIER=staging`, `LIFECYCLE_AWARE_CONFIRM=shadow`, `LIFECYCLE_AWARE_EXTRACTION=shadow`, `LIFECYCLE_AWARE_SCORING=shadow`, `LIFECYCLE_AWARE_REMINDERS=shadow` — all shadow-only @ `906e67b6`.  
**Production configuration:** `render.production.yaml` — **no lifecycle flags** (including no `LIFECYCLE_AWARE_REMINDERS`).

---

## 4. Phase 3 scope delivered

- `lifecycle_aware_scoring_config.py` — flag, tier guards, boot validation
- `lifecycle_scoring_gates.py` — resolver context, shadow observe, projector gate helper
- `compliance_scoring_v2.py` — dual-run shadow; active gates via `requires_expiry_date`; suppress non-`EXPIRY_BASED` `due_date` penalties
- `customer_status_projector_v2.py` — `EXPIRY_DATE_NEEDED` gated when scoring active
- CI governance for production blueprint
- STREAM_B §5b scoring authority inventory

**Not implemented (Phase 4 S4.4+):** dedicated `attention_kind` email/SMS template bodies, KPIs, reports, legacy deprecation.

---

## 4b. Phase 4 S4.2/S4.3 scope delivered (merged PR #12)

- `lifecycle_reminder_gates.py` — resolver context, shadow `lifecycle_reminder_shadow_*` logs, active certificate-expiry pipeline gates, template routing authority
- `reminder_truth_service.py` — dual-run shadow; active uses lifecycle eligibility (legacy authoritative on staging shadow)
- `jobs.py` — `resolve_lifecycle_reminder_template_key` for email/SMS sends; `lifecycle_attention_kind` on reminder items
- `test_lifecycle_reminders_s42_s43.py` — shadow divergence, active gates, template routing

**Staging behaviour:** `LIFECYCLE_AWARE_REMINDERS=shadow` keeps legacy eligibility authoritative; lifecycle path observe-only.

**Active (preview-tier only):** suppresses non-`EXPIRY_BASED` requirements from `DAILY_COMPLIANCE_EXPIRY_*` pipeline.

**Not in S4.2/S4.3:** scheduler registration changes, email/SMS template body changes, customer wording changes, scoring/dashboard/report changes.

---

## 4a. Phase 4 S4.1 scope delivered (infrastructure only)

- `lifecycle_aware_reminders_config.py` — flag, tier guards, boot validation (`validate_lifecycle_reminder_boot`)
- `server.py` — boot guard registration (after scoring)
- `deployment_governance_ci_gate.py` — reject `LIFECYCLE_AWARE_REMINDERS=active` in production blueprints
- `render.staging.yaml` — `LIFECYCLE_AWARE_REMINDERS=shadow`
- `test_lifecycle_reminders_s4.py` — flag/tier/CI tests
- STREAM_B §5c reminder authority inventory (planned only)

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
| `LIFECYCLE_AWARE_REMINDER_PREVIEW_OVERRIDE` | unset | unset (staging) | **never** enables active on production |

**Preview override env vars:** `LIFECYCLE_AWARE_CONFIRM_PREVIEW_OVERRIDE`, `LIFECYCLE_AWARE_EXTRACTION_PREVIEW_OVERRIDE`, `LIFECYCLE_AWARE_SCORING_PREVIEW_OVERRIDE`, `LIFECYCLE_AWARE_REMINDER_PREVIEW_OVERRIDE` — allow raw `active` on non-production tiers only.

**Safety:** tier guards, boot validation, CI production blueprint gate, shadow modes keep legacy authoritative on staging.

---

## 6. Test inventory (2026-06-25)

| Suite | Count |
|-------|-------|
| Full `test_lifecycle_*.py` on `develop` | **243** |
| `test_lifecycle_scoring_s31.py` | **9** |
| `test_lifecycle_scoring_s32_s33.py` | **11** |
| `test_lifecycle_reminders_s4.py` | **11** |
| `test_lifecycle_reminders_s42_s43.py` | **13** |
| `test_lifecycle_extraction_s5_extract.py` | **46** |
| Frontend `LifecycleAwareConfirm` | **12** |

---

## 7. Dependency map

```
Phase 1 + Phase 2 + Phase 3 (COMPLETE on develop)
    └── Phase 4 reminders (LIFECYCLE_AWARE_REMINDERS)  ← S4.1–S4.3 COMPLETE; S4.4+ NEXT
            └── Phase 5 dashboard KPIs
                    └── Phase 6 reports
                            └── Phase 7 legacy deprecation
```

---

## 8. Go / no-go gates

| Gate | Current |
|------|---------|
| **Phase 3 feature-complete on `develop`** | **PASS** — PRs #9–#10 merged |
| **Staging shadow (confirm + extraction + scoring + reminders)** | **ACTIVE** @ `906e67b6` |
| **Reminder shadow runtime evidence** | **PENDING** — operational |
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

**Begin Phase 4 S4.4 planning** (dedicated `attention_kind` email/SMS templates). Do not add Phase 3 slices. Run reminder shadow runtime evidence campaign on staging in parallel.

**Tracker verdict:** `READY_FOR_PHASE4_S4_4_PLANNING`
