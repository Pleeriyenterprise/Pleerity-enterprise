# Operations watchlist (post invoice closeout)

## Resolved (2026-06-04 closeout)

- [x] INVOICING enabled on Wales HMO pilot via governed `PATCH /api/admin/ops/clients/{id}/feature-flags`.
- [x] Contractor submit → landlord approve → mark paid proven (contractor portal state + PATCH mutations).
- [x] Edge cases: pre-completion blocked, duplicate blocked, needs_info path, permission boundaries.

## Deploy follow-up

- [ ] Deploy `approval_service._invoice_for_api` serialization fix to staging/production so `GET /client/approvals` returns 200 (currently 500 after successful mutations).
- [ ] Re-run `operations_family_invoice_closeout_01_execute.py` after deploy to confirm landlord approvals API JSON (remove `STAGING_APPROVALS_GET_500_UNTIL_DEPLOY` flag).

## Optional hygiene

- [ ] Revert INVOICING manual override on pilot if staging policy requires plan-default only.
- [ ] Clean up marker invoices/work orders from closeout runs if portfolio noise is undesirable.
