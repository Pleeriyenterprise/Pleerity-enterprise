# Explanation Engine

The **Explanation Engine** is the explainability layer for Pleerity. It provides contextual explanations for risk signals, compliance alerts, contractor scores, and related insights so users understand why an alert exists and what action is recommended.

---

## 1. Overview

- **Service:** `backend/services/explanation_engine.py`
- **Output shape:** Every explanation returns:
  - `explanation_text` — Short summary plus context (for display or tooltips).
  - `why_it_matters` — Contextual paragraph (legal, risk, or operational context).
  - `recommended_action_text` — Clear suggested next step (e.g. "Schedule a Gas Safe inspection", "Consider contractors with scores above 85% for urgent work").

Explanations are **generated on demand** (not stored in the database) so copy and rules can be updated in one place.

---

## 2. How Explanations Are Generated

### Risk signals (`explain_risk_signal(signal)`)

- **Input:** A risk signal document (e.g. from `get_risk_signal_by_id`) with `risk_type`, `reasons`, `recommended_action`, optional `metadata`.
- **Logic:** By `risk_type` (e.g. Boiler Failure Risk, Damp / Moisture Risk, Electrical Risk, SLA Breach, Certificate Expiry Soon), the engine:
  - Builds a **why_it_matters** paragraph (e.g. boiler age and failure stats, damp and property age, legal/regulatory context).
  - Appends the first one or two items from `reasons` for context.
  - Uses the signal’s `recommended_action` as **recommended_action_text** when present.
- **Used by:** GET `/api/client/maintenance/risk-signals/{signal_id}/explanation`.

### Compliance alerts (`explain_compliance_alert(requirement, catalog_entry)`)

- **Input:** A requirement row (property + client) and optional catalog entry (title, code).
- **Logic:** By requirement `code` (e.g. `gas_safety`, `eicr`, `epc`, `hmo_license`, `fire_risk_assessment`):
  - Sets **legal context** (e.g. UK annual gas safety, EICR every 5 years).
  - Sets **risk of non-compliance** (fines, liability, enforcement).
  - Combines with status (OVERDUE, EXPIRING_SOON, PENDING/MISSING) to form **why_it_matters**.
  - Sets **recommended_action_text** (e.g. "Schedule a Gas Safe inspection", "Upload the required document").
- **Used by:** GET `/api/client/properties/{property_id}/requirements/explanation?requirement_code=...` (or `requirement_id=...`).

### Contractor score (`explain_contractor_score(contractor)`)

- **Input:** Contractor document with `performance_score`, `reliability_score`, and related metrics.
- **Logic:**
  - If no score: explains that scores come from jobs and suggests assigning work to see a score.
  - Otherwise: explains that the score is based on reliability (completed vs assigned), SLA success, response time, and invoice approval; adds usage guidance by band (e.g. ≥85% for urgent work, 70–85% consider higher for urgent, &lt;50% consider reassigning critical work).
- **Used by:** GET `/api/client/contractors/{contractor_id}/explanation` (client) and GET `/api/admin/ops/contractors/{contractor_id}/explanation` (admin).

### Compliance score / portfolio (`explain_compliance_score(client_id, score_data)`)

- **Input:** Optional `score_data` (score, breakdown/stats).
- **Logic:** If no data, returns a short generic summary of how the score works and how to improve it. If data is provided, builds a short summary and recommended action from it.
- **Note:** For trend explanations (“why did my score change?”), the existing `compliance_trending.get_score_change_explanation` is used (e.g. GET `/api/client/compliance-score/explanation`). The engine’s `explain_compliance_score` is for a static, one-off summary when needed.

---

## 3. Where Explanations Appear in the UI

| Location | Behaviour |
|----------|-----------|
| **Risk signals (client)** | Operations → Risk Signals: in the signal detail drawer, an expandable **“Why this matters”** panel. On expand, the app calls the risk-signal explanation API and shows `why_it_matters` and `recommended_action_text`. |
| **Compliance alerts (property)** | Property detail → Compliance/Evidence: in the “Urgent items” list, each row has a **“Why this matters”** link. On expand, the app calls the requirement explanation API with `requirement_code` and shows `why_it_matters` and `recommended_action_text`. |
| **Contractor score (client)** | Operations → Work orders: in the work order detail drawer, under “Recommended contractors”, each contractor row has **“Why this matters”**. On expand, the app calls the contractor explanation API and shows `why_it_matters` and `recommended_action_text`. |
| **Contractor score (admin)** | Admin → Ops → Contractors: on the **Analytics** tab, each contractor row has **“Why this matters”**; on expand, the app calls the contractor explanation API and shows `why_it_matters` and `recommended_action_text`. Admin → Ops → Maintenance → Work order detail: under “Recommended contractors”, each row has **“Why this matters”** with the same expandable panel. |

All of these use **small expandable panels** so the main view stays uncluttered while still giving clarity and a single recommended action.

---

## 4. Action Guidance

Each explanation includes a **recommended_action_text** suitable for the context:

- **Risk signals:** e.g. “Schedule boiler inspection or replacement review”, “Review contractor performance and prioritise unresolved jobs”.
- **Compliance:** e.g. “Schedule a Gas Safe inspection and upload the new certificate when complete”, “Upload the required document or evidence for this requirement.”
- **Contractors:** e.g. “Consider contractors with scores above 85% for urgent work”, “Consider reassigning critical work to higher-scoring contractors where possible.”

The UI can show this as the primary suggested action (e.g. “Create work order”, “Upload certificate”, “Schedule inspection”, “Review invoice”) next to or inside the expandable block.

---

## 5. How to Add New Explanations

1. **New insight type (e.g. portfolio health, new alert type)**  
   - In `explanation_engine.py`, add a new function, e.g. `explain_xyz(input_doc) -> dict`, returning `explanation_text`, `why_it_matters`, `recommended_action_text`.  
   - Add a route (client or admin) that loads the relevant entity, calls the new function, and returns the dict.  
   - In the UI, add an expandable “Why this matters” (or similar) that calls this endpoint and renders the three fields.

2. **New risk type**  
   - In `explain_risk_signal`, add a branch for the new `risk_type` and set `why_it_matters` (and optionally override `recommended_action_text`).  
   - No new API or UI contract is required if the existing risk-signal explanation endpoint is used.

3. **New requirement type (compliance)**  
   - In `explain_compliance_alert`, add a branch for the new requirement `code` (and catalog entry if needed) to set legal context, risk of non-compliance, and recommended action.  
   - The existing requirement explanation endpoint and property UI “Why this matters” will pick it up.

4. **New copy or rules**  
   - Edit the appropriate function in `explanation_engine.py` and redeploy; no schema or API changes are required.

---

## 6. Files Touched

| File | Role |
|------|------|
| `backend/services/explanation_engine.py` | Defines `explain_risk_signal`, `explain_compliance_alert`, `explain_contractor_score`, `explain_compliance_score`. |
| `backend/routes/client_maintenance.py` | GET `.../risk-signals/{signal_id}/explanation`. |
| `backend/routes/client.py` | GET `.../properties/{property_id}/requirements/explanation`, GET `.../contractors/{contractor_id}/explanation`. |
| `backend/routes/contractors.py` | GET `.../contractors/{contractor_id}/explanation` (admin). |
| `frontend/src/api/client.js` | `getRiskSignalExplanation`, `getRequirementExplanation`, `getContractorExplanation`; admin `getContractorExplanation`. |
| `frontend/src/pages/ClientRiskSignalsPage.js` | Expandable “Why this matters” in risk signal drawer. |
| `frontend/src/pages/PropertyDetailPage.js` | Expandable “Why this matters” per urgent requirement row. |
| `frontend/src/pages/ClientMaintenancePage.js` | Expandable “Why this matters” per recommended contractor in WO drawer. |
| `frontend/src/pages/admin/AdminOpsContractorsPage.js` | Expandable “Why this matters” per contractor in Analytics table. |
| `frontend/src/pages/admin/AdminWorkOrderDetailPage.js` | Expandable “Why this matters” per recommended contractor. |
| `docs/EXPLANATION_LAYER_TASK_ANALYSIS.md` | Task vs codebase analysis and design choices. |
| `docs/EXPLANATION_ENGINE.md` | This document. |

---

## 7. Dependencies and Limits

- **Risk signal:** Requires the risk signal to exist and to belong to the client (existing auth and `get_risk_signal_by_id`).
- **Requirement:** Requires `requirement_code` or `requirement_id`, and that the requirement belongs to the given property and client.
- **Contractor (client):** Requires CONTRACTOR_NETWORK and that the contractor is visible to the client (same visibility as the client’s contractor list).
- **Contractor (admin):** Any contractor the admin can load is allowed.

No caching is implemented; each request runs the engine once. For high traffic, consider a short TTL cache keyed by (entity type, entity id) if needed.
