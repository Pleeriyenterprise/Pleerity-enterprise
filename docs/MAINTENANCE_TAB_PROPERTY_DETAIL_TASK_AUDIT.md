# Maintenance Tab (Property Detail) – Task vs Codebase Audit

**Task:** Implement the Maintenance tab for the Property Detail page as an enterprise-grade issue and work order control workspace.

**Audit purpose:** Identify what is implemented, what is missing, how it was implemented, and any conflicts with the safest option. **No implementation in this document** – audit only.

**References:** `PropertyDetailPage.js` (Maintenance tab), `client_maintenance.py`, `maintenance_service.py`, `maintenance_issues_service.py`, `maintenance_triage.py`, `job_runner.py` (SLA breach job), `ClientIssuesPage.js`, `docs/MAINTENANCE_INTELLIGENCE_FLOW_TASK_AUDIT.md`.

---

## 1. EXECUTIVE SUMMARY

| Task section | Implemented | Missing / partial |
|--------------|-------------|-------------------|
| **§1 Tab purpose** | Tab exists; answers “work orders” only. | Issues not shown; no “what issues are open”, “which assets”, “which contractors”, “SLA status”, “historically” in one place. |
| **§2 Tab structure** | Single “Work orders” list + “Add issue” (creates WO). | No summary row (A), no Issues queue (B), no separate Work Orders queue with full columns (C), no SLA/Breach panel (D), no Recurring/repair history (E). |
| **§3 Summary row** | — | No cards: Open Issues, Draft WOs, Active WOs, SLA Breaches, High Severity, Last Activity. |
| **§4 Issues queue** | Backend: issues API + triage; ClientIssuesPage shows issues. | Property Detail tab does **not** load or display issues; no table, filters, or actions (View, Triage, Create WO, Link Asset, Close). |
| **§5 Issue detail** | Backend: GET issue with triage. | No issue detail drawer/page on Property Detail; no full description, triage reasoning, suggested asset, related WO, timeline. |
| **§6 Work orders queue** | List of WOs (description, created_at, status); “Add issue” creates WO. | No columns: title, linked issue, asset, severity, SLA due, contractor, last updated; no filters; no actions (View, Update status, Assign, Mark completed, Verify). |
| **§7 Work order detail** | Backend: GET work order; recommend-contractors. | No WO detail view/drawer on Property Detail; no header, linked issue, asset, contractor, status timeline, notes, cost, completion outcome. |
| **§8 SLA/Breach panel** | Backend: work orders have sla_respond_by, sla_complete_by, sla_breach_risk_at, sla_breached_at; job sets breach flags. | No SLA/Breach panel in UI; no “nearing breach”, “breached”, “next deadline”, quick actions. |
| **§9 Recurring / repair history** | Backend: triage has recurrence_flag; risk_signal_service has recurring-repairs rules. | No “Recurring Issues & Repair History” section; no API returning recurringPatterns for property; no UI. |
| **§10 Triage integration** | Backend: triage on issue create (severity, priority_score, sla_hours, reasoning, recommended_contractor_type); stored in issue.triage. | Not surfaced on Property Detail (no issue list/detail). ClientIssuesPage can show issues but not triage reasoning in detail. |
| **§11 Asset linkage** | Backend: issues and work_orders have asset_id; inference from category on issue create. | Property Maintenance tab does not show asset column or “Unlinked” / “Link Asset”; no CTA. |
| **§12 Contractor linkage** | Backend: work_orders have contractor_id; recommend-contractors endpoint; contractor_assignments on update. | No assignment from Property Detail; no “assigned contractor” in WO list; no deep link to Contractors tab; no “Recommended contractors” in WO detail. |
| **§13 Risk signal linkage** | Backend: risk signals reference asset/issue context; work orders can be created from risk signal. | No “Created from Boiler Risk Signal” badge; no deep link to Risk Signals tab; no “Recurring issue may affect risk score” on Property Detail. |
| **§14 Backend** | GET /client/maintenance/issues?property_id=, GET /client/maintenance/work-orders?property_id=; no unified property maintenance endpoint. | No GET /api/properties/:id/maintenance with summary + issues + workOrders + recurringPatterns. Task suggests unified endpoint; current is separate calls. |
| **§15 Feature flag** | Locked state when MAINTENANCE_WORKFLOWS disabled (UpgradePrompt). | Aligned. |
| **§16 Empty states** | “No work orders… Use Add issue to create one.” Single CTA. | No “Add Issue” vs “Create Work Order” distinction; no “View Assets” / “Browse Contractors” per task. |
| **§17 Design** | Simple list; no severity/status badges, no separation of Issues vs Work Orders. | Enterprise structure, badges, separation, mobile, drawers not implemented on this tab. |
| **§18 Acceptance** | Tab shows work orders only; locked state works. | Summary, issue queue, WO queue, SLA panel, recurring section, triage visibility, asset/contractor linkage not present on Property Detail. |

---

## 2. CURRENT MAINTENANCE TAB IMPLEMENTATION (Property Detail)

**Location:** `PropertyDetailPage.js`, block `activeTab === TAB_MAINTENANCE && hasFeature('maintenance_workflows')`.

**Data loaded:** `getMaintenanceWorkOrders({ property_id: propertyId, limit: 100 })` only. **Issues are not loaded.**

**UI:**
- Title: “Work orders” with button “Add issue”.
- “Add issue” opens a modal: description (required), no category/severity/asset in UI (form state has category/severity but createMaintenanceWorkOrder is called with description, property_id, category, severity).
- List: `<ul>` of work orders; each row: description, “Created {date} · {status}”; status badge (COMPLETED green, CANCELLED gray, else amber).
- Empty state: “No work orders for this property. Use ‘Add issue’ to create one.”
- No summary row, no issues list, no SLA panel, no recurring section, no issue or WO detail drawer.

**Backend (existing):**
- **Issues:** `maintenance_issues` collection; create (with triage), list (property_id, status, category, severity), get (by issue_id), create-work-order-from-issue. Triage: severity, priority_score, sla_hours, recommended_contractor_type, reasoning[].
- **Work orders:** `work_orders` with asset_id, issue_id, status (OPEN, ASSIGNED, IN_PROGRESS, COMPLETED, CANCELLED, DRAFT, SCHEDULED, etc.), sla_respond_by, sla_complete_by, sla_breach_risk_at, sla_breached_at, contractor_id, cost_estimate_min/max, resolution_outcome; list, get, update (status, contractor_id, etc.); recommend-contractors by work_order_id.
- **SLA:** `run_work_order_sla_breach_job` sets sla_breached_at and sla_breach_risk_at.
- **Contractor:** contractor_id on WO; contractor_assignments inserted on update; recommend-contractors endpoint (CONTRACTOR_NETWORK).

**Conflict (task vs current flow):**  
Task expects **Issues** (intake/triage) and **Work Orders** (execution) as distinct. Property Detail “Add issue” currently **creates a work order directly** (createMaintenanceWorkOrder), not an issue. So the tab behaves as “work orders only” with a mislabelled “Add issue” that creates a WO. The **safest option** is to keep the existing “Add issue” → work order path as one flow (e.g. “Quick report” or “Add work order”), and **add** a proper Issues queue and “Report issue” that creates an issue (then “Create work order” from issue). Do not remove or blindly replace the current flow without product decision.

---

## 3. CONFLICTS AND SAFEST OPTIONS

| Topic | Task | Current | Safest option |
|-------|------|--------|----------------|
| **Unified endpoint** | GET /api/properties/:propertyId/maintenance → summary, issues, workOrders, recurringPatterns. | Separate GET issues?property_id= and GET work-orders?property_id=. | **Option A:** Add GET /client/maintenance/properties/:property_id/maintenance that aggregates summary + issues + work_orders (and optionally recurring from risk/analytics). **Option B:** Keep separate calls; frontend fetches issues and work orders by property_id and builds summary client-side. Prefer A for one round-trip and consistent summary; B is additive and avoids new endpoint. |
| **“Add issue” behaviour** | Issue intake → triage → then “Create work order”. | “Add issue” creates work order directly. | Keep current “Add issue” as **quick path** (create WO). Add **“Report issue”** that calls createMaintenanceIssue; show issues queue with “Create work order” per issue. Label clearly: e.g. “Add work order” vs “Report issue” so both paths exist without breaking existing behaviour. |
| **Issue statuses** | New, Triaged, Monitoring, Ready for Work Order, Closed. | Backend: new, triaged, monitoring, ready_for_work_order, closed. | Already aligned. |
| **Work order statuses** | Draft, Assigned, Scheduled, In Progress, Completed, Verified, Closed. | Backend: OPEN, ASSIGNED, IN_PROGRESS, COMPLETED, CANCELLED, DRAFT, SCHEDULED, AWAITING_PARTS, VERIFIED, CLOSED. | Map OPEN→Active, ASSIGNED→Assigned; show existing statuses; add Verified/Closed in UI if not already. No schema change required. |
| **SLA due** | Single slaDueAt. | sla_respond_by, sla_complete_by. | Keep both; for “SLA due” display use sla_complete_by (or “Respond by” / “Complete by” in panel). No breaking change. |
| **Recurring patterns API** | recurringPatterns in response. | No property-scoped recurring API; risk_signal_service has recurring rules for signals. | Add optional “recurring” aggregation (e.g. by property: same category/asset in last 12 months, count) in unified endpoint or a small service; or derive from existing risk signals / work order history. Do not duplicate risk signal logic; reuse or expose a read-only view. |

---

## 4. WHAT EXISTS ELSEWHERE (REUSE)

- **ClientIssuesPage** (Operations → Issues): loads both work orders and issues; filters (property, status, category, severity); can create issue or work order; shows issues and open WOs. Logic and API usage can be reused for the Property Detail Maintenance tab (load issues + WOs by property_id, filters, create issue, create WO from issue).
- **Assets tab:** same page; “View issues” links to Maintenance tab. Asset linkage (asset_id) and “View issues” per asset already exist; Maintenance tab can show asset column and “Link Asset” using existing asset list.
- **Risk Signals tab:** same page; deep link from Maintenance to Risk Signals tab is a navigation constant.
- **Contractors:** getRecommendContractors(workOrderId) exists; Contractors tab or deep link can be reused.
- **Timeline:** property_timeline_service includes work_orders; timeline can show WO created/completed if extended; issue events could be added later.

---

## 5. FILES AND ENDPOINTS

**Existing (no change required for audit):**
- **Backend:** `routes/client_maintenance.py` (GET/POST issues, GET issue, POST create-work-order-from-issue, GET/POST work-orders, GET work order, GET recommend-contractors). `services/maintenance_issues_service.py`, `maintenance_service.py`, `maintenance_triage.py`. `job_runner.run_work_order_sla_breach_job`.
- **Frontend:** `PropertyDetailPage.js` (Maintenance tab block), `api/client.js` (getMaintenanceWorkOrders, getMaintenanceIssues, getMaintenanceIssue, createMaintenanceIssue, createWorkOrderFromIssue, getMaintenanceWorkOrder, getRecommendContractors).

**To add (for full task):**
- **Backend (optional):** GET /client/maintenance/properties/:property_id/maintenance → summary (openIssues, draftWorkOrders, activeWorkOrders, slaBreaches, highSeverity, lastActivityAt), issues[], work_orders[], recurringPatterns[] (or leave recurring to client/risk).
- **Frontend:** Property Detail Maintenance tab: summary row, Issues queue (table + filters + actions), Work orders queue (table + filters + actions), SLA/Breach panel, Recurring/repair history strip; issue detail drawer; work order detail drawer; empty states per task; asset and contractor columns and CTAs; risk signal badges/links.

---

## 6. MODELS RELIED ON

- **maintenance_issues:** issue_id, property_id, client_id, asset_id, source, category, description, severity, priority_score, status, recurrence_flag, triage { severity, priority_score, sla_hours, recommended_contractor_type, reasoning[] }, created_at, updated_at, etc.
- **work_orders:** work_order_id, property_id, client_id, asset_id, issue_id, description, status, contractor_id, sla_respond_by, sla_complete_by, sla_breach_risk_at, sla_breached_at, cost_estimate_min/max, resolution_outcome, created_at, updated_at, completed_at, etc.
- **contractor_assignments:** work_order_id, contractor_id, assigned_at, assigned_by (written on WO update).
- **property_assets:** for asset labels and “Link asset” (existing).
- **risk_signals:** for “Created from risk signal” and recurring context (existing).

---

## 7. RECOMMENDED ADDITIONS (PRIORITY, NO DUPLICATION)

1. **Load issues on Maintenance tab**  
   Call `getMaintenanceIssues({ property_id: propertyId })` when tab is active (with existing work orders load). Use same feature gate. No new endpoint.

2. **Summary row**  
   Compute from loaded issues + work_orders: open issues (status not closed), draft WOs (status DRAFT), active WOs (OPEN, ASSIGNED, IN_PROGRESS, etc.), SLA breaches (sla_breached_at set), high severity count, last activity (max of issue/wo updated_at). Can be client-side from existing data or from a new summary endpoint.

3. **Issues queue**  
   Table/cards: title (description snippet), category, severity, priority score, asset (resolve asset_id to label or “Unlinked”), source, status, created_at; actions: View, Triage/Edit, Create work order, Link asset, Close. Filters: status, severity, category, source, asset. Reuse ClientIssuesPage patterns.

4. **Work orders queue**  
   Table: description/title, linked issue (issue_id → link or “—”), asset, severity, status, SLA due (sla_complete_by or respond_by), assigned contractor, last updated; actions: View, Update status, Assign contractor, Mark completed, Verify/Close. Filters: status, severity, contractor, SLA risk (e.g. sla_breach_risk_at / sla_breached_at). Reuse existing WO fields.

5. **Issue detail drawer**  
   On “View” issue: GET issue by id; show description, triage (severity, priority, reasoning, recommended contractor type, SLA), suggested/linked asset, related work order if any; actions: Edit, Create work order, Link asset, Close. Reuse getMaintenanceIssue and createWorkOrderFromIssue.

6. **Work order detail drawer**  
   On “View” WO: GET work order; show header, linked issue, asset, contractor, SLA dates, status timeline (from updated_at/history if available), notes, cost, completion outcome; actions: Assign contractor (recommend-contractors), Update status, Mark completed, Verify/Close.

7. **SLA/Breach panel**  
   Filter work_orders (not completed/cancelled) where sla_breached_at set or sla_breach_risk_at set; show list with due time, hours overdue/remaining, link to WO. Data already on WO; no new API required.

8. **Recurring / repair history**  
   Option A: Backend endpoint that aggregates by property (e.g. same category/asset in last 12 months, count); Option B: Use risk signals that already encode “recurring repairs” and show a strip “Recurring issues” with link to Risk Signals tab. B is additive and avoids new analytics.

9. **Empty states**  
   When no issues: “No maintenance issues recorded for this property.” Buttons: Add Issue (create issue), View Assets (switch to Assets tab). When no work orders: “No work orders created yet.” Buttons: Create work order, Browse Contractors (if CONTRACTOR_NETWORK). Differentiate “Add issue” (issue flow) vs “Create work order” (direct WO).

10. **Asset and contractor linkage**  
    Show asset column (and “Unlinked” + “Link asset”); show contractor in WO list; link to Contractors tab; in WO detail show “Recommended contractors” via existing recommend-contractors API. Gate contractor UI by CONTRACTOR_NETWORK.

11. **Risk signal linkage**  
    If issue or WO was created from a risk signal, show badge and link to Risk Signals tab (requires risk_signal_id or origin on issue/WO if stored; otherwise skip or add when backend supports it).

---

## 8. PLACEHOLDER / FALLBACK LOGIC

- **Recurring patterns:** If no dedicated API, show “Recurring issues” strip with “View risk signals” linking to Risk Signals tab, or “No recurring patterns identified” until backend provides data.
- **Contractor:** If CONTRACTOR_NETWORK disabled, hide “Assign contractor” and “Browse Contractors”; show “Contractor network not enabled” or locked state.
- **Triage reasoning:** If issue has no triage or reasoning[], show “—”; otherwise list reasoning bullets.
- **Linked issue on WO:** If issue_id missing, show “—”; else link to issue (e.g. open issue drawer).
- **SLA panel:** If no WOs at risk or breached, show “No SLA breaches or jobs at risk” or collapse panel.

---

## 9. ASSUMPTIONS

- Property Detail remains a single page; Maintenance tab is one tab among many; no tenant portal in scope.
- Existing “Add issue” → create work order flow can stay as a quick path; second path “Report issue” → issue → “Create work order” is additive.
- Summary can be computed client-side from issues + work_orders for this property to avoid breaking existing APIs; optional unified endpoint can be added later.
- Recurring section can initially reuse risk signals or a simple count-by-category/asset; no need to duplicate full risk engine.
- All new UI is behind existing MAINTENANCE_WORKFLOWS (and CONTRACTOR_NETWORK where applicable).
