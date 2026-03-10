# Property Command Centre – Task vs Codebase Audit

**Task:** Redesign and extend the Property Detail page into an enterprise-grade "Property Command Centre" without breaking existing routes, data, or workflows.

**Audit date:** Based on current codebase state. Purpose: identify what is implemented, what is missing, and any conflicts or duplication risks before implementation.

---

## 1. PROPERTY PAGE STRUCTURE (Tabs)

### Task requirement
Tabs in this order: **1. Overview, 2. Compliance, 3. Maintenance, 4. Evidence, 5. Contractors, 6. Timeline, 7. Risk Signals, 8. Assets.**  
Locked tabs when module not enabled: show locked state with upgrade prompt. Use existing feature-flag pattern.

### Current implementation
- **File:** `frontend/src/pages/PropertyDetailPage.js`
- **Tabs present:** Overview, Compliance, Maintenance, Evidence, Contractors, Timeline, Risk Signals.
- **Tab order:** Matches task except **Assets is missing** (task requires 8th tab).
- **Feature gating:** Maintenance tab only if `hasFeature('maintenance_workflows')`; Contractors only if `hasFeature('contractor_network')`; Risk Signals only if `hasFeature('predictive_maintenance')`. Evidence and Timeline are always shown (no lock).
- **Locked state:** When a feature is off, the **tab is hidden**, not shown as locked. Task asks to "show a locked state with upgrade prompt" for disabled modules.

### Gaps
| Item | Status | Action |
|------|--------|--------|
| **Assets tab** | Missing | Add 8th tab "Assets"; gate by `predictive_maintenance` (assets API is under maintenance/predictive). |
| **Tab order** | Correct except Assets | Insert Assets after Risk Signals. |
| **Locked tabs** | Tabs hidden, not locked | Option A: Keep current (hidden when no feature). Option B: Show all 8 tabs; for disabled features show tab with locked state + upgrade CTA. Task says "show a locked state" – **recommend Option B** for consistency with task and discoverability. |

### Conflict / recommendation
- **Conflict:** Task: "show a locked state with upgrade prompt". Current: hide tab.  
- **Safest option:** Show all 8 tabs in the required order. For tabs that depend on a feature flag, if the feature is disabled render the tab content as a single card: "This feature is not available on your plan" + upgrade CTA (reuse existing `UpgradeRequired` / upgrade pattern if present). Do not remove the current hide behaviour for the **nav items** that are today hidden; instead add Assets and optionally show Maintenance/Contractors/Risk Signals/Assets as visible but locked when disabled.

---

## 2. PROPERTY HEADER

### Task requirement
Summary header with: Property name/address, Property type, Jurisdiction, HMO status, Occupancy status (if available), Compliance score, Maintenance risk, Open work orders count, Next upcoming compliance due item, Last updated.  
Top-right actions: **Upload Evidence**, **Add Issue**, **View Reports**. Compact, executive-style.

### Current implementation
- **Header:** Single card with address (from `address_line_1`, `address_line_2`, `postcode`), and a line of chips: `property_type`, HMO badge, has_gas. No jurisdiction, occupancy, compliance score, maintenance risk, open work orders count, next due, or last updated in the header. No header action buttons.
- **Data available:** `property` from `clientAPI.getProperties()` (property list); `complianceDetail` from `getComplianceDetail(propertyId)` (score, risk_level, last_updated_at); `workOrders.length` for open count. Backend property model (`core.py`) includes `jurisdiction`, `occupancy`; they may not be in the client properties API response.

### Gaps
| Item | Status | Action |
|------|--------|--------|
| Jurisdiction, occupancy in header | Missing | Ensure client properties API returns them; display in header. |
| Compliance score in header | Missing | Already in state (`complianceDetail.score`); add to header. |
| Maintenance risk in header | Missing | Can derive from predictive insights or placeholder "—"; add. |
| Open work orders count in header | Missing | `workOrders` filtered by OPEN/ASSIGNED; add. |
| Next upcoming compliance due | Missing | From `requirements` (sort by due_date, take next); add. |
| Last updated in header | Missing | `complianceDetail.last_updated_at`; add. |
| Upload Evidence button | Missing | Add; link to `/documents?property_id=...` or open upload flow. |
| Add Issue button | Missing | Add; open same create work order modal as Maintenance tab. |
| View Reports button | Missing | Add; link to reports with property context or `/reports`. |

### Recommendation
Extend the existing header card (additive): add one line of key metrics (score, risk, open WOs, next due, last updated) and a row of action buttons (Upload Evidence, Add Issue, View Reports). Keep existing address and chips. Do not remove any existing field.

---

## 3. OVERVIEW TAB

### Task requirement
- **A) Snapshot cards:** Compliance Score, Maintenance Risk, Open Issues, Open Work Orders, Upcoming Compliance Items, Contractor Activity (if applicable).
- **B) Current Alerts:** Cards (e.g. Gas Safety overdue, Boiler risk elevated, Damp issue reported, Invoice pending) with deep-links.
- **C) Recommended Next Actions:** e.g. Upload Gas Safety certificate, Confirm EICR expiry, Create inspection for boiler risk, Assign contractor to open issue.
- **D) Mini timeline preview:** Latest 5 key events (document uploaded, issue created, work order completed, contractor assigned, score changed).  
Answer: "What is happening with this property right now?"

### Current implementation
- Snapshot cards: Compliance score (from complianceDetail), Open work orders (from workOrders, OPEN+ASSIGNED), Risk signals count (from predictiveInsights), Evidence/documents (link). **Missing:** Maintenance Risk as a distinct card, Upcoming Compliance Items as a card, Contractor Activity.
- "Next due / action needed": List of requirements with status OVERDUE/EXPIRING_SOON/PENDING/MISSING (up to 5) + "View all requirements". **Partial:** This is requirement-based, not full "Current Alerts" (no gas safety overdue, boiler risk, damp, invoice).
- **No** "Recommended Next Actions" section.
- **No** mini timeline preview (latest 5 events).

### Gaps
| Item | Status | Action |
|------|--------|--------|
| Maintenance Risk card | Missing | Add; use predictive risk or "—" if no data. |
| Upcoming Compliance Items card | Partial | Reframe or add card; already have "Next due / action needed". |
| Contractor Activity card | Missing | Add when `contractor_network`; show count or "View" if backend supports. |
| Current Alerts (gas, boiler, damp, invoice) | Missing | Build from requirements (overdue/expiring) + risk signals + placeholder for invoice; deep-link each to tab/workflow. |
| Recommended Next Actions | Missing | Derive from requirements (upload, confirm expiry) + risk signals (create inspection/WO) + optional assign contractor; list 3–5. |
| Mini timeline (5 events) | Missing | Needs property-scoped timeline (see §8); then show latest 5. |

### Recommendation
Additive only. Add missing snapshot cards (maintenance risk, upcoming compliance, contractor activity). Add an "Current Alerts" section from requirements + risk signals (and later invoice). Add "Recommended Next Actions" from same data. Mini timeline depends on property-scoped timeline endpoint (§8).

---

## 4. COMPLIANCE TAB

### Task requirement
Requirement list for property; status chips (valid/expiring/overdue/missing evidence); due dates; "Fix now" actions; link to evidence; link to score explanation. If requirement impacts score, show badge: Impact High/Medium/Low.

### Current implementation
- Full requirements matrix: Requirement, Evidence status, Expiry date, Days left, Action (View document / Upload, Mark not applicable, Request help). Uses `getEvidenceStatus(r.status)`, `formatDate`, deep-links to `/documents?property_id=...&requirement_id=...`. Score strip and "View change history" above table.
- **Missing:** Explicit "Fix now" label (Upload/View already act as fix). No "Impact: High/Medium/Low" badge per requirement. No explicit link to "score explanation" (could link to compliance-score page or in-page copy).

### Gaps
| Item | Status | Action |
|------|--------|--------|
| Fix now | Partial | Consider renaming or adding "Fix now" to primary action; optional. |
| Impact badge | Missing | Add if backend/catalog provides impact or derive from criticality/weight. |
| Score explanation link | Missing | Add link to /compliance-score or expand in-page. |

### Recommendation
Minimal change. Add optional impact badge if catalog/compliance detail returns per-requirement impact or criticality. Add one "How is score calculated?" link. No removal of existing columns or actions.

---

## 5. MAINTENANCE TAB

### Task requirement
Open issues, open work orders, severity, SLA status, assigned contractor, Create issue button. Allow: create issue, view issue details, open work order detail, filter by status.

### Current implementation
- Work orders list for property (from `getMaintenanceWorkOrders({ property_id })`); status badge; "Add issue" opens create work order modal (description only). No severity column, no SLA status, no assigned contractor column. No filter by status. No issue/work order detail view (no drill-down).

### Gaps
| Item | Status | Action |
|------|--------|--------|
| Severity | Missing | Add column if API returns severity (create form has severity). |
| SLA status | Missing | Add if backend work order model has SLA fields; else "—" or later. |
| Assigned contractor | Missing | Add column if API returns assignee/contractor. |
| Filter by status | Missing | Add status filter (dropdown or chips). |
| View issue/work order detail | Missing | No detail route/modal; link to work order detail if backend has it. |

### Recommendation
Additive. Add columns for severity and contractor when API provides them. Add status filter. SLA and work order detail depend on backend; add placeholders or "—" if not yet available.

---

## 6. EVIDENCE TAB

### Task requirement
Uploaded documents for this property; status (Uploaded/Extracted/Confirmed/Applied); requirement linked; dates extracted/confirmed; Confirm Details action; Download/View. Audit-oriented.

### Current implementation
- Single card: short copy + "Open documents" button → `/documents?property_id=...`. No in-page list of documents, no status, no requirement link, no Confirm Details/Download/View per doc.

### Gaps
| Item | Status | Action |
|------|--------|--------|
| Document list for property | Missing | Call list documents with `property_id` (backend supports it); clientAPI currently has `getDocuments()` with no params – add `getDocuments({ property_id })` or use existing API with param. |
| Status chips (Uploaded/Extracted/Confirmed/Applied) | Missing | Map document status from API; show per row. |
| Requirement linked, dates, Confirm Details, Download/View | Missing | Add table or list; link to requirement; add actions (confirm details → existing Documents flow or API). |

### Recommendation
Additive. Add `clientAPI.getDocuments(property_id)` (or equivalent) and render a table in Evidence tab: document name, status, linked requirement, dates, actions (Confirm details, View, Download). Reuse document status and action logic from DocumentsPage where possible to avoid duplication. If full parity with DocumentsPage is heavy, start with list + link to "Open in Documents" for actions.

---

## 7. CONTRACTORS TAB

### Task requirement
Contractors assigned to this property; job history by contractor; credential status; performance (SLA compliance, rework rate, last used). Allow: assign contractor to issue/WO, view contractor detail. If locked, show upgrade CTA.

### Current implementation
- Single card: copy + "View all contractors" → `/operations/contractors`. No per-property list, no job history, no credentials, no performance, no assign action.

### Gaps
| Item | Status | Action |
|------|--------|--------|
| Contractors assigned to property | Missing | Backend: client contractors list is global; no "assigned to this property" API. Can derive from work orders (assignee_id/contractor_id) if present. |
| Job history, credentials, performance | Missing | Backend may not expose; show placeholder or "—" until API exists. |
| Assign contractor to issue/WO | Missing | Backend: assign is likely admin-side; client may be read-only. Confirm with API. |
| Locked state | Partial | Tab shown only when `contractor_network`; no locked state if tab visible but plan limited. |

### Recommendation
Additive. If backend supports "contractors for property" or "contractors from work orders for property", show list. Otherwise keep current card + "View all contractors" and add one line: "Contractors assigned to this property will appear here when assigned via work orders." Add locked state if task requires showing tab with upgrade when not entitled.

---

## 8. TIMELINE TAB

### Task requirement
Unified chronological stream: evidence uploaded, requirement status changes, issues created, work orders updated, contractors assigned, invoices approved, score changes, provisioning/setup. Each entry: timestamp, event type, description, actor, link to related item. Critical for trust and audit.

### Current implementation
- Placeholder card: "A unified timeline of documents, compliance updates, maintenance, and contractor activity will appear here. Coming soon."

### Gaps
| Item | Status | Action |
|------|--------|--------|
| Property-scoped timeline | Missing | Backend: `GET /portfolio/audit-timeline` is portfolio-wide, no `property_id` filter. Audit logs have `resource_type`, `resource_id`; document/maintenance events may have `property_id` in metadata. Need endpoint: e.g. `GET /portfolio/properties/{property_id}/timeline` returning merged stream (audit_logs where resource_id=property_id or metadata.property_id=property_id + score_change_log + work order events if stored). |
| Event types and links | Missing | Define event types and map to tab/detail links; implement once backend exists. |

### Recommendation
**Backend first.** Add `GET /api/portfolio/properties/{property_id}/timeline` (or equivalent) that returns a unified, chronological list of events for that property (audit_logs, score_change_log, optionally work order updates). Then frontend: replace placeholder with list (timestamp, type, description, actor, link). Do not invent client-side aggregation of multiple endpoints that are not designed for it.

---

## 9. RISK SIGNALS TAB

### Task requirement
Boiler, Damp, Electrical, other heuristic risks. Per signal: risk level, explanation, drivers, last updated, recommended action; buttons: Create inspection, Create work order, Monitor. If feature disabled: locked state + upgrade path. Transparent, rule-based (no "AI magic").

### Current implementation
- Uses `getPredictiveInsights()` and filters to current property. Lists insights with recommendation, detail, risk badge; button "Create work order" (opens Maintenance create with description prefilled). No "Create inspection" or "Monitor". No locked state when tab is hidden (tab only shown when `predictive_maintenance`).

### Gaps
| Item | Status | Action |
|------|--------|--------|
| Risk type (Boiler/Damp/Electrical) | Partial | Insights may have type/asset_type; display explicitly if present. |
| Explanation, drivers, last updated | Partial | `detail` and `recommendation` shown; add drivers and last updated if API provides. |
| Create inspection | Missing | Add button; link to same flow as work order with type "inspection" or placeholder. |
| Monitor | Missing | Add if product defines "Monitor" (e.g. add to watch list); else omit. |
| Locked state | Partial | Same as §1: show tab with locked + upgrade when feature off. |

### Recommendation
Additive. Add "Create inspection" (reuse create WO with category or description). Show risk type and last updated from API if available. Align with task copy (transparent, rule-based).

---

## 10. ASSETS TAB

### Task requirement
Table: Asset | Type | Status | Last Service | Open Issues | Risk. Example types: Main Boiler, Electrical, Roof, Plumbing, Windows/Doors, Damp/Moisture, Smoke/CO Alarm. Allow: basic edit, view linked issues, view linked evidence, open risk signal if exists. Empty state: "Assets will be created automatically as your property setup is completed."

### Current implementation
- **Tab does not exist.** Backend: `GET /client/maintenance/properties/{property_id}/assets` and POST to add asset (gated by PREDICTIVE_MAINTENANCE). `property_assets_service.list_assets` returns list with asset_type, install_date, last_service_date, notes. No "Status", "Open Issues", "Risk" in current asset schema.

### Gaps
| Item | Status | Action |
|------|--------|--------|
| Assets tab | Missing | Add 8th tab; call `clientAPI.getPropertyAssets(propertyId)`; gate by `predictive_maintenance`. |
| Table columns | Partial | Backend has asset_type, install_date, last_service_date, notes. Add Status (derived or placeholder), Open Issues (from work orders linked to asset if backend supports), Risk (from risk signals if linked). |
| Edit, linked issues, linked evidence, risk signal | Missing | Basic edit: use existing add/edit asset API if any; linked issues/evidence/risk depend on backend links. |
| Empty state | Missing | Use task copy when no assets. |

### Recommendation
Add tab. Render table from `getPropertyAssets(propertyId)`. Columns: Asset (name/type), Type, Status (optional), Last Service (last_service_date), Open Issues / Risk as "—" or from related APIs when available. Empty state per task. Do not remove or change existing assets API.

---

## 11. DEEP LINKING + CROSS-MODULE BEHAVIOUR

### Task requirement
Consistent linking: alert → tab; requirement row → Evidence or Maintenance; risk signal → work order creation; timeline entry → issue/document/requirement; asset row → linked issues.

### Current implementation
- Overview cards link to other tabs (`setActiveTab(TAB_*)`) or `/documents?property_id=`. Risk Signals "Create work order" opens Maintenance create with prefilled description. Compliance requirement rows link to documents with property_id and requirement_id. No timeline or assets yet.

### Gaps
- Timeline and Assets not yet implemented; deep links from those will follow.
- Alert cards on Overview (when added) should link to relevant tab or workflow; same for Recommended Actions.

### Recommendation
When adding Current Alerts and Recommended Next Actions, every card/row must have a clear target (tab or URL). Reuse existing pattern (setActiveTab or navigate).

---

## 12. FEATURE FLAG / PLAN LOCKING

### Task requirement
Gate: Contractors, Risk Signals, some Maintenance actions. Show tab if feature exists; lock with upgrade prompt if not entitled. Do not expose backend data without entitlements.

### Current implementation
- Maintenance, Contractors, Risk Signals tabs are **hidden** when feature is off. API calls are guarded (e.g. loadWorkOrders only when `hasFeature('maintenance_workflows')`). No "locked" tab content with upgrade CTA.

### Conflict
- Task: "show the tab if the feature exists; but lock access with upgrade prompt if not entitled."
- Current: tab is hidden when feature off.

### Recommendation
**Safest:** Keep existing API guards. For UI, either (A) keep hiding tabs when feature is off (no change), or (B) show all 8 tabs and for disabled features show tab content as locked + upgrade CTA. If product prefers discoverability, choose (B); otherwise (A). Do not expose locked-tab data from backend.

---

## 13. BACKEND SUPPORT

### Task suggestion
Optional: `GET /api/properties/:propertyId/command-centre` with aggregated response (propertySummary, compliance, maintenance, evidence, contractors, timeline, riskSignals, assets).

### Current implementation
- **No single command-centre endpoint.** Data comes from: `getProperties()` (then find property), `getComplianceDetail(propertyId)`, `getPropertyRequirements(propertyId)`, `getMaintenanceWorkOrders({ property_id })`, `getPredictiveInsights()` (then filter by property), `getScoreHistory(propertyId)`. Documents: list with property_id not used from property page. Assets: `getPropertyAssets(propertyId)`. Timeline: no property-scoped endpoint.

### Recommendation
- **Option A (preferred for now):** Do not add a new aggregate endpoint. Use existing endpoints; frontend already composes them. Reduces backend change and keeps single responsibility per API.
- **Option B:** Add `GET /client/properties/{property_id}/command-centre` (or under portfolio) that aggregates read-only data from compliance, work orders, insights, assets, and optionally timeline. Eases frontend and improves load if many round-trips are an issue. Implement only if product/backend agree.

If adding a property-scoped **timeline**, a small new endpoint is needed (e.g. `GET /portfolio/properties/{property_id}/timeline`) because current audit-timeline is portfolio-wide.

---

## 14. UX / DESIGN RULES

### Task requirement
Clean enterprise card layout; no flashy animations; clarity and actionability; mobile responsive; consistent badges, tables, action buttons; same styling language as rest of product.

### Current implementation
- Property page uses Card, CardContent, CardHeader, CardTitle, Button, table, badges. Styling consistent with client dashboard (electric-teal, midnight-blue, gray neutrals). No animation. Responsive (flex-wrap, grid). Matches task.

### Recommendation
Keep current design system when adding new sections. No new frameworks or styles.

---

## 15. ACCEPTANCE CRITERIA (SUMMARY)

| Criterion | Status | Notes |
|-----------|--------|--------|
| Property page has all required tabs | Partial | Missing Assets; order correct for 7 tabs. |
| Overview answers "what's happening right now?" | Partial | Snapshot + next due exist; missing alerts, recommended actions, mini timeline. |
| Tabs link together logically | Done | Overview → other tabs; Risk → Create WO. |
| Locked features show upgrade prompt | Partial | Tabs hidden, not locked. |
| Assets tab exists and supports future predictive | Missing | Add Assets tab; use existing assets API. |
| Timeline is unified and useful | Missing | Backend + frontend needed. |
| No existing property route broken | Done | Route unchanged; additive only. |

---

## 16. FILES CHANGED (CURRENT)

- **Frontend:** `frontend/src/pages/PropertyDetailPage.js` (tabs, header, Overview, Compliance, Maintenance, Evidence, Contractors, Timeline, Risk Signals).
- **Routes/endpoints:** None modified for property page; existing: `GET /portfolio/properties/{id}/compliance-detail`, `GET /portfolio/properties/{id}/score-history`, `GET /client/maintenance/work-orders?property_id=`, `GET /client/maintenance/predictive-insights`, `GET /client/maintenance/properties/{id}/assets`, `GET /client/properties/{id}/requirements`, etc.

---

## 17. PROPOSED CHANGES (SAFEST / ADDITIVE)

1. **Tabs:** Add **Assets** tab (8th); optionally show **locked** state for Maintenance, Contractors, Risk Signals, Assets when feature is off (upgrade CTA) instead of hiding.
2. **Header:** Enrich with: compliance score, maintenance risk (or "—"), open WOs count, next due, last updated; add **Upload Evidence**, **Add Issue**, **View Reports**.
3. **Overview:** Add snapshot cards (maintenance risk, upcoming compliance, contractor activity); add **Current Alerts** (from requirements + risk signals); add **Recommended Next Actions**; add **mini timeline** when property-scoped timeline API exists.
4. **Compliance:** Optional impact badge and score explanation link; keep existing matrix and actions.
5. **Maintenance:** Add severity, contractor, status filter when API supports; add SLA/detail when backend ready.
6. **Evidence:** Add document list for property (`getDocuments` with property_id); table with status, requirement, dates, actions (Confirm details, View, Download).
7. **Contractors:** Keep or enhance with "assigned to this property" when backend supports; locked state if tab shown but not entitled.
8. **Timeline:** New backend endpoint for property-scoped timeline; then replace placeholder with unified stream and links.
9. **Risk Signals:** Add "Create inspection"; show type/drivers/last updated if API provides; locked state if required.
10. **Assets:** New tab; table from `getPropertyAssets`; columns and empty state per task; edit/linked issues when backend supports.
11. **API:** Add `clientAPI.getDocuments({ property_id })` (or equivalent) for Evidence tab. Optional: `GET /portfolio/properties/{id}/timeline` and/or aggregate command-centre endpoint.

---

## 18. CONFLICTS AND SAFEST OPTIONS

| Conflict | Safer option |
|----------|----------------|
| Tabs hidden vs show locked | Either keep hidden, or show all 8 tabs with locked content + upgrade CTA for disabled features. Document choice. |
| Single aggregate endpoint vs multiple | Keep multiple existing calls unless product requests one aggregate; add only property-scoped timeline endpoint if timeline is required. |
| Evidence: full in-page vs link to Documents | Add in-page list + key actions; keep "Open in Documents" for full workflow to avoid duplicating all DocumentsPage logic. |

No existing property route, data fields, or workflows should be removed or broken; all changes must be additive or refactor-only, with feature flags and entitlements respected.
