# Timeline Tab – Task vs Codebase Audit

**Task:** Implement the Timeline tab for the Property Detail page as a unified enterprise-grade activity and audit stream.

**Audit date:** Based on current codebase state. Purpose: identify what is implemented, what data/APIs exist, what is missing, and the safest implementation path without duplication or conflict.

---

## 1. CURRENT STATE: TIMELINE TAB

### Frontend (`frontend/src/pages/PropertyDetailPage.js`)

- **Tab:** Timeline is the 6th tab (Overview, Compliance, Maintenance, Evidence, Contractors, **Timeline**, Risk Signals, Assets). It has no feature gate (`feature: null`).
- **Content:** Placeholder only:
  - Single `Card` with title "Timeline" and body: *"A unified timeline of documents, compliance updates, maintenance, and contractor activity will appear here. Coming soon."*
- **No** filters, no event list, no empty state, no deep links, no loading state.

### Conclusion

The Timeline tab **exists in the UI** but has **no implementation**. All task requirements for this tab are currently **missing**.

---

## 2. BACKEND: EXISTING EVENT SOURCES AND ENDPOINTS

### A) Property-scoped (usable today)

| Source | Collection / Service | Client endpoint | Property filter | Shape (relevant fields) |
|--------|----------------------|-----------------|-----------------|--------------------------|
| **Score ledger** | `score_ledger_events` | `GET /api/client/ledger` | `property_id` query | `items[]`: `created_at`, `trigger_type`, `trigger_label`, `before_score`, `after_score`, `delta`, `actor_type`, `requirement_id`, `document_id`, `property_id` |
| **Score change log** | `score_change_log` | `GET /api/portfolio/properties/:propertyId/score-history` | path | `entries[]`: `previous_score`, `new_score`, `delta`, `reason`, `created_at`, `changed_requirements` |
| **Work orders** | `work_orders` | `GET /api/client/maintenance/work-orders?property_id=...` | `property_id` query | `work_orders[]`: `work_order_id`, `description`, `status`, `created_at`, `property_id` (no “updated_at” event log; list is current state) |

- **Ledger** (`score_ledger_service.list_ledger`) already supports `property_id`, `trigger_type`, `from_date`, `to_date`, `limit`, `cursor`. Trigger types map to task-friendly labels (e.g. DOCUMENT_UPLOADED, CERT_DETAILS_CONFIRMED, REQUIREMENT_STATUS_CHANGED).
- **Score history** returns simple score-delta entries; no `document_id`/`requirement_id` in response (only in ledger).
- **Work orders**: only current list; no dedicated “work order created / status changed” event store. Events could be inferred from `created_at` (and optional `updated_at` if added later) as synthetic “Work order created” / “Work order updated” events.

### B) Client-scoped (no property filter today)

| Source | Collection / Service | Client endpoint | Property in data? | Notes |
|--------|----------------------|-----------------|--------------------|--------|
| **Audit timeline** | `audit_logs` | `GET /api/portfolio/audit-timeline?limit=50` | In **metadata** for some actions (e.g. DOCUMENT_UPLOADED has `metadata.property_id`) | Returns flat `timeline[]` + `categorized`. No `property_id` query param. Filtering by property would require client-side or new backend filter. |
| **Score events (“What changed”)** | `score_events` | `GET /api/client/score/changes?limit=...` | Yes, each item has `property_id` | `get_changes(client_id, limit)` in `score_events_service` does **not** accept `property_id`; would need backend change to filter. |

- **Audit log** entries: document uploads (and some others) store `metadata.property_id`. So a property-scoped timeline could either:
  - Add a new backend endpoint that queries `audit_logs` with `metadata.property_id = :propertyId`, or
  - Use portfolio audit-timeline and filter client-side (weaker for large portfolios).
- **Score events**: perfect for evidence/score narrative and already have `property_id`; adding an optional `property_id` to `get_changes()` (or a dedicated property timeline) would allow property-scoped “What changed” feed.

### C) Not present or not event-shaped

- **Contractor assignments**: No dedicated event log found; tenant/maintenance routes log work_order creation to audit with `resource_type="work_order"`, but no “contractor assigned” event store for client.
- **Predictive / risk signals**: No “risk signal created/updated” event log; insights are computed on demand.
- **Provisioning / setup**: Audit has PROVISIONING_* actions but they are client-level; no property-scoped “property created” event API for client.

---

## 3. TASK REQUIREMENTS vs AVAILABILITY

### 3.1 Timeline event types (task §2)

| Category | Task event types | Available in backend | Notes |
|----------|------------------|----------------------|--------|
| **Compliance** | requirement created/status changed, expiring/overdue, not applicable | Partially | Ledger: `REQUIREMENT_STATUS_CHANGED`, `SCHEDULED_RECALC` (expiry). No explicit “requirement created” or “marked N/A” event stream. |
| **Evidence** | document uploaded, extraction completed, confirmed, linked, removed | Partially | Ledger: `DOCUMENT_UPLOADED`, `CERT_DETAILS_CONFIRMED`, `DOCUMENT_REMOVED`, `DOCUMENT_STATUS_CHANGED`. Score events: `DOCUMENT_UPLOADED`, `DOCUMENT_CONFIRMED`. Audit: DOCUMENT_* actions (some with metadata.property_id). |
| **Maintenance** | issue created, severity updated, WO created/status changed/completed | Partially | Work orders list gives “created” via `created_at`. No status-change event log; could add synthetic “Work order created” from list. |
| **Contractors** | contractor assigned/changed, visit scheduled, invoice submitted/approved | No | No client-facing contractor event log found. Placeholder only. |
| **Score / risk** | compliance score changed, risk changed, predictive signal created/updated | Yes (score); no (risk) | Ledger + score_change_log + score_history: score changes. No risk/signal event log. |
| **System / setup** | property created, provisioning completed, default assets | Partial | Audit has PROVISIONING_* but not property-scoped for client. Placeholder or filter audit by metadata if present. |

### 3.2 UI (task §3–4)

- **Header, filters, list, event cards, detail/expand, deep links:** Not implemented; design can follow task once data is defined.
- **Empty state (task §9):** Not implemented; task asks for “No activity…” plus Upload Evidence / Add Issue / View Property Setup.

### 3.3 Filters (task §5)

- **Event type:** Must be implemented in UI; backend can support via `trigger_type` (ledger) and a unified endpoint that maps to a single “category” field.
- **Date range:** Ledger supports `from_date`, `to_date`; score-history and others can be filtered by date in a unified endpoint.
- **Actor:** Ledger has `actor_type` (user/admin/system); can be exposed as filter.

### 3.4 Feature flag behaviour (task §10)

- Task: Timeline tab always shown; if maintenance/contractor/risk modules disabled, still show timeline but hide or lock unavailable event **links**.
- Current: Timeline tab has no feature gate and no content. Aligning with task means implementing the tab and only gating **links** to Maintenance/Contractors/Risk Signals by feature flags, not the whole tab.

---

## 4. CONFLICTS AND RECOMMENDATIONS

### 4.1 One endpoint vs multiple calls

- **Task (§6):** Prefer a single property timeline endpoint, e.g. `GET /api/properties/:propertyId/timeline` (or `/api/portfolio/properties/:propertyId/timeline`), with a unified `items[]` shape.
- **Current:** No such endpoint. Existing data is split across:
  - `GET /api/client/ledger?property_id=...`
  - `GET /api/portfolio/properties/:id/score-history`
  - `GET /api/client/maintenance/work-orders?property_id=...`
  - Optionally `GET /api/portfolio/audit-timeline` (then filter by property)
  - Optionally `GET /api/client/score/changes` (if backend adds `property_id` filter)

**Recommendation:** Add a **property-scoped timeline endpoint** on the backend that:

- Merges (and optionally deduplicates) at least: **score_ledger_events** (by property_id), **score_change_log** (by property_id), and optionally **work_orders** for this property (synthetic “Work order created” from `created_at`).
- Optionally includes a subset of **audit_logs** where `metadata.property_id === propertyId` (if index/performance allows).
- Returns a single chronological list with a **normalized shape** (id, timestamp, category, eventType, title, description, actorType, linkedEntityType, linkedEntityId, linkedEntityLabel, impact).
- Supports **filters**: event type/category, date range, actor (and optionally search), so the frontend does not need to merge or filter multiple feeds.

**Safest option:** Implement the new endpoint and keep existing endpoints unchanged. Frontend uses only the new timeline API for the Timeline tab. No removal of existing routes or behaviour.

### 4.2 Frontend merge vs backend merge

- Task (§6): “Do NOT build the merge entirely on the frontend if avoidable.”
- **Recommendation:** Implement the merge in the backend (single timeline endpoint). If a temporary solution is needed before that endpoint exists, a **short-term** frontend-only merge from ledger + score-history + work orders is acceptable as a stopgap, with a clear comment and follow-up to replace it with the backend endpoint. Prefer not to add audit-timeline merge on the frontend (large payload, mixed property_ids).

### 4.3 Event types not yet available

- **Contractor events, risk signal events, provisioning (property-level):** No backend event streams today.
- **Recommendation:** Backend timeline endpoint should define a **normalized event model** and return only what exists. Frontend renders all categories (Compliance, Evidence, Maintenance, Contractors, Score & Risk, System) in filters and in event type mapping, but **gracefully degrades**: show “No events” for categories with no data; for “Contractors” / “Risk” / “System” use placeholders or hide those filters until data exists. Task (§2) says to include placeholders and note them clearly.

---

## 5. DATA MODEL ALIGNMENT

### 5.1 Suggested backend response (task §6)

Unified endpoint response can follow the task’s shape and map existing data as below:

- **id:** Unique per item (e.g. ledger `created_at` + index, or a composite id).
- **timestamp:** ISO date; from ledger `created_at`, score_change_log `created_at`, work_orders `created_at`.
- **category:** EVIDENCE | COMPLIANCE | MAINTENANCE | CONTRACTORS | SCORE_RISK | SYSTEM (map from ledger `trigger_type` and source).
- **eventType:** e.g. DOCUMENT_UPLOADED, CERT_DETAILS_CONFIRMED, WORK_ORDER_CREATED, SCORE_RECALCULATED.
- **title, description:** From ledger `trigger_label` + enrichment; or from score_change_log `reason`; or from work order description.
- **actorType / actorLabel:** From ledger `actor_type`; or “System” for score_change_log.
- **linkedEntityType / linkedEntityId / linkedEntityLabel:** From ledger `document_id`, `requirement_id`; work_order_id; etc.
- **impact:** From ledger `delta` (score delta); score_change_log `delta`.

### 5.2 Sources → categories (mapping)

- **score_ledger_events** → EVIDENCE (DOCUMENT_*), COMPLIANCE (REQUIREMENT_*, SCHEDULED_RECALC), SCORE_RISK (score changes), SYSTEM (PROPERTY_ADDED, etc.).
- **score_change_log** → SCORE_RISK (score change; can merge with ledger or dedupe by time window).
- **work_orders** (current list) → MAINTENANCE; one “Work order created” event per row using `created_at` and `description`/`work_order_id`.
- **audit_logs** (if included) → EVIDENCE / COMPLIANCE / SYSTEM depending on action; filter by `metadata.property_id`.
- **Contractors / risk / provisioning:** No mapping until event stores exist; placeholder or future extension.

---

## 6. FILES AND TOUCHPOINTS

### 6.1 Frontend (Timeline tab only)

- **`frontend/src/pages/PropertyDetailPage.js`**
  - Replace Timeline placeholder with:
    - Header: title “Timeline” + filters (event type, date range, actor) + optional search.
    - Loading and error states.
    - List of event cards (icon, title, description, timestamp, actor, linked label, impact badge, action link).
    - Expandable row or detail panel for full details and link to related tab (Evidence / Compliance / Maintenance / Contractors / Risk Signals).
    - Empty state: “No activity has been recorded for this property yet.” + Upload Evidence, Add Issue, View Property Setup.
  - Deep links: by `category`/`eventType` and `linkedEntityId` → set `activeTab` and/or navigate to documents with query params.
  - Feature flags: only control visibility of **links** to Maintenance/Contractors/Risk Signals, not the tab or other events.

### 6.2 Backend (recommended)

- **New route (e.g. under portfolio or client):**
  - `GET /api/portfolio/properties/:propertyId/timeline` (or `GET /api/client/properties/:propertyId/timeline`)
  - Query params: `category`, `from_date`, `to_date`, `actor_type`, `limit`, `cursor`.
- **New service or module:** e.g. `property_timeline_service` (or extend an existing service) that:
  - Reads from `score_ledger_events`, `score_change_log`, `work_orders` (and optionally `audit_logs`) for the given property.
  - Merges and sorts by timestamp descending.
  - Normalizes to the unified event shape.
  - Applies filters and pagination.

### 6.3 Optional backend changes (if not doing unified endpoint first)

- **`GET /api/client/score/changes`:** Add optional `property_id` query; filter `score_events` by it. Frontend could then call ledger + score-history + score/changes(property_id) + work_orders and merge in the client (temporary).
- **Audit timeline:** Add optional `property_id` to `GET /api/portfolio/audit-timeline` and filter by `metadata.property_id` when provided. Allows property-scoped audit events without a full merge in the first iteration.

---

## 7. PLACEHOLDERS / FALLBACKS

- **Contractor events:** No data → filter “Contractors” can show “No events” or be hidden; event type still in enum for future.
- **Risk signal events:** No event log → same; optional “Risk signal updated” placeholder text only if needed.
- **System / provisioning:** Use audit PROVISIONING_* only if we include audit and can filter by property (metadata may not always have property_id). Otherwise “No events” for System.
- **Work order status changes:** Only “Work order created” from current list; “Work order completed” could be added when backend writes such events (e.g. when status becomes COMPLETED). Until then, no “status changed” events.

---

## 8. ACCEPTANCE CRITERIA VS CURRENT STATE

| Criterion | Status | Action |
|-----------|--------|--------|
| Timeline tab exists and loads property-specific event history | Tab exists; no load | Add data fetch (unified endpoint or multi-call stopgap) and render list. |
| Events in reverse chronological order | N/A | Backend sort desc by timestamp; frontend preserves order. |
| Filters work | Not implemented | Add event type, date range, actor (and optional search); wire to API params or client filter. |
| Events link to correct workflows/tabs | Not implemented | Map category/linkedEntity to tab and document/requirement/work order links. |
| Empty state clear | Not implemented | Add copy + Upload Evidence, Add Issue, View Property Setup. |
| Missing module data degrades gracefully | N/A | Show timeline even when maintenance/contractors/risk disabled; lock or hide only those links. |
| No existing property route broken | OK | Additive only; no route or contract change on existing endpoints unless optional query added. |

---

## 9. SUMMARY

- **Implemented:** Only the Timeline tab shell (placeholder text). No events, no filters, no empty state, no deep links.
- **Available today:** Property-scoped **score ledger** and **score change history**; property-scoped **work orders** list. Client-scoped **audit timeline** and **score/changes** (the latter has `property_id` per item but no API filter).
- **Missing:** (1) A **unified property timeline API** that merges ledger, score_change_log, work orders (and optionally audit); (2) **Timeline tab UI** (filters, event cards, detail, empty state, deep links); (3) **Contractor / risk / system** event sources (placeholders only).
- **Conflict:** Task prefers one backend endpoint; current design has no property timeline endpoint. **Safest approach:** add `GET /api/portfolio/properties/:propertyId/timeline` (or under client) with normalized event model and filters; implement Timeline tab to consume it only; leave existing endpoints unchanged. If timeline endpoint is deferred, a **temporary** frontend merge from ledger + score-history + work orders is acceptable with a clear migration path to the backend endpoint.
- **Event types:** Evidence and score/risk are well covered by ledger + score_change_log; compliance partially; maintenance as “work order created” only; contractors and risk signals as placeholders until event stores exist.

---

## 10. OUTPUT CHECKLIST (FOR IMPLEMENTATION)

When implementing:

- **Files to change:**  
  - Frontend: `PropertyDetailPage.js` (Timeline tab only).  
  - Backend: new route + service for property timeline (and optionally client.js getScoreChanges(propertyId) if using multi-call approach).

- **Event sources used:**  
  - Live: `score_ledger_events` (property_id), `score_change_log` (property_id), `work_orders` (property_id).  
  - Optional: `audit_logs` (metadata.property_id), `score_events` (if filtered by property_id).

- **Endpoints created or reused:**  
  - New: `GET /api/portfolio/properties/:propertyId/timeline` (recommended).  
  - Reused as-is: `getLedger`, `getScoreHistory`, `getMaintenanceWorkOrders` if a temporary frontend merge is used.

- **Placeholder/fallback logic:**  
  - Contractor / risk / system categories: no data or placeholder text; filters still available for future.  
  - Work orders: only “created” events until status-change events are logged.

- **Live vs prepared:**  
  - **Live:** Evidence (document uploaded/confirmed/removed), compliance (requirement status, expiry recalc), score changes, work order created (synthetic).  
  - **Prepared for later:** Contractor assigned/changed, risk signal created/updated, property created/provisioning (if audit included and filtered by property).
