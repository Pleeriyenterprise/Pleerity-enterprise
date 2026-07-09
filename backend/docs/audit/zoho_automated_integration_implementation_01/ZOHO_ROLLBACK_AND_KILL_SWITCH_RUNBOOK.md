# Zoho Rollback and Kill Switch Runbook

**Programme:** ZOHO AUTOMATED INTEGRATION IMPLEMENTATION

## Immediate stop (kill switch)

1. Set `ZOHO_KILL_SWITCH=true` in environment
2. Restart backend service
3. Verify `GET /api/admin/integrations/zoho/status` shows `kill_switch_active: true`
4. All outbound sync returns skipped; queue processing stops

## Disable single integration

Set specific flag false, e.g. `ZOHO_CRM_SYNC_ENABLED=false` — CRM only stops; others unaffected.

## Disable entire Zoho layer

Set `ZOHO_INTEGRATION_ENABLED=false` — admin and webhook routes return 404.

## Rollback deployment

1. Revert git commit containing integration layer
2. Deploy previous backend SHA
3. Existing `zoho_sync_*` collections remain (read-only history) — no data authority impact
4. Pleerity SoR unchanged — leads, billing, compliance unaffected

## Replay failed syncs

1. Fix root cause (credentials, mapping, API outage)
2. `POST /api/admin/integrations/zoho/replay` with `dead_letter_id`
3. Verify sync run status → success in admin sync-runs

## CRM sync rollback

- Disabling CRM stops new outbound sync
- Zoho replica may be stale — Pleerity remains authoritative
- Optional: manual Zoho cleanup of test records (ops procedure)

## Production enablement checklist

- [ ] Staging pilot complete
- [ ] DPIA signed
- [ ] P0 policies published
- [ ] OAuth production org configured
- [ ] Webhook secrets set
- [ ] Kill switch tested
- [ ] One integration enabled at a time
