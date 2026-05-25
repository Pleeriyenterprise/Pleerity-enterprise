# Watchlist — performance_runtime_verify_01

1. **Backend `/client/command-center`** — Browser primary ~97s with shell at 580ms; classify as capacity/perf workstream (not hidden by UI).
2. **Backend `/today/items`** — API ~30s / ~1.6MB; Today primary ~3s in browser (progressive win) but payload slimming still needed.
3. **Stale-refresh banner** — Shipped (`portal-stale-refresh-banner` in `main.2865d241.js`); add manual UX check on rapid cross-nav during slow refetch, or extend harness to force expired cache + in-flight refresh.
4. **Requirements/Documents cold primary ~22–24s** — Shell immediate; investigate requirements presentation payload and documents list projection.
5. **Dashboard cold ~25s** — Revisit within 45s should use cache (not re-probed after long cold run); confirm with operator session.
