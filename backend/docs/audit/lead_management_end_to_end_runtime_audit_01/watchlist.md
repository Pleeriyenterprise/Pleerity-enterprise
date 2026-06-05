# Lead Management E2E watchlist

- Classification: `PARTIAL`
- [ ] Blocker: **conversion**
- [ ] **LEAD_CONVERSION_DRIFT:** POST `/admin/leads/{id}/convert` accepts LOST leads (no 409); add status guard in `LeadService.convert_lead`.
- [ ] **LEAD_CONVERSION_DRIFT:** duplicate convert returns 200 instead of idempotent 409.
- [ ] Optional: ROLE_SUPPORT-only CRM permission boundary probe.
- [ ] Optional: CHECKOUT_CREATED / ACTIVATED_CTS dedicated staging fixtures when available.
- [ ] Optional: staging AI summary (`generate-summary`) reliability when provider healthy.
