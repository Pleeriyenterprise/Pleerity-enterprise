# REVIEW-ASSURANCE-SIMPLIFICATION-01 watchlist

- [ ] Staging browser proof after deploy: self-recorded declaration modal, escalation queue row, document verification modal
- [ ] Migrate any DB rows with `review_owner=org_admin` to platform escalation or self-recorded (orphan audit surfaces these)
- [ ] Remove dead `org_verification_pending` branch in `cognition_next_step_for_requirement` when no longer reachable
- [ ] Historical audit scripts under `backend/tmp_*` still reference ORG_ADMIN_REVIEWED (documentation only)
- [ ] `SOURCE_ORG_REVIEW` satisfaction source label — legacy read-only compatibility
