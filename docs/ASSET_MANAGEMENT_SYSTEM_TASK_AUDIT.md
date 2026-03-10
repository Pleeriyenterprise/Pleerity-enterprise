# Asset Management System – Task vs Codebase Audit

**Task:** Implement a lightweight Asset Management System for properties: track major systems, link maintenance and compliance to those systems, support predictive risk signals.

**Audit purpose:** Identify what is implemented, what is missing, how it was implemented, and any conflicting instructions with the safest option. **No implementation in this document** – audit only.

**References:** `property_assets_service.py`, `client_maintenance.py`, `provisioning_status_hook.py`, `database.py`, `PropertyDetailPage.js`, `maintenance_issues_service.py`, `maintenance_service.py`, `documents.py`, `property_timeline_service.py`, `risk_signal_service.py`, existing `docs/ASSETS_TAB_TASK_AUDIT.md`.

---

## 1. PURPOSE (§1)

**Task:** Answer what major systems exist, which compliance/evidence relate to which systems, which issues/repairs affect which systems, which systems are at elevated risk, and service/repair history per system.

**Current state:**
- **Implemented:** Property assets list and detail; issues and work orders have optional `asset_id`; evidence (Gas Safety, EICR) can update asset `last_service_date`; asset events (issue_created, repair_completed, document_linked) stored; risk signals and predictive insights use `asset_id`; property timeline includes asset events; Assets tab shows summary, table, detail drawer, edit.
- **Gaps:** Linked evidence count in summary is 0 (no evidence→asset link stored on evidence doc); “Linked evidence” column in table is "—"; detail drawer “Linked compliance” is placeholder "—". Risk signal generation already links to `asset_id`; no further gap there.

---

## 2. ASSET MODEL (§2)

**Task:** Collection `propertyAssets`. Required: _id, orgId, propertyId, assetType, name, status, make, model, installedYear, ageEstimate, lastServiceDate, metadata, createdAt, updatedAt. Status: ACTIVE, INACTIVE, REPLACED, REMOVED. Asset types: BOILER, HEATING_SYSTEM, ELECTRICAL_INSTALLATION, ROOF, PLUMBING, WINDOWS_DOORS, DAMP_MOISTURE, SMOKE_CO_ALARM_SYSTEM, FIRE_ALARM_SYSTEM, OTHER.

**Current state:**
- **Collection:** `property_assets` (snake_case). Fields: `asset_id`, `property_id`, `client_id`, `asset_type`, `name`, `status`, `make`, `model`, `installed_year`, `age_estimate`, `install_date`, `last_service_date`, `notes`, `metadata`, `created_at`, `updated_at`. Optional fields are nullable.
- **Naming:** Codebase uses `client_id` (multi-tenant by client), not orgId. Asset types stored in **lowercase snake_case** (e.g. `boiler`, `electrical_installation`, `smoke_co_alarm`). Task uses UPPER_SNAKE for type enum; API/UI can display with friendly labels.
- **Status:** Stored lowercase: `active`, `inactive`, `replaced`, `removed`. Matches task semantics.
- **Gaps:** Task lists `FIRE_ALARM_SYSTEM` as optional “if fire alarm system is relevant”; codebase does **not** create `fire_alarm_system` by default. Acceptable as optional.
- **Conflict / safest:** Keep `property_assets`, `client_id`, snake_case. No need to rename to propertyAssets or introduce orgId.

---

## 3. DEFAULT ASSET CREATION RULES (§3)

**Task:** Helper `createDefaultAssetsForProperty(property)`. Always create: ELECTRICAL_INSTALLATION, ROOF, PLUMBING, WINDOWS_DOORS, DAMP_MOISTURE. If property.hasGas: BOILER, HEATING_SYSTEM. If alarms present or compliance engine active: SMOKE_CO_ALARM_SYSTEM. Optional: FIRE_ALARM_SYSTEM. Idempotent, no duplicates.

**Current state:**
- **Implemented:** `ensure_default_assets_for_property(client_id, property_id)` in `property_assets_service.py`. Uses `DEFAULT_ASSET_TYPES_ALL` (electrical_installation, roof, plumbing, windows_doors, damp_moisture, smoke_co_alarm) and `DEFAULT_ASSET_TYPES_IF_GAS` (boiler, heating_system). Reads property `has_gas_supply`; only creates if no document exists for `(property_id, asset_type)`. Idempotent and safe to rerun.
- **Difference:** Task says “if alarms are present or compliance engine active” for SMOKE_CO_ALARM; codebase **always** creates smoke_co_alarm. Safer (no missed properties); no conflict.
- **Gap:** Default assets are created **without** a human-friendly `name` (e.g. “Main Boiler”). UI falls back to formatting `asset_type`. Task “Naming examples” can be satisfied by either (a) adding default display names when creating defaults, or (b) keeping UI-only formatting. Optional enhancement.

---

## 4. PROVISIONING INTEGRATION (§4)

**Task:** On property created, onboarding provisioning runs, or admin backfill – create missing default assets; log audit event ASSETS_INITIALISED; append property timeline event. Do not create duplicates on rerun.

**Current state:**
- **Implemented:** `update_provisioning_status_for_property` (in `provisioning_status_hook.py`) is called from `properties.py` on property create and on property update. It calls `ensure_default_assets_for_property(client_id, property_id)` after writing provisioning status. Default asset creation is idempotent; no duplicates.
- **Gaps:**
  1. **ASSETS_INITIALISED audit event:** Not logged anywhere. Task asks for an audit event when assets are initialised.
  2. **Property timeline event:** No dedicated “assets initialised” event appended to the property timeline when default assets are first created. Asset events (issue_created, repair_completed, document_linked) **do** appear in the timeline via `list_asset_events_for_property` in `property_timeline_service.py`.
- **Conflict / safest:** Add a single audit log write (e.g. to existing audit/trail or score_events) with type ASSETS_INITIALISED when `ensure_default_assets_for_property` actually creates at least one asset. Optionally append a timeline item for “Assets initialised” when new defaults are created; keep it minimal to avoid noise on every provisioning run (e.g. only when count created > 0).

---

## 5. ASSET EVENTS / HISTORY (§5)

**Task:** Collection `assetEvents`. Fields: _id, orgId, propertyId, assetId, eventType, description, source, relatedIssueId, relatedWorkOrderId, relatedEvidenceId, createdAt, metadata.

**Current state:**
- **Implemented:** Collection `asset_events` exists. Fields: `event_id`, `asset_id`, `property_id`, `client_id`, `event_type`, `description`, `source`, `related_issue_id`, `related_work_order_id`, `timestamp`, `created_at`. Indexes: (asset_id, timestamp), (property_id, timestamp), event_id unique. Event types used: `issue_created`, `repair_completed`, `document_linked`, `risk_signal_updated` (and `inspection_completed` defined but not yet written).
- **Writes:** Issue create → `add_asset_event(ASSET_EVENT_ISSUE_CREATED)`; work order completion → `add_asset_event(ASSET_EVENT_REPAIR_COMPLETED)`; evidence→asset update → `add_asset_event(ASSET_EVENT_DOCUMENT_LINKED)`.
- **Gap:** Task mentions `relatedEvidenceId`. Current schema has no `related_evidence_id`. For document_linked events we could add it for traceability. Optional.
- **Task event types:** ASSET_CREATED, SERVICE_DATE_UPDATED, ISSUE_LINKED, REPAIR_COMPLETED, INSPECTION_COMPLETED, EVIDENCE_LINKED, RISK_SIGNAL_UPDATED, ASSET_REPLACED. Current code uses snake_case and slightly different names (issue_created vs ISSUE_LINKED, document_linked vs EVIDENCE_LINKED). Semantically aligned; no conflict. ASSET_CREATED is not written when default assets are created; could be added for completeness.

---

## 6. ASSET LINKAGE TO MAINTENANCE (§6)

**Task:** maintenanceIssues and workOrders optional assetId; suggest default asset from category; when linked, create assetEvent.

**Current state:**
- **Implemented:** `maintenance_issues` and `work_orders` have optional `asset_id`. Create-issue flow calls `infer_asset_id_from_category(property_id, client_id, category, description)` when `asset_id` is not provided; result is used as default. Work order create/update accepts `asset_id`. When issue is created with asset_id, `add_asset_event(ASSET_EVENT_ISSUE_CREATED)` is called. When work order is completed with asset_id, `add_asset_event(ASSET_EVENT_REPAIR_COMPLETED)` is called.
- **Category mapping:** `CATEGORY_TO_ASSET_TYPE` maps heating/boiler→boiler, electrical→electrical_installation, plumbing/leak→plumbing, roof→roof, damp/moisture→damp_moisture, smoke/alarm→smoke_co_alarm. Aligned with task examples.
- No conflict.

---

## 7. ASSET LINKAGE TO EVIDENCE / COMPLIANCE (§7)

**Task:** Evidence can support a requirement AND optionally update an asset (e.g. Gas Safety → boiler.lastServiceDate, EICR → electrical metadata); create assetEvent. Do not auto-apply without user confirmation if flow requires confirmation.

**Current state:**
- **Implemented:** `update_asset_last_service_from_requirement(property_id, client_id, requirement_type, last_service_date, document_id)` in `property_assets_service.py`. Maps `gas_safety`→boiler, `eicr`→electrical_installation; finds asset by `asset_type`, updates `last_service_date`, writes `document_linked` asset event. Called from **documents.py** in the **AI extraction apply** path (after extraction is applied and requirement/due_date updated). So it runs when the user confirms AI-applied extraction, not on raw upload.
- **Gap:** If there is a **separate** evidence confirmation flow (e.g. manual confirm without AI apply), that path does not currently call `update_asset_last_service_from_requirement`. Audit should confirm whether all “evidence confirmed” paths go through the same handler that calls this; if not, add the call there.
- **EICR metadata:** Task mentions “update metadata.lastInspectionDate” for EICR. Current implementation only updates `last_service_date`. Adding `metadata.lastInspectionDate` for EICR would be an optional enhancement.
- **Conflict / safest:** Do not auto-apply to assets before user confirmation. Current behaviour (run on AI apply, which is after user applies extraction) is consistent. If manual confirm exists elsewhere, invoke asset update there too without changing existing behaviour.

---

## 8. PROPERTY PAGE INTEGRATION (§8)

**Task:** Assets tab: summary cards, asset table, asset detail drawer, linked issues/evidence/risk signals. Columns: Asset Name, Type, Status, Last Service, Open Issues, Risk Level, Linked Evidence, Actions (View Details, Edit, View Issues, View Evidence).

**Current state:**
- **Implemented:** Assets tab exists. Summary row: Total assets, Open issues, Elevated risk (gated by predictive_maintenance), Recent work orders, Compliance linked. Table: Asset (name or formatted type), Type, Status, Last service, Open issues, Risk (from insights, gated by predictive), Linked evidence (column present but "—"), Actions: View, Edit, View issues. Detail drawer: name, type, status, last service, installed year, make/model, “Linked compliance” (placeholder "—"), maintenance history (events), risk signals (link to tab). Edit modal: name, status, last service date, make, model. Mobile cards present. Tab content visible when MAINTENANCE_WORKFLOWS or PREDICTIVE_MAINTENANCE is on.
- **Gaps:** “Linked evidence” / “Linked compliance” not populated (no stored link count or list from evidence to asset). “View Evidence” action not present (only “View issues”). Filling these requires either (a) storing asset_id on evidence/requirement rows and aggregating, or (b) deriving from requirement_type (e.g. gas_safety → boiler) for display only.

---

## 9. ASSET DETAIL VIEW (§9)

**Task:** Detail view: name, type, status, make/model, installedYear, ageEstimate, lastServiceDate, linked evidence, linked issues, linked work orders, linked risk signals, recent asset events.

**Current state:**
- **Implemented:** GET `/client/maintenance/properties/{property_id}/assets/{asset_id}` returns asset + events. Drawer shows name, type, status, last service, installed year, make/model; “Linked compliance” and “Maintenance history” (events); risk signals section (predictive_maintenance). Linked issues and work orders are not loaded in the single-asset response; user can use “View issues” to go to Maintenance tab (filtered by asset could be a future enhancement).
- **Gaps:** Linked evidence list empty. Linked issues/work orders not aggregated in asset detail API (could be added by querying issues/work_orders by asset_id).

---

## 10. API ENDPOINTS (§10)

**Task:** GET/POST /api/properties/:propertyId/assets, PATCH /api/assets/:assetId, GET /api/assets/:assetId/events. Response shape with summary (totalAssets, openIssues, elevatedRisk, linkedEvidence) and assets array.

**Current state:**
- **Implemented:** Under **client** maintenance API (not generic /api/properties):  
  - `GET /client/maintenance/properties/{property_id}/assets` → `{ assets, summary }` with summary: total, with_open_issues, with_elevated_risk, recent_work_orders, with_compliance_linkage (0), per_asset (open_issues, risk).  
  - `POST /client/maintenance/properties/{property_id}/assets` → add asset.  
  - `GET /client/maintenance/properties/{property_id}/assets/{asset_id}` → single asset + events.  
  - `PATCH /client/maintenance/properties/{property_id}/assets/{asset_id}` → update asset.  
  - `GET /client/maintenance/properties/{property_id}/assets/{asset_id}/events` → events list.
- **Path difference:** Task suggests `/api/properties/:propertyId/assets`; codebase uses `/client/maintenance/properties/{property_id}/assets` (client-scoped, feature-gated). Safer to keep client path and feature gate.
- **Response shape:** Snake_case (total, with_open_issues, etc.). Frontend consumes it. No conflict.

---

## 11. EDITING RULES (§11)

**Task:** Users can rename asset, update make/model, installed year, age estimate, service date, mark inactive/replaced. Do not allow easy deletion of core assets; if deletion exists, restrict to admin and log heavily.

**Current state:**
- **Implemented:** PATCH asset supports name, status, last_service_date, make, model, installed_year, age_estimate, notes. Edit modal in UI covers name, status, last service date, make, model. No delete endpoint exposed in client API; no “delete asset” in UI.
- **Gap:** installed_year and age_estimate are in API but not in the current Edit modal (only name, status, last_service_date, make, model). Adding them to the modal would align with task.
- No conflict.

---

## 12. BACKFILL / LEGACY SUPPORT (§12)

**Task:** When property page loads and no assets exist, allow “Initialise Assets” or run background migration. Legacy properties must work without errors.

**Current state:**
- **Implemented:** Default assets are created only when `update_provisioning_status_for_property` runs (property create or update). Legacy properties that were created before this hook do not have assets until provisioning runs again or a backfill runs.
- **Empty state:** UI shows “No assets yet”, “Assets will be automatically created when property setup completes”, and **Refresh Assets** (re-fetches only). There is **no** “Initialise Assets” button or API that triggers `ensure_default_assets_for_property` for the current property.
- **Gap:** No way for a user to one-click create default assets for an existing property. Safest option: add a **client** endpoint, e.g. `POST /client/maintenance/properties/{property_id}/assets/ensure-defaults`, that calls `ensure_default_assets_for_property` (idempotent) and returns the updated list or count. Empty state button can be “Initialise Assets” that calls this then refreshes. No background migration script exists for assets; optional admin script could iterate properties and call ensure_default_assets_for_property.

---

## 13. RISK SIGNAL SUPPORT (§13)

**Task:** Design so risk signals can link to assets (e.g. Boiler Failure Risk → assetId = boiler). Linkage must be straightforward.

**Current state:** Risk signals collection and service use `asset_id`; signals are generated per asset where applicable (e.g. boiler, electrical, damp). Property and portfolio risk-signals APIs return `asset_id`; UI shows it in table and drawer. No conflict.

---

## 14. CONTRACTOR SUPPORT (§14)

**Task:** Work orders linked to assets should support contractor history later (e.g. contractor performance by asset type). No extra UI now; schema must not block.

**Current state:** work_orders have `asset_id` and `contractor_id`; contractor_assignments exist. Schema does not block aggregating by asset type. No conflict.

---

## 15. AUDIT + TIMELINE (§15)

**Task:** When asset is created/updated/linked to issue/evidence/service/replaced: log assetEvent, auditEvent, property timeline where appropriate.

**Current state:**
- **Asset events:** Written for issue_created, repair_completed, document_linked. Not written for default asset creation (ASSET_CREATED) or for every asset update (e.g. SERVICE_DATE_UPDATED when user edits last service date).
- **Audit:** No ASSETS_INITIALISED or generic “asset created/updated” audit event.
- **Timeline:** Asset events are merged into property timeline via `list_asset_events_for_property` in `property_timeline_service.py`. No dedicated “Assets initialised” timeline entry.
- **Gaps:** (1) ASSETS_INITIALISED (or equivalent) when default assets are first created. (2) Optionally ASSET_CREATED in asset_events when defaults are created. (3) Optional timeline event “Assets initialised” when count created > 0. (4) Optional audit/timeline for asset updates (e.g. status change, last service date) if enterprise trust requires it.

---

## 16. FEATURE FLAG / PLAN BEHAVIOUR (§16)

**Task:** Assets exist structurally once maintenance intelligence is present; if predictive/contractor modules disabled, keep assets functional and only hide dependent sections (e.g. risk display).

**Current state:** Assets tab and APIs are gated by **MAINTENANCE_WORKFLOWS or PREDICTIVE_MAINTENANCE** (`_require_assets_enabled`). So assets are available when either feature is on. Risk column and elevated-risk summary are gated by predictive_maintenance in the UI. Aligned with task.

---

## 17. EMPTY STATES (§17)

**Task:** If no assets: “Assets will be created automatically as property setup completes.” Buttons: “Initialise Assets”, “View Property Setup”.

**Current state:** Copy is close: “Assets will be automatically created when property setup completes.” Button is “Refresh Assets” only. No “Initialise Assets” (no API to trigger defaults). No “View Property Setup” link. Adding “Initialise Assets” depends on §12 backfill endpoint; “View Property Setup” could link to property edit or onboarding step if such a route exists.

---

## 18. ACCEPTANCE CRITERIA (§18)

| Criterion | Status |
|-----------|--------|
| Default assets created based on property attributes | ✅ ensure_default_assets_for_property; has_gas_supply for boiler/heating |
| Asset creation idempotent | ✅ Check by (property_id, asset_type) before insert |
| Issues and work orders can link to assets | ✅ asset_id optional; inference from category |
| Evidence can optionally link to and update assets | ✅ Gas Safety/EICR → last_service_date + document_linked event; trigger is AI-apply path |
| Asset events stored | ✅ asset_events collection; issue_created, repair_completed, document_linked |
| Property Assets tab works | ✅ Summary, table, drawer, edit, mobile cards |
| Legacy properties do not break | ✅ No assets = empty state; no errors |
| No duplicate assets on provisioning rerun | ✅ Idempotent by (property_id, asset_type) |

**Gaps relative to full task:** ASSETS_INITIALISED audit/timeline, “Initialise Assets” backfill for existing properties, linked evidence count/display, optional ASSET_CREATED and related_evidence_id.

---

## CONFLICTS AND SAFEST OPTIONS

| Topic | Conflict | Safest option |
|-------|----------|---------------|
| Model naming | Task: orgId, propertyAssets, camelCase. Current: client_id, property_assets, snake_case. | Keep client_id and property_assets; no rename. |
| API path | Task: /api/properties/:id/assets. Current: /client/maintenance/properties/:id/assets. | Keep client path and feature gate. |
| Smoke/Fire alarms | Task: SMOKE_CO_ALARM “if alarms present or compliance active”; FIRE_ALARM optional. Current: always create smoke_co_alarm; no fire_alarm. | Keep current; add FIRE_ALARM_SYSTEM only if product requires it. |
| Evidence→asset trigger | Must not auto-apply without confirmation. Current: runs on AI extraction apply. | Keep; add call in any other “evidence confirmed” path if present. |
| Default asset names | Task gives “Main Boiler” etc. as examples. Current: no name set; UI formats type. | Optional: set default `name` per asset_type in ensure_default_assets. |
| Delete assets | Task: do not allow easy deletion; if any, admin-only and log. Current: no delete in client API/UI. | Keep no delete; if added later, restrict to admin and audit. |

---

## FILES CHANGED (existing implementation)

- **Backend:** `property_assets_service.py` (model, ensure_default_assets, asset_events, evidence→asset, inference), `provisioning_status_hook.py` (call ensure_default_assets), `database.py` (property_assets and asset_events indexes), `client_maintenance.py` (assets routes), `maintenance_issues_service.py` (asset_id, inference, asset event), `maintenance_service.py` (asset_id, repair_completed event), `documents.py` (update_asset_last_service_from_requirement on AI apply), `property_timeline_service.py` (asset_events in timeline), `risk_signal_service.py` (asset_id usage).
- **Frontend:** `PropertyDetailPage.js` (Assets tab: summary, table, drawer, edit modal, empty state), `client.js` (getPropertyAssets, getPropertyAsset, updatePropertyAsset, getPropertyAssetEvents).

---

## MODELS / COLLECTIONS

- **property_assets:** asset_id, property_id, client_id, asset_type, name, status, make, model, installed_year, age_estimate, install_date, last_service_date, notes, metadata, created_at, updated_at. Indexes: (property_id, asset_id) unique, property_id, (property_id, asset_type).
- **asset_events:** event_id, asset_id, property_id, client_id, event_type, description, source, related_issue_id, related_work_order_id, timestamp, created_at. Indexes: (asset_id, timestamp), (property_id, timestamp), event_id unique.

---

## PROVISIONING HOOK LOCATION

- **Current:** `provisioning_status_hook.update_provisioning_status_for_property` (called from `properties.py` on property create and update) calls `ensure_default_assets_for_property(client_id, property_id)` after writing provisioning status. Idempotent; no duplicates.

---

## RECOMMENDED ADDITIONS (no duplication)

1. **Backfill / Initialise Assets:** Add `POST /client/maintenance/properties/{property_id}/assets/ensure-defaults` that calls `ensure_default_assets_for_property` and returns e.g. `{ created: number, assets: list }`. Empty state button “Initialise Assets” calls it then refreshes.
2. **Audit/timeline when defaults created:** When `ensure_default_assets_for_property` creates at least one asset, log an audit event (e.g. ASSETS_INITIALISED) and optionally append one property timeline entry (“Assets initialised”) so §4 is fully satisfied.
3. **Optional:** ASSET_CREATED event in asset_events when each default asset is created; optional `related_evidence_id` on asset_events for document_linked events.
4. **Optional:** “Linked evidence” in summary/table/drawer – either store asset_id on evidence/requirement and aggregate, or derive from requirement_type (gas_safety/eicr) for display.
5. **Optional:** Edit modal fields for installed_year and age_estimate; “View Property Setup” in empty state if a route exists.

---

## ASSUMPTIONS DOCUMENTED

- `client_id` is the tenant boundary; no orgId layer.
- Asset types are stored in lowercase snake_case; task enum names (e.g. BOILER) are reflected in display only.
- Evidence→asset update runs only after user-driven confirmation (AI apply). Any other confirm flow must call the same helper if evidence should update assets.
- Default assets are one per (property_id, asset_type); no duplicate types per property.
- Deletion of assets is out of scope for client UI; if introduced, it should be admin-only and audited.
- FIRE_ALARM_SYSTEM is not created by default; add only if product requires it.
