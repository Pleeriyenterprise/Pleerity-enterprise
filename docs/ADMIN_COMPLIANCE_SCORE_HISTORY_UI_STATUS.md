# Admin Compliance Score History UI — Implementation Status

## Implemented

| Requirement | Status | Notes |
|-------------|--------|--------|
| **UI placement** | Done | Inside Client Detail (modal) → Overview → select property via "Score history" → section with current score + history table. No new global tab. |
| **Current compliance score** | Done | Shown as "Current score: X" with last_calculated_at when history is loaded. |
| **Compliance Score History table** | Done | Last 20 entries; columns: Timestamp (created_at), Score, Trigger reason (reason), Actor. Newest first. |
| **View full history modal** | Done | When ≥20 entries, "View Full History" loads up to 200 and shows in modal. |
| **API endpoint** | Done | GET /api/admin/properties/{property_id}/compliance-score-history (backend, admin-only). |
| **Auth** | Done | Uses same `api` client with Bearer token; backend enforces admin_route_guard. |
| **Error handling** | Done | Toast + inline error message; no dashboard crash. |
| **Empty state** | Done | "No history recorded." (see below for exact copy). |
| **Loading state** | Done | Spinner while loading (see below for skeleton). |
| **Access control** | Done | Only admin/owner can reach the endpoint; client users do not see this UI. |

## Implemented (gaps closed)

| Requirement | Status |
|-------------|--------|
| **adminApi function** | Added `adminAPI.getComplianceScoreHistory(propertyId, limit)` in `frontend/src/api/client.js`; AdminDashboard uses it. |
| **403/401 message** | On 403/401 response we show "Not authorized". |
| **Empty state copy** | "No compliance score history recorded yet." |
| **Loading: skeleton rows** | Five skeleton rows with animate-pulse in the table while loading. |
| **Retry button** | On error, inline "Retry" button that re-fetches (data-testid="retry-score-history"). |
| **"Compliance" panel** | Section titled "Compliance" with (a) "Current Compliance Score" and (b) "Compliance Score History" table. |

## Backend response shape (reference)

- `current_score`, `last_calculated_at`, `compliance_version`, `property_id`, `client_id`
- `history`: array of `{ created_at, score, reason, actor: { id, role } }`
