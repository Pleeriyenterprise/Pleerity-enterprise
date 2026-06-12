# OPERATIONS-ENTITLEMENT-ACTION-UX-CLOSEOUT-01

- [x] CONTRACTOR_NETWORK guard on POST /jobs/{id}/assign-contractor
- [x] Issues assign_contractor locked CTA when no contractor_network
- [x] Job detail locked assign state + upgrade modal
- [x] UpgradePrompt contractor_network → PLAN_3_PRO / Professional
- [x] Assign modal auto-focus (select / early-network / add form)
- [x] Staging API guard proof (Professional allowed; Portfolio 403 covered by pytest — fixture D has no maintenance jobs on staging)
- [x] Staging issues locked CTA browser proof
- [x] Staging job detail locked UX browser proof
- [x] Staging modal focus desktop + 390px
- [x] Unit/regression tests green
- [ ] Monitor risk-signals assign_contractor locked CTA styling (handler gated; list buttons may still look executable)
- [x] Booking-guard modal routes non-entitled users to locked upsell (not silent no-op)
