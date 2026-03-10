# Maintenance Intelligence Flow – Task vs Codebase Audit

**Task:** Implement an enterprise-grade Maintenance Intelligence Flow (rule-based triage, priority scoring, work order drafts, contractor recommendation, SLA monitoring, completion effects).

**Audit date:** Based on current codebase state. Purpose: identify what is implemented, what matches or conflicts with the task’s data models and flows, and the safest additive path.

---

## 1. EXECUTIVE SUMMARY

| Area | Task expectation | Current state | Gap / conflict |
|------|------------------|---------------|----------------|
| **Data: Issues** | Separate `maintenanceIssues` with status (new → triaged → ready_for_work_order → closed), source, priorityScore, recurrenceFlag | **No issues collection.** Reporting (tenant/client/admin) creates **work orders** directly. | Task assumes **issue → triage → work order**. Codebase has **report → work order** only. |
| **Data: Triage** | `triageResults` with issueId, severity, priorityScore, slaHours, recommendedContractorType, reasoning[] | **None.** Only `_categorise_severity(description)` (keyword heuristic) used when creating work order; no stored triage result or reasoning. | Full triage engine and storage missing. |
| **Data: Work orders** | issueId, assetId, status (draft | assigned | scheduled | in_progress | awaiting_parts | completed | verified | closed), slaDueAt, costEstimateMin/Max, resolutionOutcome | **work_orders:** client_id, property_id, description, source, category, severity, status (OPEN | ASSIGNED | IN_PROGRESS | COMPLETED | CANCELLED), contractor_id, sla_respond_by, sla_complete_by, completed_at. **No:** orgId (we use client_id), assetId, issueId, draft/scheduled/awaiting_parts/verified/closed, cost estimates, resolutionOutcome. | Naming and status set differ; several fields missing. |
| **Data: Contractor assignments** | Dedicated `contractorAssignments` (workOrderId, contractorId, assignedAt, assignedBy, status) | **No.** Assignment = `contractor_id` on work_order; no assignment history or status. | Task expects first-class assignment records. |
| **Triage engine** | `triageMaintenanceIssue(issue, property, assetHistory)` with rules (heating + no heat Oct–Mar → high/Gas Safe/24h; recurrence; damp → inspection) and reasoning[] | **Partial.** `_categorise_severity(description)` only (leak/no heat/etc → urgent/high/medium). No seasonality, recurrence, asset history, contractor type, SLA hours, or reasoning. | Most triage logic and storage missing. |
| **Priority scoring** | priorityScore + band from urgency, category, seasonality, recurrence, asset type | **None.** Severity is set once at creation (user or heuristic); no numeric score or band. | Additive: new scoring module. |
| **Work order flow** | Issue → “Create Work Order”; draft after triage if severity ≥ threshold; user confirmation before assignment | **Direct create.** No issue step; no draft state; assignment is optional field on PATCH. | Would require issue layer and/or draft status. |
| **Contractor recommendation** | Recommend by trade, region, credential, SLA performance, pricing; no auto-assign | **List only.** Client/admin list contractors (trade_types, areas_served, vetted). No recommendation API, no SLA/pricing data. | Recommendation engine and data missing. |
| **SLA monitoring** | slaDueAt from triage; job to mark breach risk / breached; surface in dashboard | **Partial.** work_orders have sla_respond_by, sla_complete_by. **No** job that marks work order SLA breach or breach_risk. (Leads and compliance recalc have SLA breach jobs elsewhere.) | Work-order SLA breach job and dashboard surfacing missing. |
| **Completion effects** | Timeline event, asset history event, contractor performance, risk recalculation | **Partial.** Completion calls `record_maintenance_event` (asset history). **No** property timeline event for “work order completed”, **no** contractor performance counters, risk recalc is existing predictive flow. | Timeline + contractor stats missing. |
| **UI** | Issue form, Issues page with filters, Issue detail (triage + reasoning + create WO), WO detail, Contractor recommendation panel, deep links | **Existing:** Issues page = open work orders + “Report issue” (creates WO). Work orders page = list + create. Admin: list WO, assign contractor, change status. **No** issue detail, **no** WO detail screen, **no** triage/reasoning UI, **no** recommendation panel. | Several screens and panels missing. |
| **Feature flags** | MAINTENANCE_WORKFLOWS, CONTRACTOR_NETWORK where applicable | **In place.** Both flags used for client/tenant maintenance and contractor list. | Align. |

---

## 2. DATA MODELS: TASK VS CODEBASE

### 2.1 maintenanceIssues (task) vs current

- **Task:** _id, orgId, propertyId, assetId, source, category, description, photos[], reporterName/Contact, reportedUrgency, severity, priorityScore, status (new | triaged | monitoring | ready_for_work_order | closed), recurrenceFlag, createdAt, updatedAt.
- **Current:** **No `maintenance_issues` collection.** Tenant report and client “Report issue” both call `create_work_order`; admin creates work order directly. So “issues” in the UI are just work orders in OPEN/ASSIGNED.
- **Conflict:** Task assumes a separate issue lifecycle (new → triaged → … → ready_for_work_order) then “Create Work Order”. Codebase has a single step: report → work order.
- **Safest option:** Introduce `maintenance_issues` **additively**: new reports can create an issue first; add triage job or on-read triage; “Create Work Order” creates from issue and links issueId. Keep existing “Report issue” → work order path as **optional shortcut** (e.g. config or flag “create_work_order_directly”) so existing behaviour remains until issue flow is adopted.

### 2.2 triageResults (task) vs current

- **Task:** issueId, assetTypeSuggested, severity, priorityScore, slaHours, recommendedContractorType, requiresUserApproval, reasoning[], createdAt.
- **Current:** **No triage result storage.** `maintenance_service._categorise_severity(description)` returns low/medium/high/urgent and is used only at creation; result is not stored and there is no reasoning array.
- **Gap:** Full triage engine and `triageResults` (or embedded triage on issue) need to be added. Reuse/extend keyword logic and add seasonality, recurrence (from history), asset type suggestion, SLA hours, contractor type, and reasoning array.

### 2.3 workOrders (task) vs current

- **Task:** orgId, propertyId, assetId, **issueId**, status (draft | assigned | scheduled | in_progress | awaiting_parts | completed | verified | closed), severity, slaDueAt, assignedContractorId, costEstimateMin/Max, resolutionOutcome, createdAt, updatedAt.
- **Current (maintenance_service + DB):** client_id, property_id, work_order_id, description, source, category, severity, status (OPEN | ASSIGNED | IN_PROGRESS | COMPLETED | CANCELLED), contractor_id, created_at, updated_at, sla_respond_by, sla_complete_by, completed_at.
- **Mapping:** orgId → client_id, propertyId → property_id. Task “assigned” ≈ ASSIGNED, “in_progress” ≈ IN_PROGRESS, “completed” ≈ COMPLETED.
- **Missing today:** assetId, issueId, draft/scheduled/awaiting_parts/verified/closed, single slaDueAt (we have sla_respond_by + sla_complete_by), costEstimateMin/Max, resolutionOutcome.
- **Conflict:** Status set differs (draft/scheduled/awaiting_parts/verified/closed vs OPEN/ASSIGNED/…). **Safest:** Add new statuses and fields **additively** (e.g. allow draft, scheduled, awaiting_parts, verified, closed in addition to existing); add optional asset_id, issue_id, cost_estimate_min/max, resolution_outcome, and optionally a single sla_due_at (or keep both SLA fields and add “breach” from them). Do not remove existing statuses or fields.

### 2.4 contractorAssignments (task) vs current

- **Task:** workOrderId, contractorId, assignedAt, assignedBy, status.
- **Current:** Only `contractor_id` on work_order; no assignment history.
- **Safest option:** Add `contractor_assignments` (or equivalent) when assignment is set/updated: record work_order_id, contractor_id, assigned_at, assigned_by. Keep contractor_id on work_order for current behaviour; use assignment table for history and future “status” (e.g. accepted/declined) if needed.

---

## 3. TRIAGE ENGINE

- **Task:** Rule-based `triageMaintenanceIssue(issue, property, assetHistory)` with examples (heating + “no heating” Oct–Mar → high, Gas Safe, 24h; leak/plumbing; recurrence in 90 days; damp → inspection); store reasoning[].
- **Current:** `_categorise_severity(description)` in maintenance_service: keywords → urgent/high/medium. Used at create time only; no property, no asset history, no seasonality, no recurrence, no contractor type, no SLA hours, no stored reasoning.
- **Gap:** Implement triage as a dedicated function (or module) that:
  - Takes issue (or description + category + source + property_id), property, and asset/maintenance history.
  - Applies rules (category + keywords, seasonality, recurrence from history, damp → inspection).
  - Returns (and optionally stores) severity, priorityScore, slaHours, recommendedContractorType, reasoning[].
- **Recurrence:** Task wants “same category/asset in last 90 days” → recurrenceFlag and priority boost. Requires querying past work_orders (or issues) by property_id and category/asset; no such logic today.

---

## 4. PRIORITY SCORING

- **Task:** priorityScore + band from user urgency, category, seasonality, recurrence, asset type.
- **Current:** No numeric score or band; only severity (low/medium/high/urgent) and category.
- **Gap:** Add a small scoring model (e.g. 0–100 or 1–5) and band (e.g. P1–P4), computed in triage or on issue create/update. Additive only.

---

## 5. WORK ORDER FLOW

- **Task:** Issue → “Create Work Order”; optionally auto-create draft after triage if severity ≥ threshold; user confirms before contractor assignment.
- **Current:** No issue; create work order directly; assignment via PATCH; no draft state.
- **Safest path:**  
  - If issues are introduced: “Create Work Order” from issue creates a work order with issue_id (and optional draft status).  
  - Keep existing “create work order” from client/tenant/admin as-is; optionally allow it to create an issue first then WO, or keep direct WO as a bypass.  
  - Add “draft” status to work orders and, if desired, auto-create draft when triage severity ≥ threshold; require explicit user step to “confirm” or “assign” before contractor assignment.

---

## 6. CONTRACTOR RECOMMENDATION

- **Task:** If CONTRACTOR_NETWORK: recommend by trade, region, credential match, SLA performance, pricing benchmark; no auto-assign.
- **Current:** Contractors have trade_types, areas_served, vetted; list by client. No recommendation endpoint, no SLA performance, no pricing, no credential matching.
- **Gap:** Add a recommendation endpoint (e.g. by work_order_id or by trade + property/region) that filters/scores contractors; add over time: SLA performance (e.g. from work order completion vs sla_complete_by), pricing if available, credentials if stored. **Do not** auto-assign; keep current “admin picks from list” behaviour.

---

## 7. SLA MONITORING

- **Task:** Set slaDueAt from triage; checker job marks “breach risk” and “breached”; surface in dashboard/property overview.
- **Current:** work_orders have sla_respond_by, sla_complete_by (fixed 24h / 5 days at create). No job that sets breach_risk or breached on work_orders. (Other SLA breach logic exists for leads and compliance recalc.)
- **Gap:** Add a scheduled job that: finds work orders with status not in (COMPLETED, CANCELLED) and (sla_respond_by or sla_complete_by) past or near; updates a field such as sla_breach_risk_at and sla_breached_at (or single sla_status). Add dashboard/property overview widgets that show counts or list (e.g. “at risk” / “breached”). Additive; reuse existing SLA patterns where possible.

---

## 8. COMPLETION EFFECTS

- **Task:** On work order completed: append property timeline event; append asset history event; update contractor performance; trigger risk recalculation if linked asset.
- **Current:**  
  - **Asset history:** `update_work_order(..., status=COMPLETED)` calls `record_maintenance_event` (predictive_maintenance_service) → maintenance_events.  
  - **Timeline:** Property timeline (property_timeline_service) currently includes “Work order created” from work_orders list; it does **not** include “Work order completed” as a distinct event (no completion event in ledger/score_log).  
  - **Contractor performance:** Not implemented; no counters or stats per contractor.  
  - **Risk recalculation:** Predictive insights are computed from assets/events; no explicit “trigger risk signal recalculation” on completion (could be implicit if maintenance_events feed insights).
- **Gap:**  
  - Add a “work order completed” event to the property timeline (e.g. new event source or write to a small completion_events collection that the timeline merges).  
  - Add contractor performance (e.g. jobs_completed, jobs_on_time, avg_completion_hours) and update on completion.  
  - Optionally call predictive/risk refresh for the property (or rely on existing event-driven logic).

---

## 9. UI REQUIREMENTS

| Task requirement | Current | Gap |
|------------------|--------|-----|
| Issue reporting form (tenant + internal) | Tenant: report-maintenance (description, property). Client: “Report issue” modal (property, description, category, severity). Admin: create WO form. | Add reportedUrgency, photos if needed; keep tenant-friendly and internal-friendly. |
| Issues page with filters | ClientIssuesPage = open work orders (OPEN/ASSIGNED) + “Report issue”. No filters by category/severity/property/date. | Add filters; if issues exist, show issues with status filter. |
| Issue detail: triage result, reasoning, “Create work order” | **None.** No issue detail screen. | New screen: issue by id, triage result, reasoning[], “Create Work Order” button. |
| Work order detail: lifecycle statuses | **None.** Admin list has inline status change and assign; no dedicated WO detail page. | New screen: WO by id, full lifecycle, status history if stored, assign contractor, resolution. |
| Contractor recommendation panel | **None.** Admin picks from dropdown in list. | Panel (e.g. on WO detail or assign modal) calling recommendation API; show recommended + “Assign” (no auto-assign). |
| Deep links to property / timeline | Links from dashboard and risk signals to property; timeline tab on property. | Ensure issue/WO detail link to property and timeline; already partially there. |

---

## 10. FEATURE FLAGS

- **Task:** MAINTENANCE_WORKFLOWS and CONTRACTOR_NETWORK where applicable.
- **Current:** Both flags exist (ops_compliance_feature_flags). Client/tenant maintenance and contractor list are gated. Admin ops (work orders, contractors) are admin-only; no extra flag check.
- **Recommendation:** Keep as-is. Gate any new “issue” and “recommendation” APIs behind MAINTENANCE_WORKFLOWS / CONTRACTOR_NETWORK as appropriate.

---

## 11. CONFLICTS AND SAFEST OPTIONS

### 11.1 Issue vs work order

- **Conflict:** Task has a two-step flow (issue → triage → work order); codebase has a one-step flow (report → work order).
- **Safest:** Introduce issues **in parallel**: new collection `maintenance_issues`, new endpoints (create issue, list issues, get issue, triage). “Create Work Order” from issue links issue_id to work_order. Keep existing “Report issue” → create work order path working; optionally later make it “create issue then auto-create WO” behind a flag or config so behaviour is controllable.

### 11.2 Naming: orgId vs client_id

- **Conflict:** Task uses orgId; codebase uses client_id everywhere.
- **Safest:** Do **not** rename. Map “orgId” → client_id in docs and any new APIs; keep client_id in DB and APIs.

### 11.3 Work order status set

- **Conflict:** Task uses draft | assigned | scheduled | in_progress | awaiting_parts | completed | verified | closed. Current uses OPEN | ASSIGNED | IN_PROGRESS | COMPLETED | CANCELLED.
- **Safest:** Add new statuses **in addition** to existing: e.g. DRAFT, SCHEDULED, AWAITING_PARTS, VERIFIED, CLOSED. Map OPEN→“open”, ASSIGNED→“assigned”, COMPLETED→“completed” in any task-facing docs. Avoid removing or breaking existing status values.

### 11.4 contractorAssignments vs contractor_id

- **Conflict:** Task has first-class assignment records; codebase has a single contractor_id on work_order.
- **Safest:** Add assignment history (e.g. contractor_assignments) when contractor is set/changed; keep contractor_id on work_order for backward compatibility and simple “current” assignment.

---

## 12. TESTS (TASK)

- **Triage rules produce expected severity/contractor/SLA:** Not implemented; add once triage engine exists.
- **Recurrence boosts priority:** Not implemented; add once recurrence is in triage.
- **Work order draft can be created from issue:** N/A today (no issues); add when issue → WO flow exists.
- **Completed work order updates timeline/asset history:** Asset history ✅; timeline ❌ (add completion event and timeline merge).

---

## 13. OUTPUT CHECKLIST (FOR IMPLEMENTATION)

- **Files to add/change (conceptual):**  
  - **Backend:** New or extended: maintenance_issues collection + CRUD; triageResults or embedded triage; triage engine (e.g. triage_service.py); priority scoring; work_order fields (asset_id, issue_id, draft/scheduled/…, cost_estimate_*, resolution_outcome); contractor_assignments + write on assign; work order SLA breach job; completion handler (timeline event, contractor stats); contractor recommendation endpoint.  
  - **Frontend:** Issue create/detail screens; Issues page filters; WO detail screen; contractor recommendation panel; any new fields in forms.

- **New models/endpoints/screens:**  
  - Models: maintenance_issues, triage_results (or embedded), contractor_assignments (optional).  
  - Endpoints: e.g. POST/GET /issues, GET /issues/:id (with triage), POST /issues/:id/create-work-order; GET /work-orders/:id (detail); GET /work-orders/:id/recommend-contractors; PATCH work order (existing, extend with new statuses/fields).  
  - Screens: Issue detail (triage + reasoning + Create WO); Work order detail; Contractor recommendation panel (e.g. in assign flow).

- **Feature flags:** MAINTENANCE_WORKFLOWS (issue reporting, work orders, triage); CONTRACTOR_NETWORK (contractor list, recommendation panel).

- **Live vs prepared for later:**  
  - **Live today:** Work order create/list/update (client, tenant, admin), severity heuristic at create, contractor assign (field), completion → asset event, property timeline “Work order created”.  
  - **Prepared / to implement:** Issues and triage storage, full triage engine and reasoning, priority score/band, draft WO from issue, SLA breach job for work orders, completion → timeline event and contractor stats, contractor recommendation API and UI, issue/WO detail screens, recurrence and seasonality in triage.

---

## 14. RECOMMENDED IMPLEMENTATION ORDER (SAFE, ADDITIVE)

1. **Extend work_orders only (no issues yet):** Add optional asset_id, issue_id, cost_estimate_min/max, resolution_outcome; add statuses DRAFT, SCHEDULED, AWAITING_PARTS, VERIFIED, CLOSED without removing existing ones.
2. **Triage engine (stateless):** Implement `triage_maintenance_issue(issue, property, asset_history)` returning severity, priority_score, sla_hours, recommended_contractor_type, reasoning[]; call it when creating work order (or when creating issue later) and optionally store result (e.g. on issue or in triage_results).
3. **Issues layer:** Add maintenance_issues collection and APIs; optionally make “Report issue” create an issue then auto-create WO (or keep direct WO); add “Create Work Order” from issue and link issue_id.
4. **SLA breach job:** Job that sets sla_breach_risk / sla_breached on work_orders from sla_respond_by / sla_complete_by; surface in admin and optionally property/dashboard.
5. **Completion effects:** On WO completed: write “work order completed” to property timeline (or event store consumed by timeline); update contractor performance (new collection or fields); keep existing asset event.
6. **Contractor recommendation:** Endpoint that returns suggested contractors for a work order (or trade+property); UI panel in assign flow; no auto-assign.
7. **UI:** Issue detail (triage + reasoning + Create WO); WO detail page; filters on Issues page; recommendation panel.

This order avoids big-bang rewrites, keeps existing flows working, and adds the task’s behaviour incrementally.
