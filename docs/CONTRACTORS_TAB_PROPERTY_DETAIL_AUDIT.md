# Contractors Tab (Property Detail) – Task vs Codebase Audit

**Task:** Implement the Contractors tab for the Property Detail page as an enterprise-grade contractor assignment and performance workspace.

**Audit purpose:** Identify what is implemented, what is missing, how it was implemented, and any conflicting instructions. Recommend the safest, most professional options. **Do not implement blindly.**

**References:** [CONTRACTOR_MANAGEMENT_TASK_AUDIT.md](CONTRACTOR_MANAGEMENT_TASK_AUDIT.md), PropertyDetailPage.js, client routes (contractors, maintenance), contractor_service, contractor_recommendation.

---

## 1. TAB PURPOSE (Task §1)

**Task asks the tab to answer:**
- Which contractors are available for this property?
- Which have already worked here?
- Who is best suited for a specific job?
- Are they verified / credentialed?
- How have they performed?

**Current state (Property Detail – Contractors tab):**
- **Implemented:** Tab exists; when CONTRACTOR_NETWORK is off → UpgradePrompt. When on → single card: “Contractors assigned to work at this property or with past jobs here will appear in this list” + button “View all contractors” (navigate to `/operations/contractors`).
- **Missing:** No property-scoped contractor data; no summary, no assigned/recent list, no available list, no drawer, no recommendation/assignment panel. Tab does not answer any of the five questions in-context.

**Gap:** The tab is a placeholder. Full purpose requires a property-scoped API and the five sections (summary, assigned/recent, available list, detail drawer, recommendation panel).

---

## 2. TAB STRUCTURE (Task §2)

**Task order:** A) Contractor Summary Row → B) Assigned / Recent Contractors → C) Available Contractors List → D) Contractor Detail Drawer → E) Recommendation / Assignment Panel.

**Current structure:** One card with short text and one CTA. No A–E.

**Gap:** All five sections are missing.

---

## 3. CONTRACTOR SUMMARY ROW (Task §3)

**Task:** Cards: Total contractors available, Assigned to this property, Verified, Active jobs, Avg rating, Best match available.

**Current:** Not present. No endpoint returns these counts for a property.

**Backend:** No `GET /api/client/properties/:propertyId/contractors` or equivalent. Client has `GET /api/client/contractors` (list for client, not property-scoped). Recommendation is work-order–scoped: `GET /api/client/maintenance/work-orders/:workOrderId/recommend-contractors`.

**Gap:** Need property-scoped endpoint (or derived from existing list + work orders + assignments) that returns `summary: { totalAvailable, assignedHere, verified, activeJobs, avgRating, bestMatchAvailable }`.

---

## 4. ASSIGNED / RECENT CONTRACTORS (Task §4)

**Task:** Contractors connected to this property via past jobs or active assignments. Fields: name, trade, last job, last used, current assignment status, performance summary, actions (View / Reassign / Open Jobs).

**Current:** No property-scoped “recent/assigned” list. Data exists in: work_orders (property_id, contractor_id, assigned_at, completed_at), contractor_assignments (work_order_id, contractor_id, assigned_at). contractor_service has no function that returns “contractors for property X”.

**Gap:** Need to derive or add “recent/assigned contractors for property” (e.g. from work_orders + contractor_assignments joined to contractors) and expose in property-scoped API.

---

## 5. AVAILABLE CONTRACTORS LIST (Task §5)

**Task:** Table/cards: Name, Trade, Region, Credentials, Verified, SLA compliance, Rating, Avg response time, Benchmark fit, Source type (My Contractor / Network / Marketplace), filters (trade, region, verified only, source, recommended only).

**Current:** Client has `GET /api/client/contractors` (list_contractors_for_client) with optional source_type, vetted_only, skip, limit. No property_id; no SLA/rating/rework on response unless contractor doc is extended. Contractor doc has: rating_average, job_count, sla_compliance_rate, rework_rate (all optional; rework_rate never computed). contractor_performance has jobs_completed, jobs_on_time.

**Gap:** Use existing list for “available”; optionally filter/prioritise by property postcode/region. Add filters (trade, region, verified, source_type) if not already in API. Expose SLA/rating from contractor or contractor_performance. “Benchmark fit” and “price from price_books” require price_books (see §13).

---

## 6. CONTRACTOR DETAIL DRAWER (Task §6)

**Task:** Drawer: company name, contact, trade, region, credentials, insurance, source type, verified, job count, SLA compliance, rework rate, rating, linked jobs for this property, notes/tags.

**Current:** No drawer on Property Detail. Client can get one contractor via admin-style GET only from ops; client has no GET /contractors/:id. Contractor doc already has company_name, phone, email, trade_types, region, credentials, insurance_details, vetted, rating_average, job_count, sla_compliance_rate, rework_rate (rework_rate never set).

**Gap:** Add client GET /contractors/:contractor_id (or reuse existing if client can call it) for drawer. Enrich with “linked jobs for this property” from work_orders (property_id, contractor_id). Show rework_rate only when computed (see §Rework).

---

## 7. RECOMMENDATION / ASSIGNMENT PANEL (Task §7)

**Task:** If property has open issue / draft work order / risk signal with recommended inspection, show “Recommended Contractors” panel. Labels (Best Match, Best Value, Fastest Response), score, reasons, trade, rating, SLA, benchmark fit, assign button. Use recommendation engine if it exists.

**Current:** Recommendation engine exists: `contractor_service.recommend_contractors_for_work_order(work_order_id, client_id, limit)`. Used by `GET /api/client/maintenance/work-orders/:work_order_id/recommend-contractors`. Returns contractors with score, reasons, recommendation_label, etc. No property-level “recommended for this property” without a work order; so panel should be shown when there is an open WO (or draft) and then call recommend-contractors for that WO.

**Gap:** Frontend: when property has open/draft work order(s), show recommendation panel and call existing recommend-contractors for the chosen WO. Do not show randomly; use existing endpoint. Hide panel when no open WO / recommendation engine disabled (task §11).

---

## 8. ASSIGNMENT FLOW (Task §8)

**Task:** On Assign: create contractorAssignment linked to workOrder; update workOrder status to Assigned; update timeline; notify contractor (if email flow exists or create it). No auto-dispatch; user confirms. If no work order: allow “Create Work Order + Assign” only if maintenance workflows enabled.

**Current:**
- **Admin:** PATCH `/api/admin/ops/work-orders/:id` with contractor_id updates work order and records contractor_assignments (in maintenance_service.update_work_order). Timeline already shows “Contractor assigned” from work_orders. **No contractor notification on assign.**
- **Client:** No PATCH work order in client API. Client can list work orders, create work order, get recommend-contractors for a WO, but **cannot assign** contractor from client portal (only admin can).

**Conflict:** Task implies landlord/user assigns from the tab; current implementation allows only admin to assign. CONTRACTOR_MANAGEMENT_TASK_AUDIT states “Admin and client can assign” but client routes do not expose PATCH work order.

**Recommendation (safest):** Add **client** PATCH for work order assignment only: e.g. `PATCH /api/client/maintenance/work-orders/:work_order_id` with body `{ contractor_id }` (and optionally `status`), scoped to client’s own work orders. Reuse maintenance_service.update_work_order internally. Then implement contractor notification on assign (email to contractor when contractor_id and email exist). “Create Work Order + Assign” = create WO then call assign in one flow (optional UX).

---

## 9. CONTRACTOR PERFORMANCE SUMMARY (Task §9)

**Task:** Show where available: Job count, Avg rating, SLA compliance %, Rework rate, Avg completion time, Last used date. Do not fake; show “No job history yet” if unavailable.

**Current:** contractor_performance has jobs_completed, jobs_on_time, last_used_at (updated on WO completion). contractor doc has rating_average (from contractor_ratings), job_count, sla_compliance_rate, rework_rate. job_count/sla_compliance_rate are synced from contractor_performance in maintenance_service._update_contractor_performance_on_completion. **rework_rate is never computed.** Avg completion time is not stored.

**Gap:** Rework rate: define as “follow-up work order for same property within N days after completion”. Compute from work_orders (same property_id, same contractor_id, created_at within N days of previous completed_at). Update contractor.rework_rate periodically or on WO completion. Avg completion time would require storing completed_at − assigned_at per WO and aggregating (optional/future).

---

## 10. CONTRACTOR ENTRY SUPPORT (Task §10)

**Task:** Support (A) My Contractors, (B) Network Contractors, (C) Marketplace (approved self-registered). “Add Contractor” opens existing or new contractor creation form.

**Current (from CONTRACTOR_MANAGEMENT_TASK_AUDIT and code):**
- **A) Landlord-added:** POST /api/client/contractors exists (create_contractor_landlord); source_type=landlord_added, client_id set. **Live.**
- **B) Network:** POST /api/admin/ops/contractors/network exists; client_id=null, vetted=true, source_type=platform_network. **Live.**
- **C) Marketplace:** Self-registration POST (public) exists; CONTRACTOR_SELF_REGISTRATION_ENABLED env; approve via PATCH .../approve. **Live (flag-gated).**

Contractors tab has no “Add Contractor” button; client can add from ClientContractorsPage (/operations/contractors). Tab could add same CTA that navigates to add flow or opens a modal.

**Gap:** Add “Add Contractor” to Contractors tab (navigate to /operations/contractors or open add form). No conflict.

---

## 11. FEATURE FLAG / PLAN BEHAVIOUR (Task §11)

**Task:** If contractor feature disabled → locked state + upgrade CTA. If enabled but predictive/recommendation not → show list normally, hide recommendation panel. Flags: CONTRACTOR_NETWORK, CONTRACTOR_SELF_REGISTRATION, MAINTENANCE_WORKFLOWS.

**Current:** Tab shows UpgradePrompt when `!hasFeature('contractor_network')`. When CONTRACTOR_NETWORK is on, a single card is shown. No distinction for “recommendation engine off”; recommendation is driven by recommend-contractors endpoint (no separate predictive flag for contractors).

**Gap:** Align locked state with task. When CONTRACTOR_NETWORK is off, current behaviour is correct. When on, show full tab (summary, lists, drawer, panel). Recommendation panel visibility can depend on “has open work order” and CONTRACTOR_NETWORK + MAINTENANCE_WORKFLOWS (recommend endpoint requires both). CONTRACTOR_SELF_REGISTRATION affects only who can register; tab can show marketplace contractors when visible (approved only).

---

## 12. PROPERTY CONTEXT (Task §12)

**Task:** Filter/prioritise by property postcode/region, required trade, asset type if issue/WO exists, property’s job history. If no issue/WO: show general available contractors for region; show recent for this property first.

**Current:** list_contractors_for_client has no property_id. recommend_contractors_for_work_order uses property postcode/region for scoring. No “contractors for property” aggregation.

**Gap:** New or extended endpoint that accepts property_id and returns summary + recent/assigned + available (prioritised by property postcode/region and recent use at this property). Reuse list_contractors_for_client and work_orders/assignments for property to build “recent/assigned” and “available” with ordering.

---

## 13. BACKEND EXPECTATIONS (Task §13)

**Task suggests:** GET /api/properties/:propertyId/contractors with response `{ summary, recentContractors, availableContractors, recommendedContractors }`. Reuse GET /api/work-orders/:id/recommend-contractors.

**Current:** No GET /api/client/properties/:propertyId/contractors. Client prefix is /api/client; so suggested path would be GET /api/client/properties/:propertyId/contractors. recommend-contractors is GET /api/client/maintenance/work-orders/:work_order_id/recommend-contractors. **Reuse recommend endpoint;** add property-scoped endpoint that returns summary + recent + available; recommendedContractors can be empty unless frontend passes a work_order_id and calls recommend-contractors separately (or endpoint accepts optional work_order_id and fills recommendedContractors when provided).

**Recommendation:** Add GET /api/client/properties/:property_id/contractors (or GET /api/client/maintenance/properties/:property_id/contractors to keep under maintenance/contractor namespace). Response: summary (totalAvailable, assignedHere, verified, activeJobs, avgRating, bestMatchAvailable), recentContractors (from WOs for this property), availableContractors (list_contractors_for_client, optionally ordered by recent use at property). recommendedContractors: only when optional work_order_id is provided, call recommend_contractors_for_work_order and return; else [].

---

## 14. EMPTY STATES (Task §14)

**Task:** No contractors → “No contractors are available for this property yet.” + Add Contractor + Browse Network Contractors. Feature locked → clear locked state and upgrade prompt.

**Current:** When CONTRACTOR_NETWORK is on, content is one card and “View all contractors”. No empty state when list is empty; locked state is UpgradePrompt.

**Gap:** When tab content is implemented, add empty state with message and CTAs. Locked state already present.

---

## 15–16. DESIGN RULES & ACCEPTANCE CRITERIA

**Current:** Tab is a single card. Acceptance: property-relevant contractors (no), recent/assigned (no), available list with filters (no), detail drawer (no), recommendation panel (no), assign flow (admin only; client no), locked state (yes). No existing routes broken.

---

## IMPLEMENTATION REQUESTS (from user)

### Contractor notification on assign

- **Current:** When a work order is updated with contractor_id, maintenance_service.update_work_order writes contractor_assignments and (if COMPLETED) records maintenance event and contractor_performance. **No email/notification to contractor.**
- **Required:** On assignment (contractor_id set), send notification to contractor (e.g. email) if contractor has email. Use existing notification/orchestrator pattern if present; else add a direct send (e.g. Postmark) or a template CONTRACTOR_ASSIGNED in notification_templates and trigger from maintenance_service or route.
- **Safest:** Add template key CONTRACTOR_ASSIGNED (admin-manual or dedicated alias), and in maintenance_service.update_work_order when contractor_id is set (and different from previous), call a small notification helper that looks up contractor email and sends “You have been assigned to work order …” with link/instructions. Do not expose landlord data in email; only work order reference and property address if acceptable.

### Rework rate computation

- **Current:** contractor.rework_rate is never set; contractor_recommendation uses it for scoring.
- **Definition:** Rework rate = follow-up work order (same property, same contractor) within N days of a completed WO. E.g. WO1 completed at T; if WO2 for same property and same contractor has created_at in [T, T+N days], count as rework. Rate = (rework jobs) / (completed jobs) per contractor (or per contractor-client).
- **Required:** Compute rework_rate (e.g. N=30 or 60 days) from work_orders: same contractor_id, same property_id, completed_at of first WO, created_at of second WO within N days. Update contractor.rework_rate (and optionally contractor_performance) when WOs are completed or via a periodic job. Prefer updating on WO completion: after marking WO completed, recompute rework_rate for this contractor (and client) and update contractor doc.
- **Safest:** Add function in contractor_service: compute_rework_rate(contractor_id, client_id) that counts completed WOs and rework WOs (second WO same property+contractor within N days of first completion). Call it from maintenance_service when a work order is completed (status=COMPLETED) and update contractor.rework_rate (and contractor_performance if that table has rework_rate).

### Price/benchmark from price_books

- **Current:** contractor_recommendation._price_fit(wo, c, price_books, weights) returns 0, [], None when price_books is None. contractor_service.recommend_contractors_for_work_order passes price_books=None. No price_books collection or loading.
- **Required:** “Price/benchmark from price_books” implies a price_books structure (e.g. trade/category → benchmark price or range). If price_books exist, load them and pass to recommend; _price_fit should score/return benchmark_fit string.
- **Safest:** Add optional collection or config for price_books (e.g. trade_type / category → benchmark_min, benchmark_max or single benchmark_price). In contractor_service.recommend_contractors_for_work_order, load price_books (if any) and pass to rule_recommend. In _price_fit, if price_books provided and WO has category/trade, compare contractor’s typical price (if ever stored) or leave benchmark_fit as “Benchmark available” without numeric score until cost data exists. Minimal: add price_books collection/index, load in recommend, extend _price_fit to return a simple benchmark_fit label when price_books exist; no fake prices.

---

## CONFLICTS AND SAFEST OPTIONS

| Topic | Conflict | Recommendation |
|-------|----------|----------------|
| Assignment from client | Task implies landlord assigns; only admin can PATCH WO today | Add client PATCH /api/client/maintenance/work-orders/:id for contractor_id (and status) scoped to client’s WOs. Reuse maintenance_service.update_work_order. |
| Contractor notification | Not implemented | Add CONTRACTOR_ASSIGNED notification when contractor_id is set on WO; send to contractor email; no landlord data in body. |
| Rework rate | Field exists, never set | Compute from follow-up WO within N days (e.g. 30); update contractor.rework_rate on WO completion or periodic job. |
| Price/benchmark | price_books not present | Add optional price_books; pass into recommend; extend _price_fit for benchmark_fit label when data exists. |
| orgId / propertyId | Task uses camelCase | Keep client_id, property_id in API/schema. |

---

## OUTPUT REQUIRED (SUMMARY)

### Files to change (for full Contractors tab + the three implementations)

- **Backend**
  - **contractor_service.py:** Add get_contractors_for_property(property_id, client_id) returning summary, recentContractors, availableContractors; add compute_rework_rate(contractor_id, client_id) and call on WO completion; optionally load price_books and pass to recommend.
  - **maintenance_service.py:** On update_work_order when contractor_id is set, trigger contractor notification (CONTRACTOR_ASSIGNED); on status=COMPLETED, call contractor_service to update rework_rate for that contractor.
  - **contractor_recommendation.py:** Extend _price_fit when price_books provided to return a benchmark_fit label (no fake data).
  - **Routes:** Add GET /api/client/maintenance/properties/:property_id/contractors (or /api/client/properties/:property_id/contractors); add PATCH /api/client/maintenance/work-orders/:work_order_id for client (body: contractor_id, optional status).
  - **Notification:** Add CONTRACTOR_ASSIGNED template and send path when contractor is assigned (contractor email only; no landlord PII).
  - **Database / config:** Optional price_books collection or config; indexes if needed.

- **Frontend**
  - **PropertyDetailPage.js:** Contractors tab: summary row, assigned/recent section, available list (with filters), contractor detail drawer, recommendation/assignment panel (when open WO exists), empty state, “Add Contractor” CTA. Call new property contractors endpoint; call recommend-contractors for a chosen WO; call client PATCH work order on Assign.

- **API client (frontend):** getPropertyContractors(propertyId), updateWorkOrderClient(workOrderId, body) if client PATCH is added.

### Endpoints reused or created

| Endpoint | Status | Notes |
|----------|--------|--------|
| GET /api/client/contractors | Reused | List available; optionally used to build property view. |
| GET /api/client/maintenance/work-orders/:id/recommend-contractors | Reused | Recommendation panel. |
| GET /api/client/maintenance/properties/:property_id/contractors | **Create** | summary, recentContractors, availableContractors; optional work_order_id for recommendedContractors. |
| PATCH /api/client/maintenance/work-orders/:work_order_id | **Create** | Client assign (contractor_id, optional status); reuse maintenance_service.update_work_order. |
| POST /api/client/contractors | Reused | Add Contractor. |

### Feature flags used

- **CONTRACTOR_NETWORK:** Tab content and list/assign; already used.
- **MAINTENANCE_WORKFLOWS:** Required for work orders and assign; already used.
- **CONTRACTOR_SELF_REGISTRATION:** Controls self-registration only; tab shows approved marketplace contractors when visible (no change).

### Assignment flow changes

- **Current:** Only admin can set contractor_id on a work order (PATCH /api/admin/ops/work-orders/:id).
- **Change:** Client can set contractor_id (and optionally status) via new PATCH /api/client/maintenance/work-orders/:id for own client’s work orders. Same maintenance_service.update_work_order; add contractor notification when contractor_id is set; timeline already shows “Contractor assigned”.

### Contractor entry models: live vs future-ready

| Model | Status | Notes |
|-------|--------|--------|
| **A) Landlord-added** | Live | POST /api/client/contractors; source_type=landlord_added; client_id set. |
| **B) Platform network** | Live | POST /api/admin/ops/contractors/network; client_id=null; source_type=platform_network. |
| **C) Marketplace (self-registered)** | Live (flag-gated) | Public register; CONTRACTOR_SELF_REGISTRATION_ENABLED; approve via PATCH .../approve. Visible in list when status=active and vetted. |

No redesign of the property page; additive Contractors tab only. Preserve existing routes and maintenance flows.

---

**End of audit.** Implement only after approval; prefer minimal, safe changes for notification, rework rate, and price_books.
