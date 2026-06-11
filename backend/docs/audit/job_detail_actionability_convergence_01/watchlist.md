# Watchlist — job detail actionability (post-deploy)

## Closed

- [x] Staging backend on `024f580e+`
- [x] Frontend bundle contains fix markers + build SHA
- [x] Hero “Assign contractor” opens modal (not Visit scroll) — job `e670afc5-ef2d-487b-b688-ac8d865daf63`
- [x] Contractor section same modal workflow
- [x] Progress “Awaiting contractor assignment” when unassigned (no false “Contractor assigned”)
- [x] Cancel gated on `next_actions.cancel`, placed in Job options (not hero)
- [x] Sophie entitlement guard (no executable assign without `contractor_network`)
- [x] Browser screenshots captured under `post_deploy_screenshots/`

## Non-blocking

- Cancel button is below the fold — users must scroll to Job options; consider sticky lifecycle panel in a future UX pass (out of scope for 024f580e).
- No staging fixture for `status=ASSIGNED` + `contractor_id=null`; API/unit tests cover drift correction.
- `test_operational_cognition_service::test_requirement_envelope_false_progression` remains a pre-existing unrelated failure.
