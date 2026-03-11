# Contractor Visibility and Sharing Rules – Task vs Codebase Audit

**Task:** Implement contractor visibility and sharing rules so contractor records are safe, professional, and multi-tenant aware (private, platform network, marketplace; submit-to-network flow; audit; assignment rules).

**Audit purpose:** Identify what is implemented, what is missing, how it was implemented, and any conflicts. Recommend the safest, most professional options. **Do not implement; analysis only.**

**References:** `contractor_service.py`, `contractors.py` (admin), `client.py` (GET/POST contractors, rate), `public.py` (self-register), `contractor_recommendation.py`, `ClientContractorsPage.js`, `ops_compliance_feature_flags.py`, `CONTRACTORS_TAB_PROPERTY_DETAIL_AUDIT.md`, `CONTRACTOR_MANAGEMENT_TASK_AUDIT.md`.

---

## 1. EXECUTIVE SUMMARY

| Task section | Implemented | Missing / partial |
|--------------|-------------|-------------------|
| **§1 Data model** | contractor_id, client_id, source_type (landlord_added \| platform_network \| self_registered), status (active \| pending_review \| suspended), vetted, company_name, contact_name, trade_types, phone, email, region, credentials, insurance_details, created_at, updated_at. | **visibility_scope** (private \| network \| marketplace) not stored; **orgId** named as **client_id** (acceptable). **submitted_to_network_at**, **approved_for_network_at**, **approved_by_admin_id** not present. **verified** is **vetted** in code. |
| **§2 Private contractors** | Landlord add: source_type=landlord_added, client_id=org, vetted=false; visible only to that org via _visibility_query. | visibility_scope not set to "private" (could derive). Default “private” behaviour is correct. |
| **§3 Platform network** | Admin add: create_contractor_network → client_id=null, source_type=platform_network, vetted=true, status=active. | visibility_scope not set to "network". |
| **§4 Marketplace** | Self-register (public) → source_type=self_registered, status=pending_review, vetted=false; approve → status=active, vetted=true. Gated by CONTRACTOR_SELF_REGISTRATION_ENABLED (env). | visibility_scope not "marketplace"; CONTRACTOR_SELF_REGISTRATION is env, not per-client flag; marketplace tab not in UI. |
| **§5 Query rules** | list_contractors_for_client uses _visibility_query: (client_id match) OR (client_id null + platform_network) OR (client_id null + self_registered + vetted). Optional source_type filter. Legacy: status missing or client_id match. | **A) My Contractors** = source_type=landlord_added (correct). **B) Network** = source_type=platform_network (correct). **C) Marketplace** = no dedicated query; would need source_type=self_registered and gate by CONTRACTOR_SELF_REGISTRATION. |
| **§6 Submit to network** | — | **POST /api/contractors/:id/submit-to-network** does not exist. No submitted_to_network_at, no admin notification/review task, no Approve/Reject/Request more info. |
| **§7 UI** | Tabs: My Contractors, Network Contractors. Add contractor (landlord). Vetted badge. | **Marketplace tab** missing (and gated by self-registration). No **source labels** (e.g. "Private", "Network", "Marketplace"). No **Edit** / **Assign** / **Submit to Network Review** row actions on My Contractors. No **View** / **Assign** on network rows. No **Request Quote** placeholder for marketplace. |
| **§8 Assignment rules** | recommend_contractors_for_work_order uses _visibility_query(client_id); client PATCH work order can set contractor_id. | **No validation** that contractor_id on PATCH is in the visible set for that client; client could theoretically assign another org’s private contractor if they knew the id. |
| **§9 Security / multi-tenancy** | list_contractors_for_client and recommend both use _visibility_query(client_id). Client cannot list other clients’ contractors. | **Single-contractor access:** No GET /api/client/contractors/:id; client only sees contractors in list. **Assignment:** Must validate contractor_id in visible set on PATCH. |
| **§10 Audit logging** | — | No audit events for contractor created, submitted to network, approved/rejected, suspended, or contractor assigned to work order. create_audit_log exists; no contractor-specific AuditAction values. |
| **§11 Feature flags** | CONTRACTOR_NETWORK (per-client); CONTRACTOR_SELF_REGISTRATION (env is_contractor_self_registration_enabled()). | CONTRACTOR_SELF_REGISTRATION is system-wide env, not per-client (task says “feature flag”; current design is acceptable for “self-registration on/off”). Marketplace tab should be hidden or locked when self-registration disabled. |
| **§12 Acceptance** | Private stay private; network shared; self-registered hidden until approved; recommendation uses visibility. | Submit-to-network flow missing; assignment validation missing; audit logging missing; UI gaps (tabs/actions/source labels). |

---

## 2. DATA MODEL (CURRENT VS TASK)

### 2.1 Current contractor document (from contractor_service and usage)

- **contractor_id** (uuid)
- **client_id** (optional; None = platform/marketplace, set = landlord-added for that org)
- **name**, **company_name**, **contact_name**
- **trade_types** (list)
- **phone**, **email**
- **region**, **areas_served**
- **credentials** (list), **insurance_details**
- **vetted** (bool)
- **status** (active \| pending_review \| suspended)
- **source_type** (landlord_added \| platform_network \| self_registered)
- **created_at**, **updated_at**
- **rating_average**, **job_count**, **sla_compliance_rate**, **rework_rate**, **notes**

**Not present:** visibility_scope, submitted_to_network_at, approved_for_network_at, approved_by_admin_id. Task uses **orgId** → we use **client_id** (same meaning; keep client_id). Task uses **verified** → we use **vetted** (keep vetted for backward compatibility; can alias in API if needed).

### 2.2 Visibility rules (task)

- landlord_added + orgId set → visibilityScope = "private"
- platform_network + orgId null → visibilityScope = "network"
- self_registered + orgId null + verified → visibilityScope = "marketplace"

**Current:** Visibility is **implicit** in _visibility_query (client_id + source_type + status + vetted). No stored visibility_scope. Adding **visibility_scope** as a stored field is additive and would align with task and simplify query/UI labelling.

---

## 3. QUERY LOGIC (CURRENT)

**Location:** `contractor_service._visibility_query(client_id)` and `list_contractors_for_client`.

```python
def _visibility_query(client_id: str) -> Dict[str, Any]:
    return {
        "$or": [
            {"status": STATUS_ACTIVE, "client_id": client_id},
            {"status": STATUS_ACTIVE, "client_id": None, "source_type": SOURCE_PLATFORM_NETWORK},
            {"status": STATUS_ACTIVE, "client_id": None, "source_type": SOURCE_SELF_REGISTERED, "vetted": True},
            {"status": {"$exists": False}, "client_id": client_id},
            {"status": {"$exists": False}, "client_id": None},
        ],
    }
```

- **My Contractors (A):** Frontend passes `source_type=landlord_added`. Backend applies _visibility_query and source_type → effectively `client_id = current_client_id` and source_type landlord_added (plus legacy without status). **Correct:** no other org’s private contractors.
- **Network (B):** `source_type=platform_network` → client_id null, platform_network, active. **Correct.**
- **Marketplace (C):** Task wants visibilityScope=marketplace, verified=true, status=active, only if CONTRACTOR_SELF_REGISTRATION. Current _visibility_query already includes self_registered + vetted + active; there is no separate “marketplace only” list that is gated by CONTRACTOR_SELF_REGISTRATION. **Gap:** Add a way to request “marketplace only” (e.g. source_type=self_registered) and gate the Marketplace tab by CONTRACTOR_SELF_REGISTRATION so that when the flag is off, the tab is hidden or shows locked state.

**Conclusion:** Query logic is multi-tenant safe for list and recommend. No merge of other orgs’ private contractors.

---

## 4. ASSIGNMENT AND RECOMMENDATION

- **Recommendation engine:** `recommend_contractors_for_work_order` loads contractors with _visibility_query(client_id), then passes them to rule-based scoring. Only visible contractors are suggested. **Correct.**
- **Client PATCH work order (assign):** `client_maintenance.update_my_work_order` accepts `contractor_id`. It does **not** check that contractor_id is in the visible set for user["client_id"]. So a client could pass an id from another org’s private contractor (if they knew it) and the DB would allow the update. **Gap / risk:** Enforce in backend that the contractor is visible to the client (e.g. fetch contractor, then require that it satisfies _visibility_query for the WO’s client_id) before updating the work order.

---

## 5. SUBMIT-TO-NETWORK FLOW (TASK §6)

**Task:** “Submit to Network Review” – landlord submits private contractor for review; contractor stays private; set submitted_to_network_at; create admin notification/review task. Admin can Approve to Network, Reject, Request more info. If approved, create new network contractor or convert with consent and audit.

**Current:** None of this exists. No endpoint, no fields, no notifications.

**Recommendation (safest):**

1. **Add fields (additive):** submitted_to_network_at (datetime), approved_for_network_at (datetime), approved_by_admin_id (str), optional rejection_reason / request_more_info.
2. **Endpoint:** POST `/api/client/contractors/:contractor_id/submit-to-network` (client_route_guard, CONTRACTOR_NETWORK). Verify contractor belongs to client (client_id = user["client_id"]), then set submitted_to_network_at (and optionally a status like submitted_for_review if you add it). Create admin notification or review task (e.g. audit log + admin queue or email).
3. **Admin actions:** Reuse or extend PATCH `/api/admin/ops/contractors/:id` for Approve to Network / Reject / Request more info. “Approve to Network” best implemented by **creating a new platform_network contractor** (copy sanitised data) and optionally linking to original (e.g. metadata.original_private_contractor_id) so the private record stays unchanged and audit trail is clear. Do not mutate the private contractor’s visibility by default.

---

## 6. UI (CLIENT CONTRACTORS PAGE)

**Current:** `ClientContractorsPage.js` – two tabs (My Contractors, Network Contractors), list of contractors, “Add contractor” on My, vetted badge. No Marketplace tab, no row actions (Edit, Assign, Submit to Network Review), no source labels, no View/Assign on network, no Request Quote placeholder.

**Task:** Tabs – My Contractors, Network Contractors, Marketplace (if enabled). Per-tab: source labels, verification badges, actions as specified.

**Gaps:**

- Add **Marketplace** tab when CONTRACTOR_SELF_REGISTRATION is enabled (or show locked state when disabled). Call GET contractors with source_type=self_registered (and ensure backend returns only approved marketplace contractors when so filtered).
- **Source labels:** Show “Private”, “Network”, “Marketplace” (or “My contractor”, “Platform network”, “Marketplace”) per row from source_type / visibility_scope.
- **My Contractors row actions:** Edit (navigate or modal), Assign (navigate to work orders or open assign flow), Submit to Network Review (call new endpoint; only if submitted_to_network_at is null).
- **Network row actions:** View (detail drawer or page), Assign.
- **Marketplace row actions:** View, Assign, optional “Request Quote” placeholder.

---

## 7. FEATURE FLAGS

- **CONTRACTOR_NETWORK:** Exists (per-client in ops_compliance_feature_flags). Used for client list/create contractors, recommend-contractors, rate. Defaults False for Solo/Portfolio, True for Pro. **Aligned.**
- **CONTRACTOR_SELF_REGISTRATION:** Exists as key; behaviour is **system-wide** via `is_contractor_self_registration_enabled()` (env CONTRACTOR_SELF_REGISTRATION_ENABLED). Task says “feature flag”; keeping env is acceptable. When disabled: hide or lock Marketplace tab; do not expose self-registered contractors in client-facing marketplace list (they already only appear when vetted=true in _visibility_query, so “approved” marketplace is already gated; the tab visibility should be gated by the flag).

---

## 8. CONFLICTS AND SAFEST OPTIONS

| Topic | Task | Current | Recommendation |
|-------|------|--------|-----------------|
| **orgId** | orgId (camelCase) | client_id | Keep **client_id** everywhere; treat “organisation” as client_id. No schema rename. |
| **visibility_scope** | Stored field | Derived from source_type + client_id | **Option A:** Add **visibility_scope** on write/read (set from rules in §1) for clarity and future querying. **Option B:** Keep derived only. Prefer A for consistency with task and UI labels. |
| **verified** | verified (boolean) | vetted | Keep **vetted** in schema/API; document “verified” in task as vetted. |
| **Submit to network** | New flow | Missing | Add endpoint, fields, and admin review path; prefer creating new network contractor on approve and keeping private record. |
| **Assignment validation** | Only assign visible contractors | No check on PATCH | **Mandatory:** Before updating work order with contractor_id, verify contractor is in visible set for the work order’s client_id (e.g. get contractor, apply same rules as _visibility_query). Return 403 if not allowed. |
| **Audit** | Log contractor events | No contractor audit | Add audit events (e.g. CONTRACTOR_CREATED, CONTRACTOR_SUBMITTED_TO_NETWORK, CONTRACTOR_APPROVED_FOR_NETWORK, CONTRACTOR_REJECTED, CONTRACTOR_SUSPENDED, CONTRACTOR_ASSIGNED_TO_WORK_ORDER) or use generic action with resource_type="contractor" and metadata. Call create_audit_log from routes or service. |
| **Marketplace tab** | Show when enabled | No tab | Add Marketplace tab; show only when CONTRACTOR_SELF_REGISTRATION is enabled (frontend: use existing entitlements/feature API if available for system-wide flag, or backend can expose “marketplace_available” in feature flags). |

---

## 9. FILES AND LOCATIONS

### 9.1 Backend

| File | Role | Changes (when implementing) |
|------|------|-----------------------------|
| **services/contractor_service.py** | Visibility query, list, create, approve, recommend | Add visibility_scope in create/update (or helper to set from source_type+client_id+vetted). Add submitted_to_network_at, approved_for_network_at, approved_by_admin_id in create/update. Add function “submit_contractor_to_network(contractor_id, client_id)”. Add “contractor_visible_to_client(contractor_id, client_id)” for assignment check. Optionally separate list functions for My / Network / Marketplace. |
| **routes/client.py** | GET/POST contractors | POST submit-to-network: new endpoint POST /contractors/:id/submit-to-network (verify ownership, set submitted_to_network_at, create notification/audit). |
| **routes/client_maintenance.py** | PATCH work order (assign) | Before calling update_work_order with contractor_id, verify contractor is visible to client (e.g. contractor_service.contractor_visible_to_client(contractor_id, wo_client_id)); 403 if not. |
| **routes/contractors.py** | Admin list/create/update/approve | Admin approve/reject/request-more-info: extend PATCH or add PATCH .../approve, .../reject with reason. On “approve to network”, create new platform_network contractor (copy data), optionally link to original; audit. |
| **routes/public.py** | Self-registration | No change for visibility; already creates self_registered, pending_review. |
| **utils/audit.py** / **models (AuditAction)** | Audit | Add contractor-related actions or use resource_type=contractor; call create_audit_log from contractor create, submit-to-network, approve, reject, suspend, and from maintenance_service when contractor_id is set on WO. |
| **database.py** | Indexes | If adding visibility_scope, add index for visibility_scope + status for client queries. |

### 9.2 Frontend

| File | Role | Changes (when implementing) |
|------|------|-----------------------------|
| **ClientContractorsPage.js** | Tabs, list, add | Add Marketplace tab (when CONTRACTOR_SELF_REGISTRATION). Add source labels and row actions (Edit, Assign, Submit to Network Review for My; View, Assign for Network; View, Assign, Request Quote for Marketplace). Call new submit-to-network endpoint. |
| **api/client.js** | API | Add submitContractorToNetwork(contractorId) if new endpoint is added. |

### 9.3 Query logic locations

- **My Contractors:** `list_contractors_for_client(client_id, source_type="landlord_added")` – `contractor_service.py`, used by GET /api/client/contractors (client.py).
- **Network Contractors:** same with `source_type="platform_network"`.
- **Marketplace:** same with `source_type="self_registered"` (and ensure only vetted/active); gate by CONTRACTOR_SELF_REGISTRATION.
- **Recommendation:** `recommend_contractors_for_work_order` uses _visibility_query(client_id) – `contractor_service.py`.
- **Assignment:** `update_work_order` in maintenance_service; called from client_maintenance.update_my_work_order – **add visibility check here**.

---

## 10. PRIVATE → NETWORK PROMOTION (TASK §6 “BEST PRACTICE”)

Task: “Prefer creating a new network contractor record and preserving original private record linkage.”

**Recommendation:**

1. **Submit:** Landlord calls POST submit-to-network. Backend sets submitted_to_network_at on the **private** contractor; no change to visibility. Create audit + admin notification/review task.
2. **Admin review:** Approve / Reject / Request more info. Store approved_for_network_at, approved_by_admin_id (and rejection/request reason if needed) on the **private** record.
3. **On Approve to Network:** Create a **new** contractor document: source_type=platform_network, client_id=null, vetted=true, status=active; copy allowed fields (company_name, contact_name, trade_types, phone, email, region, credentials, insurance_details, etc.). Optionally set metadata.original_private_contractor_id = contractor_id of the private record. Do **not** change the private contractor’s client_id or source_type so it remains “My Contractor” for that org; the new network record is what appears in Network Contractors for all orgs. Audit both “contractor approved for network” and “new network contractor created” with linkage.

---

## 11. OUTPUT CHECKLIST (FOR TASK DELIVERABLES)

- **Files changed (when implementing):** contractor_service.py, client.py, client_maintenance.py, contractors.py (admin), utils/audit.py and/or models (AuditAction), database.py (indexes if needed), ClientContractorsPage.js, api/client.js.
- **Model fields added/updated:** visibility_scope (optional), submitted_to_network_at, approved_for_network_at, approved_by_admin_id (and optional rejection/request fields). Keep client_id, vetted, source_type.
- **Endpoints created:** POST /api/client/contractors/:contractor_id/submit-to-network. Optional: PATCH .../reject, .../request-more-info if not covered by existing PATCH.
- **Query logic locations:** _visibility_query and list_contractors_for_client (contractor_service.py); add contractor_visible_to_client and use in client_maintenance PATCH work order.
- **UI tabs/visibility:** My Contractors, Network Contractors, Marketplace (if CONTRACTOR_SELF_REGISTRATION). Source labels and row actions as above.
- **Notes on private→network:** Prefer new network contractor on approve; keep private record unchanged; store linkage and full audit trail.

---

*End of audit. No code or assets were changed.*
