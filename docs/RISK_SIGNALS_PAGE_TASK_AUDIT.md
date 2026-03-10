# Operations → Risk Signals Page: Task vs Codebase Audit

**Task:** Implement the top-level Operations → Risk Signals page as an enterprise-grade portfolio-wide predictive maintenance and risk intelligence workspace.  
**Constraints:** Additive only; preserve existing routes and schemas; heuristic/explainable rules only; PREDICTIVE_MAINTENANCE gate.

This document records what is **implemented**, what is **missing**, any **conflicts**, and the **safest implementation approach**. No implementation is done until the plan is approved.

---

## 1. Current State Summary

| Area | Status | Notes |
|------|--------|--------|
| **Route** | Exists | `/operations/risk-signals` → `ClientRiskSignalsPage` (App.js) |
| **Backend API** | Exists | `GET /api/client/maintenance/risk-signals` (portfolio), `GET /api/client/maintenance/properties/{id}/risk-signals`, `POST .../recalculate/{property_id}`, `PATCH .../risk-signals/{signal_id}` |
| **Backend service** | Exists | `risk_signal_service.py`: stored `risk_signals` collection, heuristic rules (boiler, damp, electrical, recurring, SLA breach, compliance churn, maintenance frequency), status workflow |
| **Feature flag** | Exists | PREDICTIVE_MAINTENANCE; EntitlementProtectedRoute; locked state with upgrade message |
| **Portfolio page** | Partial | Single card with list of signals; summary total/high/medium in header; no KPI row, no filters, no table, no high-priority panel, no detail drawer; Acknowledge/Resolve not on page |
| **Property tab** | Implemented | Risk Signals tab: summary cards, Recalculate, list with Acknowledge/Resolve, Create work order |

---

## 2. Implemented vs Missing (by task section)

### 2.1 Page purpose (§1)

- **Implemented:** Backend and data answer “which properties have elevated risk,” “why flagged” (reasons), “what to do next” (recommended_action). Risk types and levels exist.
- **Missing on portfolio page:** Clear “which assets” (asset shown in list but not prominent); “rising/stable/improving” not emphasised in UI (trend is in data, default “stable”).

### 2.2 Page structure (§2)

- **A) Summary KPI row:** Partial. Summary (total, high, medium, low) exists in API and is shown inline in the card header on the portfolio page. **Missing:** Dedicated KPI row with separate cards; **Low** count in summary (API has it, UI doesn’t show it); **Properties Affected**; **Preventive Actions Recommended**; click-to-apply filter on cards.
- **B) Filter + search bar:** **Missing.** Backend supports only `property_id`, `status`, `limit`. No riskLevel, riskType, assetType, trend, q, from, to.
- **C) Active risk signals table/cards:** **Partial.** Current UI is a list of cards (property, risk_type, recommended_action, reasons slice, risk_level, status). **Missing:** Table layout with columns: Risk Type, Property, Asset, Risk Level, Trend, Why Flagged, Recommended Action, Last Updated, Actions (View, Create Inspection, Create Work Order, Acknowledge, Mark Resolved). “Create work order” and “View property” exist; Create Inspection and row-level Acknowledge/Resolve do not.
- **D) High priority / escalation panel:** **Missing.** No “High Priority Risks” panel; API does not return `highPriority` array.
- **E) Risk detail drawer:** **Missing.** No side panel/drawer; no GET-by-signal_id (drawer can use list item data). No “related records” (linked issues, work orders, evidence) in API.
- **F) Trend / snapshot strip:** **Missing.** Trend is stored (default “stable”); no snapshot history or trend strip in API/UI.

### 2.3 Summary KPI row (§3)

- **Implemented:** Backend summary: total, high, medium, low, lastRecalculatedAt. Frontend shows total/high/medium (and lastRecalculatedAt) in the card header.
- **Missing:** Separate clickable KPI cards; Low in UI; **propertiesAffected**; **preventiveActions** (or equivalent); click-to-filter behaviour.

### 2.4 Filter + search bar (§4)

- **Implemented:** Backend: `property_id`, `status`, `limit` only.
- **Missing:** Filters for risk level, risk type, property (dropdown), asset type, trend, status (already in backend), date range. Search (q) for property name/address, asset name, risk type keywords.

### 2.5 Active risk signals table (§5)

- **Implemented:** List shows risk type, property, recommended action, reasons (first 2), risk level badge, status; actions: Create work order, View property.
- **Missing:** Table format; **Asset** column (data exists as `asset_id`); **Trend** column; **Why Flagged** as single concise line (reasons exist); **Last Updated** column (`updated_at` in DB); **View** (open drawer); **Create Inspection**; **Acknowledge** and **Mark Resolved** in table row (they exist on Property tab only).

### 2.6 High priority / escalation panel (§6)

- **Missing:** Entire panel. Backend does not return `highPriority`; no “High Priority Risks” section with short reason and primary action per item.

### 2.7 Risk detail drawer (§7)

- **Missing:** Drawer/panel. **Implemented elsewhere:** Full signal doc (reasons, recommended_action, risk_level, trend, status, generated_at, updated_at) is in list response; property tab shows same data in list form. **Missing:** Right-side drawer; related records (linked issues, work orders, evidence); “Create inspection” in actions; status controls (Acknowledge/Resolve) in drawer.

### 2.8 Heuristic sources (§8)

- **Implemented:** Rules use property age, asset age, maintenance issue frequency, work orders, recurring repairs, SLA breach, compliance overdue, maintenance frequency. Explainable reasons per signal. No black-box AI.

### 2.9 Action handoff (§9)

- **Implemented:** Create work order (navigates with property_id + description), View property. PATCH status (acknowledge/resolve) exists in API and on Property tab.
- **Missing:** “Create Inspection” (no separate flow; could map to work order or placeholder); linking a created work order back to the risk signal (no `risk_signal_id` or similar on work order); portfolio page does not expose Acknowledge/Resolve.

### 2.10 Backend expectations (§10)

- **Endpoint:** Task suggests `GET /api/risk-signals`. **Actual:** `GET /api/client/maintenance/risk-signals`. Same idea, different path; consistent with other client maintenance APIs.
- **Query params:** **Implemented:** property_id, status, limit. **Missing:** riskLevel, riskType, assetType, trend, q, from, to.
- **Response:** **Implemented:** summary (total, high, medium, low, lastRecalculatedAt), signals[]. **Missing:** summary.propertiesAffected, summary.preventiveActions (or equivalent); **highPriority[]** array.

### 2.11 Status workflow (§11)

- **Implemented:** active / acknowledged / resolved; PATCH `.../risk-signals/{signal_id}` with body `{ status }`; audit on acknowledge/resolve. Property tab exposes Acknowledge and Resolve.
- **Missing:** Portfolio page does not show Acknowledge / Mark Resolved (only Property tab does).

### 2.12 Linkage to other modules (§12)

- **Implemented:** View property (navigate to property); Create work order (prefills description); Property Risk Signals tab and Assets tab; audit events for signal lifecycle.
- **Missing:** Explicit “linked issues / work orders / evidence” in API or drawer; “View asset” when asset_id present (could link to property Assets tab with focus).

### 2.13 Feature flag / plan behaviour (§13)

- **Implemented:** PREDICTIVE_MAINTENANCE gates backend (403) and frontend (EntitlementProtectedRoute); locked state with upgrade CTA; no risk data when disabled.

### 2.14 Empty states (§14)

- **Implemented:** Message when no signals: “No risk signals yet. Signals are generated from property data…”.
- **Missing:** Buttons “View Properties” and “View Assets” on empty state; “No risk signals match your current filters” when filters return empty (once filters exist).

### 2.15 Design rules (§15)

- **Implemented:** Enterprise tone; no AI-marketing language; reasons visible in list.
- **Missing:** Clear trend indicators in UI; table and structure described in task.

### 2.16 Acceptance criteria (§16)

| Criterion | Status |
|-----------|--------|
| Risk Signals page loads portfolio-wide risk signals | Yes |
| Summary cards and filters work | Partial (summary inline; no filter bar) |
| High priority panel exists | No |
| Detail drawer shows reasoning and actions | No |
| Actions link to relevant workflows | Partial (work order, property; no inspection; no Acknowledge/Resolve on page) |
| Locked state when predictive maintenance disabled | Yes |
| No existing routes or property pages broken | Yes |

---

## 3. Conflicts and Recommendations

### 3.1 API path: `/api/risk-signals` vs `/api/client/maintenance/risk-signals`

- **Task:** “GET /api/risk-signals”.
- **Codebase:** Client-scoped APIs live under `/api/client`; risk signals sit under `client_maintenance` as `/api/client/maintenance/risk-signals`.
- **Recommendation:** Keep **GET /api/client/maintenance/risk-signals**. Do not add a separate `/api/risk-signals` without client context. Document the task path as conceptual; implementation stays consistent with existing client routes.

### 3.2 Summary shape: propertiesAffected, preventiveActions

- **Task:** summary.propertiesAffected, summary.preventiveActions (e.g. “Preventive Actions: 4”).
- **Current:** summary has total, high, medium, low, lastRecalculatedAt.
- **Recommendation:** Add **propertiesAffected** (distinct property_id count in filtered set) and **preventiveActions** (e.g. count of unique recommended_action or count of active signals—clarify with product). Additive change in `get_risk_signals_for_client` and in the API response.

### 3.3 highPriority array

- **Task:** Response includes `highPriority: [...]` for “top high-risk signals.”
- **Current:** No such field.
- **Recommendation:** Add **highPriority** to the portfolio response: e.g. top N (e.g. 10) signals where `risk_level` is high or critical, same filters as main list, with fields needed for the panel (property, asset, risk level, short reason, primary action). Derive from same `signals` query or a second query; avoid duplication of logic.

### 3.4 Create Inspection

- **Task:** “Create Inspection” as an action.
- **Current:** No separate “inspection” entity; work orders are the main action.
- **Recommendation:** Treat as **Create Work Order** with a description like “Inspection: [risk type]” (or add a separate inspection type later). In UI, either label “Create work order” as “Create inspection” for asset/boiler/electrical risks or add a “Create inspection” button that opens the same work-order flow with pre-filled inspection wording. No new backend entity in this task unless product specifies one.

### 3.5 Linking work order to risk signal

- **Task:** “If work order is created: link work order back to risk signal.”
- **Current:** Work orders do not store `risk_signal_id`; no reverse link.
- **Recommendation:** Optional enhancement: add optional `risk_signal_id` (or `linked_risk_signal_id`) to work order creation when started from a risk signal; then timeline/property can show the link. Additive and backward compatible; can be phase 2 if scope is tight.

---

## 4. Recommended Implementation Plan (additive only)

1. **Backend – extend list API**
   - In `risk_signal_service.get_risk_signals_for_client`, support optional filters: risk_level, risk_type, asset_type (e.g. from asset_id lookup or metadata), trend, q (text search on property label, asset name, risk_type), from/to (date on generated_at or updated_at).
   - Add to summary: **propertiesAffected** (distinct property_id count), **preventiveActions** (e.g. count of active signals with a recommended_action, or distinct action count—define with product).
   - Add **highPriority**: e.g. first 10–15 signals with risk_level in (high, critical), same filters, optionally sorted by updated_at/generated_at.
   - Expose **low** in summary (already computed; ensure returned).
   - In `client_maintenance.py`, add query params for riskLevel, riskType, assetType, trend, q, from, to; pass through to service.

2. **Frontend – ClientRiskSignalsPage**
   - **Summary KPI row:** Separate cards for Total, High, Medium, Low, Properties Affected, Preventive Actions; click a card to set the corresponding filter (e.g. click High → riskLevel=high).
   - **Filter bar:** Risk level, risk type, property (dropdown from properties list), asset type (dropdown or free text), trend, status; search q; date range from/to. Call existing API with new params once backend supports them.
   - **Table:** Replace card list with a table: Risk Type, Property, Asset, Risk Level, Trend, Why Flagged (e.g. first reason or joined string), Recommended Action, Last Updated, Actions (View, Create work order, Acknowledge, Mark Resolved). Reuse existing API; add “View” to open detail drawer; add Acknowledge/Resolve as on Property tab (reuse `updateRiskSignalStatus`).
   - **High priority panel:** “High Priority Risks” section above or beside the table; render from `data.highPriority` (or from `data.signals` filtered by high/critical until backend returns highPriority). Show property, asset, risk level, short reason, primary action (e.g. Create work order / View property).
   - **Detail drawer:** On “View” (or row click), open a right-side Sheet/Drawer with: core info (risk type, property, asset, level, trend, generated/updated); detailed reasoning (reasons list); related records (placeholder or “View property” / “View asset” links; linked issues/WOs only if backend or existing APIs expose them); recommended actions (Create work order, Create inspection if same as WO, View property, View asset); Acknowledge / Mark Resolved.
   - **Empty states:** When no signals: add buttons “View Properties”, “View Assets”. When filters return empty: “No risk signals match your current filters.”
   - **Optional trend strip:** If snapshot/trend data is added later, show a small strip; otherwise omit.

3. **Backend – GET by signal_id (optional)**
   - If the drawer should always load fresh data, add `GET /api/client/maintenance/risk-signals/{signal_id}` returning one signal; ensure client_id/property_id scoped. Not strictly required if list payload is sufficient for the drawer.

4. **Placeholders / fallbacks**
   - Asset label: if no asset_id, show “—”; if asset_id present, resolve from property assets (e.g. in frontend from property list or a small lookup) or show asset_id until an asset-label endpoint exists.
   - “Related records”: in drawer, show “View property” and “View asset” (and “View work orders” for property) as links; only show “Linked issues/WOs” if backend adds linkage or if existing property/issue APIs can be queried by property_id.

5. **No breaking changes**
   - Keep existing routes and response shape; extend response with optional summary fields and highPriority. Add optional query params; default behaviour unchanged when params omitted.

---

## 5. Files to Touch (summary)

| Location | Action |
|----------|--------|
| `backend/services/risk_signal_service.py` | Extend `get_risk_signals_for_client` with filters (risk_level, risk_type, asset_type, trend, q, from, to); add propertiesAffected, preventiveActions, highPriority to return. |
| `backend/routes/client_maintenance.py` | Add query params to GET /maintenance/risk-signals; optionally add GET .../risk-signals/{signal_id} for drawer. |
| `frontend/src/pages/ClientRiskSignalsPage.js` | KPI row, filter bar, table, high-priority panel, detail drawer, empty-state buttons, Acknowledge/Resolve in table and drawer. |
| `frontend/src/api/client.js` | Add any new params to getRiskSignals (e.g. riskLevel, riskType, propertyId, assetType, trend, status, q, from, to); optional getRiskSignal(signalId) if endpoint added. |

---

## 6. Notes on Linkage

- **Property:** Each signal has `property_id`; “View property” navigates to `/properties/{property_id}` (or equivalent). Already present.
- **Assets:** Signals can have `asset_id`. “View asset” can link to `/properties/{property_id}` with Assets tab active and optional focus on asset (if supported by routing).
- **Maintenance / work orders:** Create work order pre-fills description from recommended_action; work orders are created for the same property. No stored link from WO to signal today; optional later: pass risk_signal_id when creating WO from signal.
- **Timeline / audit:** Risk signal create/acknowledge/resolve already emit audit events; no change needed for this task unless timeline is extended to show risk_signal events on the property timeline.

---

*Audit complete. Implement only after approving this plan; additive changes only.*
