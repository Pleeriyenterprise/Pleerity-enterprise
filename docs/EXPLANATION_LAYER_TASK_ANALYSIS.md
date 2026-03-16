# Explainability Layer — Task vs Codebase Analysis

**Purpose:** Identify what exists, what is missing, and avoid duplication or conflict before implementing the Explanation Engine.

---

## Current State Summary

| Area | Existing implementation | Gap |
|------|-------------------------|-----|
| **Risk signals** | `risk_signal_service`: `reasons` (list), `recommended_action` (string from RECOMMENDED_ACTIONS). UI: "Why flagged" (reasons), "Recommended action" in drawer and table. No contextual "why it matters" paragraph (e.g. boiler age + failure stats). | Add structured **explanation_text** / **why_it_matters** and optional **recommended_action_text**; add expandable "Why this matters" panel in UI. |
| **Compliance alerts** | Requirements show "Overdue by X days" / "Expires in X days" / "Missing evidence". No legal context or "Why this matters" for certificates. `GET /compliance-score/explanation` exists for **score trend** only (what changed), not per-alert. | Add per-requirement explanation (legal context, risk of non-compliance, recommended action) and expandable panel where alerts are shown. |
| **Contractor score** | `contractor_intelligence_service`: performance_score (0–100), reliability_score, weights (reliability 40%, SLA 25%, response 20%, invoice 15%). UI shows "Reliability: X%" with no explanation. | Add explanation text (how score is calculated, what high/low means, usage guidance) and expandable panel on contractor views. |
| **Compliance / portfolio score** | `compliance_trending.get_score_change_explanation`: trend explanation. ClientDashboard has expandable "Score explanation" and risk band text from `riskLabel.js`. | Explanation engine can **reuse** or wrap trend explanation; ensure portfolio insights use consistent copy. |
| **Unified explanation API** | None. No single service returning `{ explanation_text, why_it_matters, recommended_action_text }` for multiple insight types. | Create `explanation_engine.py` and optional endpoints or response enrichment. |

---

## Conflicts and Safest Choices

| Topic | Choice | Recommendation |
|-------|--------|----------------|
| **Risk signal storage** | Store explanation in DB vs generate on read | **Generate on read** via explanation_engine. Avoids schema migration; single source of truth for copy; can persist later if needed. |
| **Existing "Why flagged" / "Recommended action"** | Replace vs add | **Add** expandable "Why this matters" section that includes contextual paragraph + recommended action. Keep existing "Why flagged" (reasons) and "Recommended action" so behaviour stays backward compatible. |
| **Compliance explanation** | Per-requirement API vs embed in list | **Per-requirement endpoint** (e.g. GET explanation for one requirement) so UI can fetch when user expands. Avoids bloating property requirements payload. |
| **Contractor explanation** | In detail response vs separate endpoint | **Include in contractor detail response** when available (or separate GET .../explanation). List view can show "See why" that opens detail or a small expandable. |
| **Legal/certificate copy** | Generic vs per requirement type | **Per requirement type** (gas_safety, eicr, epc, etc.) using catalog `code` so we can say "UK law requires annual gas safety inspections" for gas_safety. |

---

## Implementation Order

1. **Backend:** Create `explanation_engine.py` with: `explain_risk_signal(signal_doc)`, `explain_compliance_alert(requirement_doc, catalog_entry=None)`, `explain_contractor_score(contractor_doc)`, plus optional `explain_compliance_score(...)` / `explain_portfolio_health(...)` that delegate to existing trend logic where appropriate.
2. **Risk signals:** Add GET `/client/maintenance/risk-signals/{signal_id}/explanation` (or enrich GET signal with `?include=explanation`). Frontend: in risk signal drawer/cards, add expandable "Why this matters" that fetches and shows explanation.
3. **Compliance:** Add GET `/client/properties/{property_id}/requirements/explanation` with `requirement_id` or `requirement_code`. Frontend: on property detail (compliance/urgent items), add expandable "Why this matters" per row that fetches explanation.
4. **Contractor:** Add explanation to contractor detail API or GET `/client/contractors/{id}/explanation`. Frontend: contractor profile/detail and list (expandable or "See why") show explanation.
5. **Portfolio/score:** Use explanation_engine for consistency where we already show score explanation; optional.
6. **Docs:** Create `docs/EXPLANATION_ENGINE.md` (how generated, where they appear, how to add more).

No duplication: we **do not** remove or replace existing `reasons` or `recommended_action`; we **add** structured explanation and UI panels that consume them.
