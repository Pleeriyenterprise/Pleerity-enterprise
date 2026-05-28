# Watchlist — operations outcome coherence

- Programme classification: **VERIFIED_OPERATIONALLY** (post-remediation staging run on `ef84b606`).
- Pilot property carries high historical WO debt from prior verification runs; production clients with many duplicate test WOs may still need data hygiene (out of scope).
- Frontend bundle deploy lag: verify production CDN serves latest JS after frontend deploy if UI parity regresses.
- Monitor Command Centre primary latency under degraded path (maintenance debt fallback adds DB reads).
