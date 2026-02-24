# Analytics Dashboard (Conversion Funnel)

Operational analytics for the admin dashboard: conversion tracking from **Lead → Paid → Provisioned → Activated → First Value**. This document describes metric definitions, data source, and the **First Value** definition.

## Data source

- **Collection:** `analytics_events` (MongoDB)
- **Schema:** `ts`, `event`, `lead_id`, `client_id`, `customer_reference`, `email`, `source`, `plan_code`, `properties_count`, `stripe_session_id`, `stripe_subscription_id`, `metadata`, optional `idempotency_key`
- Analytics is **passive**: events are logged from existing flows; no business logic is changed. Provisioning remains triggered only by Stripe webhooks and the existing provisioning runner.

## Events logged

| Event | When | Idempotency |
|-------|------|--------------|
| `lead_captured` | After lead creation (chatbot, contact form, compliance checklist, document service, WhatsApp) | — |
| `intake_submitted` | After client + properties created in intake submit | — |
| `checkout_started` | When Stripe checkout session is created (intake checkout) | — |
| `payment_succeeded` | After Stripe checkout.session.completed or invoice.paid handled | By Stripe `event.id` |
| `provisioning_started` | When provisioning runner sets status to PROVISIONING_STARTED | — |
| `provisioning_completed` | When job reaches PROVISIONING_COMPLETED | — |
| `provisioning_failed` | When job status set to FAILED | — |
| `activation_email_sent` | When WELCOME_EMAIL send succeeds (password setup link) | — |
| `email_failed` | When activation email send fails or is blocked | — |
| `password_set` | After successful set-password (token-based) | — |
| `doc_uploaded` | On each successful document upload (client or admin) | — |
| `first_doc_uploaded` | Once per `client_id` (first document upload) | Once per client |
| `checkout_failed` | When checkout session creation fails | — |

## First Value (MVP definition)

**First Value** is achieved when a client has at least one **document uploaded** to a property after activation.

- **Implementation:** A client is counted as “First Value” if there is at least one `analytics_events` document with `event = "first_doc_uploaded"` and that `client_id`.
- **Funnel:** The “First Value” KPI and funnel stage use the count of **distinct `client_id`** with `first_doc_uploaded` in the selected date range.
- No legal or compliance meaning: this is an operational/product metric only.

## Conversion definitions

- **Lead → Intake:** unique `client_id` with `intake_submitted` / unique `lead_id` with `lead_captured`
- **Intake → Checkout:** unique `client_id` with `checkout_started` / unique `client_id` with `intake_submitted`
- **Checkout → Paid:** unique `client_id` with `payment_succeeded` / unique `client_id` with `checkout_started`
- **Paid → Provisioned:** unique `client_id` with `provisioning_completed` / unique `client_id` with `payment_succeeded`
- **Provisioned → Activated:** unique `client_id` with `password_set` / unique `client_id` with `provisioning_completed`
- **Activated → First Value:** unique `client_id` with `first_doc_uploaded` / unique `client_id` with `password_set`

All stage counts use **unique** identifiers (lead_id or client_id) in the selected period to avoid double-counting.

## Admin API

- **GET /api/admin/analytics/overview** — KPIs, conversion rates, median times (paid→provisioned, provisioned→password_set, password_set→first_value), leads by source, failures by error_code. Query: `from`, `to`, `period`, `source`, `plan`. RBAC: owner/admin.
- **GET /api/admin/analytics/funnel** — Stage counts, step conversion %, drop-off. Same filters. RBAC: owner/admin.
- **GET /api/admin/analytics/failures** — Recent failure events with request_id, stripe ids, metadata. Query: `from`, `to`, `period`, `type` (checkout | email | provisioning). RBAC: owner/admin.

## UI

- **Route:** `/admin/analytics`
- **Section:** “Conversion Funnel (Lead to First Value)” with filters (date range, source, plan), KPI cards, funnel table, median time-to-complete, leads by source table, failures panel (with “Copy request_id”).
- For avoidance of doubt: the dashboard is for **operational analytics only**; it does not provide legal or compliance advice.
