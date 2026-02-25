# Revenue Analytics Module — Audit vs Requirements

**Purpose:** Check the codebase against the Revenue Analytics task requirements; identify what is implemented, what is missing, and any conflicts. No implementation in this doc — proposal only.

---

## 1. Data sources (task vs codebase)

| Task requirement | Codebase reality | Gap / note |
|------------------|------------------|------------|
| **payments collection** (normalized Stripe payments) | **Does not exist.** Revenue is derived from `orders` (`stripe_payment_status` = paid, `pricing.total_pence`) and from `client_billing`/`clients` for subscription status. Reporting and analytics both use `orders`. | **New `payments` collection required** if task is followed literally. |
| **subscriptions collection** | No CVP `subscriptions` collection. Subscription state lives in **`client_billing`** (e.g. `stripe_customer_id`, `stripe_subscription_id`, `subscription_status`, `current_plan_code`) and is mirrored on **`clients`** (`subscription_status`, `plan_code`). | Use **`client_billing` + `clients`** as the subscription source (active/cancelled, plan, MRR). |
| **clients collection** | Exists and is used. | No gap. |

**Conclusion:**  
- **Option A (task wording):** Introduce a `payments` collection and normalize Stripe payment events into it; Revenue Analytics reads from `payments` + `client_billing`/`clients`.  
- **Option B (minimal change):** Keep using `orders` for one-time/order revenue and `client_billing`/`clients` for subscription metrics; add a **Revenue** dashboard that computes KPIs from these existing sources. No `payments` collection.  

The task and the “What You Should Track” section both say revenue should **not** rely only on Stripe webhooks and should use a **normalized payments store** as single source of truth. So the **safest and most professional** approach is **Option A**: add `payments` and wire webhooks to it, then build Revenue Analytics on `payments` + subscriptions (client_billing/clients).

---

## 2. STEP 1 — Payments normalization (Stripe webhook)

| Requirement | Current behaviour | Gap |
|-------------|-------------------|-----|
| On **successful payment**: create `payments` record with `client_id`, `stripe_event_id`, `amount`, `currency`, `type` (subscription \| setup \| audit \| pack), `status: "paid"`, `created_at` | **No `payments` collection.** `invoice.paid` and `checkout.session.completed` update `client_billing`/`clients` and (for orders) create/update `orders` with `stripe_payment_status`. No central payment record. | **Missing:** create/update `payments` from webhooks. |
| On **failed**: `status = "failed"` | `invoice.payment_failed` updates billing/subscription status only; no payment row. | **Missing:** insert/update `payments` with status failed. |
| On **refund**: `status = "refunded"` | **No refund webhook handler.** Handlers: `checkout.session.completed`, `customer.subscription.*`, `invoice.paid`, `invoice.payment_failed`. No `charge.refunded` / `invoice.refund`-type handler. | **Missing:** handle refund event and set `status = "refunded"` (or link to existing payment). |

**Conflicts / choices:**  
- **Type mapping:** Task uses `subscription | setup | audit | pack`. Today we have: (1) subscription checkouts → `client_billing`; (2) order intake (one-off) → `orders` with `service_code`. You’ll need a clear rule to map Stripe objects (invoice line items, payment_intent metadata) to `type` (e.g. subscription vs setup vs pack; “audit” may map to a specific service_code).  
- **Idempotency:** `stripe_events` already stores `event_id` for idempotency. When writing to `payments`, use `stripe_event_id` (and optionally Stripe payment/intent id) to avoid duplicate rows on retries.

---

## 3. STEP 2 — KPI calculations

| KPI | Task definition | Current implementation | Gap |
|-----|-----------------|------------------------|-----|
| total_revenue_lifetime | Sum of `payments` where status = paid | N/A (no payments). Summary uses **orders** (paid) total. | Need to define: from `payments` (once it exists) or keep from orders for “order revenue” only. |
| revenue_period | Sum paid payments in date filter | **Analytics summary** uses orders in range, `stripe_payment_status` = paid. | Same as above. |
| recurring_revenue | Sum subscription payments normalized to monthly | Not computed. Plan registry has `monthly_price` (19/39/79 GBP). | Can compute from **active subscriptions** × plan `monthly_price` (client_billing + plan_registry). |
| one_time_revenue | Sum payments where type ≠ subscription | Orders revenue is effectively one-time; not split from subscription in one metric. | From `payments.type` once payments exist; or from orders only for “order revenue”. |
| active_subscribers | Count subscriptions status = active | Not as a KPI. `clients` / `client_billing` have `subscription_status`. | **Easy:** count `client_billing` (or clients) where `subscription_status` in (ACTIVE, active). |
| churn_rate | cancelled / active previous period | Not implemented. | Need “previous period” active count and cancelled count (e.g. from client_billing status changes or cancellation events). |
| ARPU | recurring_revenue / active_subscribers | Not implemented. | After recurring_revenue and active_subscribers. |

Existing **analytics** (`/api/admin/analytics/summary`, `/revenue/daily`, etc.) use **orders** and **admin_route_guard**. They do **not** use a `payments` collection or subscription-based MRR/ARPU.

---

## 4. STEP 3 — Subscriber breakdown table

| Requirement | Current | Gap |
|-------------|---------|-----|
| Group by plan_name: active, cancelled, mrr_contribution | Not present. Plan names and monthly prices exist in **plan_registry** (e.g. Solo Landlord, Portfolio Landlord, Professional). `client_billing` has `current_plan_code`. | **Implement:** aggregate `client_billing` by `current_plan_code` (or plan_name from registry): count active (subscription_status active), cancelled (e.g. CANCELED), and MRR contribution (active × plan monthly_price). |

No conflict with existing code; net new.

---

## 5. STEP 4 — Revenue charts

| Requirement | Current | Gap |
|-------------|---------|-----|
| Time-series by day/month; filters 7d, 30d, 90d, 12m | **`/api/admin/analytics/revenue/daily`** returns daily revenue from **orders** (paid) for a `period` (e.g. 30d). **`/api/admin/analytics/v2/trends`** supports granularity and metrics including `revenue`. | **Avoid duplication:** Reuse or extend existing date range and aggregation (e.g. same `period` / `from_date`–`to_date`). New Revenue module can call same or new endpoint that aggregates **payments** (when available) or keep order-based series and add a separate “recurring” series from subscription data. |

**Conflict / choice:**  
- If Revenue is **payments-based**, add a dedicated time-series endpoint that aggregates `payments` by day/month (7d, 30d, 90d, 12m).  
- If Revenue stays **orders + subscriptions** without `payments`, extend existing revenue/daily or v2/trends to support “All / Recurring / One-time” breakdown (recurring from subscription snapshot or first payment per sub; one-time from orders).  

Safest: implement **payments** first, then add a **revenue time-series** that reads from `payments` (and optionally supplements with subscription MRR by date).

---

## 6. STEP 5 — Setup fee profit tracking

| Requirement | Current | Gap |
|-------------|---------|-----|
| If product has `cost_per_unit`: gross_profit = revenue - (cost_per_unit * quantity) | **No `cost_per_unit`** (or similar) in codebase. Products/plans are defined in plan_registry and service catalogue; no cost field. | **New:** Add optional `cost_per_unit` (e.g. on product/plan or service definition). Then in Revenue (or reporting), compute gross_profit per product/order. |

No conflict; additive.

---

## 7. STEP 6 — RBAC

| Requirement | Current | Gap |
|-------------|---------|-----|
| Only Owner/Admin can access Revenue dashboard | Analytics routes use **`admin_route_guard`** (require admin). Marketing Funnel uses **`require_owner_or_admin`**. | Align: use **`require_owner_or_admin`** for all Revenue Analytics endpoints so only Owner/Admin can access (matches task and Marketing Funnel). |

Recommendation: **Use `require_owner_or_admin`** for every Revenue-specific route.

---

## 8. UI: Admin → Analytics → Revenue

| Requirement | Current | Gap |
|-------------|---------|-----|
| Admin → Analytics → **Revenue** (separate section or page) | Single route **`/admin/analytics`** → `AdminAnalyticsDashboard.js`. No sub-route for “Revenue”. Sidebar: “Analytics” → `/admin/analytics`. | **Option A:** Add route `/admin/analytics/revenue` and a dedicated Revenue page (or tab). **Option B:** Add a “Revenue” section/card on the existing Analytics dashboard (like Marketing Funnel). Task says “Admin → Analytics → Revenue” which can be read as a sub-page or a section; both are valid. |

**Safest:** Add **Revenue** as a **section** on the existing Analytics page first (same pattern as Marketing Funnel), with its own KPIs, chart, subscriber table, payment health, and setup fee profit. If you later want a dedicated URL, add `/admin/analytics/revenue` and move the section into that page.

---

## 9. “What You Should Track” (detailed list) vs codebase

| Metric | In codebase? | Note |
|--------|----------------|------|
| Total Revenue (lifetime) | From orders (summary), not from payments | Add from `payments` or keep orders-only until payments exist. |
| Revenue (selected period) | Yes (summary + daily) from orders | Extend to payments when available. |
| MRR | Placeholder in Marketing Funnel only | Compute from active subscriptions × plan monthly_price. |
| ARR | No | MRR × 12. |
| One-time Revenue | Not split out | From payments.type or orders. |
| Subscription Revenue | Not as metric | Same as recurring_revenue. |
| Total / Active Subscribers | No | Count from client_billing/clients. |
| Past Due / Failed Payments | No | From payments (failed) or client_billing (past_due). |
| Churned Subscribers | No | Define “churn” (e.g. cancelled in period); count from billing/subscription events. |
| ARPU | No | recurring_revenue / active_subscribers. |
| Revenue breakdown: Recurring vs One-time | Partially (orders = one-time; no recurring series) | Add recurring from subscriptions. |
| Subscriber overview by plan (active, cancelled, MRR) | No | Step 3 above. |
| Revenue graph with 7d/30d/90d/12m and All/Recurring/One-time | Daily revenue exists (orders); no toggle | Add period and breakdown toggle. |
| Payment health (failed, past due, refunds, chargebacks) | No | From payments + client_billing. |
| Setup fee profit (revenue − cost) | No | Needs cost_per_unit and Step 5. |

---

## 10. Conflicting instructions and recommended approach

**Conflict 1 — Data source**  
- Task: “Revenue calculation should NOT rely only on Stripe webhooks” and “Store normalized payments in a payments collection … single source of truth.”  
- Codebase: No payments collection; everything is orders + client_billing.  

**Recommendation:** Implement the **payments** normalization (Step 1) first: create `payments` collection and on Stripe webhook (payment success / fail / refund) write or update `payments`. Then build Revenue KPIs, charts, and tables from `payments` + `client_billing`/`clients`. This avoids duplication and gives one source of truth.

**Conflict 2 — “subscriptions collection”**  
- Task mentions a “subscriptions collection.”  
- Codebase has **client_billing** (and clients) for CVP subscriptions, no `subscriptions` collection.  

**Recommendation:** Do **not** add a new CVP `subscriptions` collection unless you have a separate requirement. Use **client_billing** (+ plan_registry for plan_name and monthly_price) for active/cancelled counts and MRR by plan. Name the API/UI “subscriber” or “subscription” breakdown but read from client_billing.

**Conflict 3 — RBAC**  
- Task: “Only Owner/Admin can access Revenue dashboard.”  
- Analytics currently uses `admin_route_guard`.  

**Recommendation:** Use **`require_owner_or_admin`** for all Revenue endpoints (and, if you split the UI, for the Revenue page) so behaviour is explicit and consistent with Marketing Funnel.

---

## 11. Implementation order (recommended)

1. **Payments normalization (Step 1)**  
   - Create `payments` collection (schema: client_id, stripe_event_id, amount, currency, type, status, created_at, and any needed Stripe ids).  
   - In Stripe webhook: on success (e.g. invoice.paid, checkout.session.completed for one-off), insert `payments` with status paid; on invoice.payment_failed, insert/update failed; add handler for refund (e.g. charge.refunded) and set status refunded.  
   - Map event types to `type`: subscription | setup | audit | pack (and one-time from orders if needed).

2. **Revenue API under `/api/admin/analytics` (or `/api/admin/analytics/revenue`)**  
   - All endpoints protected with **require_owner_or_admin**.  
   - KPIs (Step 2): total_revenue_lifetime, revenue_period, recurring_revenue (from client_billing × plan_registry), one_time_revenue, active_subscribers, churn_rate, ARPU.  
   - Subscriber breakdown (Step 3): by plan_name (from plan_registry), active count, cancelled count, mrr_contribution.  
   - Time-series (Step 4): aggregate payments (and optionally subscription MRR) by day/month; support 7d, 30d, 90d, 12m.  
   - Payment health: failed (last 30d), past due (from client_billing), refunds, chargebacks if you store them.  
   - Setup fee profit (Step 5): when product has cost_per_unit, expose gross_profit (revenue - cost × quantity); add optional cost_per_unit to product/plan or service where appropriate.

3. **Frontend: Revenue section on Admin Analytics**  
   - Same page as current Analytics dashboard (or dedicated `/admin/analytics/revenue` if you prefer).  
   - Section 1: KPI cards (Total Revenue lifetime, Revenue period, MRR, Active Subscribers, Churn, Failed Payments).  
   - Section 2: Revenue graph (date axis, 7d/30d/90d/12m, toggle All/Recurring/One-time).  
   - Section 3: Subscriber overview table (Plan, Active, Cancelled, MRR Contribution).  
   - Section 4: Payment health (failed, past due, refunds, chargebacks).  
   - Section 5: Setup fee profit table when cost_per_unit exists.

4. **Optional: cost_per_unit**  
   - Add to plan_registry or service/product definition; use in Step 5 for gross profit.

---

## 12. Summary table

| Item | Status | Action |
|------|--------|--------|
| payments collection | Missing | Create; normalize from Stripe webhooks (paid/failed/refund). |
| subscriptions source | client_billing + clients | Use as-is for subscriber counts and MRR by plan. |
| Stripe refund handling | Missing | Add webhook handler; write refunded status to payments. |
| Revenue KPIs (lifetime, period, MRR, one-time, active, churn, ARPU) | Mostly missing | Implement in new Revenue API from payments + client_billing. |
| Subscriber breakdown by plan | Missing | Aggregate client_billing by plan; add plan_name from registry. |
| Revenue time-series 7d/30d/90d/12m | Partially (orders daily) | Add payments-based series; support period and Recurring/One-time. |
| Setup fee profit | Missing | Add cost_per_unit where needed; compute gross_profit in API. |
| RBAC Owner/Admin only | Analytics uses admin_route_guard | Use require_owner_or_admin for Revenue endpoints. |
| Admin → Analytics → Revenue UI | Missing | Add Revenue section (or page) with KPIs, chart, tables, payment health. |

This audit is the basis for a safe, non-duplicative implementation plan; implement in the order above and align with existing patterns (Marketing Funnel, analytics routes, plan_registry).
