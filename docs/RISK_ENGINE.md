# Risk Engine — Predictive Risk and Suggested Actions

This document describes the Predictive Risk and Suggested Actions Engine: risk signal types, suggested actions, how signals are generated, and how users interact with them.

---

## Overview

The risk engine turns compliance, operations, and maintenance data into **risk signals** with **recommended actions** and **suggested actions** (actionable buttons). Signals are stored per property, updated by a daily job and on-demand recalculate. Clients and admins can view signals, trigger actions (create issue, create work order, schedule inspection), and resolve or dismiss them.

**Feature flag:** `PREDICTIVE_MAINTENANCE` (and `MAINTENANCE_WORKFLOWS` for creating issues/work orders).

---

## Risk Signal Types

Signals are grouped into three **categories** and have a **risk type** and **severity** (risk_level).

### Categories

| Category       | Description |
|----------------|-------------|
| **asset**      | Property/asset condition and failure risk (boiler, damp, electrical, recurring repairs, maintenance frequency). |
| **operational** | Work order and contractor performance (SLA breach). |
| **compliance** | Certificate and obligation status (compliance churn, certificate expiry soon). |

### Risk Types (and task mapping)

| Risk type (display)       | Task code / condition     | Trigger |
|---------------------------|---------------------------|--------|
| Boiler Failure Risk       | asset_failure_risk        | Boiler/heating asset age &gt; 10 years and ≥2 heating issues/WOs in 12 months. |
| Damp / Moisture Risk      | asset_failure_risk        | ≥2 damp-related issues/WOs in 12 months (older property stock). |
| Electrical Risk           | asset_failure_risk        | ≥2 electrical issues/WOs in 12 months or EICR overdue. |
| Recurring Repairs Risk    | repeated_issue_pattern    | Same asset/category ≥3 issues or WOs in 12 months. |
| Maintenance Frequency Risk| —                         | ≥4 issues or WOs in 6 months. |
| SLA Breach Risk           | sla_breach_risk           | ≥2 work orders with SLA breached in 30/60 days. |
| Compliance Churn Risk     | —                         | Repeated overdue/missing obligations. |
| Certificate Expiry Soon  | certificate_expiry_soon  | One or more requirements with status EXPIRING_SOON. |

### Severity (risk_level)

- **low**, **medium**, **high**, **critical** — used in UI and admin dashboards. Stored as `risk_level`; in task wording this is “severity”.

---

## Signal Fields

Each stored risk signal includes:

- **signal_id**, **client_id**, **property_id**, **asset_id** (optional)
- **signal_category**, **risk_type**, **risk_level**
- **description** — short summary (e.g. risk_type + first reason)
- **reasons** — list of explainable reasons
- **recommended_action** — human-readable recommendation
- **suggested_actions** — list of action codes (see below)
- **status** — active | acknowledged | resolved
- **source** — heuristic (rule-based)
- **generated_at**, **updated_at**

---

## Suggested Actions

**suggested_actions** is an array of action codes that drive which buttons appear in the UI.

| Action code                  | Description                    | Implemented |
|-----------------------------|--------------------------------|-------------|
| **create_issue**            | Create a maintenance issue from the signal. | Yes |
| **create_work_order**       | Create a work order (property/asset/description pre-filled from signal). | Yes |
| **schedule_inspection**     | Create an inspection-type issue (“Inspection: …”). | Yes |
| **send_contractor_reminder**| Send a reminder to the contractor. | No (future) |
| **reassign_contractor**      | Reassign work order to another contractor. | No (future) |

Mapping from signal category/risk type to suggested_actions is defined in `risk_signal_service._suggested_actions_for_signal()`. Compliance signals typically get `schedule_inspection` and either `create_work_order` (certificate expiry) or `create_issue`. Asset and operational signals get `create_work_order`, `create_issue`, and `schedule_inspection`.

---

## How Signals Are Generated

### Rules and data sources

- **Compliance:** Requirements (overdue, missing, pending, **expiring soon**).
- **Work orders:** Last 12 months for categories; last 30/60 days for SLA breaches (`sla_breached_at` set by `work_order_sla_breach_job`).
- **Issues:** Last 12 months by category/asset.
- **Assets:** Property assets (age, type) for boiler/electrical rules.
- **Property:** e.g. building age for damp/electrical.

### Generation flow

1. **Per property:** `generate_risk_signals_for_property(property_id, client_id)` loads the above data, runs each rule, deduplicates by (risk_type, asset_id), then **replaces** all active heuristic signals for that property with the new set. Each new signal gets a `signal_id`, `description`, and `suggested_actions`.
2. **Per org:** `generate_risk_signals_for_org(client_id)` runs step 1 for every active property of the client.

### When generation runs

- **Scheduled job:** `risk_signals_job` runs **daily at 04:30 UTC** for all clients with PREDICTIVE_MAINTENANCE. It calls `generate_risk_signals_for_org` per client.
- **On-demand:** Client can trigger **Recalculate** for a single property from the Property detail → Risk Signals tab (`POST /api/client/maintenance/risk-signals/recalculate/{property_id}`).

---

## Action Execution

When the user clicks a suggested action:

| Action               | Backend                                      | Audit |
|----------------------|----------------------------------------------|-------|
| **Create issue**     | `POST .../risk-signals/{id}/create-issue`   | ISSUE_CREATED_FROM_RISK_SIGNAL |
| **Create work order**| `POST .../risk-signals/{id}/create-work-order` | WORK_ORDER_CREATED_FROM_RISK_SIGNAL |
| **Schedule inspection** | `POST .../risk-signals/{id}/schedule-inspection` | INSPECTION_CREATED_FROM_RISK_SIGNAL |

- Create issue: creates a maintenance issue linked to the signal (`risk_signal_id`), with description from the signal (or override).
- Create work order: creates a work order with property, optional asset, and description from the signal.
- Schedule inspection: creates an issue with description prefixed by “Inspection: ” and the same link to the risk signal; audited as INSPECTION_CREATED_FROM_RISK_SIGNAL.

All actions require PREDICTIVE_MAINTENANCE and MAINTENANCE_WORKFLOWS.

---

## How Users Interact With Signals

### Client

- **Operations → Risk Signals** (`/operations/risk-signals`): Portfolio list and filters; click a signal to open a drawer with details, reasons, recommended action, and **Suggested actions** buttons (Create issue, Create work order, Schedule inspection). Acknowledge and Mark resolved in the drawer.
- **Property detail → Overview:** “Suggested actions” panel shows up to five active signals with severity, recommended action, and the same action buttons plus Acknowledge/Resolve. “View all risk signals” goes to the Risk Signals tab.
- **Property detail → Risk Signals tab:** Full list for the property with Create work order / Create issue / Schedule inspection (from suggested_actions), Recalculate, Acknowledge, Resolve.

### Admin

- **Ops → Risk & Insights** (`/admin/ops/risk`): Risk intelligence dashboard with:
  - KPIs: active signals, by level, top properties/clients
  - By risk type; top affected properties
  - **Top compliance risks**, **Top maintenance risks**, **Properties with repeated issues**, **SLA breach risks**
  - **Portfolio risk heatmap** (top properties by signal count, by severity)
  - Recent risk signals table  
  Filters: client, risk level, risk type, status.

---

## Implementation References

- **Service:** `backend/services/risk_signal_service.py` — rules, generation, create_issue_from_risk_signal, create_work_order_from_risk_signal, create_inspection_issue_from_risk_signal, get_risk_signals_admin_summary.
- **Client API:** `backend/routes/client_maintenance.py` — GET/PATCH risk-signals, POST create-issue, create-work-order, schedule-inspection, recalculate.
- **Admin API:** `backend/routes/ops_compliance.py` — GET risk-signals/summary.
- **Job:** `backend/job_runner.run_risk_signals_job`; scheduled in `backend/server.py` (daily 04:30 UTC).
- **UI:** `ClientRiskSignalsPage.js`, `PropertyDetailPage.js` (Overview + Risk Signals tab), `AdminRiskDashboardPage.js`.
