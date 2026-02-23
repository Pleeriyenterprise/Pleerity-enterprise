# Downgrade Support Audit – Compliance Vault Pro (Stripe + Portal)

## 1) Billing portal

| Requirement | Status | Location |
|-------------|--------|----------|
| POST /api/billing/portal (auth, returns Stripe billing portal URL) | **Implemented** | `backend/routes/billing.py` – `create_billing_portal()` uses `stripe.billing_portal.Session.create()`, returns `portal_url`. Client resolved via `client_route_guard`. |

No change needed.

---

## 2) Webhook truth

| Event | Handler | Client/client_billing fields updated |
|-------|---------|----------------------------------------|
| checkout.session.completed | `_handle_checkout_completed` | client: billing_plan, subscription_status, stripe_customer_id, stripe_subscription_id, entitlement_status, entitlements_version. client_billing: current_plan_code, subscription_status, current_period_end, stripe_subscription_id, etc. |
| customer.subscription.created | `_handle_subscription_change` | client: billing_plan, subscription_status, entitlement_status, entitlements_version. client_billing: current_plan_code, subscription_status, current_period_end, over_property_limit (on downgrade). |
| customer.subscription.updated | `_handle_subscription_change` | Same as above. |
| customer.subscription.deleted | `_handle_subscription_deleted` | subscription_status CANCELED, entitlement_status DISABLED. |
| invoice.paid | `_handle_invoice_paid` | subscription_status, entitlement_status from subscription. |

**Note:** `plan_code` in the task is represented as `billing_plan` on `clients` and `current_plan_code` on `client_billing`. `current_period_end` and `stripe_subscription_id` live on `client_billing`; `stripe_subscription_id` is also set on `clients` in checkout flow. Entitlements are driven only by webhook updates; no front-end granting.

---

## 3) Downgrade enforcement (server-side)

| Guard | Status | Location |
|-------|--------|----------|
| Create property | **Implemented** | `backend/routes/properties.py` – `plan_registry.enforce_property_limit()`, 403 with `error_code="PLAN_LIMIT"`; audit `PLAN_LIMIT_EXCEEDED`. Counts only active properties. |
| Bulk create | **Implemented** | Same file, bulk create path; same 403 + PLAN_LIMIT. |
| Upload documents | **Implemented** | Single and bulk upload block when property `is_active` is False (archived/read-only). Zip upload gated by `zip_upload` feature. |
| Reminders/digests | **Implemented** | `backend/services/jobs.py` – entitlement_status and plan checks; no sends for non-ENABLED. |
| Reports | **Implemented** | `backend/routes/reports.py` – `plan_registry.enforce_feature("reports_pdf"`, etc.) |

No user data is deleted on downgrade; webhook sets `over_property_limit` on `client_billing` when property count > new plan limit.

---

## 4) Over-limit handling

| Requirement | Status | Notes |
|-------------|--------|--------|
| over_limit + over_limit_details in setup-status | **Implemented** | Add to GET /api/portal/setup-status from client_billing.over_property_limit and property counts. |
| API + UI to select which properties are ACTIVE | **Implemented** | Add property-level `is_active` (default true); when over limit, only “active” count toward limit; archived = read-only. API: PATCH property to set is_active; document upload blocked for archived. |

---

## 5) FAQ / UI copy

| Requirement | Status | Location |
|-------------|--------|----------|
| “Your data is not deleted on downgrade” | **Present** | `frontend/src/pages/BillingPage.js` – “Your data is never deleted. If you exceed the property limit…” |
| Read-only/archive behaviour | **Partial** | Same FAQ mentions archiving; can add explicit “archived properties are read-only”. |

---

## 6) Tests

| Test | Status |
|------|--------|
| Webhook subscription.updated to lower plan updates plan_code and limits | **Partial** | Webhook tests exist; add/confirm assertion for plan update and over_property_limit. |
| Over-limit blocks create-property with PLAN_LIMIT | **Implemented** | `tests/test_downgrade_support.py`: test_create_property_over_limit_returns_403_with_plan_limit. |
| Data remains present, only access changes | **Implemented** | test_data_remains_archived_property_still_listed; test_over_limit_archived_property_blocks_upload. |

---

## Implementation summary (no conflicts)

- **Billing portal:** Already in place; no duplication.
- **Webhooks:** Already handle all five events and update client/client_billing; keep as-is; optionally ensure `error_code` in API responses uses `PLAN_LIMIT` where specified.
- **Guards:** Align property-create 403 detail to include `error_code: "PLAN_LIMIT"`; add document upload block for archived properties.
- **Setup-status:** Add `over_limit` and `over_limit_details` (properties: active, allowed).
- **Property active/archived:** Add `is_active` to Property; enforce limit on active count only; PATCH API to set is_active; block uploads to archived properties.
- **FAQ/copy:** Keep existing; add one line on read-only/archive if needed.
- **Tests:** Add/update tests for webhook plan update, over-limit 403 with PLAN_LIMIT, and data retention.
