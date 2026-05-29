# Watchlist

- Classification: **VERIFIED_OPERATIONALLY** (closeout 2026-05-29 after Vercel deploy)
- Blockers: none
- Invariant: operational UI must never use `projection=list`.
- `OPERATIONAL_CACHE_KEYS.requirements` remains list projection for KPI surfaces only.
- `OPERATIONAL_CACHE_KEYS.requirementsOperational` → `projection=full` for Requirements workspace.
- Residual: some rows still show primary CTA **Upload document** when server `take_action.primary` is upload-oriented (6 of first 12 sampled); authority-specific labels dominate (e.g. Legionella, HMO licence, gas/EICR).
- Monitor: cross-surface samples currently pilot-property scoped; expand if new authority regressions reported.
