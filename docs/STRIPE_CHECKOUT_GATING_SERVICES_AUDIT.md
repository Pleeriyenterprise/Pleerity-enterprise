# Stripe Checkout Gating for Services — Audit & Implementation Summary

**Scope:** Services only (AI automation, Market research, Compliance services, Document packs). CVP subscription flow is separate and unchanged.

---

## Task Requirements vs Codebase

| Requirement | Status | Implementation |
|-------------|--------|----------------|
| **1. Checkout page calls POST /api/checkout/create-session with draft_ref** | Done | Backend: `routes/checkout_validation.py` — `POST /api/checkout/create-session` (body: `draft_ref`, optional `success_url`, `cancel_url`). Frontend: `checkoutApi.createCheckoutSession(draft_ref)`; `UnifiedIntakeWizard` uses it when proceeding to payment. |
| **2. Backend validates draft exists, service active, price + add-ons** | Done | `create_checkout_session` in checkout_validation: `get_draft_by_ref(draft_ref)` → 404 if missing; check draft not CONVERTED; `service_catalogue_v2` with `active: True`; `validate_draft(draft_id)` for ready_for_payment. Session creation uses draft `pricing_snapshot` (price + add-ons). |
| **3. Stripe Session metadata: draft_ref, service_code, environment** | Done | `intake_draft_service.create_checkout_session`: metadata includes `draft_id`, `draft_ref`, `service_code`, `type: "order_intake"`, `environment` (from env). |
| **4. Webhook POST /api/webhooks/stripe** | Done | `routes/webhooks.py` — `POST /api/webhooks/stripe` (and `/api/webhook/stripe`) → `stripe_webhook_service.process_webhook`. |
| **5. checkout.session.completed: validate metadata, create Order from draft** | Done | `_handle_order_payment`: requires `metadata.draft_id`; logs warning if `draft_ref` or `service_code` missing. Calls `convert_draft_to_order(...)`. |
| **6. order_ref format PLE-YYYYMMDD-XXXX** | Done | `intake_draft_service.generate_order_ref()` returns `PLE-{YYYYMMDD}-{####}`. |
| **7. Status PAID → QUEUED** | Done | `convert_draft_to_order` sets order `status`/`workflow_state` to PAID; then `workflow_automation_service.wf1_payment_to_queue(order_id)` transitions to QUEUED. |
| **8. Store stripe session id and payment intent** | Done | Order `pricing.stripe_checkout_session_id`, `pricing.stripe_payment_intent_id`. |
| **9. Enqueue workflow job generation** | Done | `wf1_payment_to_queue` enqueues workflow (QUEUED → generation). |
| **10. Order not created if payment fails or webhook not received** | Done | Order is created only inside webhook handler after `checkout.session.completed`. No order created on failed payment or missing webhook. |
| **11. Idempotency: stripe event id + session id** | Done | Global: `stripe_events` table keyed by `event_id` (one process per event). Order-level: unique index `orders.pricing.stripe_checkout_session_id`; unique `orders.source_draft_id`. Order document now stores `pricing.stripe_event_id` for audit. Duplicate webhook: existing order found by `source_draft_id` and same result returned. |

---

## Changes Made (Minimal, No CVP Impact)

1. **Frontend**
   - **checkoutApi.js:** Added `createCheckoutSession(draftRef, options)` calling `POST /api/checkout/create-session` with `{ draft_ref }`. Exported in default object.
   - **UnifiedIntakeWizard.js:** Proceed-to-payment now uses `createCheckoutSession(draft.draft_ref)` instead of `POST /intake/draft/{draft_id}/checkout`. Redirect uses `res.checkout_url`.

2. **Backend**
   - **intake_draft_service.convert_draft_to_order:** Added optional `stripe_event_id`; stored in `order["pricing"]["stripe_event_id"]` for idempotency/audit.
   - **stripe_webhook_service._handle_order_payment:** Validates metadata (logs warning if `draft_ref` or `service_code` missing). Passes `event_id` into `convert_draft_to_order` as `stripe_event_id`.

---

## Flow Summary

1. User completes intake in `UnifiedIntakeWizard` and clicks pay.
2. Frontend calls `POST /api/checkout/create-session` with `{ draft_ref: draft.draft_ref }`.
3. Backend validates draft (exists, not converted, service active, ready_for_payment), then creates Stripe Checkout Session with metadata (`draft_id`, `draft_ref`, `service_code`, `type`, `environment`), returns `checkout_url`.
4. User is redirected to Stripe; on success Stripe sends `checkout.session.completed` to `POST /api/webhooks/stripe`.
5. Webhook handler routes to `_handle_order_payment` (mode payment, type order_intake). Idempotency: if order already exists for `source_draft_id`, returns it. Otherwise `convert_draft_to_order` creates order (PAID), stores session id, payment intent id, event id; marks draft CONVERTED; calls `wf1_payment_to_queue` (PAID → QUEUED, enqueue generation).

---

## Key Files

- **Checkout gating:** `backend/routes/checkout_validation.py` (create-session), `backend/services/intake_draft_service.py` (create_checkout_session, convert_draft_to_order, generate_order_ref).
- **Webhook:** `backend/routes/webhooks.py`, `backend/services/stripe_webhook_service.py` (_handle_checkout_completed → _handle_order_payment).
- **Frontend:** `frontend/src/api/checkoutApi.js` (createCheckoutSession), `frontend/src/pages/UnifiedIntakeWizard.js` (proceedToPayment).
- **Idempotency:** `stripe_events.event_id` (global); `orders.pricing.stripe_checkout_session_id` (unique); `orders.source_draft_id` (unique).

---

*CVP subscription checkout and webhook handling are unchanged.*
