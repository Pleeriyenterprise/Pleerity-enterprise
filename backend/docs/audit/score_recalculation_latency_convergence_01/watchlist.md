# Watchlist — final verification (2026-06-03)

## Classification: VERIFIED_OPERATIONALLY

- Fix commit: `d5252f99`
- REQUEUE_DRIFT: **closed** on staging
- Pending visible: yes (23.13s)
- Worker converged: yes (72.78s, score 42→52)
- Latency class: acceptable

## Screenshots

- `screenshots/final_verification/dashboard_pending.png`
- `screenshots/final_verification/property_pending.png`
- `screenshots/final_verification/dashboard_converged.png`
- `screenshots/final_verification/property_converged.png`

## Follow-ups (non-blocking)

1. **Backend build SHA endpoint** — deploy verification currently infers fix via behavioural probe; expose git SHA on `/health` for deterministic deploy checks.
2. **Admin recalc trigger** — set `STAGING_ADMIN_PASSWORD` in CI for governed admin repair path (fallback sync works but is noisier).
3. **Unified poll script** — `score_recalculation_latency_final_verification_01.py` updated to avoid missing short pending windows during browser capture.
