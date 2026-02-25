# Executive Overview Runbook

This runbook documents how the **Executive Overview** dashboard (Admin → Analytics → Executive Overview) computes key metrics and how to interpret them. Use it for investor reporting, internal health checks, and support.

---

## 1. NRR (Net Revenue Retention)

**Definition:** NRR is the percentage of prior-month MRR retained from existing customers (expansion and churn netted). Formula used:

- **NRR = (Current month MRR / Previous month MRR) × 100**
- Current and previous month MRR are stored in the `mrr_snapshots` collection (one document per `period` = `"YYYY-MM"`).
- Each time the Executive Overview (or any job that records MRR) runs, it upserts the current period’s `mrr_pence` and `recorded_at`.
- If there is no previous month’s snapshot, the UI shows a note: *"Record MRR snapshots (next month) for NRR."*

**Interpretation:** NRR &gt; 100% means expansion outweighs churn; &lt; 100% means net contraction. Early-stage SaaS often targets NRR in the 90–110% range.

---

## 2. LTV (Lifetime Value)

**Formula used:**

- **LTV = ARPU / Churn rate (decimal)**
- **ARPU** = MRR / Active subscribers (pence).
- **Churn rate** = Canceled (and similar) subscribers / (Active + Canceled) in the current billing snapshot (percent). Converted to decimal for LTV (e.g. 5% → 0.05).

**Caveats:**

- This is a simple steady-state LTV. It does not use cohort retention curves or discounting.
- If churn rate is 0 or there are no canceled subscribers, LTV is not computed (shown as null).
- ARPU and churn are derived from current `client_billing` and `plan_registry`, not from historical payment events.

---

## 3. Top 5% Revenue Risk (Revenue concentration)

**What it is:** `risk_indicators.revenue_top5_pct` is the percentage of **YTD revenue** that comes from the **top 5 customers** (by total paid amount in the `payments` collection).

**Interpretation:**

- High values (e.g. &gt; 40–50%) indicate concentration risk: a few customers leaving would materially impact revenue.
- Used for investor and board reporting; also useful for account health and diversification discussions.

**Computation:** Sum of paid `amount` YTD per `client_id`, take top 5, sum their revenue, divide by total YTD revenue × 100.

---

## 4. Other Executive Overview sections

- **Row 1 (Core financials):** MRR, ARR, Revenue YTD, Gross profit YTD (revenue YTD − cost YTD from `cost_pence` on payments), with YoY and month-over-month trend.
- **Row 2 (SaaS health):** Active subscribers, new subscribers (30d), churn rate, NRR, ARPU, LTV.
- **Subscription performance:** Table by plan (active, trial, churned, MRR contribution).
- **Revenue composition:** Donut (Subscription vs Document Packs vs Setup & other) for YTD.
- **Monthly trend (12 months):** Recurring and one-time revenue by month.
- **Financial stability:** Cash in last 30d, failed payments, refunds, past-due accounts.
- **Valuation snapshot:** ARR × 5–8× multiple → implied valuation range (confidential).
- **Growth efficiency:** Leads (30d), trials (30d), paid count, conversion %; placeholders for cost per lead, CPA, payback.

---

## 5. Data sources

| Metric / section      | Source(s)                                      |
|-----------------------|-------------------------------------------------|
| MRR / ARR             | `client_billing` + `plan_registry`              |
| Revenue YTD / trends  | `payments` (status = paid, created_at)         |
| Gross profit YTD      | `payments` (amount, optional `cost_pence`)      |
| NRR                   | `mrr_snapshots` (current and previous period)  |
| LTV / ARPU / churn    | `client_billing`, `plan_registry`               |
| Top 5 revenue %       | `payments` YTD aggregated by `client_id`       |
| New subscribers 30d   | First subscription payment in last 30d (payments)|

---

## 6. Payments backfill (historical data)

Revenue and Executive Overview read from the **`payments`** collection (normalized from Stripe). If this collection was introduced after you already had live Stripe usage, historical paid invoices will not be in `payments` until you backfill.

**When to run:** After enabling Revenue Analytics for the first time, or after a migration that did not backfill `payments`. Run once (or periodically if you add backfill for new invoice types) to populate history.

**Script:** `backend/scripts/backfill_payments_from_stripe.py`

**Requirements:**
- `STRIPE_SECRET_KEY` or `STRIPE_API_KEY` in env
- `MONGO_URL`, `DB_NAME` in env
- Run from the **backend** directory:  
  `python scripts/backfill_payments_from_stripe.py [limit]`  
  Default limit is 500 invoices; pass a number to cap (e.g. `2000`).

**What it does:** Lists Stripe paid subscription invoices, resolves `client_id` from `client_billing.stripe_customer_id`, and inserts one payment document per invoice. Uses `stripe_event_id = "backfill-inv-{invoice_id}"` so re-runs are **idempotent** (already-inserted invoices are skipped).

**After running:**
1. Check script output: `inserted`, `skipped_no_client`, `skipped_duplicate`, and any `errors`.
2. In Admin → Analytics → Revenue, confirm Revenue in period and time series reflect expected history.
3. In Executive Overview, confirm Revenue YTD and 12‑month trend look reasonable. If you see zeros for past months, ensure `payments` has documents with `created_at` in those months and `status: "paid"`.

**Note:** The script only backfills **subscription** invoices. One-time and document-pack payments are recorded by the webhook when they occur; no separate backfill is provided for those unless you extend the script.

---

## 7. Access and RBAC

- **Route:** `GET /api/admin/analytics/executive-overview`
- **RBAC:** Owner or Admin only (`require_owner_or_admin`). Unauthorized requests return 401.
