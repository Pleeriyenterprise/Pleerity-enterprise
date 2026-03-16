# Predictive Risk and Suggested Actions Engine — Task vs Codebase Analysis

**Purpose:** Identify what is already implemented, what is missing, and any conflicts before implementation. Do not implement blindly.

---

## 1. Current State Summary

| Component | Location | Status |
|-----------|----------|--------|
| **Risk signal engine** | `backend/services/risk_signal_service.py` | Implemented: rule-based generation; writes to `risk_signals` collection. |
| **Risk types (current)** | Same file | Boiler Failure, Damp/Moisture, Electrical, Recurring Repairs, **SLA Breach**, Compliance Churn, Maintenance Frequency. |
| **Signal fields** | Stored doc | signal_id, client_id, property_id, asset_id, signal_category, **risk_type**, **risk_level**, trend, reasons[], **recommended_action**, status, source, generated_at, updated_at. |
| **Create issue from signal** | `create_issue_from_risk_signal()` | Implemented; audits ISSUE_CREATED_FROM_RISK_SIGNAL. |
| **Create work order from signal** | `create_work_order_from_risk_signal()` | Implemented; audits WORK_ORDER_CREATED_FROM_RISK_SIGNAL. |
| **Client API** | `GET/PATCH .../risk-signals`, `POST .../create-issue`, `POST .../create-work-order` | Implemented. Gated by PREDICTIVE_MAINTENANCE / MAINTENANCE_WORKFLOWS. |
| **Client Risk Signals page** | `ClientRiskSignalsPage.js` | Portfolio list + drawer with "Create issue from signal", "Create work order from signal", Acknowledge, Resolve. |
| **Property detail** | `PropertyDetailPage.js` | Risk Signals tab: list with Create work order, Acknowledge, Resolve; "Current alerts" and "Recommended next actions" panels. |
| **Admin risk** | `AdminRiskDashboardPage.js` + `GET /admin/ops/risk-signals/summary` | byLevel, byType, topProperties, topClients, recentSignals; filters (client, risk_level, risk_type, status). |
| **Scheduled job** | `risk_signals_job` in job_runner + server | Runs for clients with PREDICTIVE_MAINTENANCE; calls `generate_risk_signals_for_org()`. |
| **Data scanned** | `generate_risk_signals_for_property()` | Property, assets, work_orders (12m), work_orders_breached (30/60d), issues (12m), requirements (overdue/expiring). |

---

## 2. Task Requirements vs Current State

### PART 1 — Risk Signal Engine

**Task:** Extend to detect: `certificate_expiry_soon`, `repeated_issue_pattern`, `sla_breach_risk`, `asset_failure_risk`. Each signal: risk_type, property_id, severity, description, recommended_action.

| Task condition | Current equivalent | Gap |
|----------------|--------------------|-----|
| certificate_expiry_soon | None | **Missing.** Requirements with EXPIRING_SOON exist in compliance; no rule in risk_signal_service that produces a signal for “certificate expiring soon”. |
| repeated_issue_pattern | Recurring Repairs Risk (same asset/category ≥3 in 12m) | Implemented; could alias as repeated_issue_pattern for API if desired. |
| sla_breach_risk | SLA Breach Risk (≥2 breached WOs in 30/60d) | Implemented. |
| asset_failure_risk | Boiler Failure, Damp/Moisture, Electrical (asset/age/service) | Implemented as multiple risk types; task “asset_failure_risk” is a family, not a single type. |

**Fields:** We have risk_type, property_id, **risk_level** (≈ severity), **reasons[]** and **recommended_action**. We do **not** have a single **description** field. Options: (A) Add `description` (e.g. `risk_type + ": " + first reason` or recommended_action), or (B) Keep deriving in UI from risk_type + reasons. **Recommendation:** Add optional `description` when persisting signals for API/UI consistency.

**Conflict / naming:** Task uses snake_case codes (certificate_expiry_soon, etc.); codebase uses human-readable risk_type (e.g. "SLA Breach Risk"). **Recommendation:** Add new risk type constant e.g. `RISK_TYPE_CERTIFICATE_EXPIRY_SOON = "Certificate Expiry Soon"` and keep existing human-readable risk_type values; no need to change existing types to snake_case.

---

### PART 2 — Suggested Actions

**Task:** Add `suggested_action` field. Examples: create_issue, create_work_order, schedule_inspection, send_contractor_reminder, reassign_contractor. UI button to trigger action.

| Task action | Current | Gap |
|-------------|---------|-----|
| create_issue | Implemented (button + API) | Add to suggested_action list; keep existing behaviour. |
| create_work_order | Implemented | Same. |
| schedule_inspection | Not as distinct action | Implement as create_issue with category/title indicating inspection (or dedicated “inspection” flow). |
| send_contractor_reminder | Not implemented | Requires contractor notification path; document as future or stub. |
| reassign_contractor | Not implemented | Requires work order reassignment; document as future or stub. |

**Recommendation:** Add `suggested_actions` (array of strings) to each risk signal document. Populate from risk_type/category (e.g. compliance → schedule_inspection; operational → create_work_order, create_issue). UI shows only buttons for suggested_actions present on that signal. Implement create_issue, create_work_order, schedule_inspection; leave send_contractor_reminder and reassign_contractor for later (optional placeholder in docs/UI).

---

### PART 3 — Action Execution

**Task:** On confirm: create_issue → create issue; create_work_order → open/create WO pre-filled; schedule_inspection → generate inspection issue. Audit logs.

| Action | Current | Gap |
|--------|---------|-----|
| create_issue | Implemented; audit ISSUE_CREATED_FROM_RISK_SIGNAL | None. |
| create_work_order | Implemented; audit WORK_ORDER_CREATED_FROM_RISK_SIGNAL | Optional: pre-fill property/asset in client WO creation form when opened from signal (partially present via description). |
| schedule_inspection | Not explicit | Add: create_issue with description/title like “Inspection: [risk_type]” and optionally category or tag “inspection”; reuse same audit. |

No conflict; extend with schedule_inspection and ensure audit on all paths.

---

### PART 4 — Property Dashboard “Suggested Actions” Panel

**Task:** Panel showing active risk signals, severity, recommended actions, action buttons; allow resolve/dismiss.

**Current:** “Current alerts” (overdue, expiring, high risk signals, open WOs) and “Recommended next actions” (links to tabs). Risk Signals **tab** has full list with Create work order, Acknowledge, Resolve.

**Gap:** No single panel titled “Suggested Actions” that combines (1) active risk signals, (2) severity, (3) recommended_action, (4) **per-signal action buttons** (Create Issue, Create Work Order, etc.). **Recommendation:** Add a “Suggested Actions” panel on the property dashboard (e.g. above or beside “Recommended next actions”) that lists active risk signals with severity, recommended_action, and buttons driven by suggested_actions (Create issue, Create work order, Schedule inspection). Keep existing Acknowledge/Resolve (resolve/dismiss).

---

### PART 5 — Admin Risk Dashboard

**Task:** Risk intelligence dashboard: portfolio risk heatmap, top compliance risks, top maintenance risks, properties with repeated issues, SLA breach risks; filtering.

**Current:** AdminRiskDashboardPage shows totalActive, totalSignals, byLevel, byType, topProperties, topClients, recentSignals; filters (client, risk_level, risk_type, status).

**Gap:** No explicit “portfolio risk heatmap”, “top compliance risks”, “top maintenance risks”, “properties with repeated issues”, “SLA breach risks” as separate sections. **Recommendation:** Extend admin summary (backend) and dashboard (frontend): (1) **Top compliance risks** — filter by signal_category=compliance (or risk_type Compliance Churn); (2) **Top maintenance risks** — asset + operational categories or relevant risk_types; (3) **Properties with repeated issues** — filter risk_type Recurring Repairs / repeated_issue; (4) **SLA breach risks** — filter risk_type SLA Breach. **Heatmap:** Simple implementation = table/grid of properties (or clients) × risk level counts, or “top N properties by signal count” with severity colour; no new backend if we derive from existing summary + filters.

---

### PART 6 — Automation Job

**Task:** Scheduled job that evaluates risk daily; scan compliance, work order performance, issue history; generate risk signals.

**Current:** `risk_signals_job` runs on schedule; calls `generate_risk_signals_for_org(client_id)` for each client with PREDICTIVE_MAINTENANCE; per property we already scan work_orders, issues, requirements (overdue). We do **not** currently create signals for “certificate expiring soon” (EXPIRING_SOON).

**Gap:** Add a rule that fetches requirements in EXPIRING_SOON (and optionally PENDING/MISSING where relevant) and emits certificate_expiry_soon signals. Job itself exists; ensure it remains daily and that new rule is called from `generate_risk_signals_for_property()`.

---

### PART 7 — Documentation

**Task:** Create docs/RISK_ENGINE.md: risk signal types, suggested actions, how signals are generated, how users interact.

**Current:** OPERATIONAL_FEATURES_USER_GUIDE.md and OPERATIONS_GAP_CLOSURE_SUMMARY mention risk signals; RISK_SIGNAL_DETECTION_LAYER_AUDIT exists. No single RISK_ENGINE.md. **Recommendation:** Add docs/RISK_ENGINE.md describing: risk types (including certificate_expiry_soon), categories, suggested actions, generation (rules + job), client and admin UI, and action execution (create issue/WO, schedule inspection, audit).

---

## 3. Conflicts and Safest Choices

| Topic | Conflict / choice | Recommendation |
|-------|-------------------|----------------|
| risk_type naming | Task snake_case vs current display names | Keep current human-readable risk_type; add only new type for Certificate Expiry Soon. Optionally expose a `risk_type_code` for API (certificate_expiry_soon, repeated_issue_pattern, etc.) if needed later. |
| suggested_action | Single vs multiple | Use array `suggested_actions` so a signal can support both “create_issue” and “create_work_order” where appropriate. |
| send_contractor_reminder / reassign_contractor | No existing backend | Do not implement in first iteration; document as future. Add to suggested_actions only when backend exists. |
| description | Not stored today | Add optional `description` when building signal (e.g. from risk_type + first reason or recommended_action) for consistency with task and future APIs. |
| severity | Task says “severity” | Keep using **risk_level** in storage/API; document “severity” in RISK_ENGINE.md as the same concept (low/medium/high/critical). |

---

## 4. Proposed Implementation Order (No Code Yet)

1. **Part 1 + 6:** Add certificate_expiry_soon rule (requirements EXPIRING_SOON); add optional `description` to signal doc; ensure job remains daily. Align task names in docs only (repeated_issue_pattern ↔ Recurring Repairs, etc.).
2. **Part 2:** Add `suggested_actions` (array) to signal doc; populate in `generate_risk_signals_for_property()` by risk_type/category; extend ClientRiskSignalsPage and PropertyDetailPage to show buttons from suggested_actions.
3. **Part 3:** Add schedule_inspection action: new endpoint or reuse create_issue with inspection wording/category; ensure audit. Optionally improve WO pre-fill from signal (property/asset) in client UI.
4. **Part 4:** Add “Suggested Actions” panel on property dashboard (active signals, severity, recommended_action, action buttons, resolve/dismiss).
5. **Part 5:** Extend admin summary and AdminRiskDashboardPage: top compliance risks, top maintenance risks, properties with repeated issues, SLA breach risks; simple heatmap (e.g. table by property/level).
6. **Part 7:** Create docs/RISK_ENGINE.md.

---

## 5. Files to Touch (Summary)

- **Backend:** `risk_signal_service.py` (new rule, description, suggested_actions), optionally `client_maintenance.py` (schedule_inspection endpoint or param), `ops_compliance.py` if admin summary is extended.
- **Frontend:** `ClientRiskSignalsPage.js`, `PropertyDetailPage.js` (suggested action buttons + Suggested Actions panel), `AdminRiskDashboardPage.js` (new sections + heatmap).
- **Docs:** New `docs/RISK_ENGINE.md`; optionally update OPERATIONAL_FEATURES_USER_GUIDE.md.
- **Job:** No structural change; ensure risk_signals_job schedule remains and new rule is invoked from existing generator.

No duplication of the existing risk_signals collection or replace of current risk types; only additive changes and one new risk type (certificate_expiry_soon).
