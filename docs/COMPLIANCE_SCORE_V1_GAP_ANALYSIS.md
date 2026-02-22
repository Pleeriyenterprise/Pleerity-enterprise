# Compliance Score v1 – Task vs Codebase Gap Analysis

**Constraint:** Evidence-based, no legal verdicts. PR-ready diff and file:line references; add specified unit tests.

---

## Summary Table

| # | Task requirement | Current state | Status |
|---|------------------|---------------|--------|
| 1 | Add scoring module `backend/services/compliance_scoring.py` (inputs: property + requirements + documents → score_0_100, risk_level, breakdown) | No such file. `compliance_score.py` = client-level reader from stored scores; `compliance_scoring_service.py` = property calc with different formula | **Missing** – new module needed |
| 2 | Status factor S(r): Valid 1.0, Expiring soon 0.7, Overdue 0.25, Missing 0.0, Needs review 0.5 | Current: COMPLIANT 100, PENDING 70, EXPIRING_SOON 40, OVERDUE 0 (points, not factors); no “Needs review” | **Missing** – new mapping |
| 3 | Base weights W(r): Gas 30 (if gas), EICR 25, EPC 15, Licence 20 (if licence_required), Tenancy 10; renormalize to 100 | Current: REQUIREMENT_TYPE_WEIGHTS (1.0–1.6), no applicability (gas/licence), no renormalization | **Missing** – new weights + applicability |
| 4 | Multipliers M(r): HMO (Gas 1.1, EICR 1.15, Licence 1.25); occupancy != single_family or bedrooms >= 5 → Licence 1.1 | Current: HMO 1.2 for HMO-specific types only; no Gas/EICR/Licence multipliers; no occupancy/bedrooms | **Missing** – new multipliers |
| 5 | Property score: We=W*M, Wn=100*We/sum(We), Score=sum(Wn*S) | Current: 35% status + 25% expiry + 15% doc + 15% overdue + 10% risk (different model) | **Missing** – new formula |
| 6 | Risk label: critical = Gas, EICR, Licence (when required); Critical if any critical missing OR score<40; High if any critical overdue OR 40≤score<60; Medium 60≤score<80; Low score≥80 and no critical overdue/missing | Current: `risk_bands.score_to_risk_level(score)` only (80/60/40 bands); catalog_compliance has critical-override for missing | **Partial** – need v1 rule in new module |
| 7 | Persist: properties.compliance_score, properties.risk_level, properties.score_breakdown | Current: compliance_score, compliance_breakdown (different shape); risk_level not persisted on property | **Partial** – add risk_level + score_breakdown (v1 shape) |
| 8 | Trigger: doc create/update/delete; property update (is_hmo, bedrooms, occupancy, licence_required); nightly sweep | Current: doc create/update/delete ✓; property **create** ✓; property **update** not triggering; nightly = expiry rollover job exists | **Partial** – add property-update trigger + optional nightly sweep |
| 9 | Portfolio: E(p)=1+0.5 HMO +0.2 bedrooms≥4 +0.2 occupancy≠single_family; weighted avg by E(p); portfolioRisk = worst(propertyRisk) | Current: catalog uses weighted-by-matrix-weights avg; portfolio_risk = max(property risk); no E(p) weights | **Missing** – new portfolio formula in v1 |
| 10 | Frontend: per-property score + risk in Properties list and Property detail | Property detail uses compliance-detail API (catalog or fallback); dashboard uses portfolio summary. Stored risk_level not yet used from property doc | **Partial** – use stored score/risk when available |
| 11 | Dashboard: portfolio score + worst risk + top urgent | Already present (portfolio summary + Next Actions) | **Done** |
| 12 | Remove “compliant/non-compliant”; use Evidence Status chips | Already done in prior work (Valid, Expiring soon, etc.) | **Done** |

---

## Conflicts and Safest Options

### 1) File name: `compliance_scoring.py` vs existing

- **Task:** Add `backend/services/compliance_scoring.py`.
- **Current:** `compliance_score.py` (client-level, reads stored scores); `compliance_scoring_service.py` (property calc + persist).
- **Conflict:** Name collision with “compliance_scoring” (service already exists).
- **Safest option:** Add **`backend/services/compliance_scoring.py`** as the **v1 scoring engine** (pure function: property + requirements + documents → score, risk_level, breakdown). Have **`compliance_scoring_service.py`** call this module for the calculation when using v1 (e.g. via a version flag or as the default going forward), and keep persistence/history/audit in the service. Do not rename or remove existing files; add the new module and integrate.

### 2) Two scoring models (current vs v1)

- **Current:** Status points 100/70/40/0, component weights 35/25/15/15/10, requirement weights 1.0–1.6, no applicability.
- **Task v1:** Status factors 1.0/0.7/0.25/0.0/0.5, base weights Gas/EICR/EPC/Licence/Tenancy with applicability, renormalization, multipliers, score = sum(Wn*S).
- **Safest option:** Implement v1 in `compliance_scoring.py`. In `compliance_scoring_service.calculate_property_compliance` either (A) call v1 and return its output shape (and persist risk_level + score_breakdown), or (B) add a feature flag and run v1 when enabled. Prefer (A) and make v1 the single property-scoring path to avoid long-term duplication; keep client-level `compliance_score.calculate_compliance_score` unchanged (it aggregates stored property scores).

### 3) Risk level source (score-only vs critical rules)

- **Current:** `risk_bands.score_to_risk_level(score)` (80/60/40). Catalog has “critical missing → Critical”.
- **Task:** Critical = Gas, EICR, Licence (when required); Critical if any critical missing OR score<40; High if any critical overdue OR 40≤score<60; etc.
- **Safest option:** Implement risk in **`compliance_scoring.py`** only (v1). Persist `risk_level` on property from v1. Do not change `risk_bands.py` (used elsewhere); v1 returns its own risk label string (Low/Medium/High/Critical risk to align with frontend “Medium” wording). Callers that read stored property score/risk use the new fields.

### 4) Portfolio score source

- **Current:** `catalog_compliance.get_portfolio_compliance_from_catalog` (catalog-driven) or `portfolio.get_compliance_summary` legacy (average of property scores).
- **Task:** E(p) weights, weighted average by E(p), portfolio risk = worst(property risk).
- **Safest option:** Add a **portfolio function in `compliance_scoring.py`** (or in the service) that, given client’s properties with stored v1 `compliance_score` and `risk_level`, computes portfolio score = weighted average by E(p) and portfolio risk = max(property risk). Use this when reading from DB (stored v1 scores); keep catalog path for when catalog is used (or migrate portfolio to always use stored v1 + this formula).

---

## Implementation Completed (PR)

- **New:** `backend/services/compliance_scoring.py` – v1 engine (status_factor, applicable weights, multipliers, compute_property_score, _risk_level_from_breakdown, portfolio_score_and_risk).
- **Updated:** `backend/services/compliance_scoring_service.py` – uses `compute_property_score` from compliance_scoring; persists `risk_level` and `score_breakdown` on property; returns `risk_level` and `score_breakdown` in result.
- **Triggers:** Document create/update/delete and property create already enqueue recalc. **Property update** (PATCH) of is_hmo, bedrooms, occupancy, licence_required, has_gas: when a dedicated property-update route exists, call `enqueue_compliance_recalc` with a new trigger e.g. `TRIGGER_PROPERTY_UPDATED`. Nightly sweep: existing expiry rollover job enqueues recalc; optional full-sweep job can be added later.
- **Frontend:** Per-property score and risk already displayed from compliance-detail/portfolio APIs; stored `risk_level` is now populated and can be returned by portfolio/compliance-detail when reading from property doc.
- **Unit tests:** `backend/tests/test_compliance_scoring_v1.py` – status factor mapping, renormalization when gas not applicable, critical missing forces Critical, portfolio weighted average and worst-risk rule (15 tests).

---

## Implementation Plan (file:line references)

### New file: `backend/services/compliance_scoring.py`

- **Status factor:** Function `status_factor(status, days_to_expiry, has_doc, needs_review)` → 1.0 | 0.7 | 0.25 | 0.0 | 0.5 per spec.
- **Applicable requirements:** From property (has_gas, licence_required, is_hmo, bedrooms, occupancy) determine which of Gas / EICR / EPC / Licence / Tenancy apply; base weights W(r) and multipliers M(r); build list of (requirement_key, weight, multiplier).
- **Breakdown:** For each applicable requirement, resolve status and linked document → status_factor, days_to_expiry; output breakdown array.
- **Score:** We = W*M, Wn = 100*We/sum(We), score = round(sum(Wn*S)), clamped 0–100.
- **Risk:** critical_requirements = [Gas, EICR, Licence (if licence_required)]; apply task rules (critical missing → Critical; critical overdue → at least High; then score bands).
- **Output:** `{score_0_100, risk_level, breakdown: [{requirement_key, weight, status, status_factor, days_to_expiry}]}`.
- **Portfolio:** `portfolio_score_and_risk(properties_with_scores)` → E(p) = 1 + 0.5*is_hmo + 0.2*(bedrooms>=4) + 0.2*(occupancy!=single_family); weighted_avg = sum(score*E(p))/sum(E(p)); risk = max(property risk).

### Changes to existing files

- **`backend/services/compliance_scoring_service.py`**
  - Replace (or branch) `calculate_property_compliance` to use `compliance_scoring.compute_property_score(property_doc, requirements, documents)` and return structure that includes `risk_level` and `score_breakdown` (v1 shape).
  - In `recalculate_and_persist`: persist `risk_level` and `score_breakdown` (optional array) on property; keep `compliance_score`, `compliance_breakdown` (can keep for backward compat or map from v1 breakdown).
- **`backend/routes/portfolio.py`**
  - When using stored property data, include `risk_level` and score from property if present; portfolio summary can call new portfolio function when all properties have v1 data.
- **Property update trigger**
  - In `backend/routes/properties.py` (or wherever property PATCH/PUT is), after update, if `is_hmo`, `bedrooms`, `occupancy`, `licence_required`, or `has_gas`/`has_gas_supply` changed, call `enqueue_compliance_recalc`.
- **Nightly sweep**
  - Existing `run_expiry_rollover_recalc` or a similar job can enqueue all client properties for recalc as a safety net (e.g. once per night).

### Frontend

- **Properties list:** Already shows score and risk from portfolio summary or property; ensure when API returns stored `compliance_score` and `risk_level` they are displayed (likely already via portfolio or property detail).
- **Property detail:** Already shows score and risk from compliance-detail API; if we add stored `risk_level`/`compliance_score` to property and API returns them, no change or minimal.
- **Dashboard:** Already portfolio + worst risk + Next Actions; Evidence Status chips done.

### Unit tests (add to e.g. `backend/tests/test_compliance_scoring_v1.py`)

1. **Status factor mapping:** For each status + days_to_expiry + has_doc + needs_review, assert expected S(r) (1.0, 0.7, 0.25, 0.0, 0.5).
2. **Renormalization when gas not applicable:** Property without gas: Gas excluded, remaining weights renormalize to 100, score computed only from applicable.
3. **Critical missing forces Critical:** Even if numeric score is high, if any critical requirement (Gas/EICR/Licence when required) is missing evidence, risk_level = Critical.
4. **Portfolio weighted average and worst-risk rule:** Mock properties with E(p) and scores; assert portfolio_score = weighted average by E(p); assert portfolio_risk = worst of property risks.

---

## File:Line References (current codebase)

- **Property score calculation:** `backend/services/compliance_scoring_service.py:44–228` (`calculate_property_compliance`).
- **Persistence:** `backend/services/compliance_scoring_service.py:263–272` (update_one properties with compliance_score, compliance_breakdown).
- **Risk from score only:** `backend/utils/risk_bands.py:13–21` (`score_to_risk_level`).
- **Client score (aggregate):** `backend/services/compliance_score.py:69–118` (reads stored property scores).
- **Recalc triggers (doc):** `backend/routes/documents.py` (multiple lines 298, 591, 697, 807, 880, 968, 1020, 1068, 1584).
- **Recalc trigger (property create):** `backend/routes/properties.py:105–106`.
- **Portfolio (catalog):** `backend/services/catalog_compliance.py:220–279` (`get_portfolio_compliance_from_catalog`).
- **Compliance-detail route:** `backend/routes/portfolio.py:123–184` (property compliance detail).
- **Profile for applicability:** `backend/utils/catalog_rules.py:77–92` (`build_property_profile`); add bedrooms/occupancy if needed for v1.

---

## Optional: Backward compatibility

- Keep `compliance_breakdown` on property as a summary (e.g. status_score, expiry_score, …) derived from v1 breakdown for existing consumers, or deprecate once all readers use `score_breakdown`.
- Frontend and portfolio can prefer stored `risk_level` when present and fall back to `score_to_risk_level(compliance_score)` for older data.
