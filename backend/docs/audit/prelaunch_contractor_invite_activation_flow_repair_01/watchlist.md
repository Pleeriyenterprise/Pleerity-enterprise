# PRELAUNCH-CONTRACTOR-INVITE-ACTIVATION-FLOW-REPAIR-01 closeout watchlist

- Classification: **VERIFIED_OPERATIONALLY**
- Deploy SHA: `c8586fe9adc76dbea9d2681ff47307c86af75ee1`
- Hotfix resolves 32714209 blockers: update_contractor job_invite params, _sanitize_doc enrich, JobPage useMemo

## Verified

- [x] Deploy continuity (version, health, endpoints, bundle markers)
- [x] Landlord assign persists job_invite_sent_at + job_invite_last_work_order_id
- [x] Portal invite auto-sent on assign (portal_invite_sent_at, invite_pending)
- [x] Admin onboarding_state_label: Activation pending → Active (not Not invited)
- [x] Resend invite returns 200 and updates timestamp
- [x] link-context activation_required for inactive contractor
- [x] JobPage activation panel + resend (1 link-context call, no loop)
- [x] Inactive contractor blocked from work-order (ACTIVATION_REQUIRED)
- [x] Set-password activates contractor; job work-order accessible after
- [x] Quote submit smoke 200 on AWAITING_QUOTE job
- [x] No inactive-profile toast spam

## Residual (non-blocking)

- Landlord assign modal guidance: copy in bundle; automated browser modal open not exercised (requires job with assign next_action in UI at test time)
- Quote smoke used separate AWAITING_QUOTE job (closeout primary job had null price_status)

## Programme closed

No further work required for PRELAUNCH-CONTRACTOR-INVITE-ACTIVATION-FLOW-REPAIR-01 unless regression detected.
