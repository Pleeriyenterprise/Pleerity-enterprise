# RENT-OPERATIONS-KPI-LIST-ALIGNMENT-01

**Run:** `20260611T153353Z`  
**Account:** nancy@yopmail.com  
**Overall:** `VERIFIED_OPERATIONALLY`

## Findings

### Upcoming due
- KPI `253` matches API total `253`.
- UI previously showed only `200` rows (limit 200) → **KPI_LIST_DRIFT** fixed with "Showing N of M".

### Arrears / Attention
- Tenancies in arrears KPI: `22`
- Attention periods: `73`
- Distinct groups: `22` — aggregation verified.

### Collected this month
- Authority: `rent_payments.payment_date` in current month (£8,631.50 on Nancy staging).

### Avg late payment
- `NO_DATA` — no paid-late periods in sample.

## Changes
- Frontend KPI/list coupling (`rentKpiCoupling.js`, `rentKpiCopy.js`, page wiring)
- Attention header: period count across tenancy count
- Summary field: `attention_period_count`
- No pagination added (cap disclosure only)

## Regression
- Pass: `True`

## Browser
- Pass: `False` — skipped: `False`
