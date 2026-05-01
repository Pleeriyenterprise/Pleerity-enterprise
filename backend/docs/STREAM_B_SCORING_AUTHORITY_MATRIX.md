# Stream B — Scoring authority matrix (authoritative inventory)

**Stream:** B — Score Authority Consolidation  
**Phase:** Scoring authority matrix (audit only; no runtime or API changes)  
**Named authority (writes):** `compliance_scoring_service.recalculate_and_persist`  
**Companion reads:** `compliance_scoring_service.calculate_property_compliance` (v2 planner, no persist unless called inside `recalculate_and_persist` or read-repair), `compliance_score.calculate_compliance_score` (portfolio headline + live `stats` from persisted rows + runtime projection)  
**Last updated:** 2026-04-30 (admin repair → `recalculate_and_persist`)  

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

---

## 7. Stale-state & divergence risks

| Risk | Mechanism |
|------|-----------|
| Queue lag | `compliance_score_pending`, `enqueue_compliance_recalc` — dashboard can show old headline until worker runs |
| Read repair | `get_authoritative_property_compliance_for_client` calls `recalculate_and_persist` when `compliance_score` is **null** |
| Lazy backfill | `get_persisted_portfolio_headline_for_summary` / `calculate_compliance_score` can enqueue `TRIGGER_LAZY_BACKFILL` for missing scores |
| Digest vs live portal | Digest uses same `calculate_compliance_score` as other surfaces — **aligned** at assembly time; **time** divergence vs “live now” if email delayed |
| Partial Command Centre | Try/except per subgraph — compliance block can fail while other widgets succeed (gap analysis) |

---

## 8. Affected modules (audit)

**Write path:** `compliance_scoring_service.py`, `compliance_scoring_v2.py`, `compliance_recalc_queue.py`, `job_runner.py`, `routes/properties.py`, `services/compliance_outcome_engine.py`, `routes/admin.py` (validator repair), `score_ledger_service.py`  

**Read / aggregate:** `compliance_score.py`, `scoring_semantics_v1.py`, `portfolio_risk_override*.py`, `command_center_service.py`, `routes/client.py`, `routes/portfolio.py`, `routes/reports.py`, `routes/ops_compliance.py`, `services/reporting_service.py`, `services/monthly_digest_assembly_service.py`, `services/monthly_digest_pdf_service.py`, `services/email_service.py`, `services/compliance_trending.py`, `services/score_events_service.py`, `services/compliance_explain_admin_service.py`, `services/risk_signal_service.py`  

**Enqueue-only (many):** `routes/documents.py`, `routes/evidence_review.py`, `routes/client.py`, `routes/admin.py`, `routes/api_compliance_workflow.py`, `services/evidence_review_verify.py`, `services/jobs.py`, `services/provisioning.py`, `services/compliance_governed_rules_service.py`, `services/compliance_score.py`, `services/compliance_score_reconciliation_service.py`, etc.  

**Tests / contracts:** `test_compliance_scoring_enterprise.py`, `test_compliance_authority_alignment.py`, `test_batch1_score_authority.py`, `test_batch2_p0_score_authority_contract.py`, `test_compliance_score_golden.py`, …  

---

## 9. Recommended migration order

1. ~~**Stream B — Legacy path labelling**~~ — Done (docstrings in `compliance_score.py`, `compliance_scoring.py`, module notes in `compliance_scoring_service.py` / `admin.py`).  
2. ~~**Stream B — Admin repair alignment (Option A)**~~ — **Done:** `fix=true` → `recalculate_and_persist` + `REASON_ADMIN_VALIDATOR_REPAIR`; mismatch + repaired audits + `correlation_id`.  
3. **Stream B — Straggler wiring** — After **Stream E** mutation matrix: enqueue or sync `recalculate_and_persist` only where matrix proves a gap.  
4. **Stream B — Digest / Command Centre** — Hardening / tests only after stragglers addressed.  

---

## 10. Acceptance of this audit

- [x] Every **property score persistence** path identified (admin repair uses canonical writer).  
- [x] Major **readers** of portfolio/property headline mapped.  
- [x] Duplicate / stale / divergence **risks** listed for tracker and Stream E follow-up.  

**Tests run for this doc change:** none required (documentation-only audit).  
