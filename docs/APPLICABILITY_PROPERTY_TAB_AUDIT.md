# Applicability rule: Property tab vs Requirements tab – audit and fix

## Current state

### Requirements tab (Requirements page)
- **Data source:** `GET /client/requirements` → returns **requirement rows** from the `requirements` collection.
- **Applicability:** Each row has `applicability` (REQUIRED | NOT_REQUIRED | UNKNOWN) and optional `not_required_reason`. Users can **edit** these via the requirement Edit modal; backend `PATCH /api/properties/{property_id}/requirements/{requirement_id}` updates applicability and triggers recalc.
- **Scope:** Only **existing** requirement rows are listed. Catalog items that have no requirement row do **not** appear here.

### Property tab (Property detail page)
- **Data source:** `GET /portfolio/properties/{id}/compliance-detail` → returns a **matrix** from `catalog_compliance.get_property_compliance_detail()`.
- **Matrix build:** For each **catalog** item that applies to the property (via `evaluate_applies_to(profile, applies_to)`), the code looks for a matching requirement row (by `requirement_type` or `requirement_code` vs catalog `code`). If a row exists, status/expiry come from the row; if **no row exists**, the item is still shown with status PENDING ("Missing evidence").
- **Applicability:** There is **no** "Mark as not applicable" or applicability control on the property tab. The matrix does **not** consider requirement-row `applicability`: even if a row existed with `applicability=NOT_REQUIRED`, the catalog would still include that item (it only uses catalog `applies_to` and property profile).

### Gap
- **Missing evidence** items on the property tab are often **catalog-applicable items with no requirement row**. They cannot be marked "not applicable" from the Requirements tab because they do not appear there (no row). They cannot be marked from the property tab because there is no such control.
- Result: Users see many "Missing evidence" rows with no way to record "this does not apply to this property," which keeps scores and KPIs misleading and blocks a single place to set applicability.

## Conflicting or duplicate behaviour
- **None.** Applicability is only editable in one place (Requirements tab, for existing rows). The gap is missing functionality, not conflicting logic.

## Proposed solution (single, global approach)

### 1. Backend: Catalog matrix respects requirement-row applicability
- **File:** `backend/services/catalog_compliance.py` – `get_property_compliance_detail()`.
- **Change:** When building the matrix, for each catalog-applicable item, if a requirement row exists **and** that row has `applicability == "NOT_REQUIRED"`, **exclude** that item from the matrix (do not add it to `matrix`, and do not count it in KPIs or weighted score). So "not applicable" = not shown on the property tab and not scored.
- **Data:** Include `applicability` in the requirements query projection and use it in the loop before appending to `matrix` / updating KPIs.

### 2. Backend: Create requirement row for "Mark as not applicable"
- **New endpoint:** `POST /api/client/properties/{property_id}/requirements/mark-not-applicable` (or under portfolio/client as appropriate). Body: `{ "requirement_code": "<catalog code>", "not_required_reason": "<one of NOT_REQUIRED_REASONS>" }`.
- **Behaviour:**
  - Resolve property and client (client_route_guard; property must belong to client).
  - Validate `requirement_code` against `requirements_catalog` (must exist).
  - If a requirement row already exists for this property + code, **update** it to `applicability=NOT_REQUIRED` and `not_required_reason` (idempotent).
  - If no row exists, **create** a new requirement row with: `client_id`, `property_id`, `requirement_type` = catalog code (for matching), `requirement_code` = catalog code, `description` = catalog title, `applicability=NOT_REQUIRED`, `not_required_reason`, `status=NOT_REQUIRED` (or let deterministic status apply), `frequency_days` (e.g. 0 or from catalog), `due_date` (null or omit).
  - Trigger compliance recalc for the property after create/update.
- **Reuse:** Use the same `NOT_REQUIRED_REASONS` and validation as the existing PATCH requirement endpoint (`properties.py`).

### 3. Frontend: Property detail – "Mark as not applicable"
- **File:** `frontend/src/pages/PropertyDetailPage.js`.
- **Change:** For each matrix row that shows "Missing evidence" (status PENDING or equivalent), add a second action: **"Mark as not applicable"** (link or button). On click, open a small modal: dropdown for `not_required_reason` (same list as Requirements page: no_gas_supply, exempt, not_applicable, other) and a Confirm button. On confirm, call the new API with `requirement_code` (from matrix row) and selected reason, then refresh compliance detail (and optionally show success toast). After backend change (1), the row will disappear from the matrix on refresh.
- **Global:** This is the only place we add "Mark as not applicable" for **catalog items without a row**; the Requirements tab continues to handle applicability for **existing** rows. No duplication of logic; one source of truth (requirement row applicability).

### 4. Consistency
- **Requirements tab:** Unchanged; still shows all requirement rows and allows editing applicability. New rows created from the property tab will appear here with NOT_REQUIRED and can be reverted to REQUIRED/UNKNOWN if needed.
- **Scoring/calendar:** Already exclude NOT_REQUIRED (compliance_scoring, calendar, expiry_utils). Catalog matrix exclusion aligns property tab with that behaviour.
- **Audit:** Log requirement create/update (e.g. REQUIREMENT_UPDATED or new action) with property_id, requirement_code, applicability=NOT_REQUIRED.

## Implementation order
1. Backend: catalog_compliance – exclude NOT_REQUIRED from matrix (and KPIs/score).
2. Backend: new mark-not-applicable endpoint + create/update requirement row.
3. Frontend: Property detail – "Mark as not applicable" action + modal + API call + refresh.

## Risks and mitigations
- **Catalog code vs requirement_type mismatch:** Use catalog `code` as `requirement_type` and `requirement_code` when creating the row so `_requirement_matches_code()` continues to match. Catalog codes are lowercase (e.g. `co_alarms`); keep same format.
- **Existing NOT_REQUIRED rows:** Once we exclude them from the matrix, they stop appearing on the property tab; they remain visible and editable on the Requirements tab. No data loss.
- **Double submission:** Frontend can disable the button after first click until the request completes (and show loading state).

## Files to touch
- `backend/services/catalog_compliance.py` – exclude NOT_REQUIRED rows from matrix.
- `backend/routes/` – new route for mark-not-applicable (client or portfolio router).
- `frontend/src/pages/PropertyDetailPage.js` – action, modal, API, refresh.
- Optional: `frontend/src/api/client.js` – add `markRequirementNotApplicable(propertyId, body)`.
