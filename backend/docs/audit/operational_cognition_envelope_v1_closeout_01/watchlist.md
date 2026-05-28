# Watchlist — Operational Cognition Envelope V1 Closeout

## Post-closeout monitoring

- Re-verify list/detail parity after any change to `operational_continuation_service` or `serialize_client_job`.
- Ensure `GET /client/maintenance/issues/{id}` always attaches cognition (regression guard in API tests recommended).
- Admin unresolved queue: refresh staging admin credentials for periodic cognition spot-check.

## Non-blocking

- List row chips depend on `list_guidance.recommended_action_label`; empty guidance correctly renders no chip (not a contradiction).
