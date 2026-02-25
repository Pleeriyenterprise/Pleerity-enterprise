# Marketing Funnel Conversion Linking (Demo → Paid)

This document describes how risk-check demo leads are linked to clients and marked converted only after Stripe payment, without changing intake, billing, Stripe webhook provisioning, or provisioning triggers.

## Truth sources

| Concept | Source of truth |
|--------|------------------|
| Lead created | `risk_leads` document created by POST `/api/risk-check/report` (status `new` or `nurture_started` after email 1). |
| CTA clicked | POST `/api/risk-check/activate` sets status to `activated_cta` (idempotent). |
| Client linked | Intake submit stores `client.marketing = { source, lead_id }` and updates `risk_leads.status = "checkout_created"`, `risk_leads.client_id`. |
| Checkout started | Stripe session metadata includes `lead_id`; after session creation we write `risk_leads.stripe_session_id`. |
| **Conversion** | **Only** Stripe webhook `checkout.session.completed` sets `risk_leads.status = "converted"`, `converted_at`, `client_id`, `stripe_subscription_id`. |
| Provisioning | Unchanged: only existing webhook and provisioning runner; no new triggers. |

## Alignment with existing implementation

- **Collection:** We use the **existing** `risk_leads` collection (no second collection). Schema is extended with: `client_id`, `stripe_session_id`, `stripe_subscription_id`, `converted_at`; status enum extended with `activated_cta`, `checkout_created` (existing: `new`, `nurture_started`, `converted`).
- **Endpoints:** Existing POST `/api/risk-check/preview` and POST `/api/risk-check/report` are unchanged. We add POST `/api/risk-check/activate` to record CTA click.
- **Field names:** We keep existing names (`computed_score`, `risk_band`, `exposure_range_label`, `gas_status`, `eicr_status`, etc.). Task names like `calculated_score` / `exposure_band` map to these; we do not rename and break report or nurture.

## Flow (end-to-end)

1. **User completes risk-check** → POST `/api/risk-check/report` → lead in `risk_leads` with `status: "new"` (or `nurture_started` if email 1 sent).
2. **User clicks “Activate Monitoring”** → Frontend navigates to `/intake/start?plan=...&lead_id=<lead_id>&from=risk-check`. Optionally call POST `/api/risk-check/activate` with `{ lead_id, selected_plan_code }` to set `status: "activated_cta"`.
3. **User submits intake** → POST `/api/intake/submit` with optional `lead_id`, `source`. Backend creates client; if `lead_id` present: sets `client.marketing = { source: "risk-check", lead_id }`; updates `risk_leads` to `status: "checkout_created"`, `client_id` (best-effort; intake does not fail if risk_leads update fails).
4. **User proceeds to checkout** → POST `/api/intake/checkout?client_id=...`. Backend loads client; if `client.marketing.lead_id` present, passes `lead_id` to Stripe session metadata and, after session creation, writes `stripe_session_id` to `risk_leads` (best-effort).
5. **Stripe payment succeeds** → Webhook `checkout.session.completed` runs existing logic (billing, provisioning). **Then** if `metadata.lead_id` present: update `risk_leads` to `status: "converted"`, `converted_at`, `client_id`, `stripe_subscription_id` (idempotent). Optionally import `initial_risk_snapshot` on client if not already set.
6. **Admin** → GET `/api/admin/analytics/marketing` returns risk-check funnel counts (leads_created, activated_cta, checkout_created, converted, conversion rates). Existing admin risk-leads list and marketing-funnel remain.

## Non-regression rules

- No change to when or how provisioning is triggered (Stripe webhook only).
- No portal user or client creation from demo or from `/api/risk-check/activate`.
- Failures in `risk_leads` updates never block intake submit, checkout, or webhook.

## Idempotency

- **Activate:** Only transition from `new` or `activated_cta` to `activated_cta`.
- **Intake link:** Overwrite `risk_leads.client_id` and `status: "checkout_created"` if lead exists.
- **Webhook conversion:** If `risk_leads.status` already `converted`, do nothing.
