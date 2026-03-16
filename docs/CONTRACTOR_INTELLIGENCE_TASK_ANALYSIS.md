# Contractor Intelligence Layer — Task vs Codebase

## Existing implementation (no duplication)

- **contractor_performance** (per client): `jobs_completed`, `jobs_on_time`, `last_used_at`. Updated on work order completion in `maintenance_service._update_contractor_performance_on_completion`. Synced to contractor doc: `job_count`, `sla_compliance_rate`.
- **contractor_recommendation.py**: Rule-based scoring (trade, region, credential, SLA, rating, rework). Uses `performance_map: contractor_id -> (jobs_completed, jobs_on_time)` and `contractor.sla_compliance_rate`, `rating_average`, `rework_rate`. No overall “performance score”; no reliability_score, response_time, completion_time, invoice_approval_rate.
- **Recommendation API**: `recommend_contractors_for_work_order` in contractor_service; used by client and admin. Returns score, reasons, recommendation_label, rating_average, sla_compliance_rate.
- **Admin**: GET /api/admin/ops/contractors (list), GET/PATCH contractor. No analytics (top performers, SLA issues, rejection rates).
- **Client UI**: Recommend list shows name, score, reasons, rating, SLA %, benchmark_fit. No explicit “reliability %” or “jobs completed” in client maintenance drawer (admin WO page shows rating + SLA).
- **Work orders**: `assigned_at`, `completed_at`. No `accepted_at` (contractor acceptance time) — needed for average_response_time and for average_completion_time (accept → complete).

## Gaps

| Part | Requirement | Status |
|------|-------------|--------|
| 1 | Metrics: reliability_score, average_response_time, average_completion_time, sla_success_rate, invoice_approval_rate | **Missing** — New service to compute from work_orders, contractor_assignments, contractor_performance, invoices. Add `accepted_at` on work_orders when contractor accepts. |
| 2 | Overall score (40% reliability, 25% SLA, 20% response, 15% invoice) stored on contractor | **Missing** — Compute and store on contractor profile. |
| 3 | Rank by trade + distance + performance score; high performers first | **Partial** — Recommendation already uses trade/region/SLA/rating; add performance_score into ranking. |
| 4 | Admin analytics: top performers, SLA issues, high rejection; filtering | **Missing** — New admin endpoint(s) and UI. |
| 5 | Client visibility: contractor score, reliability %, jobs completed in selection UI | **Partial** — Recommend returns some; add score/reliability/jobs_completed to response and show in client list. |
| 6 | Log metric calc; periodic job; documentation | **Missing** — Audit log on recalc; scheduled job; doc. |

## Conflicts

- **None.** Existing recommendation weights (trade 30, region 20, etc.) stay; the task’s 40/25/20/15 define a **stored** overall contractor score. Ranking uses that score as an additional factor so high performers appear first.

## Design choices

1. **accepted_at**: Set on work_order when contractor accepts (portal and job-link accept handlers). Used for response_time (assigned_at → accepted_at) and completion_time (accepted_at → completed_at). If accepted_at is missing (e.g. old WOs), fall back to assigned_at for completion_time; response_time undefined for those.
2. **Metrics scope**: Compute per contractor (aggregate across all clients) for a single “contractor profile” score used everywhere. Optionally later add per-client metrics for admin filters.
3. **Storage**: Store on contractor doc: `reliability_score`, `average_response_time_hours`, `average_completion_time_hours`, `sla_success_rate`, `invoice_approval_rate`, `performance_score` (0–100), `performance_score_updated_at`.
4. **Recommendation**: Add a component in contractor_recommendation that uses contractor.performance_score (e.g. scale to weight 25) so higher score = higher rank; keep existing factors.
5. **Admin analytics**: GET /api/admin/ops/contractors/analytics with query params (top_performers, sla_issues, high_rejection) and filters; returns list with metrics. Admin UI: reuse contractors page or add an “Analytics” tab/section with tables.
