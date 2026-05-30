# PRELAUNCH-TENANT-INVITE-ACTIVATION-FLOW-REPAIR-01

- Classification: **VERIFIED_OPERATIONALLY**
- Deploy SHA: `8b2b3eb50cba43124c4faccdc3bd2898c92152bb`

## Verified

- [x] Tenant invite persists `portal_invite_sent_at` and `Activation pending` label
- [x] Resend updates timestamp; token hygiene with `purpose: tenant_invite`
- [x] Set-password context detects tenant; redirects to `/tenant`
- [x] Post-activation: `linked_to_tenancy` when property assigned
- [x] Tenant dashboard accessible; landlord `/client/*` blocked for tenant JWT
- [x] Landlord UI invite guidance + onboarding badges
- [x] No landlord onboarding side effects on tenant activation

## Residual (non-blocking)

- Moved-out tenant flow not re-tested in this closeout (no moved_out flag on portal_users yet)
- Dedicated admin Ops tenant page not added; landlord list API is invite truth surface
- Rent `property_tenancies` still separate from `tenant_assignments` (documented)

## Programme closed
