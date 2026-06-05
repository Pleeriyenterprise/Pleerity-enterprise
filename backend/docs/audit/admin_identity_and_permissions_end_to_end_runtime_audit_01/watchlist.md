# Admin identity & permissions watchlist

- Classification: `VERIFIED_OPERATIONALLY`
- [x] Admin identity lifecycle and permission boundaries verified on staging.
- [ ] Optional: dedicated support-lite staging persona for restricted-admin probes.
- [ ] Optional: full yopmail-backed invite onboarding completion (set-password token from inbox).
- [ ] Known drift: Team `/admin/team/users` create path does not send invite email (TODO in code).
- [ ] Known drift: Admin lifecycle actions bypass `adminActionPolicyRegistry` server enforcement.
