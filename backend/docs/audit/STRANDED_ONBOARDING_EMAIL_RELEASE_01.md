# Stranded onboarding — email release 01

## Release path

Mode `release_and_restart`:

1. Guard against paid/provisioned/password-set identities.
2. Expire open Checkout Session.
3. Revoke continuation tokens.
4. Set `onboarding_identity_status=RELEASED_FOR_RESTART`.
5. Copy canonical email to `released_canonical_email`.
6. Vacate unique `email` (and matching `contact_email`) so a new client row can insert.
7. Disable unpaid portal users without a set password (relocate `auth_email`).
8. Audit `ONBOARDING_RELEASED_FOR_RESTART`.

The attempt remains queryable by `client_id`. It leaves Pending Setup automatically.

## Re-registration

`client_email_taken` ignores released identity. Fresh intake creates a **new** `client_id` and may set `restarted_from_client_id` to the latest released attempt. Duplicate protection remains for any **active** client or portal user.
