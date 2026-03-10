# Contractor Management System – Task vs Codebase Audit

**Task:** Implement a scalable Contractor Management system with three entry paths (landlord-added, admin-curated network, contractor self-registration behind flag), performance tracking, and marketplace-ready schema.

**Audit purpose:** Identify what exists, what’s missing, and any conflicts so implementation is additive and does not duplicate or break existing behaviour.

---

## 1. EXECUTIVE SUMMARY

| Area | Task expectation | Current state | Gap / conflict |
|------|------------------|---------------|----------------|
| **Naming** | `orgId` for tenant/organisation | **client_id** everywhere (clients = landlords/orgs) | **Conflict:** Task uses orgId; codebase and prior audit (MAINTENANCE_INTELLIGENCE_FLOW_TASK_AUDIT.md) use client_id. Renaming would break all contractor/work order/performance code. |
| **Contractor schema** | sourceType, status, verified, trade enum, credentials, insuranceDetails, ratingAverage, jobCount, slaComplianceRate, reworkRate | **contractors:** contractor_id, client_id, name, trade_types[], vetted, email, phone, company_name, areas_served, notes, created_at, updated_at | Missing: sourceType, status, verified (task) vs vetted (current), credentials, insuranceDetails, rating/jobCount/SLA/rework on contractor doc. Trade is array of strings, not single enum. |
| **Entry 1: Landlord add** | POST /api/contractors, landlord or admin, sourceType=landlord_added, orgId=user org | **No client POST.** Admin only: POST /api/admin/ops/contractors with optional client_id | **Gap:** Landlords cannot add contractors via client API. Only admin can create; admin can set client_id to “assign” to an org. |
| **Entry 2: Admin network** | POST /api/admin/contractors/network, orgId=null, verified=true, status=active | Admin POST /api/admin/ops/contractors with client_id=null and vetted=true achieves same intent; no dedicated “network” endpoint | **Gap:** No dedicated “add to platform network” endpoint; behaviour is achievable via existing create with client_id=null, vetted=true. |
| **Entry 3: Self-registration** | POST /api/contractors/register (public), PATCH approve/reject, feature flag | **None.** No public contractor routes, no CONTRACTOR_SELF_REGISTRATION flag | **Gap:** Full gap. Flag and endpoint need adding; must not break existing. |
| **Selection for WOs** | Query: (orgId match OR platform_network OR approved marketplace), sort by trade/region/SLA/rating | **Implemented:** list_contractors_for_client uses client_id or null; recommend_contractors_for_work_order scores by trade + vetted + contractor_performance | Missing: explicit sourceType filter; status=active filter; optional region sort. |
| **Performance tracking** | On WO complete: jobCount++, completion time, SLA compliance, reworkRate (follow-up within X days) | **Implemented:** contractor_performance: jobs_completed, jobs_on_time, last_used_at; updated on WO completion. **Not** on contractor doc; no reworkRate, no average completion time | **Gap:** Stats live in contractor_performance only; task also wants aggregates on contractor record. Rework rate not implemented. |
| **contractorRatings** | Collection: contractorId, workOrderId, propertyId, rating 1–5, completionSpeed, professionalism, notes | **Does not exist** | **Gap:** New collection and write path (e.g. when WO completed or via rating API); feed into ratingAverage on contractor. |
| **Feature flags** | CONTRACTOR_NETWORK, CONTRACTOR_SELF_REGISTRATION | **CONTRACTOR_NETWORK** exists and is used. **CONTRACTOR_SELF_REGISTRATION** does not exist | Add CONTRACTOR_SELF_REGISTRATION; keep CONTRACTOR_NETWORK. |
| **Admin dashboard** | View by sourceType, trade, region, verification, performance; approve/reject, suspend, edit, job history | Admin has list (client_id, vetted filters), create/edit/delete. No sourceType/status, no approve/reject, no suspend, no job history view | **Gap:** Extend admin UI and API for status, sourceType, approve/reject, suspend; optional job history. |
| **Security** | Contractors never see landlord data unless assigned | No contractor portal; contractors only referenced by id in WOs. No contractor auth. | **Satisfied** for “no contractor access to landlord dashboards.” |
| **Future schema** | priceBooks, contractorAvailability, commissionRate, preferredContractor scoring – prepare only | **None** | Add as optional/future fields or separate doc; do not implement marketplace logic. |
| **Frontend** | Tabs: My Contractors, Network Contractors, Pending Approvals (admin); add form, search/filter, assign to WO | Client: single “Available contractors” list (no tabs, no add). Admin: single list + add/edit; filter by client and vetted. WO assign uses dropdown + recommend panel | **Gap:** Client “Add contractor” and tabs (My vs Network). Admin “Pending Approvals” tab and approve/reject. |

---

## 2. CONFLICTS AND SAFEST OPTIONS

### 2.1 orgId vs client_id

- **Conflict:** Task says `orgId` (nullable); codebase uses **client_id** for organisation (landlord/portfolio).
- **Recommendation:** **Do not rename.** Map task “orgId” → **client_id** in any new code and docs. Same as MAINTENANCE_INTELLIGENCE_FLOW_TASK_AUDIT.md. All existing contractor, work order, and contractor_performance code uses client_id.

### 2.2 Contractor document shape

- **Conflict:** Task expects a single `trade` enum; codebase has **trade_types** (array of strings, e.g. plumbing, electrical). Task uses **verified**; codebase uses **vetted**.
- **Recommendation:** **Additive only.** Add new fields (sourceType, status, credentials, insuranceDetails, ratingAverage, jobCount, slaComplianceRate, reworkRate) without removing name, trade_types, vetted. Treat **vetted** as the existing “verified” signal; optionally add **verified** as an alias or synonym in API/docs only, or keep only vetted. Trade: keep **trade_types**; if task expects a single primary trade, add optional **trade** (enum) for filtering/sort; do not drop trade_types.

### 2.3 Route paths

- **Conflict:** Task says POST **/api/contractors** for landlord; codebase uses **/api/client/** for client and **/api/admin/ops/** for admin.
- **Recommendation:** **Preserve existing.** Add landlord “add contractor” at **POST /api/client/contractors** (client route guard, CONTRACTOR_NETWORK or separate flag). Do not add a global POST /api/contractors (ambiguous). Admin network can stay as **POST /api/admin/ops/contractors** with explicit “network” semantics (client_id=null, vetted=true) or add **POST /api/admin/ops/contractors/network** as a dedicated endpoint that sets sourceType and defaults.

### 2.4 “Verified” vs “Vetted”

- **Conflict:** Task uses **verified**; codebase uses **vetted**.
- **Recommendation:** Keep **vetted** in DB and API. Document “verified” in task as “vetted” in implementation. No schema rename.

---

## 3. WHAT IS ALREADY IMPLEMENTED

### 3.1 Backend

- **contractors collection** with: contractor_id, client_id, name, trade_types[], vetted, email, phone, company_name, areas_served, notes, created_at, updated_at. Indexes: contractor_id (unique), client_id, (vetted, client_id).
- **contractor_performance collection** with: contractor_id, client_id, jobs_completed, jobs_on_time, last_used_at, created_at, updated_at. Updated on work order completion (maintenance_service).
- **Admin contractor API** (routes/contractors.py): GET/POST /api/admin/ops/contractors, GET/PATCH/DELETE /api/admin/ops/contractors/:id. Create accepts client_id (null = system-wide), vetted, etc.
- **Client contractor API** (routes/client.py): GET /api/client/contractors — list contractors for client (client_id match or client_id null). Gated by CONTRACTOR_NETWORK.
- **Work order assignment:** Admin and client can assign contractor_id to a work order. recommend_contractors_for_work_order (by trade match, vetted, contractor_performance) used in admin WO detail and client recommend endpoint.
- **Feature flag:** CONTRACTOR_NETWORK in ops_compliance_feature_flags; used for client contractors list and recommend-contractors.

### 3.2 Frontend

- **Client:** ClientContractorsPage — list of contractors (name, company, trade_types, vetted, contact). No add, no tabs.
- **Admin:** AdminOpsContractorsPage — list with client filter and vetted filter; add/edit/delete contractor (name, trade_types, client_id, vetted, email, phone, company_name, areas_served, notes).
- **WO assignment:** Admin maintenance list and AdminWorkOrderDetailPage — assign contractor from dropdown; recommendation panel calls getRecommendContractors.

### 3.3 Integration

- Contractors are used in maintenance (work orders), contractor_performance on WO completion, and recommend_contractors_for_work_order. No contractor auth or portal.

---

## 4. WHAT IS MISSING (BY TASK SECTION)

### 4.1 Contractor data model (task §1)

- **Missing on contractors:** sourceType, status (active | pending_review | suspended), credentials[], insuranceDetails, ratingAverage, jobCount, slaComplianceRate, reworkRate. contactName (task) vs name (current) — keep name; add contactName only if needed.
- **Rule:** landlord-added → client_id set; platform → client_id null; self-registered → client_id null, status pending_review. Currently “client_id set” vs “client_id null” exists; sourceType and status would make the three models explicit.

### 4.2 Entry 1 – Landlord adds contractor (task §2)

- **Missing:** Client (landlord) endpoint to create a contractor. Task: POST /api/contractors with companyName, trade, phone or email; system sets sourceType=landlord_added, orgId=user org, verified=false.
- **Implement as:** POST **/api/client/contractors** (client_route_guard, CONTRACTOR_NETWORK or always if contractors enabled), body: companyName, trade (or trade_types), phone, email, optional region/credentials/insuranceDetails. Service sets client_id=user["client_id"], sourceType=landlord_added (if added), vetted=false.

### 4.3 Entry 2 – Admin curated network (task §3)

- **Missing:** Dedicated “add to network” semantics. Task: POST /api/admin/contractors/network, orgId=null, verified=true, status=active.
- **Options:** (A) Add POST **/api/admin/ops/contractors/network** that creates with client_id=null, vetted=true, sourceType=platform_network, status=active; or (B) keep single admin create and document that client_id=null + vetted=true = network. **Recommendation:** (A) for clarity and auditability.

### 4.4 Entry 3 – Self-registration (task §4)

- **Missing:** Public POST **/api/contractors/register** (or /api/public/contractors/register), feature flag CONTRACTOR_SELF_REGISTRATION, and admin PATCH **/api/admin/ops/contractors/:id/approve** (approve/reject/request more info). Self-registered: sourceType=self_registered, verified=false, status=pending_review, orgId=null.
- **Implement:** Public route gated by CONTRACTOR_SELF_REGISTRATION (system-wide or env); on create set sourceType=self_registered, status=pending_review, verified=false. Admin approve sets status=active and optionally verified=true so they appear in “approved marketplace” query.

### 4.5 Contractor selection for work orders (task §5)

- **Current:** list_contractors_for_client: (client_id match OR client_id null). recommend_contractors_for_work_order: same visibility + score by trade, vetted, performance.
- **Missing:** Explicit filter “status = active” and “sourceType in (landlord_added, platform_network, self_registered with verified)”. Sort by region match and rating when available. **Recommendation:** Add status filter when status exists; add optional region to sort; use ratingAverage when present.

### 4.6 Performance tracking (task §6)

- **Current:** On WO complete, contractor_performance is updated (jobs_completed, jobs_on_time). No update to contractor doc; no reworkRate; no average completion time.
- **Missing:** (1) Optionally aggregate jobCount (and SLA rate) onto contractor record for display. (2) Rework rate: “follow-up issue within X days” — would require linking completed WO to same property/contractor and detecting a follow-up WO; new logic. (3) Average completion time: store completed_at − assigned_at or similar; currently not stored. **Recommendation:** Keep contractor_performance as source of truth; add optional denormalised fields on contractor (jobCount, slaComplianceRate) updated by job or periodic sync. Rework and average completion time can be phase 2.

### 4.7 contractorRatings (task §7)

- **Missing:** Collection contractorRatings (contractorId, workOrderId, propertyId, rating 1–5, completionSpeed, professionalism, notes, createdAt). No write path; no feed into contractor.ratingAverage.
- **Implement:** New collection; create when rating is submitted (e.g. POST from client after WO completed). Aggregate (e.g. average) into contractor.ratingAverage when present.

### 4.8 Admin dashboard (task §8)

- **Missing:** Filters: sourceType, trade, region, verification (vetted), performance. Actions: approve/reject (for self-registered), suspend, edit credentials, view job history.
- **Implement:** Extend admin list API with query params (sourceType, status, trade, region). Add PATCH approve/reject and PATCH status=suspended. “Job history” = work orders where contractor_id = id (existing data).

### 4.9 Security (task §9)

- **Satisfied:** No contractor login or portal; contractors only referenced by id. No change needed until contractor portal exists.

### 4.10 Future marketplace (task §10)

- **Missing:** Schema only: priceBooks, contractorAvailability, commissionRate, preferredContractor scoring. **Recommendation:** Add optional fields to contractor or new collections; no business logic.

### 4.11 Frontend (task §11)

- **Missing (client):** “My Contractors” vs “Network Contractors” tabs; “Add contractor” form (calls POST /api/client/contractors); search by trade; filter by region; assign to work order (already exists in WO flow).
- **Missing (admin):** “Pending Approvals” tab (self-registered, status=pending_review); approve/reject; filters by sourceType, trade, region, verification, performance.

### 4.12 Feature flags (task §12)

- **Missing:** CONTRACTOR_SELF_REGISTRATION. **Existing:** CONTRACTOR_NETWORK. Defaults: landlord add and admin network on when CONTRACTOR_NETWORK on; self-registration off until flag on.

---

## 5. FILES TO TOUCH (SUMMARY)

| Layer | Files |
|-------|--------|
| **Backend – schema / service** | database.py (indexes for status, sourceType if added; contractor_ratings collection), contractor_service.py (add sourceType/status in create paths; list filters; optional aggregates on contractor), new or extended: contractor_ratings_service or ratings in contractor_service |
| **Backend – routes** | client.py or new client_contractors route: POST /api/client/contractors. contractors.py: POST /api/admin/ops/contractors/network, PATCH .../contractors/:id/approve, PATCH .../contractors/:id (status). public or new: POST /api/public/contractors/register (gated by CONTRACTOR_SELF_REGISTRATION) |
| **Backend – feature flags** | ops_compliance_feature_flags.py: add CONTRACTOR_SELF_REGISTRATION (default False) |
| **Frontend – API** | client.js: add createContractor (client) for POST /client/contractors. adminAPI: add createNetworkContractor, approveContractor, etc. if new endpoints |
| **Frontend – Client** | ClientContractorsPage: tabs (My / Network), Add contractor form, search/filter by trade and region |
| **Frontend – Admin** | AdminOpsContractorsPage: filters (sourceType, status, trade, region), Pending Approvals tab, approve/reject, suspend |

---

## 6. IMPLEMENTATION ORDER (RECOMMENDED)

1. **Additive schema only:** Add to contractors: sourceType (default from create path), status (default active for existing and landlord/admin create; pending_review for self-reg). Add optional: credentials[], insuranceDetails, ratingAverage, jobCount, slaComplianceRate, reworkRate. Do not remove or rename client_id, vetted, trade_types.
2. **Landlord add:** POST /api/client/contractors, contractor_service.create_contractor(..., client_id=user, sourceType=landlord_added, vetted=False, status=active).
3. **Admin network:** POST /api/admin/ops/contractors/network with client_id=null, vetted=true, sourceType=platform_network, status=active.
4. **Feature flag + self-registration:** CONTRACTOR_SELF_REGISTRATION; POST /api/public/contractors/register; PATCH /api/admin/ops/contractors/:id/approve (and optional reject/request_info).
5. **Selection query:** In list_contractors_for_client and recommend_contractors_for_work_order, filter by status=active and (client_id match OR sourceType=platform_network OR (sourceType=self_registered AND vetted)); sort by trade match, region, performance, rating when present.
6. **contractorRatings:** New collection + write API; optional aggregation into contractor.ratingAverage.
7. **Performance:** Keep contractor_performance; optionally sync jobCount/slaComplianceRate to contractor doc on completion or via job.
8. **Admin UI:** Filters, Pending Approvals tab, approve/reject, suspend.
9. **Client UI:** Tabs My/Network, Add contractor form, filters.
10. **Future schema:** Add placeholder fields or collections (priceBooks, etc.); no logic.

---

## 7. ACCEPTANCE CRITERIA VS CURRENT STATE

| Criterion | Status |
|-----------|--------|
| Landlords can add their own contractors | **No** — only admin can create; no client POST. |
| Admin can add vetted platform contractors | **Yes** — admin create with client_id=null, vetted=true. Dedicated “network” endpoint would make it explicit. |
| Self-registration endpoint exists but gated | **No** — add endpoint + CONTRACTOR_SELF_REGISTRATION. |
| Contractors can be selected when assigning work orders | **Yes** — admin and client assign; recommend API exists. |
| Contractor performance stats update after job completion | **Yes** — contractor_performance updated; not yet on contractor doc. |
| No existing workflows broken | **Yes** — preserve client_id, vetted, trade_types, existing routes; additive only. |

---

**End of audit.** Use this to implement only what’s missing and to keep naming (client_id, vetted) and routes consistent with the existing stack.
