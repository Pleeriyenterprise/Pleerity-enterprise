# PRELAUNCH-CONTRACTOR-INVITE-ACTIVATION-FLOW-REPAIR-01

## Summary

Repaired split invite authority between job assignment email and portal activation.

## Root cause

Job assignment email (contractor_job_tokens + /job?token=) was sent without updating portal_access_status or issuing portal invite. Job-link API required status=active while landlord-added contractors remained approved/not_invited. Admin UI showed portal_access only, so job email sent appeared as Not invited.

## Repair

- Derived onboarding state (`job_invite_sent`, `portal_activation_pending`, etc.)
- Record `job_invite_sent_at` and auto-issue portal invite on assignment
- `GET /api/job/link-context` + activation panel (no dead-end / toast spam)
- Post-activation redirect via `return_to` on set-password URL
- Admin **Invite / activation** column uses onboarding truth
- Landlord assign modal activation guidance

## Classification

**PARTIAL**

## Runtime

- Unit tests: pass
- Staging link-context deployed: False
