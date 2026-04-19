# Older Properties Fact Backfill Proposal (Operator-Safe)

## Goal

Bring older properties into alignment with the newer intake truth model without silent fleet-wide mutation.

Design posture:

- No automatic fleet rewrite.
- No hidden assumptions.
- No manual requirement editing.
- Property truth first, then engine truth, then explicit sync.

## In-Scope Facts (Phase 1)

Per property:

1. `jurisdiction` (required for correction workflow)
2. `has_gas_supply` (nullable: true/false/unknown)
3. `tenancy_active`
4. `deposit_taken`
5. `furnished` (nullable: true/false/unknown)
6. `has_communal_areas`

## 1) Detection: Missing/Incomplete Fact Identification

### Detection rule

A property is "fact-incomplete" if any of these are true:

- `jurisdiction` is missing or invalid/cannot be canonicalized.
- `has_gas_supply` is null (unknown).
- `furnished` is null (unknown).
- Any required boolean in scope is absent in legacy rows (defensive check).

### Output model

For each flagged property return:

- `property_id`, nickname/address
- current stored values for phase-1 facts
- `missing_facts[]`
- `unknown_facts[]`
- `effective_jurisdiction_label` + `jurisdiction_source` (for operator clarity)
- `last_requirements_sync_at` (if available)

### Endpoint (admin/support)

- `GET /api/admin/properties/fact-backfill-candidates`
  - query params: `client_id`, `jurisdiction`, `limit`, `skip`, `include_complete=false`
  - returns paginated candidate list and summary counts.

## 2) Facts in Scope First

Phase 1 includes only the six fields above because they are direct requirement engine drivers and already represented in property/planner logic.

Deferred fields (later):

- detailed tenancy subtype/date signals
- advanced local licensing metadata
- any fields not currently used by planner applicability

Reason for deferment: keep diff small, auditable, and tied to known engine conditions.

## 3) Admin/Support Correction Workflow (Per Property)

### UX flow

1. Operator opens candidate list.
2. Select property -> "Fact correction" drawer/page.
3. Edit only phase-1 facts.
4. Save property facts (no requirement edits).
5. View impact preview (planner-generated diff).
6. Confirm explicit sync/rematerialization for this property.

### Enforcement

- No bulk write in phase 1.
- Per-property save requires role `support_or_above` (or existing equivalent).
- Jurisdiction required in correction UI (cannot save empty).
- Unknown/null states explicit for nullable facts.

### Endpoint touchpoints

- Reuse existing property patch:
  - `PATCH /api/properties/{property_id}`
  - allow updating phase-1 facts in one request.

## 4) Preview Requirement Impact Before Sync

Yes, required before sync.

### Preview data shown

- current property facts vs proposed facts
- generated requirement summary before and after (read-only)
- delta:
  - added requirement types
  - removed requirement types
  - changed action-type breakdown
  - top impacted requirement names

### Endpoint (admin/support)

- `POST /api/admin/properties/{property_id}/requirements/fact-change-preview`
  - body: proposed phase-1 fact values
  - implementation: run planner on current facts and proposed facts; return structured diff only.

No requirement rows are mutated in preview.

## 5) Safe Sync/Rematerialization Trigger

After property facts are saved and operator reviewed preview:

- Trigger existing explicit sync endpoint:
  - `POST /api/admin/properties/{property_id}/requirements/sync-from-registry`

Safety controls:

- explicit operator action per property
- idempotent re-materialization
- no fan-out to other properties
- clear success/failure response + correlation id

## 6) Audit Trail

Record two separate auditable events:

1. **Fact correction event** (`PROPERTY_FACTS_UPDATED_FOR_COMPLIANCE`)
   - actor
   - property_id/client_id
   - before/after for phase-1 facts
   - reason/note (optional but recommended)

2. **Sync event** (`PROPERTY_REQUIREMENTS_SYNC_TRIGGERED_AFTER_FACT_UPDATE`)
   - actor
   - property_id/client_id
   - sync result summary (`upserted`, `obsolete_marked`, etc.)
   - link to preview hash/version if available

This keeps truth mutation and engine rematerialization distinctly auditable.

## 7) Later Client Self-Confirmation (Optional Phase 2)

Recommended later (not phase 1):

- Client portal prompt for properties with unknown facts (`has_gas_supply`, `furnished`, missing `jurisdiction`).
- Client can confirm facts only, never requirements.
- Confirmation writes to property truth, then offers explicit per-property sync CTA.

Why later:

- introduces new client-facing UX and notification complexity
- should follow operator flow stabilization and audit review

## Endpoint and UI Touchpoint Map

### Backend

- New:
  - `GET /api/admin/properties/fact-backfill-candidates`
  - `POST /api/admin/properties/{property_id}/requirements/fact-change-preview`
- Reuse:
  - `PATCH /api/properties/{property_id}`
  - `POST /api/admin/properties/{property_id}/requirements/sync-from-registry`

### Frontend (admin/support)

- New page/panel:
  - `AdminPropertyFactBackfillPage` (candidate list + filters)
- Property correction UI:
  - per-property fact editor (phase-1 facts only)
- Preview component:
  - before/after facts + requirement impact summary
- Sync CTA:
  - explicit "Sync requirements for this property"

No manual requirement edit controls are added.

## Rollout Plan (Small, Reviewable)

1. Add candidate detection endpoint + admin list UI (read-only).
2. Add per-property fact correction form (save only).
3. Add planner diff preview endpoint + UI compare.
4. Wire explicit sync CTA to existing sync endpoint.
5. Add audit events and tests.

Each step is independently reviewable and deployable.
