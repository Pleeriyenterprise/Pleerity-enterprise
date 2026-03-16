# Orchestration and Copilot Layer — Task vs Codebase Analysis

**Purpose:** Identify what exists, what is missing, and avoid duplication or conflict before implementing the Priority Action Engine.

---

## 1. Current State Summary

| Area | Current implementation | Gap |
|------|------------------------|-----|
| **Client dashboard** | GET /client/dashboard: client, properties, compliance_summary (overdue, expiring_soon), onboarding_checklist. Frontend also fetches work orders, risk signals, predictive insights separately. "Action required" card shows counts (open WOs + risk signals) with "View issues" / "View risk signals" buttons. | No **unified priority actions** API; no **scoring** or **ranking**; no single panel with top actions and one button per item. |
| **Property detail** | "Current alerts", "Recommended next actions", "Suggested actions" (risk signals) — each built from separate data. | No cross-source priority list. |
| **Admin** | GET /admin/dashboard (stats); GET /admin/ops/overview (if exists); Risk & Insights, Incidents, Automation Centre are separate pages. | No **Action Queue** or **Operational Priorities** panel aggregating compliance failures, WO breach, incidents, approvals, risk hotspots. |
| **Data sources** | Requirements (overdue, EXPIRING_SOON, status); risk_signals (get_risk_signals_for_client); work_orders (sla_breach_risk_at, sla_breached_at); approval_service.list_approvals (pending); maintenance_issues (open); incidents (list_incidents); job_run / observability (degraded). | All exist but are **not** combined into one priority list. |

---

## 2. Task vs Current — Part by Part

### PART 1 — Priority Action Engine

**Task:** Service that generates priority actions for client and admin. Each action: action_type, title, description, severity/priority, related_* ids, recommended_url, recommended_action_label.

**Current:** No such service. **Gap:** Create `backend/services/priority_actions.py` with e.g. `get_priority_actions_for_client(client_id, limit)` and `get_priority_actions_for_admin(client_id_filter=None, limit)` returning list of action dicts.

### PART 2 — Input Sources

**Task:** Overdue compliance, certificates expiring soon, missing documents, active risk signals, open WOs near SLA breach, pending approvals, unresolved issues, open critical incidents (admin), stale/degraded automation (admin).

**Current:**  
- Overdue / expiring: from requirements (status OVERDUE, EXPIRING_SOON).  
- Missing documents: requirements with missing evidence or status.  
- Risk signals: risk_signal_service.get_risk_signals_for_client.  
- WOs near breach: work_orders with sla_breach_risk_at or sla_breached_at.  
- Pending approvals: approval_service.list_approvals (status pending).  
- Open issues: maintenance_issues (status not closed/resolved).  
- Incidents: incident_service.list_incidents (open, P0/P1).  
- Automation: observability job states (degraded/overdue).  

**Gap:** Wire these into the new service; no new data sources needed.

### PART 3 — Priority Scoring

**Task:** Weights (e.g. overdue = 90, cert expiring 7d = 75, high risk signal = 70, WO near breach = 80, pending invoice = 50, missing doc = 40, P0/P1 incident = 95). Return top-ranked first.

**Current:** No scoring. **Gap:** Implement numeric score per action type (configurable in code), sort by score desc, then by date/severity.

### PART 4 — Client Dashboard Integration

**Task:** "Priority Actions" panel with top actions, concise explanation, one clear action button (Create work order, Upload document, Review compliance, Approve invoice).

**Current:** "Action required" shows two lines (issues count, risk signals count). **Gap:** Add a **Priority Actions** panel (or replace/enhance Action required) that calls the new client priority API and renders each action with title, description, and a single button linking to recommended_url. **Conflict:** None; add panel alongside or above existing Action required.

### PART 5 — Admin Dashboard Integration

**Task:** Admin "Action Queue" or "Operational Priorities" panel: clients with urgent compliance failures, WOs near breach, critical incidents, approval bottlenecks, risk hotspots.

**Current:** No single panel. **Gap:** New admin API for priority actions; new panel on admin dashboard (or Ops landing) showing ranked list with same shape (title, description, link/button).

### PART 6 — Action Linking

**Task:** Each action links to correct UI (risk signal → risk detail or create issue/WO; approval → approval detail; compliance → property compliance; incident → incident detail).

**Current:** Deep links exist per area but are not centralized. **Gap:** In priority_actions service, set recommended_url (pathname) and recommended_action_label per action_type so the UI can render one button per action.

### PART 7 — Observability & Documentation

**Task:** Log action generation if useful; document how priorities are calculated; create docs/PRIORITY_ACTIONS_ENGINE.md.

**Current:** N/A. **Gap:** Add optional debug logging in the service; write PRIORITY_ACTIONS_ENGINE.md with scoring rules and flow.

### PART 8 — Deliverables

**Task:** Return files created/modified, how generated, client/admin panels added, scoring rules, remaining gaps for future copilot/AI.

**Current:** N/A. **Gap:** Deliver with summary (can be in the doc or a short handover).

---

## 3. Conflicts and Safest Choices

| Topic | Choice | Recommendation |
|-------|--------|-----------------|
| **recommended_url** | Full URL vs pathname | Use **pathname** (e.g. `/operations/risk-signals`, `/properties/{id}?tab=compliance`) so the SPA can use navigate(). |
| **severity vs priority** | Task has both | Use **priority** (numeric) for sort order; **severity** (critical/high/medium/low) for display badge. |
| **Client "Action required"** | Replace vs add | **Add** a "Priority Actions" panel that uses the new API; keep existing "Action required" for now (or hide when priority panel has content) to avoid breaking existing behaviour. |
| **Admin panel placement** | Dashboard vs Ops | Add to **admin dashboard** (Overview) as "Operational Priorities" or "Action Queue" card/section; optionally link from Ops menu. |
| **Certificate expiring within 7 days** | Exact 7d vs config | Requirements have EXPIRING_SOON (configurable window). Use **EXPIRING_SOON** for "certificate expiring soon" and assign weight 75; if we have expiry date we could later refine to "within 7 days" for a higher weight. |

---

## 4. Implementation Order

1. **Backend:** Create `priority_actions.py`: scoring constants, helpers to fetch each source (compliance, risk signals, WOs, approvals, issues, incidents, job states), build action list, score and sort, return list with recommended_url and recommended_action_label.
2. **Client API:** Add GET /api/client/priority-actions (limit, optional property_id filter). Call service for client_id from auth.
3. **Admin API:** Add GET /api/admin/ops/priority-actions (limit, client_id filter). Call service for admin (all clients or one).
4. **Client dashboard:** Add "Priority Actions" panel; fetch from new API; render top N with one button each.
5. **Admin dashboard:** Add "Action Queue" / "Operational Priorities" panel; fetch from admin API; render list with links.
6. **Docs:** Add docs/PRIORITY_ACTIONS_ENGINE.md (sources, scoring, linking, observability).
7. **Deliverables:** Summarise in the doc (files, flow, scoring, gaps).

No duplication: we do **not** replace risk signals or compliance logic; we **consume** them and add a single orchestration layer on top.
