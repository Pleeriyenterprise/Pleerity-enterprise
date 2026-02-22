# Audit Intelligence – Task vs Codebase Gap Analysis (Mathematically Robust Scoring + Enterprise UI)

**Constraint:** Do NOT change Stripe, provisioning, authentication, or entitlement logic.

This document compares the **new task** (mathematically robust risk scoring + enterprise UI layout) to the **current implementation** (previous Audit Intelligence work) and identifies conflicts, gaps, and the safest implementation path.

---

## Summary: Conflicts and Recommendations

| Area | Current implementation | New task | Conflict? | Recommended approach |
|------|------------------------|----------|-----------|----------------------|
| **EXPIRING_SOON score** | Fixed 70 | Expiry decay: 0–30d⇒70, 31–60⇒85, >60⇒100 | **Yes** | Implement decay in **portfolio summary only**; keep existing property/client score logic unchanged. |
| **Risk score bands** | 80+ Low, 60–79 Moderate, 40–59 High, 0–39 Critical | Low≥85, Moderate 70–84.99, High 55–69.99, Critical<55 | **Yes** | Use **new task bands** for portfolio/property risk in the new API and UI only. |
| **Requirement weights** | Equal per requirement (portfolio); compliance_score uses 1.0–1.6 multipliers by type | Gas 18, EICR 16, Deposit 10, etc. (baseline list) | **Yes** | Add **task baseline weights** only inside the new scoring module used for `/api/portfolio/compliance-summary`. Do not replace existing `REQUIREMENT_TYPE_WEIGHTS` in `compliance_score.py`. |
| **Risk Index + guardrails** | Not present | R = (3×overdue + 2×missing + 1×expiring_soon)/denom; guardrails for high-critical | **New** | Implement in portfolio summary path only. |
| **API response shape** | `portfolio_score`, `risk_level`, `properties[]` (no kpis, updated_at, name; expiring_soon_count) | `portfolio_score`, `portfolio_risk_level`, `updated_at`, `kpis`, `properties[]` (name, expiring_30_count, missing_count) | **Partial** | Extend existing endpoint: add fields, rename `risk_level`→`portfolio_risk_level` for clarity; keep backward-compatible alias if needed. |
| **Property compliance detail** | No dedicated endpoint | GET `/api/properties/{id}/compliance-detail` (matrix, evidence links, days_to_expiry) | **New** | Add under client/portfolio router; property detail page already has a requirements table but uses `/client/properties/:id/requirements` and no doc links. |
| **Nav** | Dashboard, Properties, Requirements, Documents, Audit Log, Calendar, Reports, Settings | Dashboard, **Portfolio**, Requirements, Documents, **Compliance Calendar**, Reports, Audit Log, Settings | **Partial** | Rename/label only: e.g. "Portfolio" as label for current Dashboard or a dedicated Portfolio view; "Compliance Calendar" = current Calendar. No structural auth change. |
| **Property detail tabs** | Single view: header + requirements matrix | Overview, Requirements Matrix, Documents, Timeline, Notes & Tasks (optional), Audit Trail | **Partial** | Add tabs to Property detail; some content exists (requirements table, doc upload). Timeline/Audit = client-scoped audit events for property. |

---

## A) Scoring Model (Server-Side) – Detail

### 1) Requirement status labels

- **Task:** VALID, EXPIRING_SOON, MISSING, OVERDUE.
- **Codebase:** `RequirementStatus`: PENDING, COMPLIANT, EXPIRING_SOON, OVERDUE (and EXPIRED in places). No explicit VALID/MISSING; COMPLIANT ≈ VALID, PENDING ≈ MISSING.
- **Gap:** Mapping only. Use: VALID↔COMPLIANT, MISSING↔PENDING; EXPIRING_SOON, OVERDUE/EXPIRED as-is.

### 2) Numeric scoring (requirement-level)

- **Task:**
  - OVERDUE ⇒ 0  
  - MISSING ⇒ 30  
  - EXPIRING_SOON ⇒ expiry decay: days_to_expiry < 0 ⇒ 0; 0–30 ⇒ 70; 31–60 ⇒ 85; >60 ⇒ 100  
  - VALID non-expiring ⇒ 100  

- **Current (portfolio.py):** Fixed points: VALID/COMPLIANT=100, EXPIRING_SOON=**70**, PENDING/MISSING=30, OVERDUE/EXPIRED=0. **No expiry decay** and no distinction for “VALID non-expiring”.

- **Conflict:** Yes. **Recommendation:** In the **portfolio summary scoring path only**, compute per-requirement score with expiry decay for EXPIRING_SOON (using `due_date`), and treat COMPLIANT with no expiry or far-future expiry as 100. Leave existing `compliance_score.py` and `compliance_scoring_service` unchanged.

### 3) Requirement weights (baseline)

- **Task:** Gas 18, EICR 16, Deposit 10, HMO/Selective licence 18 (conditional), EPC 8, Smoke 8, CO 6, Tenancy 6, Right to Rent 7, How to Rent 5, Fire RA 6 (conditional), Legionella 4, Inventory 4.

- **Codebase:** `compliance_score.py` has `REQUIREMENT_TYPE_WEIGHTS` (multipliers 0.8–1.6) and different type names (e.g. GAS_SAFETY, EICR, DEPOSIT_PROTECTION). Provisioning uses snake_case (gas_safety, eicr, epc, etc.). No numeric baseline list as in task.

- **Conflict:** Yes. **Recommendation:** Introduce a **separate** task baseline weight map (e.g. in `portfolio.py` or a small `portfolio_scoring.py`) keyed by `requirement_type` (normalised). Use it **only** for S_property and portfolio in the new API. Do **not** change `REQUIREMENT_TYPE_WEIGHTS` or existing scoring.

### 4) Applicability

- **Task:** Only include applicable requirements in the scoring denominator.

- **Codebase:** Provisioning already creates requirements per property based on applicability (e.g. gas only if has_gas_supply, HMO rules if is_hmo). So “applicable” = requirements that exist for that property. No explicit `applicable` flag on requirement docs.

- **Gap:** Use “all requirements for that property” as applicable set; no schema change required. If later we add optional “not applicable” flags, denominator can exclude those.

### 5) Property score

- **Task:** S_property = sum(w_i × s_i) / sum(w_i) over applicable requirements.

- **Current (portfolio.py):** Equal weight: property_score = average of requirement points (no w_i).

- **Gap:** Implement weighted formula in the new scoring path using the task baseline weights; keep current endpoint’s logic isolated so existing behaviour is unchanged.

### 6) Portfolio score

- **Task:** Weighted average of property scores by total applicable weights per property.

- **Current:** Weighted average by **requirement count** (not by sum of weights). So denominator is total requirement count.

- **Conflict:** Minor. **Recommendation:** Switch portfolio denominator to sum of applicable weights per property (sum over all properties of sum(w_i)) and numerator sum( S_property × sum(w_i) ) for each property. Implement only in the new path.

### 7) Risk Index (high-critical only)

- **Task:** R = (3×overdue + 2×missing + 1×expiring_soon) / max(1, total_high_critical_applicable). Not in codebase.

- **Gap:** New. **Recommendation:** Define “high-critical” from task (e.g. requirement types that have baseline weight ≥ some threshold, or an explicit list: Gas, EICR, Deposit, HMO/Selective, EPC, Smoke, CO, Fire RA). Compute R only over those; add to portfolio summary response.

### 8) Risk levels and guardrails

- **Task:**  
  - Score bands: Low≥85, Moderate 70–84.99, High 55–69.99, Critical<55.  
  - Risk index bands: Low<0.25, Moderate 0.25–0.59, High 0.60–1.19, Critical≥1.20.  
  - Final risk level = max(score-based, risk-index-based).  
  - Guardrails: any high-critical overdue ⇒ at least HIGH; ≥2 high-critical overdue ⇒ CRITICAL.

- **Current:** Score bands 80/60/40 (Low/Moderate/High/Critical). No risk index, no guardrails.

- **Conflict:** Yes. **Recommendation:** In the new API and UI only, use task bands and guardrails. Keep existing `_score_to_risk_level` (80/60/40) **only** for any legacy or non-portfolio use, or remove from portfolio path and use the new bands everywhere the new API is consumed.

---

## B) API – Detail

### GET /api/portfolio/compliance-summary

- **Exists:** Yes (`backend/routes/portfolio.py`).
- **Current response:** `portfolio_score`, `risk_level`, `properties[]` (property_id, property_score, risk_level, overdue_count, expiring_soon_count). No `updated_at`, no `kpis`, no property `name`, no `expiring_30_count` / `missing_count` per property.
- **Task response:**  
  `portfolio_score`, `portfolio_risk_level`, `updated_at`,  
  `kpis: { overdue, expiring_30, missing, compliant }`,  
  `properties: [{ property_id, name, score, risk_level, overdue_count, expiring_30_count, missing_count }]`.
- **Recommendation:** Extend the same endpoint: add `updated_at` (e.g. last recalc or now), add `kpis`, add `name` and `expiring_30_count`, `missing_count` per property; use `portfolio_risk_level` (and keep `risk_level` as alias for backward compatibility if any client relies on it). Implement new scoring (weights, decay, risk index, guardrails) behind this endpoint only.

### GET /api/properties/{id}/compliance-detail

- **Exists:** No. Client has `/api/client/properties/{id}/requirements` (list of requirements). Property detail page builds a matrix from that; no doc links or days_to_expiry in a single structured response.
- **Task:** Requirement matrix with statuses, expiry dates, evidence doc links, days_to_expiry.
- **Recommendation:** Add GET `/api/portfolio/properties/{id}/compliance-detail` (or under `/api/client/...`) with client_route_guard. Return requirements with status, due_date, days_to_expiry, and list of linked document IDs or download links (from existing documents collection by requirement_id). Frontend can keep or replace current matrix data source.

---

## C) Frontend UI – Detail

### Left nav

- **Task:** Dashboard, Portfolio, Requirements, Documents, Compliance Calendar, Reports, Audit Log, Settings.
- **Current:** Dashboard, Properties, Requirements, Documents, Audit Log, Calendar, Reports, Settings.
- **Gap:** “Portfolio” vs “Properties”, “Compliance Calendar” vs “Calendar”. **Recommendation:** Treat “Portfolio” as the dashboard view that shows portfolio summary (current dashboard can be renamed or duplicated as “Portfolio”); or add a “Portfolio” item that shows the same summary in a dedicated page. Rename “Calendar” to “Compliance Calendar”. No auth/entitlement change.

### Dashboard sections (wireframe)

- **Task:**  
  1) Portfolio header (risk badge + score + updated_at)  
  2) KPI cards (overdue / expiring / missing / compliant)  
  3) Risk Queue table sorted by severity  
  4) Property breakdown table with Open buttons  
  5) Collapsible “How scoring works” + disclaimer  

- **Current:** Welcome/Command Centre title; risk level + portfolio score line; Compliance Framework collapsible; Portfolio summary table (property, score, risk, overdue, expiring soon); then tiles (Total Requirements, Compliant, Expiring, Overdue) and other blocks. No dedicated “Risk Queue” table; no explicit KPI cards matching task (overdue, expiring_30, missing, compliant).

- **Gap:** Add/align: (1) Portfolio header with risk badge + score + updated_at from new API. (2) KPI cards from `kpis`. (3) Risk Queue table (e.g. overdue/expiring requirements across portfolio, sorted by severity). (4) Property breakdown with Open = link to property detail (already present). (5) “How scoring works” = current Compliance Framework; ensure disclaimer and non-legal wording.

### Property detail page tabs

- **Task:** Overview, Requirements Matrix, Documents, Timeline, Notes & Tasks (optional), Audit Trail.
- **Current:** Single scroll: header, requirements table, evidence status, expiry, days left, upload. No tabs; no Timeline; no Audit Trail; no Notes & Tasks.
- **Gap:** Add tabbed layout: Overview (current header + summary), Requirements Matrix (current table), Documents (filtered by property or link to /documents?property_id=), Timeline (property-level or client audit events), Audit Trail (same or filtered), Notes & Tasks optional later.

### Wording

- **Task:** Avoid implying legal certification; use “risk”, “status”, “evidence recorded”, “based on uploaded documents”.
- **Current:** “Evidence-based status summary”, “not legal advice”, “Compliance Framework”. **Recommendation:** Audit all dashboard and property copy for “certified”, “compliant” in a legal sense; prefer “evidence status”, “risk”, “recorded”, “based on uploaded documents”.

---

## Implementation Order (Safe, Minimal)

1. **Scoring module (new, isolated)**  
   - Add a dedicated module (e.g. `portfolio_scoring.py` or inside `routes/portfolio.py`) that:  
     - Maps status + due_date to requirement score (with expiry decay for EXPIRING_SOON).  
     - Uses task baseline weights and applicability (all requirements for property).  
     - Computes S_property = sum(w_i×s_i)/sum(w_i).  
     - Computes portfolio score by weight-weighted average of property scores.  
     - Computes Risk Index R for high-critical requirements.  
     - Applies score + risk-index bands and guardrails → portfolio_risk_level and per-property risk_level.  
   - Do **not** change `compliance_score.py` or `compliance_scoring_service` for existing client/score or stored property scores.

2. **GET /api/portfolio/compliance-summary**  
   - Use the new scoring module.  
   - Return task shape: portfolio_score, portfolio_risk_level, updated_at, kpis, properties (with name, score, risk_level, overdue_count, expiring_30_count, missing_count).  
   - Keep response deterministic and document that it is “evidence-based status; not legal advice”.

3. **GET /api/portfolio/properties/{id}/compliance-detail** (or /api/client/properties/{id}/compliance-detail)  
   - Return requirement matrix: requirement_id, type, status, due_date, days_to_expiry, evidence (document IDs or links).  
   - Client_route_guard; verify property belongs to client.

4. **Frontend**  
   - Consume updated compliance-summary (header, KPIs, Risk Queue, property table, “How scoring works”).  
   - Add compliance-detail to property detail (e.g. Requirements Matrix tab with doc links).  
   - Nav: align labels (Portfolio, Compliance Calendar).  
   - Property detail: add tabs (Overview, Requirements Matrix, Documents, Timeline, Audit Trail).  
   - Wording: replace any certification-like language with risk/evidence/status wording.

5. **No change**  
   - Stripe, provisioning, auth, entitlements.  
   - Existing `/client/compliance-score`, stored property score calculation, and recalc triggers (except if we explicitly want to persist “portfolio risk level” or new score for reporting only).

---

## Conflicts Summary Table

| Item | Conflict | Safest option |
|------|----------|----------------|
| EXPIRING_SOON scoring | Current fixed 70 vs task decay 70/85/100 | Use decay only in new portfolio summary scoring. |
| Risk bands | 80/60/40 vs 85/70/55 | Use 85/70/55 in new API and UI. |
| Weights | Equal vs task baseline (Gas 18, etc.) | New weight map only for new scoring path. |
| Risk Index + guardrails | Absent vs required | Implement in new path only. |
| API shape | Missing kpis, updated_at, name, expiring_30/missing | Extend response; no breaking change to existing fields. |
| Property detail | No compliance-detail endpoint, no tabs | Add endpoint; add tabs without removing existing behaviour. |

This gives a single, consistent “mathematically robust” model for the Audit Intelligence UI and new APIs while leaving existing compliance score and provisioning behaviour unchanged and avoiding duplication or conflict with existing scoring logic.

---

## Resolved: Single source of truth for risk bands (no conflict)

Risk bands and messaging are centralized so they never conflict:

- **`backend/utils/risk_bands.py`** defines the only thresholds: `RISK_BAND_LOW_MIN = 80`, `MODERATE_MIN = 60`, `HIGH_MIN = 40`; and helpers `score_to_risk_level(score)`, `score_to_grade_color_message(score)`.
- **Consumers:** `routes/portfolio.py` uses `score_to_risk_level` for portfolio and property risk_level. `services/compliance_score.py` and `services/compliance_scoring_service.py` use `score_to_grade_color_message` for grade/color/message.
- **Frontend:** Dashboard "Compliance Framework" and Compliance Score page property colours use the same thresholds (80/60/40); copy notes "aligned with server".
