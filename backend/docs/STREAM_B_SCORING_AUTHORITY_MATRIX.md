# Stream B — Scoring authority matrix (authoritative inventory)

**Stream:** B — Score Authority Consolidation  
**Phase:** Scoring authority matrix (audit only; no runtime or API changes)  
**Named authority (writes):** `compliance_scoring_service.recalculate_and_persist`  
**Companion reads:** `compliance_scoring_service.calculate_property_compliance` (v2 planner, no persist unless called inside `recalculate_and_persist` or read-repair), `compliance_score.calculate_compliance_score` (portfolio headline + live `stats` from persisted rows + runtime projection)  
**Last updated:** 2026-06-02 (Phase 5 P5-S3 active KPI authority §5d)

---

## 1. Proposed matrix structure (for ongoing maintenance)

Use one row per **entry surface** (route, job step, script, or service called by them). Columns:

| Column | Meaning |
|--------|---------|
| **Entry** | Route path, job name, CLI script, or internal caller |
| **Actor** | client / admin / system / ops |
| **Scoring source** | Module + symbol actually invoked |
| **Persisted vs computed** | Whether `Property` score fields (and related breakdowns) are written, or only read/compute |
| **Authority class** | `authoritative` · `legacy` · `diagnostic-only` · `admin-exception` |
| **Persisted fields touched** | e.g. `compliance_score`, `compliance_breakdown`, history collections |
| **Downstream consumers** | UI, email, PDF, other APIs |

---

## 2. Score writers (property-level persistence)

| Entry | Actor | Scoring source | Persisted? | Authority class | Fields / collections | Notes |
|--------|-------|----------------|------------|-------------------|----------------------|--------|
| `compliance_scoring_service.recalculate_and_persist` | system / client / admin (via triggers) | `calculate_property_compliance` → `compute_property_score_v2` | **Yes** | **authoritative** | `properties` score fields, `property_compliance_score_history`, `score_ledger_events` (via `log_score_change`), audit | Single intended write path per module contract |
| `job_runner` compliance recalc worker | system | `recalculate_and_persist` | Yes | **authoritative** | same | Drains `compliance_recalc_queue` |
| `routes/properties.py` jurisdiction patch | client | direct `recalculate_and_persist` + fallback `enqueue_compliance_recalc` | Yes (sync path) | **authoritative** | same | Sync recalc; enqueue on failure |
| `services/compliance_outcome_engine.py` | system | `recalculate_and_persist` | Yes | **authoritative** | same | After outcome events |
| `routes/admin.py` — score validator / mismatch repair (`body.fix`) | admin | `recalculate_and_persist` with `REASON_ADMIN_VALIDATOR_REPAIR` after compare | **Yes** | **authoritative** | same as canonical writer; route also emits `COMPLIANCE_SCORE_MISMATCH_DETECTED` + `COMPLIANCE_SCORE_REPAIRED` with shared `correlation_id` | Orchestration only — no direct `update_one` / history / ledger in route |
| `compliance_recalc_queue.enqueue_compliance_recalc` | any | none (queue only) | **No** (sets `compliance_score_pending`) | **n/a** | queue doc + pending flag | Indirect writer: schedules authoritative path |

**Legacy full recompute:** `compliance_score._calculate_compliance_score_legacy_from_db` — **no callers found** in repo grep (2026-04-30); retained code only.

---

## 3. Score readers (client-visible or ops-facing)

| Entry | Actor | Scoring source | Persisted vs computed | Authority class | Consumers |
|--------|-------|----------------|-------------------------|-----------------|-----------|
| `GET /api/client/compliance-score` (`routes/client.py`) | client | `compliance_score.calculate_compliance_score` | Headline **persisted** aggregate; `stats` from **live** runtime projection | **authoritative** headline + aligned stats contract | Client dashboard |
| `GET .../compliance-score/explanation` (property) | client | `get_authoritative_property_compliance_for_client` | Merges **persisted** headline with **live** `calculate_property_compliance` for operational preview | **authoritative** + live preview | Client property explainability |
| `GET /api/client/compliance-score/explanation` (client-level) | client | reads `Property.compliance_score` / breakdown from DB | persisted | **authoritative** | Client |
| `GET /api/client/compliance-score/trend` | client | `compliance_trending.get_score_trend` → uses `compliance_score_history` / property daily | persisted snapshots | **authoritative** (snapshots derived from prior `calculate_compliance_score` / property rows) | Sparkline |
| `GET /api/client/score/timeline` | client | `score_events_service.get_timeline` → events; fallback `calculate_compliance_score` | mixed | **authoritative** with event fallback | Timeline |
| `command_center_service` bundle | client | `calculate_compliance_score` | same as client compliance-score | **authoritative** | Command Centre UI |
| `routes/portfolio.py` (property / list) | client | reads `Property.compliance_score` (+ catalog lens from `catalog_compliance` where used) | persisted headline; catalog matrix **non-replacement** lens | **authoritative** headline per portfolio docstrings | Portfolio |
| `routes/reports.py` | client | `calculate_compliance_score` | headline persisted + stats | **authoritative** | PDF/CSV reports |
| `services/reporting_service.py` | client/system | `calculate_compliance_score` | headline for `compliance_score_headline` block | **authoritative** | Scheduled / unified report digest templates |
| `services/monthly_digest_assembly_service.py` | system | `calculate_compliance_score` | headline + display fields | **authoritative** | Email + PDF digest |
| `routes/ops_compliance.py` clients summary (single client) | admin/ops | `calculate_compliance_score` | headline | **authoritative** | Ops dashboard |
| `routes/admin.py` score mismatch validator (read-only compare) | admin | `calculate_property_compliance` vs stored | diagnostic compare | **diagnostic-only** | Admin tooling |
| `risk_signal_service` (score history for signals) | system | reads `property_compliance_score_history` | persisted | **authoritative** read | Risk copy / context |
| `services/compliance_explain_admin_service.py` | admin | references persisted + scoring service contract in copy | n/a | **authoritative** narrative | Admin explain |

---

## 4. Adjacent: not property compliance score (naming)

| Entry | Note |
|--------|------|
| `LeadService.recalculate_and_persist_lead_score` | **Lead** scoring — unrelated domain |
| `jobs.py` `_calculate_property_compliance` (instance method) | **Provisioning / job** requirement status heuristic — **not** `compliance_scoring_service`; do not confuse with compliance score v2 |

---

## 5. Duplicate calculations & conflicts

| Issue | Detail |
|-------|--------|
| **Admin repair bypass** | Admin `fix` path persists using hand-built `$set` + manual history/ledger instead of `recalculate_and_persist`. Second implementation of “what gets written” for the same fields. |
| **Headline vs live preview** | `get_authoritative_property_compliance_for_client` intentionally merges **persisted** headline with **live** calculation for operational fields — not a duplicate headline if UI respects `authoritative` vs `operational_preview`; **stale-state** if user compares live counts to old headline before queue drains. |
| **`calculate_compliance_score` stats** | Recomputes requirement **stats** from live DB each call while **score** is mean of persisted property scores — **intentional** split; transient mismatch vs recalc queue possible. |
| **Legacy v1 engine** | `services/compliance_scoring.py` `compute_property_score` — **tests / legacy** only; not wired to `recalculate_and_persist` (v2 path). |

---

## 5a. Admin repair authority decision (Stream B) — **implemented**

**Current behaviour:** `POST .../validate-compliance-score` with `fix=true`:

1. Compares `calculate_property_compliance` to stored fields (unchanged).
2. On mismatch: `COMPLIANCE_SCORE_MISMATCH_DETECTED` with `correlation_id` (`ADMIN_VALIDATOR_REPAIR:{property_id}:{hex}`).
3. **`recalculate_and_persist(property_id, REASON_ADMIN_VALIDATOR_REPAIR, actor=admin, context={correlation_id, diff_summary})`** — single writer; produces `COMPLIANCE_SCORE_UPDATED`, history, `score_change_log`, ledger, risk regen as normal.
4. **`COMPLIANCE_SCORE_REPAIRED`** after success, with same `correlation_id`, `canonical_reason`, and scores in metadata.

**API response shape:** unchanged (`property_id`, `stored_score`, `computed_score`, `match`, `diff_summary`, `repaired`).

---

## 6. Frontend recomputation risks

| Risk | Mitigation already in backend |
|------|------------------------------|
| Client recomputes portfolio % from raw requirements | Command Centre docstring: use `compliance_counts_authority` / `calculate_compliance_score.stats` only — **discipline**; not enforceable in this repo alone |
| Client uses catalog matrix as headline | `calculate_compliance_score` attaches `catalog_portfolio_view` as **alternate lens only** — backend contract documented |
| Client dashboard / compliance score page imply a single “moment in time” | **FE slices (2026-05-02 + 2026-04-30):** `ClientDashboard.js` surfaces `score_status` / `score_status_message` / last-calculated for non-`ok` states + portfolio timestamp when present; `ComplianceScorePage.js` surfaces `score_status_message` for all statuses when set, plus a factual **drivers vs stored headline** note; **`ClientCommandCenterPage.js`** when `compliance_status_summary` is missing shows explicit **bundle-degraded** copy + optional `score_status_message`, and shows `score_status_message` on the strip whenever set; **`PropertyDetailPage.js`** on Compliance tab (when explainability + operational preview load) shows **stored headline vs current detail** copy + `score_status_message` / `last_calculated_at` — **no API changes** (`frontend/src/utils/scoreFreshnessUi.js`; tests `ClientDashboard.scoreFreshness.test.js`, `ComplianceScorePage.asyncHonesty.test.js`, `ClientCommandCenterPage.test.js`, `PropertyDetailPage.asyncHonesty.test.js`, `scoreFreshnessUi.test.js`). |

---

## 7. Stale-state & divergence risks

| Risk | Mechanism |
|------|-----------|
| Queue lag | `compliance_score_pending`, `enqueue_compliance_recalc` — dashboard can show old headline until worker runs |
| Read repair | `get_authoritative_property_compliance_for_client` calls `recalculate_and_persist` when `compliance_score` is **null** |
| Lazy backfill | `get_persisted_portfolio_headline_for_summary` / `calculate_compliance_score` can enqueue `TRIGGER_LAZY_BACKFILL` for missing scores |
| Digest vs live portal | Digest uses same `calculate_compliance_score` as other surfaces — **aligned** at assembly time; **time** divergence vs “live now” if email delayed — **mitigated (2026-04-30):** `digest_snapshot_framing_line` (`Snapshot as of {generated_at_display}`) on digest model; email (`email_service`), PDF executive summary (`monthly_digest_pdf_service`), plain text include snapshot + `score_status` / `last_calculated_at` / optional `score_status_message` near headline; compliance summary CSV (`reporting_service`) adds `score_status_message` + `export_snapshot_note`; `GET /api/reports/score-drivers.csv` prepends `# export_snapshot_*` / `# headline_*` (legacy) or extra metadata rows when `scoring_metadata=true` |
| Partial Command Centre | Try/except per subgraph — compliance block can fail while other widgets succeed (gap analysis) |
| Dashboard headline vs live KPI counts | Same split as headline vs `stats` in `calculate_compliance_score` — mitigated on dashboard/compliance-score/Command Centre/Property Detail **copy only** (see §6 FE slices); digest email/PDF + compliance CSV + score-drivers CSV **snapshot labelling** (see §7 digest row); **`GET /api/reports/score-explanation.pdf`** (`pdf_report_builder.build_score_explanation_report`): **Snapshot as of** + `score_status_message`, persisted-vs-queue-lag copy, removal of misleading “live calculator” wording (**2026-04-30**); **Evidence Readiness PDF** (`pdf_report_builder.build_portfolio_report` / `build_property_report`): **Snapshot generated at** (export time UTC), executive **Score status** / **Last score calculation** / **Headline note** from `aggregate_persisted_portfolio_headline`, portfolio table score cells with per-property persisted meta when present, methodology wording avoids implying live portal truth (**2026-04-30**); **Professional compliance summary PDF** (`professional_reports.generate_compliance_summary_pdf`): **Snapshot generated at**, **Headline note** from `score_status_message`, **Last score calculation (persisted batch)** vs PDF generation time, executive copy avoids portal-truth implication (**2026-04-30**); optional follow-up: scheduled digest |

---

## 8. Affected modules (audit)

**Write path:** `compliance_scoring_service.py`, `compliance_scoring_v2.py`, `compliance_recalc_queue.py`, `job_runner.py`, `routes/properties.py`, `services/compliance_outcome_engine.py`, `routes/admin.py` (validator repair), `score_ledger_service.py`  

**Read / aggregate:** `compliance_score.py`, `scoring_semantics_v1.py`, `portfolio_risk_override*.py`, `command_center_service.py`, `routes/client.py`, `routes/portfolio.py`, `routes/reports.py`, `routes/ops_compliance.py`, `services/reporting_service.py`, `services/monthly_digest_assembly_service.py`, `services/monthly_digest_pdf_service.py`, `services/email_service.py`, `services/compliance_trending.py`, `services/score_events_service.py`, `services/compliance_explain_admin_service.py`, `services/risk_signal_service.py`  

**Enqueue-only (many):** `routes/documents.py`, `routes/evidence_review.py`, `routes/client.py`, `routes/admin.py` (including **standalone authority-sync** document + guided-evidence adjacency paths → `enqueue_compliance_recalc` per **Stream B straggler 2026-05-01**), `routes/client_compliance_evidence.py`, `routes/api_compliance_workflow.py`, `services/evidence_review_verify.py`, `services/jobs.py`, `services/provisioning.py`, `services/compliance_governed_rules_service.py`, `services/compliance_score.py`, `services/compliance_score_reconciliation_service.py`, etc.  

**Tests / contracts:** `test_compliance_scoring_enterprise.py`, `test_compliance_authority_alignment.py`, `test_batch1_score_authority.py`, `test_batch2_p0_score_authority_contract.py`, `test_compliance_score_golden.py`, …  

---

## 5b. Lifecycle-aware scoring gates (Phase 3 — INITIATIVE-REQUIREMENT-LIFECYCLE-SEMANTICS)

**Authority:** `ADR_REQUIREMENT_LIFECYCLE_SEMANTICS.md` constraint #5 and #10; master tracker `REQUIREMENT_LIFECYCLE_MASTER_IMPLEMENTATION_TRACKER.md`.

**Feature flag:** `LIFECYCLE_AWARE_SCORING` (`off` | `shadow` | `active`) — config in `services/lifecycle_aware_scoring_config.py` (S3.1).

| Entry / surface | Actor | Scoring source | Lifecycle gate (planned) | Flag mode behaviour |
|-----------------|-------|----------------|--------------------------|---------------------|
| `compliance_scoring_service.recalculate_and_persist` | system | `compute_property_score_v2` | `field_contract.requires_expiry_date` via resolver (S3.3) | **off:** legacy `expects_expiry_for_requirement`; **shadow:** legacy authoritative + parallel observe (S3.2); **active:** lifecycle-gated penalties (preview only) |
| `compliance_scoring_v2._status_fraction_from_requirement` | system | internal | Suppress `due_date` → `EXPIRING_SOON` for non-`EXPIRY_BASED` semantics (S3.3) | Same flag |
| `document_status_service.compute_requirement_status` | system | internal | Gate `expects_expiry` missing-expiry penalty on `requires_expiry_date` (S3.3) | Same flag |
| `customer_status_projector_v2._emit_expiry_needed` | system | overlay vocabulary | `EXPIRY_DATE_NEEDED` only when resolver allows (S3.3 boundary) | Same flag |

**Write authority unchanged:** `recalculate_and_persist` remains the sole property score persistence path. Lifecycle scoring does not add alternate writers.

**Safety (S3.1):** Tier guards mirror confirm/extraction — staging raw `active` → effective `shadow`; production raw `active` → effective `off`; CI rejects `LIFECYCLE_AWARE_SCORING=active` in production blueprints; boot guard `validate_lifecycle_scoring_boot()`.

**Not in scope for S3.1:** No changes to penalty fractions, persisted scores, or client-visible headline until S3.2 (shadow telemetry) and S3.3 (active gates).

**Implemented (S3.2/S3.3):** `lifecycle_scoring_gates.py` — shadow `lifecycle_scoring_shadow_*` logs; active gates in `compliance_scoring_v2.py` via `field_contract.requires_expiry_date` and `EXPIRY_BASED` due-date suppression; `customer_status_projector_v2` EXPIRY_DATE_NEEDED gated when scoring active.

---

## 5c. Reminder authority (Phase 4 — **complete**; INITIATIVE-REQUIREMENT-LIFECYCLE-SEMANTICS)

**Authority:** `ADR_REQUIREMENT_LIFECYCLE_SEMANTICS.md` constraints #4, #8, #161; master tracker `REQUIREMENT_LIFECYCLE_MASTER_IMPLEMENTATION_TRACKER.md`.

**Feature flag:** `LIFECYCLE_AWARE_REMINDERS` (`off` | `shadow` | `active`) — config in `services/lifecycle_aware_reminders_config.py` (S4.1). Consumers wired S4.2–S4.4.

| Entry / surface | Actor | Current authority | Lifecycle gate | Flag mode behaviour |
|-----------------|-------|----------------|----------------|---------------------|
| `services/reminder_truth_service.py` | system | legacy eligibility | Resolver eligibility + `attention_kind` (S4.2/S4.3) | **off/shadow:** legacy authoritative; **active (preview):** lifecycle eligibility |
| `services/jobs.py` — daily reminders | system | legacy send paths | `resolve_lifecycle_reminder_template_key` + gated pipeline (S4.2–S4.4) | Same flag |
| Scheduler / compliance jobs | system | legacy schedule | No lifecycle scheduler changes in Phase 4 | Same flag |
| Email / SMS templates | system | `COMPLIANCE_EXPIRY_*` (shadow/off) | `LIFECYCLE_REMINDER_*` per `attention_kind` (S4.4) | **shadow/off:** legacy templates; **active (preview):** lifecycle templates |
| `get_effective_expiry_date()` consumers | system | expiry-date inference | Unchanged in Phase 4 (carry-forward observation) | Legacy display path |
| Notification orchestrator | system | governed send path | Code-built lifecycle reminder render (S4.4) | Bypass for `is_lifecycle_reminder_email_alias()` when active |

**Safety (S4.1):** Tier guards mirror confirm/extraction/scoring — staging raw `active` → effective `shadow`; production raw `active` → effective `off`; CI rejects `LIFECYCLE_AWARE_REMINDERS=active` in production blueprints; boot guard `validate_lifecycle_reminder_boot()`.

**Implemented (S4.2/S4.3):** `lifecycle_reminder_gates.py` — shadow `lifecycle_reminder_shadow_*` logs; active gates suppress non-`EXPIRY_BASED` from `DAILY_COMPLIANCE_EXPIRY_*` pipeline; `resolve_lifecycle_reminder_template_key`; wired in `reminder_truth_service.py` and `jobs.py`.

**Implemented (S4.4):** `lifecycle_reminder_template_registry.py` — `LIFECYCLE_REMINDER_*` seed keys (EMAIL+SMS per `attention_kind`); kind-specific EmailService copy; active preview-tier routing; shadow/off remain legacy-authoritative.

**Staging (shadow):** Legacy reminder eligibility and `COMPLIANCE_EXPIRY_*` templates remain authoritative; lifecycle path observe-only.

**Active (preview-tier only):** Lifecycle-gated eligibility; sends `LIFECYCLE_REMINDER_*` templates per `attention_kind`; not enabled on staging or production.

**Not in Phase 4 (ADR Phases 5–7):** Scheduler changes, attention-date calculation changes in resolver, dashboards, reports, scoring, legacy deprecation.

---

## 5d. KPI authority (Phase 5 — P5-S1/S2 merged; **P5-S3 active authority complete**)

**Authority:** `ADR_REQUIREMENT_LIFECYCLE_SEMANTICS.md`; master tracker `REQUIREMENT_LIFECYCLE_MASTER_IMPLEMENTATION_TRACKER.md`.

**Feature flag:** `LIFECYCLE_AWARE_KPIS` (`off` | `shadow` | `active`) — config in `services/lifecycle_aware_kpis_config.py`.

**Single choke point:** `compute_client_portal_requirement_stats` in `requirement_client_runtime_surface.py`. All client-visible KPI counts (dashboard, compliance score `stats`, reporting parity paths) flow through this function. No dashboard-specific, report-specific, or API-specific KPI calculations.

### Authority model by flag mode

| Mode | Returned authority | Parallel lifecycle | Customer-visible change |
|------|-------------------|--------------------|-------------------------|
| **OFF** | Legacy only | None | None |
| **SHADOW** | Legacy only | Computed + divergence logged (`lifecycle_kpi_shadow_*`) | None |
| **ACTIVE** (preview-tier only) | Lifecycle only | N/A (lifecycle is returned) | Count values may differ; payload shape unchanged |

**OFF → legacy authority**

- `compute_client_portal_requirement_stats` returns legacy status-based aggregation only.
- No lifecycle computation.

**SHADOW → legacy authority + lifecycle observe**

- Legacy stats returned to all consumers.
- `compute_lifecycle_kpi_stats` runs in parallel via `lifecycle_kpi_gates.observe_kpi_shadow`.
- Divergence logged (`lifecycle_kpi_shadow_complete`, `lifecycle_kpi_shadow_divergence`).
- No customer-visible change.

**ACTIVE → lifecycle authority** (preview tier, or non-production preview override)

- `lifecycle_stats_authoritative_payload(compute_lifecycle_kpi_stats(...))` returned.
- Legacy stats never merged into the returned payload.
- Staging raw `active` → effective **shadow** (legacy returned).
- Production raw `active` → effective **off** (legacy returned).

### Entry / surface inventory

| Entry / surface | Actor | Current authority | Lifecycle gate | Flag mode behaviour |
|-----------------|-------|-------------------|----------------|---------------------|
| `compute_client_portal_requirement_stats` | system | **Mode-dependent** (see above) | `lifecycle_kpi_gates.py` | **off:** legacy; **shadow:** legacy + logs; **active (preview):** lifecycle |
| Dashboard KPI widgets | client/admin | legacy headline KPIs | Split per `attention_kind` | **Deferred — P5-S4** |
| Dashboard KPI APIs | client/admin | legacy aggregation paths | Additive lifecycle fields | **Deferred — P5-S5** (`lifecycle_kpi_breakdown` not exposed) |
| Command centre / digest KPI surfaces | system | legacy reporting KPIs | Section language (Phase 6) | **Deferred — P5-S6** |

**Implemented (P5-S2):** `lifecycle_kpi_gates.py` — shadow `lifecycle_kpi_shadow_*` logs; `attention_kind` bucket aggregation (internal telemetry).

**Implemented (P5-S3):** Authority switch in `compute_client_portal_requirement_stats`; explicit semantics→bucket map; `lifecycle_stats_authoritative_payload` (8-key contract); authority regression tests.

**Deferred (not in P5-S3):**

- Dashboard widget exposure — **P5-S4**
- Additive API fields / `lifecycle_kpi_breakdown` — **P5-S5**
- Reports, exports, PDFs, monthly digest — **P5-S6**
- Frontend, production config changes

**Safety (P5-S1):** Tier guards mirror confirm/extraction/scoring/reminders — staging raw `active` → effective `shadow`; production raw `active` → effective `off`; CI rejects `LIFECYCLE_AWARE_KPIS=active` in production blueprints; boot guard `validate_lifecycle_kpi_boot()`.

**Payload contract (unchanged across modes):** `total_requirements`, `compliant`, `satisfied`, `status_valid`, `pending`, `missing_evidence`, `expiring_soon`, `overdue` — no additional, removed, or renamed keys.

**Staging (shadow):** Legacy KPI stats authoritative; lifecycle path observe-only @ `LIFECYCLE_AWARE_KPIS=shadow`.

**Active (preview-tier only):** Lifecycle-gated KPI counts returned; not enabled on staging or production without preview override.

---

## 9. Recommended migration order

1. ~~**Stream B — Legacy path labelling**~~ — Done (docstrings in `compliance_score.py`, `compliance_scoring.py`, module notes in `compliance_scoring_service.py` / `admin.py`).  
2. ~~**Stream B — Admin repair alignment (Option A)**~~ — **Done:** `fix=true` → `recalculate_and_persist` + `REASON_ADMIN_VALIDATOR_REPAIR`; mismatch + repaired audits + `correlation_id`.  
3. **Stream B — Straggler wiring** — After **Stream E** mutation matrix: enqueue or sync `recalculate_and_persist` only where matrix proves a gap. **Shipped slice (2026-05-01):** standalone `sync_requirement_evidence_authority` on selected **admin** + **client guided evidence** routes → `enqueue_compliance_recalc` (see matrix row 9).  
4. **Stream B — Digest / Command Centre** — Hardening / tests only after stragglers addressed.  

---

## 10. Acceptance of this audit

- [x] Every **property score persistence** path identified (admin repair uses canonical writer).  
- [x] Major **readers** of portfolio/property headline mapped.  
- [x] Duplicate / stale / divergence **risks** listed for tracker and Stream E follow-up.  

**Tests run for this doc change:** none required (documentation-only audit).  
