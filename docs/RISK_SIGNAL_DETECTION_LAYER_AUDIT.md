# Risk Signal Detection Layer – Task vs Codebase Audit

**Task:** Implement a structured Risk Intelligence Engine that watches five signal families (property age, repeat failures, missed SLAs, compliance churn, maintenance frequency), produces explainable risk signals in three categories (asset / operational / compliance), and powers Property Risk Signals tab, Portfolio Risk Signals page, dashboard summaries, and preventive action recommendations.

**Audit purpose:** Identify what is implemented, what is missing, where conflicts or duplication could occur, and recommend the safest, most professional implementation path. **Do not implement blindly.**

---

## 1. CURRENT STATE: “RISK” / PREDICTIVE TODAY

### 1.1 What Exists

| Component | Location | Behaviour |
|-----------|----------|-----------|
| **Feature flag** | `ops_compliance_feature_flags.py` | `PREDICTIVE_MAINTENANCE` (default False on base plan; True on higher plans). |
| **Client API** | `GET /api/client/maintenance/predictive-insights` | Returns `{ client_id, properties: [ { property_id, nickname, address_line_1, postcode, building_age_years, insights[], assets_count, events_count } ] }`. Gated by PREDICTIVE_MAINTENANCE. |
| **Insights logic** | `predictive_service.py` | **Rule-based only.** Builds insights on demand (or from cache): (1) building_age > 50 → electrical survey suggestion; (2) boiler/heating assets: last service > 12 months or install age > 15 years → service/replacement; (3) ≥3 maintenance_events in 90 days → “review pattern”. No AI/ML. |
| **Alternative insights** | `predictive_maintenance_service.py` | `get_insights_for_property(property_id, client_id)` used by **property_assets_service** (asset list/detail). Similar rules: boiler/heating service overdue, boiler age, electrical age; building age > 40 if no assets. Returns list of `{ asset_id, asset_type, title, message, risk, suggested_action }`. |
| **Cache** | `predictive_insights_cache` (MongoDB) | Keyed by `client_id`; stores full `get_insights_for_client` result; TTL 24h in `predictive_service`. |
| **Scheduled job** | `job_runner.run_predictive_insights_job` | Precomputes insights for clients with PREDICTIVE_MAINTENANCE; writes cache. |
| **UI** | `ClientRiskSignalsPage.js` | Portfolio “Risk Signals” page: calls `getPredictiveInsights()`, flattens `properties[].insights`, shows recommendation / detail / risk badge; “Create work order” and “View property”. |
| **Property detail** | `PropertyDetailPage.js` | “Risk Signals” tab: same API, filters to current property; shows `predictiveInsights.insights` (recommendation, detail, risk); “Create work order”. |
| **Dashboard** | `ClientDashboard.js` | “Predicted risks” count = sum of insights across properties; links to `/operations/risk-signals`. |

**Data sources currently used for “risk”:**

- `properties.building_age_years` (not `buildYear`; task uses buildYear – **terminology mismatch**).
- `property_assets` (asset_type, install_date, last_service_date).
- `maintenance_events` (property_id, event_type, occurred_at) – generic events, not issues/work orders by category.

**Data sources NOT used today for risk:**

- `work_orders` (category, asset_id, completed_at, sla_*).
- `maintenance_issues` (category, property_id, created_at).
- Compliance obligations / overdue counts / renewal or evidence status.
- Any **stored** risk signal document; everything is computed on read (or from cache).

---

## 2. TASK REQUIREMENTS VS CURRENT STATE

### 2.1 Risk Signal Categories (Task §1)

Task requires three top-level categories with named risk types:

- **A) Asset Prediction:** Boiler Failure Risk, Damp/Moisture Risk, Electrical Risk, Recurring Repairs Risk.
- **B) Operational:** SLA Breach Risk, Contractor Delay Risk (optional), Work Order Backlog Risk (optional).
- **C) Compliance:** Compliance Churn Risk, Repeated Renewal Delay Risk, Repeated Missing Evidence Risk.

**Current:** No categories. Insights are a flat list with `type` (e.g. building_age, asset_service_due, asset_age, recent_activity) and `risk` (low/medium/high/urgent). No “asset | operational | compliance” split, no named risk types (e.g. “Boiler Failure Risk”), no damp/electrical/recurring/SLA/compliance churn as distinct types.

**Gap:** Full category model and risk-type taxonomy are missing. Existing “insight” types can be mapped into asset prediction only (building age, boiler service/age, electrical age, recent activity); operational and compliance families are absent.

---

### 2.2 Input Signals to Watch (Task §2)

| Input | Task | Current |
|-------|------|---------|
| **Property age** | buildYear / property age estimate; amplifier only | `building_age_years` used as direct trigger (e.g. > 50 → electrical). Not used only as amplifier. |
| **Repeat failures** | 2+ same category/asset in 12 months (heating, electrical, damp) | Not implemented. No aggregation of work_orders/maintenance_issues by category/asset over rolling window. |
| **Missed SLAs** | Work orders breaching SLA; 2+ in 30 days; same contractor breach patterns | `work_orders` has `sla_complete_by`, `completed_at`, `sla_breached_at`. Job `work_order_sla_breach_job` sets `sla_breached_at`. No risk **signal** from breach count or contractor pattern. |
| **Compliance churn** | Repeated overdue, late renewals, missing evidence | Compliance data exists (requirements, status, overdue) but not fed into any “risk signal” or churn metric. |
| **Maintenance frequency** | 4+ issues in 6 months; increasing repair volume | `maintenance_events` count used loosely (≥3 in 90 days → “review pattern”). No 4-in-6-months threshold; no link to work_orders/issues by property. |

---

### 2.3 Data Models (Task §3)

Task specifies:

- **riskSignals** collection: orgId, propertyId, assetId (nullable), signalCategory, riskType, riskLevel, trend, score, reasons[], recommendedAction, status (active|acknowledged|resolved), source ("heuristic"), generatedAt, updatedAt, metadata.
- **predictionSnapshots** (optional): for trend detection and historical graphs.

**Current:** No `risk_signals` collection. No `prediction_snapshots`. Insights are either computed on the fly or stored as an opaque blob in `predictive_insights_cache` (client_id → full response). So: **no stored, queryable, status-aware risk signals**.

**Conflict / choice:** Task uses `orgId`; codebase uses `client_id` everywhere. **Recommendation:** Use `client_id` in new collections for consistency; document “orgId” in API responses as alias if needed for UI.

---

### 2.4 Detection Engine (Task §4)

Task: `generateRiskSignalsForProperty(propertyId)` and `generateRiskSignalsForOrg(orgId)` that inspect property, propertyAssets, maintenanceIssues, workOrders, SLA outcomes, compliance obligations/overdue, evidence status.

**Current:** No such service. `predictive_service.get_insights_for_client` and `predictive_maintenance_service.get_insights_for_property` are the only “engine” and they do not write to risk_signals, do not read work_orders/issues by category, do not read compliance or evidence.

---

### 2.5 Initial Rule Set (Task §5)

| Rule | Task trigger | Current |
|------|----------------|--------|
| **Boiler Failure Risk** | BOILER + (age > 10 or installedYear > 10) + ≥2 heating issues in 12 months | Partial: boiler/heating asset age and service overdue; **no** “heating issues linked to boiler” count from work_orders/issues. |
| **Damp / Moisture Risk** | ≥2 damp issues in 12 months + property age threshold | Not implemented. No damp category aggregation. |
| **Electrical Risk** | ≥2 electrical issues in 12 months OR EICR overdue | Partial: building age > 50 or electrical asset age; **no** issue count; **no** EICR obligation status. |
| **Recurring Repairs Risk** | Same asset/category 3+ issues/WOs in 12 months | Not implemented. |
| **SLA Breach Risk** | ≥2 breached WOs in 30/60 days; same contractor/property | Data exists (sla_breached_at); no rule producing a signal. |
| **Compliance Churn Risk** | Same obligation type repeatedly overdue/late or repeated missing evidence | Not implemented. |
| **Maintenance Frequency Risk** | ≥4 issues in 6 months at property | Partially: 3 events in 90 days in predictive_service; not 4 in 6 months; not work_orders/issues. |

---

### 2.6 Trend (Task §6)

Task: trend (rising|stable|improving) from recent snapshots; if no history, default stable.

**Current:** No trend. Insights have no trend field; no snapshots.

---

### 2.7 Trigger Points (Task §7)

Task: Run signal generation on: property create/update, asset create/update, issue create, work order complete/update, SLA breach state change, evidence confirmed, compliance status change, nightly recalculation; plus manual `POST /api/risk-signals/recalculate/:propertyId`.

**Current:** No hooks from those events into any “risk signal generation.” Only `predictive_insights_job` runs on a schedule and refreshes the **cache** (same structure as today), not a risk_signals table. No recalculate endpoint.

---

### 2.8 Recommended Action Mapping (Task §8)

Task: Each risk type has a recommended action (e.g. Boiler → inspection/work order; Damp → investigate/specialist; Electrical → EICR/inspection; etc.).

**Current:** Free-text `suggested_action` / `recommendation` per insight; not a fixed mapping per risk type. Can be aligned with task by defining a mapping table and using it when generating signals.

---

### 2.9 API Endpoints (Task §9)

Task:

- `GET /api/properties/:propertyId/risk-signals` → summary (total, high, medium, low, lastRecalculatedAt) + signals[].
- `GET /api/risk-signals` (portfolio).
- `POST /api/risk-signals/recalculate/:propertyId`.

**Current:**

- No `GET /api/properties/:propertyId/risk-signals`. Property-level “risk” is derived by filtering client `getPredictiveInsights()` to one property.
- No `GET /api/risk-signals`. Portfolio risk is the full predictive-insights response (properties[].insights).
- No recalculate endpoint.

**Conflict:** Task suggests `/api/properties/` and `/api/risk-signals`. Codebase uses `/api/client/` for client-scoped and `/api/portfolio/` for some property endpoints. **Recommendation:** Add under client/portfolio as appropriate, e.g. `GET /api/client/maintenance/properties/:propertyId/risk-signals` and `GET /api/client/maintenance/risk-signals` (or `/api/portfolio/properties/:propertyId/risk-signals` if that’s the pattern for property-scoped reads). Keep existing `GET /api/client/maintenance/predictive-insights` for backward compatibility during migration.

---

### 2.10 UI Integration (Task §10)

Task: Engine must support Property Risk Signals tab, Portfolio Risk Signals page, Dashboard cards/alerts.

**Current:** Property tab and Portfolio page and dashboard already consume “predictive insights.” They expect a list of items with recommendation, detail, risk. To satisfy task, either (1) new endpoints return the same shape plus summary + signalCategory/riskType/trend/status/reasons, or (2) new endpoints return the new shape and frontend is updated to use it (with summary, filters, status). **Recommendation:** New API returns task structure; frontend can be extended to show summary, category, trend, status, and reasons while keeping “Create work order” and “View property” actions.

---

### 2.11 Feature Flag (Task §11)

Task: PREDICTIVE_MAINTENANCE; backend may generate/store signals even when off; frontend exposes only when entitlement/flag allows; if locked, show upgrade state.

**Current:** PREDICTIVE_MAINTENANCE already used; client endpoints 403 when off; frontend gates Risk Signals tab and page. **Recommendation:** Keep behaviour: backend can write risk_signals for all clients if desired (e.g. for future use or admin); client/portfolio **read** APIs for risk-signals remain gated by PREDICTIVE_MAINTENANCE so UI behaviour is unchanged.

---

### 2.12 Audit + Timeline (Task §12)

Task: On signal create/update/acknowledge/resolve: log audit event and add timeline event. Events: RISK_SIGNAL_CREATED, RISK_SIGNAL_UPDATED, RISK_SIGNAL_RESOLVED, RISK_SIGNAL_ACKNOWLEDGED.

**Current:** No risk-signal audit or timeline. Property timeline merges score_ledger, score_change_log, work_orders; no risk_signal event type. **Gap:** Add audit event types and, if property timeline is the single place for property-level history, add a timeline source for risk-signal events (or document that they appear only in audit log until timeline supports them).

---

### 2.13 Acceptance Criteria (Task §13)

| Criterion | Status |
|-----------|--------|
| Engine watches all five signal families | **No.** Only property age + asset age/service + loose maintenance_events count. No repeat failures by category/asset, no SLA breach signals, no compliance churn, no maintenance frequency by issues/WOs. |
| Signals separated into asset / operational / compliance | **No.** Flat list; no categories. |
| Rule-based, explainable with visible reasons | **Partial.** Current rules are explainable but not exposed as structured “reasons” array per signal. |
| Signals stored, not only in UI | **No.** Not stored; computed or cached as blob. |
| Recalculation on defined trigger points | **No.** Only scheduled job for cache; no event-driven or recalculate endpoint. |
| API supports property-level and portfolio-level | **Partial.** Portfolio via predictive-insights; no dedicated property risk-signals or portfolio risk-signals endpoint with task shape. |
| No existing workflows broken | **N/A.** New layer is additive; care needed to avoid duplicating or replacing current “insights” until migration is decided. |

---

## 3. CONFLICTS AND RECOMMENDATIONS

### 3.1 Terminology

- **orgId vs client_id:** Use `client_id` in DB and backend; expose as `orgId` in API if required by contract.
- **buildYear:** Codebase uses `building_age_years` (and optionally install dates on assets). Map task “buildYear / property age estimate” to `building_age_years` and asset install dates; document in API.

### 3.2 Two “Insight” Paths

- **predictive_service** (used by client predictive-insights API and job) and **predictive_maintenance_service** (used by property_assets_service for per-asset risk) overlap in concept but differ in shape and data. Introducing a single **risk signal engine** that writes to **risk_signals** (and optionally prediction_snapshots) gives one source of truth. Existing “predictive insights” API can either (a) be deprecated in favour of GET risk-signals endpoints, or (b) be fed from risk_signals (e.g. aggregate stored signals into the current response shape) during transition. **Recommendation:** Implement the new engine and risk_signals; keep existing predictive-insights API returning current shape until frontend is updated, then either switch API to read from risk_signals or remove it.

### 3.3 Data Sources to Add

- **work_orders:** Filter by property_id, client_id; use category, asset_id, created_at, completed_at, sla_breached_at for repeat-failure counts, SLA breach counts, and maintenance frequency.
- **maintenance_issues:** Same; category, property_id, created_at (and link to work_orders if needed).
- **Compliance:** Use existing property requirements/obligations and status (overdue, expiring, missing evidence) to drive compliance churn and repeated renewal/missing evidence signals. Do not duplicate compliance logic; call into existing compliance/requirements APIs or DB views.
- **property_assets:** Already used; add `installed_year` / install_date for boiler age; use asset_id to count “same asset” recurring issues.

### 3.4 Safest Implementation Order

1. **Add collections and schema:** `risk_signals` (and optionally `prediction_snapshots`) with task fields; use `client_id` (not orgId) in DB.
2. **Add risk signal service:** e.g. `risk_signal_service.py` with `generate_risk_signals_for_property(property_id, client_id)` and `generate_risk_signals_for_org(client_id)`. Implement rules in clear, rule-only functions (no black-box AI). Prefer one module per family (asset / operational / compliance) or one module with three internal sections.
3. **Implement initial rules** in order: (1) Boiler Failure Risk (using assets + work_orders/issues by category/asset), (2) Damp/Moisture, (3) Electrical (incl. EICR overdue from compliance), (4) Recurring Repairs, (5) SLA Breach, (6) Compliance Churn, (7) Maintenance Frequency. Use property age as amplifier where specified; do not emit “property age only” as a major signal.
4. **Trigger points:** (a) Nightly job (extend or replace predictive_insights_job to run new engine and write risk_signals). (b) Optional: hooks from property/asset/issue/work order/compliance/evidence handlers to call generator for affected property/client. (c) `POST /api/.../risk-signals/recalculate/:propertyId` (and optionally for org) for manual run.
5. **APIs:** Add GET property risk-signals and GET portfolio risk-signals with task response shape (summary + signals). Add POST recalculate. Keep existing predictive-insights behind feature flag until migration is done.
6. **Trend:** If prediction_snapshots are written (e.g. on each run), derive trend from prior snapshot; else default “stable.”
7. **Audit/timeline:** Emit audit events on signal create/update/acknowledge/resolve; add timeline event type for property timeline if that’s in scope.
8. **Frontend:** Update Property Risk Signals tab and Portfolio Risk Signals page to call new endpoints and display summary, category, risk type, trend, reasons, status, recommended action. Keep feature flag PREDICTIVE_MAINTENANCE for visibility.

---

## 4. FILES / AREAS TO TOUCH (SUMMARY)

| Area | Action |
|------|--------|
| **New** | `backend/services/risk_signal_service.py` (or split: `risk_signal_engine.py`, `risk_signal_rules_asset.py`, `_operational.py`, `_compliance.py`) – generation and rule logic. |
| **New** | `backend/routes/risk_signals.py` or extend `client_maintenance.py` – GET property risk-signals, GET portfolio risk-signals, POST recalculate. |
| **New** | Collections `risk_signals`, optionally `prediction_snapshots`; indexes (client_id, property_id, status, generatedAt). |
| **Existing** | `predictive_service.py` / `predictive_maintenance_service.py` – keep as-is until new engine is live; then either deprecate or refactor to read from risk_signals. |
| **Existing** | `maintenance_service.py`, `property_assets_service.py`, compliance/requirements services – no change to core logic; risk engine **reads** from them. |
| **Existing** | `job_runner.py` – add or replace job to run `generate_risk_signals_for_org` per client (and write risk_signals); keep or remove predictive_insights_job. |
| **Existing** | Property timeline / audit – add event types and, if required, timeline entries for risk signal lifecycle. |
| **Frontend** | Property detail Risk Signals tab, ClientRiskSignalsPage, dashboard – switch to new API response shape when ready; retain feature flag. |

---

## 5. SAMPLE GENERATED RISK SIGNALS (TARGET SHAPE)

```json
{
  "summary": {
    "total": 3,
    "high": 1,
    "medium": 2,
    "low": 0,
    "lastRecalculatedAt": "2025-02-20T12:00:00Z"
  },
  "signals": [
    {
      "id": "rs_abc123",
      "signalCategory": "asset",
      "riskType": "Boiler Failure Risk",
      "riskLevel": "high",
      "trend": "stable",
      "reasons": [
        "Boiler age estimate exceeds 10 years",
        "3 heating-related issues recorded in the last 12 months"
      ],
      "recommendedAction": "Schedule boiler inspection or replacement review",
      "status": "active",
      "updatedAt": "2025-02-20T12:00:00Z",
      "assetId": "ast_boiler_01"
    },
    {
      "id": "rs_def456",
      "signalCategory": "operational",
      "riskType": "SLA Breach Risk",
      "riskLevel": "medium",
      "reasons": ["2 work orders breached SLA in the last 30 days"],
      "recommendedAction": "Review contractor performance and prioritise unresolved jobs",
      "status": "active"
    }
  ]
}
```

---

## 6. ASSUMPTIONS

- **client_id** is the canonical org identifier in DB; **orgId** in API is an alias if needed.
- **Property age** is taken from `properties.building_age_years` and/or asset install dates; no separate `buildYear` field is added unless product explicitly requires it.
- **Work order category** and **maintenance_issues** category (and link to asset) are the source for “repeat failures” and “maintenance frequency”; maintenance_events remain secondary if at all.
- **Compliance** data is read from existing requirements/obligations and status (overdue, missing evidence, renewal date); no new compliance model.
- **Feature flag** PREDICTIVE_MAINTENANCE continues to gate **visibility** of risk signals in client UI; backend may still write signals for all clients.
- **No AI/ML:** All rules are deterministic, explainable, and code-only.

---

**End of audit.** Implement the risk signal layer additively; preserve existing models and routes; extend with risk_signals and new endpoints; then migrate UI and optionally retire or refactor the old “predictive insights” path.
