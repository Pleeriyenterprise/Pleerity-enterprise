# Contractor Intelligence Layer

This document describes the contractor performance scoring system used to turn the contractor network into a performance-aware system and help users choose reliable contractors.

## Overview

The system computes **contractor performance metrics** from operational data (work orders, contractor_performance aggregates, invoices), combines them into an **overall performance score (0–100)** stored on the contractor profile, and uses the score in **recommendations** and **admin analytics**. Clients see basic ratings in the contractor selection UI.

---

## Part 1 — Contractor Performance Metrics

Metrics are calculated by `services/contractor_intelligence_service.py` from:

| Metric | Definition | Source |
|--------|------------|--------|
| **reliability_score** | `completed_jobs / assigned_jobs` (0–1) | work_orders (assigned), contractor_performance (jobs_completed) |
| **average_response_time** | Time between assignment and contractor acceptance (hours) | work_orders: `assigned_at` → `accepted_at` |
| **average_completion_time** | Time between acceptance and job completion (hours) | work_orders: `accepted_at`/`assigned_at` → `completed_at` |
| **sla_success_rate** | Jobs completed before SLA deadline (0–1) | contractor_performance: `jobs_on_time` / `jobs_completed` |
| **invoice_approval_rate** | Approved (or paid) invoices / submitted invoices (0–1) | invoices: status in `approved`, `paid` |

Contractors with no assignments have no metrics (and no score) until they receive at least one assignment and data is aggregated.

---

## Part 2 — Contractor Performance Score

The **overall score** is a 0–100 value stored on the contractor document (`performance_score`, `performance_score_updated_at`).

**Weights:**

- reliability_score — **40%**
- sla_success_rate — **25%**
- response time (normalised) — **20%**: 0–24h = 1.0, 24–72h = linear decay, 72h+ = 0
- invoice_approval_rate — **15%**

Partial data is supported: the score is normalised by the sum of weights for which data exists. If no data exists for any component, the contractor has no `performance_score` (treated as 0 in ranking).

**Stored fields on contractor:**

- `performance_score`, `performance_score_updated_at`
- `reliability_score`, `sla_success_rate`, `invoice_approval_rate`
- `average_response_time_hours`, `average_completion_time_hours`
- `assigned_jobs`, `completed_jobs` (for display)

---

## Part 3 — Contractor Recommendation Engine

When recommending contractors for a work order, results are ranked using:

- **Trade match** (trade types vs work order)
- **Distance / service area**
- **Contractor performance score**

High-performing contractors appear first. The recommendation API returns `performance_score`, `reliability_score`, `completed_jobs`, `assigned_jobs` for each recommended contractor.

---

## Part 4 — Admin Contractor Analytics

**Endpoint:** `GET /api/admin/ops/contractors/analytics`

**Query parameters:** `view`, `client_id`, `limit`

**Views:**

- **top_performers** — Contractors sorted by `performance_score` descending
- **sla_issues** — Contractors with `sla_success_rate` &lt; 80%
- **high_rejection** — Contractors with `invoice_approval_rate` &lt; 80%

Admin UI: **Ops → Contractors → Analytics** tab, with view selector, client filter, and limit. Table shows name, trades, client, score, reliability %, SLA %, invoice %, and jobs (assigned/completed).

---

## Part 5 — Client Visibility

In the contractor selection interface (e.g. recommended contractors when assigning a work order):

- **Contractor score** (performance_score)
- **Reliability %** (reliability_score × 100)
- **Jobs completed** (completed_jobs)

Same fields are shown in the admin work order detail recommendation list.

---

## Part 6 — Observability and Recalculation

**Logging:** Each contractor score update logs at INFO, e.g.  
`contractor_intelligence contractor_id=… performance_score=… reliability=…`  
Bulk recalc logs a summary and any per-contractor errors.

**Recalculation triggers:**

1. **On work order completion** — When a work order is marked completed, the assigned contractor’s performance score is updated (best-effort; completion still succeeds if the update fails).
2. **Periodic job** — The **contractor_performance_recalc** job runs **daily at 03:00 UTC**. It recalculates metrics and score for all contractors and is visible in the automation/observability job list. It is non-critical for system health (scores can be slightly stale).

**Audit:** Each score update can create an audit log entry (`CONTRACTOR_PERFORMANCE_SCORE_UPDATED`) with contractor_id, performance_score, reliability_score, completed_jobs.

**Manual run:** Admins can trigger **contractor_performance_recalc** from the Jobs / Automation centre “Run now” action.

---

## Implementation References

- **Metrics and score:** `backend/services/contractor_intelligence_service.py`
- **Recommendation integration:** `backend/services/contractor_recommendation.py`, `contractor_recommendation_config.py`
- **Score update on completion:** `backend/services/maintenance_service.py` (`_update_contractor_performance_on_completion`)
- **Admin analytics API:** `backend/routes/contractors.py` (`GET /contractors/analytics`)
- **Scheduled job:** `backend/job_runner.py` (`run_contractor_performance_recalc`), `backend/server.py` (scheduler), `backend/services/job_schedule_registry.py`
