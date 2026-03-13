# Admin – Property Management (Training Manual)

## 1. Module name
**Property Management (Admin view)**

## 2. Audience
**Admin / internal staff only.** Clients use the client-facing Properties and Property Detail pages; this manual covers how admins see and manage client properties.

## 3. Purpose
Admins need to view and sometimes manage client properties (e.g. for support, provisioning, or overrides). Property creation and editing are primarily **client-facing**; the admin dashboard and client-context views expose client data including properties. Plan limits and provisioning status affect whether a client can add properties.

## 4. Where to find it in the UI
- **Admin:** Client list or search on Admin Dashboard → select a client. Client detail or context may show that client’s properties. There may be an explicit “Properties” or “Portfolio” section when viewing a client.
- **Backend:** Client dashboard API `GET /api/client/dashboard` (used by client) returns properties; admin may use `GET /admin/search` and then client-specific endpoints or admin endpoints that return client data including properties.
- **Implementation note:** The codebase has client-side `PropertiesPage` and `PropertyDetailPage` under `/properties` and `/properties/:propertyId`. Admin “property management” is often **viewing the same data in admin context** (e.g. after selecting a client) rather than a separate admin-only property list page. *Confirm in your environment where admins see client properties.*

## 5. What the user sees
- When viewing a client: list of that client’s properties (address/nickname, compliance status, property_id).
- Property limits are enforced on **create** via `POST /api/properties/create` (plan_registry). Admins may have ability to override or adjust limits (implementation-specific; not assumed).
- Provisioning: clients must be in `onboarding_status = PROVISIONED` to add properties (enforced in properties create route).

## 6. Step-by-step actions (admin)
| Action | What to do | What happens |
|--------|-------------|--------------|
| View a client’s properties | Open client (from search or Clients tab) | Client’s properties load; source is dashboard or client-scoped API. |
| Resolve “client can’t add property” | Check: (1) Client provisioned? (2) Plan property limit reached? | If not provisioned, complete onboarding. If at limit, client must upgrade or admin may adjust plan/limit if supported. |

## 7. What happens after each action
- View: Properties list displays; admin can use this for support (e.g. “I see your 3 properties”).
- Plan limit: When client hits limit, `POST /api/properties/create` returns 403 with `error_code: PLAN_LIMIT`; client sees error and possibly upgrade prompt.

## 8. Status/outcome examples
- **No properties:** Client has not added any; or data not loaded (check client_id/API).
- **403 on create (client):** Account not provisioned or plan limit exceeded; audit log may record `PLAN_LIMIT_EXCEEDED`.

## 9. Common errors or confusing points
- **Where do admins add a property for a client?** Typically the **client** adds properties from their portal. Admin may only view or have a separate tool; confirm in build.
- **Property “status” vs “compliance status”:** Properties have `compliance_status` (GREEN/AMBER/RED) derived from requirements; this is not the same as “active/inactive” (is_active).

## 10. Current limitations or known gaps
- Admin-specific “property management” UI (dedicated list of all clients’ properties) may not exist; admin may see properties only in client context. **Needs runtime confirmation.**
- Property edit/delete: implemented in client routes (`PATCH /api/properties/{id}`, soft delete); admin ability to edit on behalf of client is implementation-specific.

## 11. Notes for training staff
- Train admins: “Client properties are managed by the client. You can view them when you open that client.”
- For “client can’t add property” tickets: check provisioning status and plan limit; refer to Billing/plan if at limit.

---

## Trainer walkthrough (5 minutes)

1. **Open Admin Dashboard** → search for a client that has properties.
2. **Open that client** → locate where properties are shown (e.g. in a tab or section).
3. **Explain:** “This is the same data the client sees under their Properties page. We use it for support.”
4. **If a client reports they can’t add a property:** “Check they’re provisioned and under their plan’s property limit; limits are enforced when they click Add Property.”
