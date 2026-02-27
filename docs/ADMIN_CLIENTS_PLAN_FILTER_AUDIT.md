# Admin Clients List – Plan-Based Filtering: Implementation Audit

## Task requirements (summary)

- **Backend:** Client records must expose: `plan_code`, `subscription_status`, `current_period_end`, `cancel_at_period_end`, `property_count`, `portfolio_score_band`.
- **Backend:** Add query params to `GET /admin/clients`: `plan_code` (solo|portfolio|pro), `subscription_status`, `min_properties`, `max_properties`, `risk_band`, `q` (search name/email/CRN).
- **Backend:** Add indexes on `plan_code` and `subscription_status` for performance.
- **Frontend (Admin → Clients):** Filter bar with Plan dropdown + Status dropdown + Clear button; persist filters in URL; default view: all active plans.

---

## Current state

### 1. Backend: `GET /api/admin/clients` (`backend/routes/admin.py`, ~584–619)

| Requirement | Status | Notes |
|-------------|--------|--------|
| Expose `plan_code` | **Partial** | Client doc has `billing_plan` (e.g. `PLAN_1_SOLO`). Not named `plan_code` in response; can alias or keep and document. |
| Expose `subscription_status` | **Done** | On client doc (synced from Stripe). |
| Expose `current_period_end` | **Missing** | Lives in `client_billing`, not on `clients`. List returns only `db.clients.find()` with no join. |
| Expose `cancel_at_period_end` | **Missing** | Same as above; in `client_billing` only. |
| Expose `property_count` | **Missing** | Not stored on client; must be computed (e.g. `properties.count_documents({ client_id })`) or joined. |
| Expose `portfolio_score_band` | **Missing** | Not stored on client. Portfolio score/risk is computed on demand (e.g. portfolio route, catalog_compliance). No cached band on client. |
| Query param `plan_code` (solo|portfolio|pro) | **Missing** | Only `subscription_status` and `onboarding_status` exist. |
| Query param `subscription_status` | **Done** | Already supported. |
| Query param `min_properties`, `max_properties` | **Missing** | Not implemented. Requires aggregation or pre-stored count. |
| Query param `risk_band` | **Missing** | No filter. Would need stored or computed portfolio risk band. |
| Query param `q` (search name/email/CRN) | **Missing** | No text search param; filtering is client-side in the frontend. |

**Implementation detail:** Endpoint builds a query from `subscription_status` and `onboarding_status`, then `db.clients.find(query, {"_id": 0}).skip(skip).limit(limit)`. No aggregation, no join with `client_billing` or `properties`.

### 2. Backend: Indexes

| Requirement | Status | Notes |
|-------------|--------|--------|
| Index on `plan_code` | **Missing** | Client doc uses `billing_plan`; no index on it in `database.py`. Indexes on `clients`: `client_id`, `customer_reference`, `email`, `full_name`. |
| Index on `subscription_status` | **Missing** | No index on `subscription_status` for `clients`. |

### 3. Frontend: Admin → Clients (`frontend/src/pages/AdminDashboard.js`)

- **Location:** Clients list is inside AdminDashboard (e.g. “Clients” section with table), not a separate route. Fetches `GET /admin/clients?limit=100` with no query params.
- **Filter bar:** Search box (name/email) and one dropdown: “All Status” / “Provisioned” / “Pending Payment” / “Intake Complete” (maps to `onboarding_status`). No Plan dropdown, no Subscription Status dropdown.
- **Clear button:** None.
- **URL persistence:** None; filters are local state only (`searchTerm`, `statusFilter`).
- **Default view:** All clients (limit 100). No “all active plans” default.

---

## Conflicts and design choices

### 1. `plan_code` vs `billing_plan`

- Backend and Stripe sync use `billing_plan` on the client doc (e.g. `PLAN_1_SOLO`, `PLAN_2_PORTFOLIO`, `PLAN_3_PRO`).
- Task asks for `plan_code` and filter values `solo|portfolio|pro`.  
- **Recommendation:** Keep `billing_plan` in the DB; in the API response expose `plan_code` as an alias of `billing_plan` (or same value). For the filter, accept `plan_code` with values `solo`, `portfolio`, `pro` and map to `PLAN_1_SOLO`, `PLAN_2_PORTFOLIO`, `PLAN_3_PRO` in the query. No schema change.

### 2. `current_period_end`, `cancel_at_period_end`, `property_count` on list

- These are not on `clients`: period fields are in `client_billing`, property count is from `properties`.
- **Recommendation:** For the list endpoint, join or lookup `client_billing` by `client_id` (e.g. one lookup per client or aggregation with `$lookup`) and add a property count (e.g. `$lookup` + `$size` or a separate count aggregation). Return a single response shape per client that includes `plan_code`, `subscription_status`, `current_period_end`, `cancel_at_period_end`, `property_count`. Avoid duplicating these fields on `clients`; keep billing as source of truth in `client_billing`.

### 3. `portfolio_score_band` and `risk_band` filter

- Portfolio score/risk is computed (e.g. `score_to_risk_level(portfolio_score)` → “Low Risk”, “Moderate Risk”, “High Risk”, “Critical Risk”). Not stored on client.
- **Options:**  
  - **A:** Add a cached field (e.g. `portfolio_score_band` or `portfolio_risk_level`) on `clients` or `client_billing`, updated by a job or on score change; list and filter use it.  
  - **B:** Compute in the list endpoint (e.g. for each client call compliance/portfolio logic). Expensive for large lists.  
  - **C:** Expose `portfolio_score_band` only when a cached field exists (e.g. from a future job); omit or set to `null` otherwise; implement `risk_band` filter only when that cache exists.  
- **Recommendation:** Implement list and filters **without** `portfolio_score_band` and `risk_band` first (so we don’t add N+1 or heavy aggregation). Add a short comment in the API that `portfolio_score_band` is reserved for future use. If product wants it for v1, implement Option A (cached field + job) and then add the field and `risk_band` filter.

### 4. Default view: “all active plans”

- Ambiguous: could mean “subscription_status = ACTIVE” or “plan in [Solo, Portfolio, Pro]” (i.e. paying).
- **Recommendation:** Default to “all clients” with **no** plan or subscription filter (current behaviour), but document that “default view: all active plans” can be met by defaulting the **Subscription status** dropdown to “Active” (i.e. send `subscription_status=ACTIVE` when no filter is set). That matches the existing drilldown behaviour (“Active Clients” = `subscription_status=ACTIVE`) and avoids changing semantics of “all” without product confirmation.

---

## Proposed implementation plan (no code yet)

1. **Backend – GET /admin/clients**
   - Add query params: `plan_code` (solo|portfolio|pro → `billing_plan`), `subscription_status` (existing), `min_properties`, `max_properties`, `risk_band` (optional, no-op until cache exists), `q` (search: name, email, CRN).
   - Build query: from `clients`; if `q`, add `$or` on `full_name`, `email`, `customer_reference` (regex or text search); if `plan_code`, map to `billing_plan`; keep existing `subscription_status`/`onboarding_status`.
   - For `min_properties`/`max_properties`: use aggregation: `$lookup` properties, `$addFields` with `property_count`, then `$match` on `property_count`. Alternatively, a separate pipeline or subquery that filters by client_id list where count matches.
   - Enrich each client for response: join `client_billing` (by `client_id`) for `current_period_end`, `cancel_at_period_end`; add `property_count` (from aggregation or count). Expose `plan_code` (alias of `billing_plan`). Leave `portfolio_score_band` as `null` or omit until a cached field exists.
   - Keep response paginated (`skip`, `limit`, `total`).

2. **Backend – Indexes**
   - In `database.py`, add indexes on `clients`: `billing_plan` (for plan filter), `subscription_status` (for status filter). Use `billing_plan` so it matches the field name in the DB; API can still expose it as `plan_code`.

3. **Frontend – Admin Clients**
   - Add filter bar: Plan dropdown (All / Solo / Portfolio / Pro), Subscription Status dropdown (All / Active / Pending / etc.), optional Clear button.
   - Persist filters in URL (e.g. `?plan_code=portfolio&subscription_status=ACTIVE`). Use the same param names as the API.
   - On load, read query string and set initial filter state; when filters change, update URL and refetch.
   - Default: no filter (all clients), or if “default view: all active plans” is confirmed, set default Subscription Status to “Active” and reflect that in the URL.
   - Optional: show `current_period_end`, `cancel_at_period_end`, `property_count` in the table if the API returns them.

4. **risk_band / portfolio_score_band**
   - Defer until a cached band exists or product decides to add a job. Document in API and audit that `portfolio_score_band` is reserved and `risk_band` filter is a no-op until then.

---

## Summary

| Area | Implemented | Missing |
|------|-------------|--------|
| Client fields in list | `subscription_status`, `billing_plan` (as plan) | `plan_code` (alias), `current_period_end`, `cancel_at_period_end`, `property_count`, `portfolio_score_band` |
| Query params | `subscription_status`, `onboarding_status` | `plan_code`, `min_properties`, `max_properties`, `risk_band`, `q` |
| Indexes | — | `billing_plan`, `subscription_status` on `clients` |
| Frontend filters | Search (local), onboarding status dropdown | Plan dropdown, Subscription Status dropdown, URL persistence, Clear, default “active” if desired |

No duplicate or conflicting list endpoints: the single list is `GET /api/admin/clients`. Billing-specific search is `GET /api/admin/billing/clients/search` (different use case). Extending `GET /api/admin/clients` with the above keeps one source of truth for the Admin Clients list.
