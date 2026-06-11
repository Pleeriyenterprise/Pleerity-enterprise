# Watchlist — job detail actionability convergence

## Post-deploy

- [ ] Staging browser proof: hero “Assign contractor” opens modal (not Visit scroll).
- [ ] Staging: account without `contractor_network` sees help state, not executable assign.
- [ ] Staging: job with `status=ASSIGNED` and empty `contractor_id` shows “Awaiting contractor assignment” in progress strip.
- [ ] Confirm Cancel appears only in Job options when `next_actions` includes `cancel`.

## Follow-up (non-blocking)

- Operations list / Today row CTAs could call `jobDetailPrimaryAction` for preview deeplink hints (detail page already converged).
- Consider suppressing empty “During / after the visit” section when only lifecycle cancel exists (cosmetic).
- Pre-existing failure: `test_requirement_envelope_false_progression` in `test_operational_cognition_service.py` (unrelated).

## Governance

- Backend still enforces assign via assignable-contractors API and entitlements.
- Whole-job cancel API unchanged; visibility now follows `next_actions` lifecycle contract.
