# REQUIREMENT-AUTHORITY-ONBOARDING-DRIFT-AUDIT-01

**Programme:** REQUIREMENT-AUTHORITY-ONBOARDING-DRIFT-AUDIT-01  
**Branch:** `develop` only  
**Verdict:** **B — Defective behaviour confirmed and partially fixed on develop with regression tests**  
**Date:** 2026-06-30  
**Production:** Not touched. Not merged to `main`.

---

## Executive summary

Investigation traced onboarding → materialisation → runtime filter → KPI stats → dashboard / risk signals / Requirements page. **Governance already defines a canonical authority chain**, but several runtime paths diverged from it or from the user’s stated operating principle (missing evidence ≠ confirmed breach).

| Observation | Root cause | Classification |
|-------------|------------|----------------|
| Onboarding “12 generated” vs Requirements “10 tracked” | Raw Mongo `count_documents` vs tracked-attention semantics (OBLIGATION rows excluded) | **Intentional semantics mismatch; onboarding API did not disclose semantics** |
| 45 generated vs fewer tracked (large portfolios) | Same + runtime surface filter (jurisdiction, visibility, obsolete reconciliation) | **Partially intentional; needs transparent counts** |
| Duplicate Occupation Contract (Wales) | Legacy `occupation_contract` DB rule + catalog `wales_occupation_contract`; no alias family | **Defect — fixed on develop** |
| “Electrical safety concern” on new user | Risk rule treated PENDING/MISSING EICR as overdue | **Defect — fixed on develop** |
| Red “Action required” for “Document: Not uploaded” | KPI `PENDING`/`MISSING` = missing evidence; UI copy conflates with breach | **Presentation gap; lifecycle fields exist but chips still read urgent** |

Fixes on develop establish Wales occupation dedupe, stop premature electrical risk signals, and expose semantic counts on `GET /api/portal/setup-status`. Regression tests prove the defects and guards.

---

## 1. Intended design (governance)

### 1.1 Canonical authority chain

`backend/docs/COMPLIANCE_CLIENT_STATUS_AUTHORITY.md` defines KPI-authoritative surfaces:

1. `filter_requirement_rows_for_client_runtime_surfaces` — eligibility, jurisdiction, visibility, **alias dedupe**
2. `project_requirement_row_client_runtime` — projected status / due / evidence
3. `client_portal_surface_visible_row` — exclude `client_surface_visible is False`
4. `compute_client_portal_requirement_stats` — aggregated buckets

Requirements page, dashboard KPIs, compliance score, Command Centre compliance counts, and reports **must** use this chain.

### 1.2 Generated vs tracked

`backend/docs/audit/dashboard_score_widget_semantic_convergence_01/governance_model_runtime.json` explicitly states:

- **Do not equate** widget `requirements_count` with Requirements page **tracked** totals unless labels disclose projection scope.
- Requirements registry **tracked_count**: `client_surface_visible` **DOCUMENT/JOB** rows (no alias dedupe on list API for count base in that audit; runtime filter still applies alias dedupe on read path).

`services/reporting_semantics_v1.py::requirement_row_in_tracked_attention_views` excludes:

- `compliance_requirement_class` in `OBLIGATION`, `SYSTEM`
- `NOT_APPLICABLE` lifecycle
- `is_tracked is False`

Frontend mirrors this in `frontend/src/utils/portalRequirementAttention.js` → `isRequirementIncludedInAttentionViews`; Requirements page stats use it (`RequirementsPage.js`).

**Conclusion:** Generated materialised rows and “tracked attention” rows are **not** the same thing by design. Wales `wales_occupation_contract` and `tenancy_agreement` are **OBLIGATION** class in the catalog planner — they appear in lists but not in the “10 tracked” headline.

### 1.3 Lifecycle: unknown vs confirmed breach

`COMPLIANCE_CLIENT_STATUS_AUTHORITY.md`:

- `PENDING` / `MISSING` → **missing_evidence** KPI bucket, not “confirmed non-compliant”
- `client_lifecycle_state` (`ACTION_REQUIRED`, `PENDING_REVIEW`, `SATISFIED_UNVERIFIED`, `VERIFIED`, `NOT_APPLICABLE`) is additive for UX; portal attention **should** prefer lifecycle over raw status

Risk signals are **operational task flow** (Command Centre / Today), not KPI truth — but they must not imply confirmed breach without evidence.

### 1.4 Materialisation idempotency

`services/requirement_materialization_service.py` documents idempotency per `(client_id, property_id, requirement_type)`. Supplemental `requirement_rules` in `provisioning._apply_db_rules` skip exact `rule_type` matches in the registry plan but **did not** treat `occupation_contract` as an alias of `wales_occupation_contract`.

**No Mongo unique index** on `(client_id, property_id, requirement_code, jurisdiction)` for active rows — application-level idempotency only.

---

## 2. Execution path traced

```
Onboarding / payment webhook
  → provisioning._generate_requirements
      → materialize_requirements_for_property (catalog plan)
      → _apply_db_rules (supplemental Mongo rules)
  → Mongo requirements collection

Client surfaces
  → GET /api/client/requirements
      → filter_requirement_rows_for_client_runtime_surfaces
      → enrich_requirements_for_client (client_lifecycle_state)
  → Requirements page: local tracked count via isRequirementIncludedInAttentionViews
  → GET /api/client/dashboard / compliance-score
      → calculate_compliance_score → compute_client_portal_requirement_stats
  → GET /api/portal/setup-status
      → requirements_count = raw count_documents (legacy)
      → requirements_tracked_attention_count (added in this audit)
  → generate_risk_signals_for_property
      → heuristic rules → risk_signals collection
  → Command Centre / Today
      → unified_tasks_service, client_priority_stream, risk_signals read model
```

---

## 3. Investigation answers (1–20)

| # | Question | Answer |
|---|----------|--------|
| 1 | Canonical source for **applicable** requirement? | `build_requirement_plan_for_property` + `materialize_requirements_for_property` (+ supplemental governed `requirement_rules`) |
| 2 | Canonical source for **tracked** requirement? | Runtime-filtered rows passing `requirement_row_in_tracked_attention_views` |
| 3 | Generated = tracked? | **No** — OBLIGATION/SYSTEM and non-tracked rows differ |
| 4 | Documented transition? | Yes — class + `is_tracked` + reporting semantics; widget vs registry divergence documented in dashboard convergence audit |
| 5 | Why 12 vs 10? | 12 raw materialised rows; 10 DOCUMENT/JOB tracked-attention rows (e.g. 2 Wales obligations) |
| 6 | Intentionally filtered? | Yes — class, visibility, jurisdiction, obsolete reconciliation, alias dedupe on runtime read |
| 7 | Visible to user? | **Was not** on onboarding counter; **now** semantic fields on setup-status |
| 8 | Why duplicate Occupation Contract? | Legacy DB slug + catalog slug; missing alias family |
| 9 | DB uniqueness constraint? | **No** composite unique index |
| 10 | Idempotency on re-run? | Per `requirement_type` yes; alias collisions **were not** prevented |
| 11 | Frontend same API as dashboard? | Requirements page computes tracked locally from same API rows; dashboard uses `calculate_compliance_score.stats` — aligned semantics, different aggregation scope |
| 12 | “Do this next” source? | Backend: `unified_tasks_service` / `client_priority_stream`; frontend `TodayExecutionHero` — not local inference of compliance breach |
| 13 | Risk signals basis? | Mixed; electrical rule **incorrectly** used PENDING/MISSING EICR — **fixed** |
| 14 | New user missing evidence? | Governance: pending verification / missing evidence; not confirmed breach |
| 15 | Lifecycle separation? | Model exists (`client_lifecycle_state`); UI chips still show “Action required” for `PENDING` |
| 16 | Governance requires distinction? | **Yes** — see COMPLIANCE_CLIENT_STATUS_AUTHORITY.md |
| 17 | Counts aligned? | KPI surfaces yes; onboarding raw count **was not** |
| 18 | Pagination hiding rows? | Not primary cause for 12/10; filter semantics explain delta |
| 19 | Background jobs partial? | No evidence of timeout-driven loss for single-property Wales case; large portfolios need separate perf audit |
| 20 | Conflicting published rules? | Supplemental `requirement_rules` can duplicate catalog slugs when alias not recognised |

---

## 4. Defects confirmed and fixes (develop)

### 4.1 Wales occupation duplicate (DEFECT)

**Root cause:** `_ALIAS_FAMILY_BY_CANONICAL` had no entry for `occupation_contract` / `wales_occupation_contract`. `_apply_db_rules` skipped only exact `rule_type` matches.

**Fix:**

- `requirement_client_runtime_surface.py` — alias family `wales_occupation_contract_alias_family`
- `provisioning.py` — skip DB `occupation_contract` when plan contains `wales_occupation_contract`

**Before:** Two list cards for same property/jurisdiction.  
**After:** Runtime dedupe keeps published-enriched winner; new provisions skip legacy DB insert.

### 4.2 Premature electrical risk signal (DEFECT)

**Root cause:** `_fetch_requirements_overdue` included `PENDING`/`MISSING`; `_rule_electrical` fired on any EICR row.

**Fix:**

- `risk_signal_service.py` — `_fetch_requirements_confirmed_calendar_risk` (OVERDUE/EXPIRED only) for electrical + compliance churn inputs
- `_rule_electrical` — status guard on EICR rows; reason text “calendar-confirmed”

**Before:** New onboarded user with PENDING EICR → “Electrical safety concern”.  
**After:** No electrical risk until calendar-confirmed OVERDUE/EXPIRED (or ≥2 operational electrical issues).

### 4.3 Onboarding count semantics (AUTHORITY DRIFT)

**Root cause:** `GET /api/portal/setup-status` exposed only raw `requirements_count`.

**Fix:** Added `requirements_runtime_visible_count`, `requirements_tracked_attention_count`, `requirements_count_semantics`.

**Before:** UI implied one number authority.  
**After:** API discloses raw vs tracked; frontend can adopt without changing legacy field.

### 4.4 Not fixed in this pass (remaining risks)

| Item | Reason |
|------|--------|
| UI copy “Action required” for missing upload | Presentation-only; needs lifecycle-aware chip copy (separate change) |
| Existing duplicate Mongo rows | Runtime dedupe hides in lists; **no data migration** — optional admin reconcile job |
| Mongo unique index | Broader migration; materialisation idempotency sufficient for new rows with alias fix |
| Frontend onboarding display | Must consume new setup-status fields |
| 45 vs half tracked (large portfolios) | Needs per-client diagnostic with semantic breakdown in admin explain API |

---

## 5. Tests and commands

**Added:** `backend/tests/test_requirement_authority_onboarding_drift_01.py`

```bash
cd backend
python -m pytest tests/test_requirement_authority_onboarding_drift_01.py -v --tb=short
```

**Result (2026-06-30):** 5 passed

| Test | Proves |
|------|--------|
| `test_wales_occupation_contract_alias_family_dedupes_duplicate_slugs` | Alias dedupe |
| `test_provisioning_skips_db_occupation_contract_when_wales_catalog_planned` | Provision guard |
| `test_electrical_risk_does_not_fire_on_pending_eicr_only` | No premature risk |
| `test_electrical_risk_fires_on_overdue_eicr` | Confirmed risk still works |
| `test_portal_setup_status_exposes_tracked_attention_semantics` | Semantic counts |

---

## 6. Changed files

| File | Change |
|------|--------|
| `services/requirement_client_runtime_surface.py` | Wales occupation alias family |
| `services/provisioning.py` | DB rule guard for occupation slug |
| `services/risk_signal_service.py` | Calendar-confirmed fetch + EICR status guard |
| `routes/portal.py` | `_portal_requirement_count_semantics` + setup-status fields |
| `tests/test_requirement_authority_onboarding_drift_01.py` | Regression suite |
| `docs/audit/requirement_authority_onboarding_drift_01/*` | This audit |

---

## 7. Production promotion recommendation

**Do not promote until:**

1. Develop fixes merged and deployed to staging.
2. Staging validation on a Wales property: single Occupation Contract card; no electrical risk with PENDING-only EICR.
3. Frontend onboarding updated to show `requirements_tracked_attention_count` with semantics footnote.
4. Optional: one-off reconcile script for existing `occupation_contract` + `wales_occupation_contract` pairs (archive loser, audit log).

**Safe to promote after staging proof:** alias dedupe, provision guard, risk signal narrowing, setup-status semantics (backward compatible).

---

## 8. Governance citations

- `backend/docs/COMPLIANCE_CLIENT_STATUS_AUTHORITY.md`
- `backend/docs/audit/dashboard_score_widget_semantic_convergence_01/governance_model_runtime.json`
- `backend/services/reporting_semantics_v1.py` — `requirement_row_in_tracked_attention_views`
- `backend/services/provisioning.py` — dual-path generation comment block
- `backend/services/requirement_materialization_service.py` — idempotency contract
- `backend/docs/audit/operations_lifecycle_convergence_audit_01/REPORT.md` — compliance risk signals not gated by operational history (intentional for calendar compliance)

Machine-readable evidence: `REQUIREMENT_AUTHORITY_ONBOARDING_DRIFT_EVIDENCE.json`
