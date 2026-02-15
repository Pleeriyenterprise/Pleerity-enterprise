# Billing / Plan / Gating – Existing Code Inventory

This document inventories existing plan, billing, and feature-gating code so we **extend** it (no parallel system). Source: repo scan for plan, billing_plan, subscription_status, entitlements, feature, gate, Stripe webhook, checkout, portal.

---

## 1. Where plan and subscription status are stored

### 1.1 Collections and fields

| Collection        | Fields used for plan/billing gating |
|-------------------|-------------------------------------|
| **clients**       | `billing_plan`, `subscription_status`, `entitlement_status`, `entitlements_version`, `stripe_customer_id`, `stripe_subscription_id` |
| **client_billing**| `client_id`, `stripe_customer_id`, `stripe_subscription_id`, `current_plan_code`, `subscription_status`, `entitlement_status`, `entitlements_version`, `current_period_end`, `cancel_at_period_end`, `onboarding_fee_paid`, `latest_invoice_id`, `over_property_limit`, `updated_at` |
| **stripe_events**  | `event_id` (idempotency), `type`, `status`, `processed_at`, `related_client_id`, `related_subscription_id` |

- **Models:** `Client` in `backend/models/core.py` has `billing_plan`, `subscription_status`, `stripe_customer_id`, `stripe_subscription_id`. It does **not** define `entitlement_status`, `entitlements_version`, or `stripe_price_id`; those are set in code on `clients` / `client_billing` by the webhook.
- **Not present:** No `plan_features` or `plan_limits` collections. Plan features and property caps are defined **in code** in `backend/services/plan_registry.py` (FEATURE_MATRIX, PLAN_DEFINITIONS, MINIMUM_PLAN_FOR_FEATURE).

---

## 2. Endpoints that enforce plan / role checks

### 2.1 Feature gating (require_feature or plan_registry.enforce_feature)

| Endpoint / location | Feature key(s) | How enforced |
|---------------------|----------------|--------------|
| **documents.py**    | `zip_upload`   | `require_feature("zip_upload")` decorator; also inline `plan_registry.enforce_feature` for upload path |
| **reports.py**      | `reports_pdf`, `reports_csv` | `plan_registry.enforce_feature(user["client_id"], "reports_pdf" | "reports_csv")` |
| **reports.py**      | `scheduled_reports` | `plan_registry.enforce_feature(..., "scheduled_reports")` |
| **client.py**       | `reports_pdf`, `tenant_portal` (multiple routes) | `plan_registry.enforce_feature(user["client_id"], "reports_pdf" | "tenant_portal")` |
| **webhooks_config.py** | `webhooks`   | `plan_registry.enforce_feature(user["client_id"], "webhooks")` on list/create/get/update/delete/test |
| **calendar.py**     | (feature check) | `plan_registry.enforce_feature` (calendar export / related) |

### 2.2 Property limit enforcement

| Endpoint / location | Limit check | Audit on deny |
|--------------------|-------------|---------------|
| **properties.py**   | `POST /api/properties/create` – count vs `plan_registry.get_property_limit(plan_code)` | `PLAN_LIMIT_EXCEEDED` |
| **properties.py**   | Bulk create – same limit check | `PLAN_LIMIT_EXCEEDED` |
| **intake.py**       | `POST /api/intake/submit` – `plan_registry.check_property_limit(plan_code, len(properties))` | Validation only (400) |

### 2.3 Subscription / entitlement checks (no plan feature key)

- **admin_billing.py** – provisioning trigger checks `entitlement_status == ENABLED`.
- **billing.py** – checkout/portal/status; no feature key, uses Stripe + client_billing.
- **stripe_webhook_service.py** – updates `subscription_status` / `entitlement_status` from Stripe only.

### 2.4 Auth and bypass

- **feature_gating.py:** `require_feature` loads client by `client_id`, checks `subscription_allows_feature_access(subscription_status)` (ACTIVE/TRIALING), then `plan_registry.get_features(plan_code)[feature_key]`. **Only `ROLE_OWNER` bypasses** plan gating; ADMIN does not.

---

## 3. Stripe webhook handlers and what they update

**File:** `backend/services/stripe_webhook_service.py`  
**Routes:** `POST /api/webhook/stripe`, `POST /api/webhooks/stripe` (alias)

| Event type                      | Handler | Updates (summary) |
|---------------------------------|--------|--------------------|
| **checkout.session.completed**  | `_handle_subscription_checkout` (when mode=subscription) | `client_billing` upsert: current_plan_code, subscription_status, entitlement_status, entitlements_version ($inc), stripe_*; `clients`: same + billing_plan. Audit: PLAN_UPDATED_FROM_STRIPE, STRIPE_EVENT_PROCESSED. Provisioning job created when entitlement ENABLED. |
| **customer.subscription.created** | `_handle_subscription_change` | `client_billing`: current_plan_code, subscription_status, entitlement_status, entitlements_version ($inc); `clients`: billing_plan, subscription_status, entitlement_status, entitlements_version. Audit: PLAN_UPDATED_FROM_STRIPE, STRIPE_EVENT_PROCESSED. Downgrade: sets over_property_limit if over new cap. |
| **customer.subscription.updated** | `_handle_subscription_change` | Same as created. |
| **customer.subscription.deleted** | `_handle_subscription_deleted` | client_billing + clients: subscription_status CANCELLED, entitlement_status DISABLED. |
| **invoice.paid**                | `_handle_invoice_paid` | client_billing + clients: subscription_status, entitlement_status from subscription. |
| **invoice.payment_failed**      | `_handle_payment_failed` | client_billing + clients: subscription_status, entitlement_status (e.g. LIMITED). |

- Plan is derived **only** from Stripe subscription line items’ `price_id` via `plan_registry.get_plan_from_subscription_price_id(price_id)`.
- Idempotency: `stripe_events` stores `event_id`; processed events are skipped.
- **Not persisted today:** `stripe_price_id` is not stored on `clients` or `client_billing` (only plan_code is).

---

## 4. Plan/feature source of truth (current)

- **Single source:** `backend/services/plan_registry.py`
  - **Plan codes:** `PlanCode` enum (PLAN_1_SOLO, PLAN_2_PORTFOLIO, PLAN_3_PRO).
  - **Property limits:** `PLAN_DEFINITIONS[code]["max_properties"]` → 2, 10, 25.
  - **Feature matrix:** `FEATURE_MATRIX[plan_code][feature_key]` (bool).
  - **Minimum plan per feature:** `MINIMUM_PLAN_FOR_FEATURE[feature_key]`.
- **Middleware:** `backend/middleware/feature_gating.py` – `require_feature(feature_key)` uses plan_registry + client from DB.
- **Service:** `plan_registry.enforce_feature(client_id, feature_key)` – subscription status + plan feature check; returns (allowed, message, details) for 403 responses.

---

## 5. Audit log action types (existing)

| Action type              | Where used |
|---------------------------|------------|
| **PLAN_UPDATED_FROM_STRIPE** | stripe_webhook_service (checkout completed, subscription created/updated) |
| **STRIPE_EVENT_PROCESSED**   | Same handlers (additional audit line) |
| **STRIPE_EVENT_FAILED**      | Webhook processing exception path |
| **PLAN_GATE_DENIED**        | feature_gating.require_feature when feature not in plan |
| **PLAN_LIMIT_EXCEEDED**     | properties.py (create + bulk create) |

**Not present:** `PLAN_CHANGE_REQUESTED` (e.g. when user clicks Upgrade and starts checkout/portal).

---

## 6. Feature keys in use (plan_registry)

- Core: compliance_dashboard, compliance_score, compliance_calendar, email_notifications, multi_file_upload, score_trending  
- AI: ai_extraction_basic, ai_extraction_advanced, extraction_review_ui  
- Documents: zip_upload  
- Reporting: reports_pdf, reports_csv, scheduled_reports  
- Communication: sms_reminders  
- Portal: tenant_portal  
- Integration: webhooks, api_access  
- Advanced: white_label_reports, audit_log_export  

---

## 7. Other relevant files

- **plan_gating.py** / **feature_entitlement.py** – legacy/alternate feature logic; **plan_registry** is the one used by routes and middleware above.
- **intake.py** – plan limits at submit; checkout creation (`POST /api/intake/checkout?client_id=...`).
- **billing.py** – `POST /api/billing/checkout` (upgrade), `GET /api/billing/status`, portal, cancel.
- **stripe_service.py** – create_checkout_session, create_upgrade_session (portal or checkout), get_subscription_status, cancel_subscription.

---

## 8. Conflicts and clarifying questions (vs your spec)

Before implementing, these need your decision:

### 8.1 Matrix differences (spec vs current code)

Your **authoritative** matrix (Website Pricing Page) differs from current `plan_registry` in these places:

| Feature / area        | Spec (SOLO / PORTFOLIO / PRO) | Current code |
|-----------------------|--------------------------------|--------------|
| **AI_EXTRACTION_ADVANCED** / **AI_REVIEW_INTERFACE** | ❌ ❌ ✅ (Pro only) | Portfolio + Pro (✅ ❌ ✅ → ✅ ✅ ✅) |
| **CSV_EXPORT** (reports_csv) | ❌ ❌ ✅ (Pro only) | Portfolio + Pro |
| **SMS_REMINDERS**     | ❌ ❌ ✅ (Pro only) | Portfolio + Pro |
| **TENANT_PORTAL_ACCESS** (tenant_portal) | ❌ ❌ ✅ (Pro only) | Portfolio + Pro |
| **WHITE_LABEL_REPORTS** | ❌ ❌ ❌ (disabled for all) | Pro only (✅) |

**Question:** Should we **change** the in-code matrix (and any DB seed we add) to match the spec exactly (Pro-only for AI advanced, CSV, SMS, tenant portal; white_label off for all)? That would **downgrade** Portfolio in code (fewer features than today).

### 8.2 plan_features / plan_limits in MongoDB

Spec: *"Create collection: plan_features (plan_code, feature_key, is_enabled); Create collection: plan_limits (plan_code, properties_max)."*  
Current: No such collections; everything is in-code in `plan_registry.py`.

**Question:** Prefer (a) **DB as source**: add `plan_features` and `plan_limits`, seed from the authoritative matrix, and have `plan_registry` (or a thin layer) **read from DB** with in-code fallback for defaults, or (b) **keep code as source**: no new collections, only align `FEATURE_MATRIX` / `PLAN_DEFINITIONS` and property limits with the spec? Option (a) extends the system with a DB layer; (b) keeps a single in-code source and avoids a second source of truth.

### 8.3 Feature key naming (UPPER_SNAKE vs snake_case)

Spec uses UPPER_SNAKE (e.g. COMPLIANCE_DASHBOARD, DOCUMENT_UPLOAD_BULK_ZIP). Code uses snake_case (compliance_dashboard, zip_upload).

**Proposal:** Keep existing snake_case keys in APIs and DB; add a mapping layer only if the frontend or docs need UPPER_SNAKE (e.g. in responses or seed data). No duplicate keys.

### 8.4 stripe_price_id on Client

Spec: *"Persist on Client (or Organization): ... stripe_price_id"*.  
Current: We persist plan_code and subscription ids but **not** the active subscription’s price_id.

**Proposal:** Extend webhook and (if present) client_billing to store **current subscription price_id** when we process subscription/checkout events (optional but useful for support and debugging). Confirm if you want this on `clients` and/or `client_billing`.

### 8.5 PLAN_CHANGE_REQUESTED

Spec: *"Log: PLAN_CHANGE_REQUESTED; PLAN_UPDATED_FROM_STRIPE"*.  
Current: No `PLAN_CHANGE_REQUESTED` when user starts checkout/portal.

**Proposal:** Add one audit log with `action_type: "PLAN_CHANGE_REQUESTED"` when the user successfully initiates upgrade (e.g. in `POST /api/billing/checkout` and when redirecting to Stripe from intake checkout), including target_plan and client_id.

### 8.6 Test accounts and seed data

Spec: seed 3 test accounts (SOLO / PORTFOLIO / PROFESSIONAL), no plaintext passwords; use password reset flow or one-time links; seed properties up to caps.  
Current: Runbook and verification script exist for **creating** 3 accounts via real intake → Stripe → webhook; no DB seed that inserts users or sets plan without Stripe.

**Proposal:** Do **not** add a seed that writes plan/subscription to DB without going through Stripe. Keep test accounts as “create via real flow + optional verification script.” If you want a separate “seed” that only creates placeholder records (e.g. email only) and relies on reset links for first login, we can add that as a separate, minimal seed (no billing_plan/subscription_status set until Stripe flow).

---

## 9. Proposed implementation plan (extend only)

Once the above are decided:

1. **Stripe remains source of truth**  
   - No change to who updates plan/status (webhook only). Optionally add `stripe_price_id` to client/client_billing in webhook.

2. **Audit**  
   - Add `PLAN_CHANGE_REQUESTED` when user starts upgrade (billing checkout + intake checkout redirect).

3. **Feature matrix and limits**  
   - Either (a) add `plan_features` and `plan_limits` collections, seed from spec, and have plan_registry read from DB with code fallback, or (b) update only in-code FEATURE_MATRIX and limits to match spec. Apply your matrix decisions from §8.1.

4. **Middleware / enforcement**  
   - Keep `require_feature` and `plan_registry.enforce_feature`; ensure every gated endpoint uses one of them before doing work. Add any missing feature checks for endpoints that should be gated per spec (list to be derived from spec matrix).

5. **Property caps**  
   - Already enforced (2/10/25); keep as-is; ensure audit remains PLAN_LIMIT_EXCEEDED.

6. **Upgrade flow**  
   - Already: upgrade button → Stripe checkout/portal only; no local plan change until webhook. Document and optionally add PLAN_CHANGE_REQUESTED.

7. **Test accounts**  
   - No new “override” seed; continue using real flow + verification script. Optionally add minimal placeholder seed (emails only + reset links) if requested.

8. **Deliverables**  
   - plan_features + plan_limits seeded (if DB option chosen) **or** updated in-code matrix only.  
   - List of endpoints protected and their feature keys (from this inventory + any new gates).  
   - Screenshots/steps for gating and upgrade in runbook or separate doc.  
   - Commit: `feat(gating): stripe-driven feature + limit gating`.

---

**Next step:** Please confirm (1) matrix choices (§8.1), (2) DB vs code for plan_features/plan_limits (§8.2), (3) stripe_price_id (§8.4), and (4) test-account seed approach (§8.6). Then implementation will extend the existing system accordingly with no parallel gating system.
