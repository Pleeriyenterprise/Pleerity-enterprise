# Billing receipts & invoices (admin & client)

This document describes where receipts/invoices are exposed, how they are stored, and how download/resend behave.

## Canonical storage (single source of truth)

| Flow | Metadata | PDF binary |
|------|-----------|------------|
| **CVP subscription checkout** (Stripe Checkout) | `stripe_checkout_invoices` (MongoDB), keyed by Stripe Checkout Session id (`_id`) | GridFS bucket `order_files` (`gridfs_id` on the ledger row) |
| **Paid service orders** (intake, one-off, CVP-linked) | `orders` (`invoice_number`, `receipt_pdf_gridfs_id`, `receipt_generated_at`, …) | Same GridFS bucket via `receipt_pdf_gridfs_id` |

No duplicate receipt store is created for the admin UI: lists and downloads read these collections and GridFS only.

### Email sent timestamps

- **Subscription:** On successful `SUBSCRIPTION_CONFIRMED` send after checkout, `receipt_email_sent_at` is set on the matching `stripe_checkout_invoices` row (when the session id is known).
- **Orders:** On successful `ORDER_CONFIRMATION` send, `order_confirmation_email_sent_at` is set on the `orders` document.

Historical rows may not have these fields until they were created after this behaviour was deployed.

## Where admins access receipts

1. Open **Admin → Billing & Subscriptions** (billing overview).
2. Search and **select a client**.
3. Scroll to **Receipts & Invoices**.

You get a merged history (newest first):

- Subscription checkout receipts for that `client_id`.
- Paid/post-payment **orders** linked by `orders.client_id` **or** by `customer.email` matching the client’s `email` / `contact_email` (case-insensitive).

Filters (query parameters on the API; mirrored in the UI):

- **Type:** all, subscription-only, orders-only, intake / one-off / CVP-linked orders.
- **Status:** e.g. `PAID` (matches `payment_status` on list rows).
- **Date range:** `date_from` / `date_to` against the row’s issue date.

### Admin API (authenticated, admin guard)

- `GET /api/admin/billing/clients/{client_id}/receipts`
- `GET /api/admin/billing/clients/{client_id}/receipts/subscription/{invoice_number_or_cs_id}/download`
- `GET /api/admin/billing/clients/{client_id}/receipts/order/{order_id}/download`
- `POST /api/admin/billing/clients/{client_id}/receipts/resend`  
  Body: `{ "source": "subscription" | "order", "ref": "<invoice or cs_… or order_id>" }`

**Download** streams the PDF and writes an audit entry (`ADMIN_ACTION` with `action_type`: `ADMIN_RECEIPT_DOWNLOADED`).

**Resend:**

- **Subscription:** Sends `SUBSCRIPTION_CONFIRMED` with the **existing** PDF from GridFS to the client’s primary email on the `clients` record. Fresh idempotency key per admin action. Audited with `ADMIN_RECEIPT_RESENT`.
- **Order:** Resends `ORDER_CONFIRMATION` (same content path as intake confirmation) with a fresh idempotency key. Audited with `ADMIN_RECEIPT_RESENT` (plus existing order email audits).

## Where clients access receipts

- **Portal:** **Settings → Billing** has an **Account & receipts** tab (summary, masked payment hint, official PDF table, Stripe invoice list) plus **Settings → Receipts** for the full receipt list (`/settings/billing/receipts`). APIs: `/api/client/billing/...` for PDF receipts; `/api/billing/payment-method-summary` for read-only card summary (Stripe-sourced); **Stripe Billing Portal** for updates.

Clients do not use the admin endpoints; scoping is enforced separately (`client_route_guard` vs `admin_route_guard`).

## Limitations

- Admin **subscription resend** uses the email on the **client** profile, not the original Stripe Checkout customer email, unless they match.
- **Orders** without `paid_at` / post-payment status may be omitted from the merged list even if a draft exists.
- **Linked by email** only considers addresses stored on the `clients` document (`email`, `contact_email`); aliases not on the client record will not attach guest orders to that client in this view.
