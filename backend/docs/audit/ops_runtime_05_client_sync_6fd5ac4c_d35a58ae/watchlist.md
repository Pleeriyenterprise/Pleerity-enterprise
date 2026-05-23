# Watchlist — F5 client sync (`20260523T184731Z`)

## Non-blocking observations

- **Property-scoped vs client-wide open counts:** `protection-snapshot` (property filter) reported `open_maintenance_issues` 34→35 while `/maintenance/issues/open-count` reported 40→41 at baseline/post-mutation. Expected if other properties hold open issues; not contradictory within each surface’s scope.
- **Staging WAF pacing:** Rapid harness calls triggered `429` / “suspicious activity” in earlier attempts. Successful run used `OPS_RUNTIME_COOLDOWN_S=90`, `OPS_API_PACE_S=3.5`, and request retries. Future OPS runs should keep paced execution.

## F6

F6 (`ops_runtime_06_rent_ops`) **may proceed** per F5 `VERIFIED_OPERATIONALLY` (subject to F6 charter).
