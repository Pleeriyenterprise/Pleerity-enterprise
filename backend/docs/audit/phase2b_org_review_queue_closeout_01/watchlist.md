# Watchlist — PHASE-2B-ORG-REVIEW-QUEUE-CLOSEOUT-01

## Open (non-blocking)

- [ ] **ROLE_CLIENT live 403:** `david@yopmail.com` returns HTTP 423 Locked on staging login — org queue 403 for ROLE_CLIENT not live-tested; code invariant `is_org_reviewer_role("ROLE_CLIENT")=false` confirmed locally.
- [ ] **Escalation resolution E2E:** Escalation queue has 4 staging rows; admin verify/override resolution browser flow not exercised in this closeout (queue visibility + separation verified only).
- [ ] **Wales occupation_contract re-pending:** After verify, Wales occupation contract reseed auto-completes to `VERIFIED`/`evidence_recorded` — use `scotland_landlord_registration` (or similar ORG family) for future org queue seeding on this pilot.

## Monitoring

- [ ] Monitor org queue row counts after production landlord ORG family submissions.
- [ ] Watch for orphan queue presentation after mixed verify/reject cycles (`audit_orphan_queue_states`).

## Closed in this closeout

- [x] Deploy `40165e8a` continuity confirmed
- [x] Org queue operational with governance invariant
- [x] Verify/reject reuse + queue row removal
- [x] Post-review convergence (Requirements / Today / CC / cognition)
- [x] Escalation queue separated from doc queue + org queue
- [x] A/C families remain queue-less
- [x] Browser proof captured
