# Watchlist — performance_runtime_verify_01

1. **Browser E2E** — Run manual checklist in `browser_navigation_timings.json` after frontend deploy; target `VERIFIED_OPERATIONALLY`.
2. **Backend `/today/items`** — ~30s / ~1.6MB on pilot account; needs projection or pagination (frontend cannot fix alone).
3. **Backend `/client/command-center`** — ~75s on staging; P2 now unblocks after CC response but CC remains bottleneck.
4. **Dashboard cold load** — Still gated on `/client/dashboard` (~24s); revisit path should feel instant via cache.
5. **Intake/layout** — `ClientPortalLayout` still fire-and-forgets dashboard for CRN; consider shared cache wiring.
