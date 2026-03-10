# Assets Tab – Task vs Codebase Audit

**Task:** Implement the Assets tab for the Property Detail page to support asset-level tracking, maintenance intelligence, and compliance linkage.

**Audit purpose:** Identify what is implemented, what is missing, how it was implemented, and any conflicting instructions with a recommended safest option. **No implementation in this document** – audit only.

**References:** Property Detail page (`PropertyDetailPage.js`), client maintenance API (`client_maintenance.py`), property assets service (`property_assets_service.py`), provisioning and provisioning status hook.

---

## 1. ASSETS TAB PURPOSE (Task §1)

**Task asks the tab to answer:**
- What key systems exist in this property?
- What is their current status?
- When were they last serviced?
- Are there active issues?
- Are there elevated risks?
- Connects: Compliance → Evidence → Maintenance → Risk Signals → Contractors.

**Current state:**
- **Implemented:** Assets tab exists; lists assets via `GET /api/client/maintenance/properties/{id}/assets`; table shows Asset (actually `asset_type`), Type (same), Status (derived as "Serviced" or "—" from `last_service_date`), Last service, Open issues ("—"), Risk ("—").
- **Missing:** No summary answering "what systems / status / last serviced / active issues / elevated risks"; no linkage to evidence or compliance documents; open issues and risk are hardcoded "—".

**Gap:** Tab is a thin list; purpose (system inventory + status + issues + risk + compliance linkage) is not fulfilled.

---

## 2. ASSETS TAB STRUCTURE (Task §2)

**Task order:** A) Asset Summary Row → B) Asset Table → C) Asset Detail Drawer → D) Asset Activity / History.

**Current structure:**
- Title "Property assets", short description, loading state, empty state, then a single table. No summary row, no detail drawer, no activity/history section.

**Gap:** All four sections need to be added or expanded; only a minimal table exists.

---

## 3. ASSET SUMMARY ROW (Task §3)

**Task:** Quick summary cards: Total assets, Assets with open issues, Assets with elevated risk, Assets with recent work orders, Assets with compliance linkage. Example: Total Assets: 6, Open Issues: 1, Elevated Risk: 1, Recent Repairs: 2.

**Current:** Not present. No summary data computed or returned by API.

**Gap:** Backend could extend list response with `summary` (e.g. total, with_open_issues, with_elevated_risk, recent_work_orders, with_compliance_linkage) or frontend could derive from assets + work orders + issues + insights; compliance linkage count requires evidence/requirement-to-asset link (not implemented).

---

## 4. DEFAULT ASSET TYPES & AUTO-CREATION (Task §4)

**Task:** Auto-create default assets during property provisioning. Minimum set: Boiler, Heating System, Electrical Installation, Roof, Plumbing, Windows/Doors, Damp/Moisture, Smoke/CO Alarm. Logic: if `property.hasGas === true` create Boiler + Heating System; every property: Electrical Installation, Roof, Plumbing, Windows/Doors. Do not duplicate if provisioning runs again.

**Current:**
- **Provisioning:** `provisioning_service` (and property create/update flows) call `update_provisioning_status_for_property` (in `provisioning_status_hook.py`) which only writes `provisioning_status` (compliance/maintenance module status). No creation of default assets. No call into `property_assets_service` or `property_assets` collection during provisioning.
- **property_assets:** Used by predictive maintenance and client assets list; no "default template" or auto-creation on property create.

**Gap:** Default asset auto-creation is **fully missing**. Must be added: hook after property create/update (or inside provisioning completion) that creates default assets idempotently (e.g. by `asset_type` + `property_id` unique key or "default" marker).

**Conflict / safest:** Task says "assets should be auto-created during property provisioning". Codebase has no such step. **Recommendation:** Add a single, idempotent "ensure default assets for property" function; call it from the same place that calls `update_provisioning_status_for_property` (e.g. after property create/update in the route or inside a dedicated provisioning step). Do not duplicate assets: use "default" asset types as a fixed set and upsert by (property_id, asset_type) for default assets only.

---

## 5. ASSET TABLE (Task §5)

**Task:** Columns: Asset Name, Asset Type, Status, Last Service, Open Issues, Risk Level, Linked Evidence, Actions (View Details, Edit, View Issues). On mobile: stacked cards.

**Current (PropertyDetailPage.js):**
- Columns: Asset, Type, Status, Last service, Open issues, Risk.
- Asset cell shows `a.asset_type` (not a separate "name"); Type shows capitalized `asset_type`; Status shows "Serviced" or "—" (derived from `last_service_date`), not Active/Inactive/Replaced/Removed; Open issues and Risk are hardcoded "—"; no Linked Evidence column; no row actions (View Details, Edit, View Issues).
- No mobile card layout.

**Backend:** `property_assets` has `asset_id`, `property_id`, `client_id`, `asset_type`, `install_date`, `last_service_date`, `notes`, `created_at`, `updated_at`; admin upsert can set `name`. No `status` field; no API returning open_issues count or risk per asset; no linked evidence.

**Gap:** Add Asset Name (use `name` or fallback to type); add Status field (task: Active/Inactive/Replaced/Removed); add Open Issues (from issues/work orders with `asset_id`); add Risk (from predictive insights or per-asset risk); add Linked Evidence column and row actions; add mobile cards.

---

## 6. ASSET STATUS TYPES (Task §6)

**Task:** Status values: Active, Inactive, Replaced, Removed (lifecycle tracking).

**Current:** No `status` on asset model. Frontend infers "Serviced" vs "—" from `last_service_date` only.

**Gap:** Add `status` to asset model (optional, nullable); allow values Active, Inactive, Replaced, Removed; default new/default assets to Active. Backend and API must support read/write of `status`.

---

## 7. ASSET DETAIL VIEW (Task §7)

**Task:** Clicking an asset opens a drawer or modal with: Asset name, type, status, installed year (optional), estimated age (optional), make/model (optional), last service date; linked compliance documents (e.g. Gas Safety, EICR); maintenance history (issues, work orders); risk signals; contractor history (jobs completed, contractor used).

**Current:** No drawer or modal. No endpoint for single-asset detail with linked docs, issues, work orders, risk, contractors.

**Gap:** Add Asset Detail drawer/modal; add API to get one asset with enriched data (linked evidence, issues, work orders, risk, contractor history) or compose from existing endpoints (asset + documents by requirement type + issues/work orders by asset_id + insights + contractor jobs).

---

## 8. ASSET DATA MODEL (Task §8)

**Task collection:** `propertyAssets`. Fields: _id, orgId, propertyId, assetType, name, status, make, model, installedYear, ageEstimate, lastServiceDate, metadata, createdAt, updatedAt. All optional fields nullable.

**Current collection:** `property_assets`. Fields: asset_id, property_id, client_id, asset_type, install_date, last_service_date, notes, created_at, updated_at; upsert adds `name`. No: status, make, model, installedYear/ageEstimate (we have install_date), metadata. Naming: `client_id` not orgId, `install_date` not installedYear.

**Conflicts and safest option:**
- **orgId vs client_id:** Codebase uses `client_id`. Keep `client_id`; do not introduce orgId.
- **Schema:** Add optional fields to existing collection: `status`, `make`, `model`, `installed_year` (or keep `install_date` as date string), `age_estimate`, `metadata`. Use snake_case and existing names where possible; keep optional fields nullable. No need to rename collection to propertyAssets; keep `property_assets`.

---

## 9. ASSET EVENTS (Task §9)

**Task:** Secondary collection `assetEvents`. Fields: assetId, propertyId, eventType, description, source, relatedIssueId, relatedWorkOrderId, timestamp. Event types: issue_created, repair_completed, inspection_completed, document_linked, risk_signal_updated. History powers predictive maintenance.

**Current:** No `asset_events` collection. `maintenance_events` exists with: event_id, property_id, client_id, event_type (repair, inspection, service), occurred_at, outcome, asset_id, notes, created_at. Used for property-level events; no relatedIssueId, relatedWorkOrderId, description, source; event types are generic (repair/inspection/service), not issue_created/document_linked/risk_signal_updated.

**Conflict and safest option:** Task wants a dedicated asset-event log for per-asset history. **Option A:** Add new collection `asset_events` with task schema (asset_id, property_id, event_type, description, source, related_issue_id, related_work_order_id, timestamp, client_id for scoping). **Option B:** Extend usage of `maintenance_events` (already has asset_id) and add optional fields (description, source, related_issue_id, related_work_order_id) and map task event types to event_type. **Recommendation:** Option A (new `asset_events`) for clear audit trail and task alignment; backend writes to it when issues created, work orders completed, evidence linked, risk updated; keep `maintenance_events` for existing predictive/analytics. If minimal change is preferred, Option B avoids a new collection but mixes property-level and asset-level semantics.

---

## 10. LINKAGE TO OTHER MODULES (Task §10)

**Task:** Issues can include assetId; evidence confirmed → update asset metadata (e.g. Gas Safety → Boiler lastServiceDate, EICR → Electrical inspection metadata); work orders linked to asset; risk signals per asset; asset events appear in property timeline.

**Current:**
- **Issues / Work orders:** Both support optional `asset_id` (CreateIssueBody, CreateWorkOrderBody; maintenance_service, maintenance_issues_service). Linkage exists.
- **Evidence → asset update:** Not implemented. No logic that on document confirmation (e.g. Gas Safety, EICR) updates `property_assets.last_service_date` or asset metadata.
- **Risk signals:** Predictive service uses property_assets and maintenance_events for insights per property; insights can reference asset_id. Per-asset risk in UI not exposed in Assets table/drawer.
- **Timeline:** Property timeline does not yet include asset events (e.g. issue_created, repair_completed). Timeline is built from score_ledger, score_change_log, work_orders; no asset_events feed.

**Gap:** Implement evidence → asset update (on confirm, update corresponding asset’s last_service_date or metadata); ensure asset events (if added) are included in property timeline; surface per-asset risk in Assets tab/drawer.

---

## 11. AUTO-LINKING RULES (Task §11)

**Task:** When issues are created, attempt to auto-link assets (e.g. heating issue → Boiler, electrical → Electrical Installation, leak → Plumbing). User can override.

**Current:** Issues accept optional `asset_id` but no auto-suggestion or auto-link from category/description.

**Gap:** Add heuristic in create-issue flow (or in triage): map category/keywords to default asset_type and suggest or set asset_id (user can override). No backend change strictly required if frontend suggests asset when creating issue; backend can optionally infer default asset_id from category.

---

## 12. FRONTEND REQUIREMENTS (Task §12)

**Task:** Add Assets tab under Property page (already present). Components: Asset summary cards, Asset table, Asset detail drawer, Edit asset modal. Actions: Edit asset name, Update service date, View linked issues, View linked evidence. Do not allow deletion of core assets unless admin.

**Current:** Tab present; table only; no summary cards, no detail drawer, no edit modal; no "Edit", "View linked issues", "View linked evidence" actions. Delete not exposed (no conflict). Assets API and tab gated by PREDICTIVE_MAINTENANCE.

**Gap:** Build summary cards, detail drawer, edit modal; add actions (edit name, update service date, view issues, view evidence); enforce no-delete for default/core assets unless admin (backend + frontend).

---

## 13. EMPTY STATE (Task §13)

**Task:** If no assets: message "Assets will be automatically created when property setup completes." Button: "Refresh Assets".

**Current:** Empty state: "No assets yet" + "Assets will be created as you add them or as your property setup is completed" + button "View risk signals". No "Refresh Assets" button.

**Gap:** Align copy with task ("Assets will be automatically created when property setup completes") and add "Refresh Assets" button that re-fetches assets (and optionally triggers backend "ensure default assets" if product wants one-click seed).

---

## 14. FEATURE FLAGS (Task §14)

**Task:** Assets tab should always be visible if maintenance module exists. If predictive maintenance not enabled: hide risk signals section (not the whole tab).

**Current:** Assets tab is visible in nav but content is gated: when PREDICTIVE_MAINTENANCE is off, the tab shows UpgradePrompt (lock icon on tab). So the whole Assets tab content is hidden without predictive.

**Conflict and safest option:** Task says "visible if maintenance module exists" and only hide "risk signals section" when predictive is off. Current behaviour hides the entire tab content without predictive. **Recommendation:** Make Assets tab content visible when MAINTENANCE_WORKFLOWS is enabled; load assets from an endpoint that does not require PREDICTIVE_MAINTENANCE for list/detail (or keep list under maintenance, with optional predictive-only fields). When PREDICTIVE_MAINTENANCE is off: show Assets tab with summary + table + detail drawer but hide "Risk signals" block in the drawer and risk column/summary. This requires: (1) Backend: allow GET (and possibly POST) assets when maintenance is enabled, even if predictive is off; (2) Frontend: show Assets content when maintenance is on, and hide only risk-related UI when predictive is off.

---

## 15. ACCEPTANCE CRITERIA (Task §15)

| Criterion | Status |
|----------|--------|
| Assets auto-created during property provisioning | ❌ Not implemented |
| Assets displayed per property | ✅ List exists; table shows assets |
| Issues can link to assets | ✅ asset_id on issues and work orders |
| Evidence can link to assets | ❌ No evidence → asset link or update |
| Asset history events stored | ⚠️ maintenance_events exists; task’s assetEvents not present |
| No duplicate assets created | ⚠️ Provisioning does not create assets; idempotent default creation not implemented |
| Asset tab loads correctly if optional modules disabled | ⚠️ Tab content locked behind predictive; task wants visible with maintenance, risk section hidden when predictive off |

---

## OUTPUT REQUIRED

### Files to change (implementation phase)

- **Backend**
  - `backend/services/property_assets_service.py` – extend asset schema (status, make, model, installed_year, age_estimate, metadata); add idempotent `ensure_default_assets_for_property(property_id, client_id, property_data)`; optional: add `asset_events` writes or extend maintenance_events.
  - `backend/database.py` – add indexes for `asset_events` if new collection added; ensure unique index on (property_id, asset_type) or equivalent for default assets to prevent duplicates.
  - `backend/routes/client_maintenance.py` – extend AddAssetBody (name, status, make, model, installed_year, age_estimate); add GET/PATCH for single asset and summary in list response; optionally allow assets when MAINTENANCE_WORKFLOWS is on (not only PREDICTIVE_MAINTENANCE).
  - Provisioning hook: either `backend/services/provisioning_status_hook.py` (add call to ensure_default_assets after status update) or the route/handler that creates or updates a property – add call to `ensure_default_assets_for_property` after property is created/updated.
  - Evidence/compliance flow: when a document is confirmed (e.g. Gas Safety, EICR), update corresponding asset’s last_service_date (e.g. in apply-extraction or confirm-details handler) – requires mapping requirement_type → asset_type and finding/upserting asset.
- **Frontend**
  - `frontend/src/pages/PropertyDetailPage.js` – Assets tab: add summary row (Total, Open issues, Elevated risk, Recent work orders, Compliance linkage); fix table columns (Name, Type, Status, Last service, Open issues, Risk, Linked evidence, Actions); add Asset Detail drawer; add Edit asset modal; add empty state "Refresh Assets" and task-aligned copy; show tab content when maintenance is on, hide only risk section when predictive off; mobile cards for assets.

### Models / collections

- **Existing:** `property_assets` – add optional fields: `status`, `make`, `model`, `installed_year`, `age_estimate`, `metadata` (all nullable). Keep `client_id`, `asset_id`, `property_id`, `asset_type`, `name`, `install_date`, `last_service_date`, `notes`, `created_at`, `updated_at`.
- **New (recommended):** `asset_events` – assetId, propertyId, clientId, eventType, description, source, relatedIssueId, relatedWorkOrderId, timestamp, createdAt. Indexes: (asset_id, timestamp), (property_id, timestamp).

### Routes added or changed

- **Existing:**  
  - `GET /api/client/maintenance/properties/{property_id}/assets` – keep; extend response with `summary` (total, with_open_issues, with_elevated_risk, recent_work_orders, with_compliance_linkage) when implemented.  
  - `POST /api/client/maintenance/properties/{property_id}/assets` – extend body with name, status, make, model, installed_year, age_estimate.
- **Add:**  
  - `GET /api/client/maintenance/properties/{property_id}/assets/{asset_id}` – single asset with enriched data (linked evidence, issues, work orders, risk, contractor history).  
  - `PATCH /api/client/maintenance/properties/{property_id}/assets/{asset_id}` – update asset (name, status, last_service_date, make, model, etc.).  
  - Optional: `GET /api/client/maintenance/properties/{property_id}/assets/{asset_id}/events` – list asset_events for drawer history.

### Provisioning hook location

- **Recommended:** In the same code path that calls `update_provisioning_status_for_property(client_id, property_id)` after a property is created or updated. That is:
  - Either in **`backend/services/provisioning_status_hook.py`**: at the end of `update_provisioning_status_for_property`, after writing provisioning_status, call a new function e.g. `ensure_default_assets_for_property(client_id, property_id)` which loads property (for has_gas_supply etc.) and creates default assets idempotently.
  - Or in the **property create/update route** (e.g. in `backend/routes/properties.py` or wherever the client or admin creates/updates a property): after saving the property and calling `update_provisioning_status_for_property`, call `ensure_default_assets_for_property(client_id, property_id)`.
- **Recommendation:** Prefer provisioning_status_hook so that any flow that updates provisioning status (e.g. onboarding completion, property edit) automatically gets default assets without touching multiple route files.

### Example asset creation logic (idempotent, no duplicates)

```text
DEFAULT_ASSET_TYPES_ALL = [
    "electrical_installation",
    "roof",
    "plumbing",
    "windows_doors",
    "damp_moisture",
    "smoke_co_alarm",
]
DEFAULT_ASSET_TYPES_IF_GAS = ["boiler", "heating_system"]

async def ensure_default_assets_for_property(client_id: str, property_id: str) -> None:
    db = database.get_db()
    prop = await db.properties.find_one(
        {"property_id": property_id, "client_id": client_id},
        {"_id": 0, "has_gas_supply": 1},
    )
    if not prop:
        return
    types_to_ensure = list(DEFAULT_ASSET_TYPES_ALL)
    if prop.get("has_gas_supply"):
        types_to_ensure.extend(DEFAULT_ASSET_TYPES_IF_GAS)
    for asset_type in types_to_ensure:
        existing = await db.property_assets.find_one(
            {"property_id": property_id, "asset_type": asset_type}
        )
        if not existing:
            await property_assets_service.add_asset(
                property_id=property_id,
                client_id=client_id,
                asset_type=asset_type,
                install_date=None,
                last_service_date=None,
                notes=None,
            )
```

- Use a **unique compound index** on (property_id, asset_type) for default types so that concurrent or repeated provisioning does not insert duplicates (insert will fail or use upsert with "only if not exists" semantics). Alternatively, use an upsert that sets default fields only when the document does not exist (e.g. `$setOnInsert` for creation, no overwrite of user-set fields).

---

## Summary of conflicts and recommendations

| Topic | Conflict | Recommendation |
|-------|----------|----------------|
| Feature flag | Task: tab visible if maintenance exists; only hide risk section if predictive off. Current: whole tab content gated on predictive. | Show Assets tab content when MAINTENANCE_WORKFLOWS is on; gate only risk-related UI on PREDICTIVE_MAINTENANCE. Allow list/detail assets API when maintenance is on. |
| Data model | Task: orgId, propertyAssets, camelCase optional fields. Current: client_id, property_assets, snake_case. | Keep client_id and property_assets; add optional status, make, model, installed_year, age_estimate, metadata (nullable). |
| Asset events | Task: separate assetEvents collection with event types. Current: maintenance_events with asset_id. | Add asset_events collection for task-aligned history; keep maintenance_events for existing analytics. |
| Provisioning | Task: auto-create default assets during provisioning. Current: no such step. | Add ensure_default_assets_for_property in provisioning path (e.g. provisioning_status_hook after status update); idempotent by (property_id, asset_type). |

No implementation has been performed; this document is audit-only.
