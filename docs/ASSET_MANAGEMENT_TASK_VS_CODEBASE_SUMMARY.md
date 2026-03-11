# Asset Management System – Task vs Codebase Summary

**Purpose:** Check the codebase against the full Asset Management System task. Identify what’s implemented, what’s missing, and any conflicts. **No implementation** – audit only.

**Full audit:** See `docs/ASSET_MANAGEMENT_SYSTEM_TASK_AUDIT.md` for section-by-section detail, file references, and recommended additions.

**Note on duplicate audits:** `docs/ASSETS_TAB_TASK_AUDIT.md` is **outdated**. It states that “default asset auto-creation is fully missing” and “no call into property_assets_service during provisioning”. The current codebase **does** call `ensure_default_assets_for_property` from `provisioning_status_hook.py` on property create/update. Use **ASSET_MANAGEMENT_SYSTEM_TASK_AUDIT.md** as the source of truth to avoid duplication or conflicting changes.

---

## 1. Implemented vs missing (high level)

| Task area | Implemented | Missing / partial |
|-----------|-------------|-------------------|
| **§1 Purpose** | Asset list/detail; issues & WOs link to assets; evidence (Gas/EICR) can update asset last_service_date; asset events; risk signals use asset_id; timeline includes asset events; Assets tab with summary, table, drawer, edit. | Linked evidence **count** in summary/table/drawer is 0 or "—" (no stored evidence→asset link for display). |
| **§2 Asset model** | `property_assets` with asset_id, property_id, client_id, asset_type, name, status, make, model, installed_year, age_estimate, install_date, last_service_date, notes, metadata, created_at, updated_at. Status: active/inactive/replaced/removed. Types in snake_case (boiler, electrical_installation, etc.). | Task uses orgId and camelCase; codebase uses client_id and snake_case – **keep as-is**. FIRE_ALARM_SYSTEM not created by default – optional per task. |
| **§3 Default asset creation** | `ensure_default_assets_for_property(client_id, property_id)` in `property_assets_service.py`. Always: electrical_installation, roof, plumbing, windows_doors, damp_moisture, smoke_co_alarm; if has_gas_supply: boiler, heating_system. Idempotent by (property_id, asset_type). | Default assets created without human-friendly `name` (e.g. "Main Boiler"); UI formats type. Optional to add default names. |
| **§4 Provisioning** | `provisioning_status_hook.update_provisioning_status_for_property` (on property create/update) calls `ensure_default_assets_for_property`. No duplicates on rerun. | **ASSETS_INITIALISED** audit event not logged. No dedicated “Assets initialised” property timeline entry when defaults are first created. |
| **§5 Asset events** | `asset_events` collection: event_id, asset_id, property_id, client_id, event_type, description, source, related_issue_id, related_work_order_id, timestamp, created_at. Writes: issue_created, repair_completed, document_linked. | Task has **relatedEvidenceId**; schema has no `related_evidence_id`. ASSET_CREATED not written when default assets are created. |
| **§6 Maintenance linkage** | maintenance_issues and work_orders have optional asset_id; infer_asset_id_from_category on create; asset events on issue create and WO completion. | — |
| **§7 Evidence linkage** | `update_asset_last_service_from_requirement` (Gas Safety→boiler, EICR→electrical); called from documents AI-extraction **apply** path (after user confirmation). | If another “evidence confirmed” path exists (e.g. manual), it may not call this. EICR only updates last_service_date; task also mentions metadata.lastInspectionDate – optional. |
| **§8 Property page** | Assets tab: summary cards, asset table, detail drawer, edit modal, View/Edit/View issues. | “Linked evidence” column/drawer not populated. No “View Evidence” action. |
| **§9 Asset detail view** | Drawer: name, type, status, last service, installed year, make/model, events, risk signals (gated). | Linked evidence list empty. Linked issues/WOs not loaded in single-asset API (user uses “View issues” to go to Maintenance tab). |
| **§10 API** | GET/POST `/client/maintenance/properties/{id}/assets`, GET/PATCH `/client/maintenance/properties/{id}/assets/{asset_id}`, GET `.../assets/{asset_id}/events`. Response has summary (total, with_open_issues, with_elevated_risk, etc.) and assets. | Task suggests `/api/properties/:id/assets`; codebase uses client-scoped, feature-gated path – **keep client path**. **No** `POST .../assets/ensure-defaults` for backfill. |
| **§11 Editing** | PATCH supports name, status, last_service_date, make, model, installed_year, age_estimate, notes. Edit modal: name, status, last service, make, model. No delete in client API/UI. | installed_year and age_estimate not in Edit modal – optional to add. |
| **§12 Backfill / legacy** | Legacy properties without assets show empty state; no errors. | **No “Initialise Assets”** button or API; only “Refresh Assets”. No one-click ensure-defaults for existing properties. |
| **§13 Risk signals** | risk_signals use asset_id; APIs and UI show it. | — |
| **§14 Contractor** | work_orders have asset_id and contractor_id; schema allows future aggregation by asset type. | — |
| **§15 Audit + timeline** | Asset events written; asset events appear in property timeline. | No ASSETS_INITIALISED audit; no ASSET_CREATED in asset_events for defaults; no “Assets initialised” timeline entry; no audit for asset updates (e.g. status change). |
| **§16 Feature flag** | Assets gated by MAINTENANCE_WORKFLOWS or PREDICTIVE_MAINTENANCE; risk display gated by predictive_maintenance. | — |
| **§17 Empty states** | Copy: “Assets will be automatically created when property setup completes.” Button: “Refresh Assets”. | No “Initialise Assets” (blocked by missing ensure-defaults API). No “View Property Setup” link. |
| **§18 Acceptance** | Default assets by attributes, idempotent, issues/WOs link, evidence updates assets (on confirm), events stored, Assets tab works, legacy OK, no duplicates on rerun. | Gaps as above (audit/timeline on init, backfill UX, linked evidence display). |

---

## 2. Conflicts and safest options

| Topic | Task vs codebase | Safest option |
|-------|------------------|----------------|
| **Naming** | Task: orgId, propertyAssets, camelCase. Code: client_id, property_assets, snake_case. | Keep client_id and property_assets; do not rename to orgId/propertyAssets. |
| **API path** | Task: `/api/properties/:id/assets`. Code: `/client/maintenance/properties/:id/assets` (client-scoped, feature-gated). | Keep client path and feature gate. |
| **Smoke / fire alarms** | Task: SMOKE_CO_ALARM “if alarms present or compliance active”; FIRE_ALARM optional. Code: always creates smoke_co_alarm; no fire_alarm. | Keep current (always smoke_co_alarm). Add FIRE_ALARM_SYSTEM only if product requires it. |
| **Evidence→asset** | Must not auto-apply without user confirmation. Code: runs on AI extraction **apply** (after user applies). | Keep; add call in any other “evidence confirmed” path if it exists. |
| **Default asset names** | Task gives “Main Boiler” etc. Code: no name set; UI formats type. | Optional: set default `name` per asset_type in ensure_default_assets. |
| **Deletion** | Task: no easy deletion; if any, admin-only and logged. Code: no delete in client API/UI. | Keep no delete; if added later, restrict to admin and audit. |

---

## 3. Recommended additions (no duplication)

1. **Backfill / Initialise Assets (§12, §17)**  
   Add `POST /client/maintenance/properties/{property_id}/assets/ensure-defaults` that calls `ensure_default_assets_for_property` (idempotent) and returns e.g. `{ created: number, assets: list }`. Empty state button “Initialise Assets” calls it then refreshes.

2. **Audit and timeline when defaults created (§4, §15)**  
   When `ensure_default_assets_for_property` creates at least one asset:  
   - Log an audit event (e.g. ASSETS_INITIALISED).  
   - Optionally append one property timeline entry (“Assets initialised”) so §4 is fully satisfied.

3. **Optional**  
   - ASSET_CREATED in asset_events when each default asset is created.  
   - `related_evidence_id` on asset_events for document_linked events.  
   - “Linked evidence” in summary/table/drawer: either store asset_id on evidence/requirement and aggregate, or derive from requirement_type (gas_safety/eicr) for display.  
   - Edit modal: installed_year and age_estimate.  
   - “View Property Setup” in empty state if a route exists.

---

## 4. Key files (existing implementation)

- **Backend:** `property_assets_service.py`, `provisioning_status_hook.py`, `database.py` (property_assets, asset_events indexes), `client_maintenance.py` (assets routes), `maintenance_issues_service.py`, `maintenance_service.py`, `documents.py`, `property_timeline_service.py`, `risk_signal_service.py`.
- **Frontend:** `PropertyDetailPage.js` (Assets tab), `client.js` (assets API).

---

## 5. Assumptions (documented in full audit)

- client_id is the tenant boundary; no orgId.
- Asset types stored in lowercase snake_case; task enums (e.g. BOILER) are for display.
- Evidence→asset update runs only after user-driven confirmation (AI apply); any other confirm flow should call the same helper if evidence should update assets.
- One default asset per (property_id, asset_type).
- Asset deletion is out of scope for client UI; if introduced, admin-only and audited.
- FIRE_ALARM_SYSTEM not created by default unless product requires it.
