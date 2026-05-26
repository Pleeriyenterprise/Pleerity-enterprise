# Performance remediation 02 — watchlist

## Post-deploy verification (required)

1. Deploy backend + frontend to staging/production.
2. Run `python tmp_performance_backend_remediation_02.py` with `OPS_API_PACE_S=6`.
3. Run `python tmp_performance_browser_verify_01.py` (or equivalent) on landlord pages.
4. Confirm Command Centre primary content **<15s** (target **<3s** where feasible).
5. Confirm Today payload **<200KB** without `include_flat_items`.
6. Second navigation hit should show `freshness.cache_hit: true` on unified surfaces within 45s TTL.

## Remaining optimisations

- Requirements list payload (~351KB): field projection or pagination (out of scope for 02).
- `portfolio/compliance-summary` used on Today for jurisdiction banner (~17s baseline) — consider scoped notice endpoint.
- Dashboard satellite calls (score trend, timeline, work orders): batch or lazy-load tabs.
- Invalidate unified cache on task override mutations (`client_task_state` writes).
- Property detail: dedicated `GET /client/properties/{id}` header endpoint to avoid any list fallback.

## Authority

- Do not remove `compliance_counts_authority` or bypass `calculate_compliance_score.stats` on Command Centre.
- Keep `projection=full` for document detail flows needing linkage governance.
