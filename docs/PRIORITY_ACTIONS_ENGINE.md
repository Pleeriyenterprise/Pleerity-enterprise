# Priority Actions Engine

The **Priority Actions Engine** is the orchestration and copilot layer for Pleerity. It combines outputs from the compliance engine, operations engine, risk signal engine, approvals/invoice engine, and (for admin) the automation/incident engine into a single ranked list of actionable priorities for client and admin users.

---

## 1. Overview

- **Client:** `GET /api/client/priority-actions` — returns top priority actions for the authenticated client (optionally filtered by `property_id`).
- **Admin:** `GET /api/admin/ops/priority-actions` — returns operational priorities across all clients (optionally filtered by `client_id`).

Each action includes:

| Field | Description |
|-------|-------------|
| `action_type` | Type identifier (e.g. `overdue_compliance`, `risk_signal`, `pending_invoice_approval`). |
| `title` | Short title for the action. |
| `description` | Concise explanation. |
| `priority` | Numeric score used for ranking (higher = more urgent). |
| `severity` | Display severity: `critical`, `high`, `medium`, `low`. |
| `related_property_id` | Optional. |
| `related_issue_id` | Optional. |
| `related_work_order_id` | Optional. |
| `related_risk_signal_id` | Optional. |
| `related_invoice_id` | Optional. |
| `related_incident_id` | Optional (admin). |
| `recommended_url` | Pathname for SPA navigation (e.g. `/operations/risk-signals`, `/properties/{id}`). |
| `recommended_action_label` | Button label (e.g. "Review compliance", "Approve invoice"). |
| `client_id` | Set for admin actions that are client-scoped. |

---

## 2. How Priorities Are Calculated

1. **Gather** — The engine queries each input source (requirements, risk signals, work orders, approvals, issues, incidents, job runs).
2. **Map** — Each raw item is turned into one or more *priority action* dicts with a **numeric priority** and a **severity**.
3. **Score** — The numeric priority is fixed per action type (see table below). No secondary scoring is applied; ordering is by this score.
4. **Deduplicate** — Actions are deduplicated by `(action_type, related_* ids, client_id)` so the same work order or requirement does not appear multiple times.
5. **Sort** — Actions are sorted by `priority` descending, then by `title`.
6. **Limit** — The top `limit` actions are returned (client default 20, admin default 30).

---

## 3. Scoring Rules (Priority Weights)

| Source / condition | Priority | Severity | Notes |
|--------------------|----------|----------|--------|
| Overdue compliance item (OVERDUE/EXPIRED) | 90 | high | Per requirement. |
| Certificate/requirement expiring soon (EXPIRING_SOON) | 75 | medium | Per requirement. |
| High/critical risk signal (active) | 70 | high | Medium risk signals use 55. |
| Work order near SLA breach (`sla_breach_risk_at` set) | 80 | medium | |
| Work order SLA breached (`sla_breached_at` set) | 85 | high | |
| Pending invoice approval | 50 | medium | |
| Missing required document (PENDING/MISSING, no evidence) | 40 | medium | |
| Open operational issue (maintenance issue not resolved/closed) | 45 | medium | |
| Open P0/P1 incident (admin) | 95 | critical | |
| Automation job failed / never run / overdue (admin) | 60 | high/medium | Degraded uses 50. |

These constants are defined in `backend/services/priority_actions.py` (`SCORE_*`, `SEVERITY_*`).

---

## 4. Input Sources

### Client

- **Overdue compliance** — `requirements` with `status` in `OVERDUE`, `EXPIRED`.
- **Certificate expiring soon** — `requirements` with `status` = `EXPIRING_SOON`.
- **Missing documents** — `requirements` with `status` in `PENDING`, `MISSING` and no `evidence_doc_id`.
- **Active risk signals** — `risk_signal_service.get_risk_signals_for_client` (status active).
- **Work orders near/breached SLA** — `maintenance_service.list_work_orders` with `sla_state` `near_breach` or `breached`.
- **Pending approvals** — `approval_service.list_approvals` with status `pending`.
- **Open operational issues** — `maintenance_issues_service.list_issues` with open-style statuses.

### Admin only

- **Clients with urgent compliance failures** — Count of overdue/expired requirements per client.
- **Work orders near/breached SLA** — Same as client but across clients (or filtered by client).
- **Open P0/P1 incidents** — `incident_service.list_incidents` (status open, severity P0 or P1).
- **Approval bottlenecks** — Pending invoice count per client (summary action per client).
- **Risk hotspots** — `risk_signal_service.get_risk_signals_admin_summary` (e.g. high-level, active) → recent signals.
- **Stale/degraded automation** — Critical jobs from `job_schedule_registry`; last run status from `job_runs` (failed, degraded, or no run).

---

## 5. Action Linking (UI Destinations)

Each action type is given a `recommended_url` (pathname) and `recommended_action_label` so the UI can render one clear button per action.

| Action type | Typical destination | Label example |
|-------------|--------------------|---------------|
| Overdue / expiring / missing doc | `/properties/{property_id}` or `/compliance-score` | Review compliance, Upload document |
| Risk signal | `/operations/risk-signals` | Review risk signal |
| Work order near/breached | `/operations/work-orders` (client), `/admin/ops/maintenance` (admin) | View work order(s) |
| Pending invoice | `/operations/approvals` (client), client link (admin) | Approve invoice, View approvals |
| Open issue | `/operations/issues` | View issue |
| Open incident (admin) | `/admin/incidents` | View incident |
| Automation degraded (admin) | `/admin/ops` (system health) | View system health |

The frontend uses these pathnames with the app router (e.g. `navigate(recommended_url)`).

---

## 6. Observability

- **Logging:** When the engine returns a non-empty list, it logs at INFO:  
  `Priority actions for client <client_id>: <n> actions` or  
  `Priority actions for admin (client_filter=...): <n> actions`.  
  This supports debugging and basic analytics without logging every fetched entity.
- **Debug:** Failures in individual source fetches (e.g. risk signals, work orders) are caught and logged at DEBUG so one failing source does not break the whole list.

---

## 7. Files Created/Modified

| File | Change |
|------|--------|
| `backend/services/priority_actions.py` | **Created.** Core engine: scoring, client/admin fetchers, dedupe, sort, limit. |
| `backend/routes/client.py` | **Modified.** Added `GET /priority-actions` (client). |
| `backend/routes/ops_compliance.py` | **Modified.** Added `GET /priority-actions` (admin). |
| `frontend/src/api/client.js` | **Modified.** Added `clientAPI.getPriorityActions`, `adminAPI.getPriorityActions`. |
| `frontend/src/pages/ClientDashboard.js` | **Modified.** Priority Actions panel: state, fetch, list with one button per action. |
| `frontend/src/pages/AdminDashboard.js` | **Modified.** DashboardOverview: state, fetch, “Operational Priorities” panel with links. |
| `docs/PRIORITY_ACTIONS_TASK_ANALYSIS.md` | **Created.** Task vs codebase analysis (conflicts, choices). |
| `docs/PRIORITY_ACTIONS_ENGINE.md` | **Created.** This document. |

---

## 8. Client Priority Actions Panel

- **Where:** Client dashboard (main dashboard view), above the existing “Action required” card.
- **When:** Rendered when `priorityActions.actions.length > 0`.
- **Content:** List of top actions (title, short description, one primary button). Button uses `recommended_url` and `recommended_action_label` from the API.

**Property-scoped panel:** The same API is used on the property detail page (Overview tab) with `property_id` set to the current property. When there are priority actions for that property, a "Priority actions" card is shown with the same pattern (title, description, one button per action).

---

## 9. Admin Action Queue / Operational Priorities Panel

- **Where:** Admin dashboard → Overview tab, at the top of the content (below the “Dashboard Overview” heading).
- **When:** The panel is always visible; when the API returns no actions, "No priority actions for the selected filter" is shown.
- **Content:** A "Filter by client" dropdown (All clients, or a specific client) and the list of operational priorities (title, description, optional client_id, one button per action). Button navigates to `recommended_url`. Filtering uses the `client_id` query param on `GET /api/admin/ops/priority-actions`.

---

## 10. Remaining Gaps for Future Copilot/AI Enhancements

- **Natural language / copilot:** The engine is rule-based and does not interpret free-text or suggest next-best action in natural language. A future copilot could consume the same `actions` list and/or raw sources to generate summaries or “what should I do next?” answers.
- **Personalisation:** No user-level preferences or “focus areas” yet; all clients see the same scoring rules. Future: weight by user role or saved preferences.
- **Time-based tuning:** Certificate “expiring within 7 days” is currently represented by the existing `EXPIRING_SOON` status; finer bands (e.g. 7d vs 30d) could drive different scores or labels.
- **Property detail:** Priority actions are implemented on the client *dashboard* only. The same API supports `property_id` filter; a “Priority actions” block on the property detail page could call the client API with that filter.
- **Filtering on admin:** Admin API supports `client_id` query param; the admin UI could add a client filter to the Operational Priorities panel.
- **Caching:** No caching layer; every request recomputes. For high traffic, a short TTL cache or background job could be added.
