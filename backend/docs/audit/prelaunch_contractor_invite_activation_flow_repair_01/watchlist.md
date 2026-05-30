# PRELAUNCH-CONTRACTOR-INVITE-ACTIVATION-FLOW-REPAIR-01 watchlist

- Deploy backend + frontend with link-context, onboarding state, and assignment portal invite.
- Re-run harness after deploy; expect `link_context_deployed: true` and full browser job-link activation E2E.
- Confirm contractor receives **two** emails on assign when inactive: job assignment + portal set-password (with return_to job).
- Legacy contractors with job_invite_sent_at backfill: optional migration for rows assigned before this repair.
- Admin resend invite should continue to update portal_invite_sent_at (unchanged path).
