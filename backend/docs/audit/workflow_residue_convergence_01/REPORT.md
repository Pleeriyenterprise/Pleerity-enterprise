# TODAY-WORKFLOW-RESIDUE-CONVERGENCE-01

**Generated:** 2026-06-09  
**Programme:** `TODAY-WORKFLOW-RESIDUE-CONVERGENCE-01`  
**Artifact:** `WORKFLOW_RESIDUE_CONVERGENCE_FINAL_20260609T101054Z.json`  
**Prior audit:** `docs/audit/today_in_progress_source_trace_audit_01/`

---

## Executive summary

Minimal global convergence fixes applied to the Today unified-task pipeline. No workflow-engine rewrite, no scoring semantic changes, no audit-record deletion.

**Final classifications:** `VERIFIED_OPERATIONALLY`, `WORKFLOW_RESIDUE_CONVERGED`

| Scenario | Result |
|----------|--------|
| A — Sophie calm (all satisfied) | `urgent=0`, `in_progress=0`, no churn residue, no duplicate lineage groups |
| B — Partial operational (solo B) | Pre-existing staging state: score 19 but Today empty (same as pre-fix audit); not a convergence regression |
| C — Nancy maintenance-heavy | 24 urgent / 83 in_progress Today; 323 unified tasks; predictive titles preserved; zero duplicate lineage groups; zero churn titles |
| D — Risk recovery | Churn rule returns `[]` when `current_bad_count==0` and no open WO/issues; stale risk-linked issues suppressed when compliance recovered |

**Regression:** 49 tests passed across convergence, Today projection, customer language, phase21 unification, risk regen governance.

---

## 1. Root-cause implementation summary

### Defects addressed (from `TODAY-INPROGRESS-SOURCE-TRACE-AUDIT-01`)

| Classification | Root cause | Fix |
|----------------|------------|-----|
| `TODAY_WORKFLOW_DRIFT` | No lineage dedupe across risk/issue/WO cards sharing `risk_signal_id` | `dedupe_operational_lineage_tasks` — keeps highest-actionability row (WO > issue > risk_signal) |
| `STALE_OPERATIONAL_RESIDUE` | Stale suppression only covered gap-bridge issues | `suppress_stale_operational_residue_tasks` — extends to risk-linked issues and recovered-property risk signals |
| `RISK_SIGNAL_RESIDUE` | Churn rule fired on temporal history when obligations recovered | `_rule_compliance_churn` early return when `current_bad_count==0` and no open WO/issues |
| `CUSTOMER_LANGUAGE_DRIFT` | Internal ontology in card titles ("Compliance Churn Risk Review…") | `_RISK_TYPE_ISSUE_SUMMARIES` + `derive_customer_safe_issue_summary` risk-aware paths |

### Files changed

| File | Role |
|------|------|
| `services/unified_tasks_operational_convergence.py` | **NEW** — suppression + dedupe + `issue_is_stale_operational_residue` |
| `services/unified_tasks_service.py` | Wire convergence after canonical guard; pass `related_risk_signal_id` in metadata |
| `services/client_priority_stream.py` | Propagate `related_risk_signal_id` from issues onto priority actions |
| `services/customer_operational_language_service.py` | Landlord-readable risk issue summaries |
| `services/risk_signal_service.py` | Churn lifecycle decay when obligations recovered |
| `services/risk_signal_regen_governance.py` | Skip stale residue issues in `collect_operational_debt_signal_ids` |
| `tests/test_unified_tasks_operational_convergence.py` | **NEW** — dedupe, suppression, language, churn decay |
| `tests/test_phase21_priority_unification.py` | `bypass_cache=True` in unit tests (cache isolation) |
| `tests/test_risk_signal_regen_governance.py` | Mock client/property docs for convergence-aware debt collection |

### Wiring point (post-canonical guard)

```
get_unified_tasks_for_client
  → _enforce_canonical_requirement_task_guard
  → suppress_stale_operational_residue_tasks   # inbox visibility only
  → dedupe_operational_lineage_tasks           # lineage identity collapse
  → partition / section / cache
```

**Preserved:** audit records, issue/WO documents, risk signal history, regen lineage, legitimate WOs, recurring-repair intelligence, contractor assignment flows.

---

## 2. Before / after workflow lineage trace

### Before (audit finding — churn duplicate pattern)

```
risk_signal_service._rule_compliance_churn
  → risk_signals (Compliance Churn Risk, temporal history)
  → create_issue_from_risk_signal × N (multiple open issues, same risk_signal_id)
  → client_priority_stream (each issue + signal as separate actions)
  → unified_tasks_service (no lineage dedupe)
  → Today: 4× "Compliance Churn Risk Review…" on Property 1
```

**Suppression gap:** `_suppress_stale_compliance_issue_tasks` only matched gap-bridge (`compliance_gap:` / `created_from=compliance`), not `risk_signal_id`-linked issues.

### After (convergence path)

```
risk_signal_service._rule_compliance_churn
  → if current_bad_count==0 AND no open WO/issues → return []  (no new churn signal)
  → else → risk_signals as before

client_priority_stream
  → actions carry related_risk_signal_id

unified_tasks_service
  → suppress_stale_operational_residue_tasks
       if obligations recovered + no active WO → drop issue/risk_signal task from inbox
  → dedupe_operational_lineage_tasks
       group by risk_signal:{id} | work_order:{id} | issue:{id} | root:{key}
       keep min(source_rank, section_rank, -impact_score)

customer_operational_language_service
  → "Compliance follow-up still unresolved" (not "Compliance Churn Risk Review…")
```

### Staging lineage traces (post-fix)

**Sophie calm** — empty task list, `duplicate_lineage_groups: {}`, `active_risk_signals: 0`.

**Nancy ops** — sample preserved operational intents (no churn, no internal leaks):

- `Frequent maintenance issues detected`
- `Repeated repairs detected`
- `Electrical safety concern`
- `Open work order (Assigned)` / `Open work order (Open)`
- `Work order — SLA deadline missed`

`duplicate_lineage_groups: {}` across all probed clients.

---

## 3. Browser proof

Screenshots captured (admin impersonation session):

| Client | File | API calm | Browser note |
|--------|------|----------|--------------|
| Sophie | `browser_sophie_20260609T101054Z.png` | urgent=0, in_progress=0 | Impersonation renders role gate ("Today is available to client users only"); API payloads authoritative |
| Partial B | `browser_partial_b_20260609T101054Z.png` | urgent=0, in_progress=0 | Same role gate |
| Nancy | `browser_nancy_20260609T101054Z.png` | urgent=24, in_progress=83 | Same role gate; `compliance_churn_mentions: 0` in body text |

API verification used `bypass_cache=true` on `/today/items` and `/client/tasks`.

---

## 4. API payload comparisons

| Client | Metric | Pre-fix audit | Post-fix convergence |
|--------|--------|---------------|----------------------|
| Sophie | `urgent_count` | 0 | 0 |
| Sophie | `in_progress_count` | 0 | 0 |
| Sophie | `churn_titles` | — | `[]` |
| Sophie | `duplicate_lineage_groups` | — | `{}` |
| Partial B | `score` | 19 | 19 |
| Partial B | `urgent_count` | 0 | 0 |
| Partial B | `all_satisfied` | false | false |
| Nancy | probe | error (auth) | urgent=24, in_progress=83, 323 unified tasks |
| Nancy | `churn_titles` | — | `[]` |
| Nancy | `duplicate_lineage_groups` | — | `{}` |
| Nancy | predictive titles | — | `Repeated repairs detected`, `Frequent maintenance issues detected` |

**Partial B note:** Empty Today with low compliance score is a **pre-existing staging fixture state** (identical in `TODAY_INPROGRESS_SOURCE_TRACE_FINAL.json`). Convergence fixes target residue/dedupe, not requirement surfacing for billing-gated accounts.

---

## 5. Non-regression proof

| Test module | Result |
|-------------|--------|
| `test_unified_tasks_operational_convergence.py` | 6 passed |
| `test_today_projection_quality.py` | 13 passed |
| `test_customer_operational_language_service.py` | 16 passed |
| `test_phase21_priority_unification.py` | 9 passed |
| `test_risk_signal_regen_governance.py` | 5 passed |

Coverage areas: Today projection, unified tasks, risk signals, maintenance issue stale suppression, work-order precedence in dedupe, customer-language sanitization, churn lifecycle decay, regen governance debt collection.

---

## 6. Final classifications

| Check | Classification |
|-------|----------------|
| Calm account (Sophie) governance | `VERIFIED_OPERATIONALLY` |
| Residue convergence (dedupe + suppression + language + churn decay) | `WORKFLOW_RESIDUE_CONVERGED` |
| Churn duplicate pattern (global) | Converged — no `DEDUPE_DRIFT` or `RISK_RESIDUE_DRIFT` on probed accounts |
| Mature maintenance account (Nancy) | `VERIFIED_OPERATIONALLY` — genuine workflows preserved |
| False calm on partial B | Not observed as regression (pre-existing empty Today) |

**Not classified:** `OPERATIONAL_SUPPRESSION_DRIFT` — no evidence of over-suppression on Nancy or Sophie.

---

## Harness

```bash
cd backend
python tmp_today_workflow_residue_convergence_01.py
python -m pytest tests/test_unified_tasks_operational_convergence.py \
  tests/test_today_projection_quality.py \
  tests/test_customer_operational_language_service.py \
  tests/test_phase21_priority_unification.py \
  tests/test_risk_signal_regen_governance.py -q
```
