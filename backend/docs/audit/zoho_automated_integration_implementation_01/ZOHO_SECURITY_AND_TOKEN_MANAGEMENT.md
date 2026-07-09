# Zoho Security and Token Management

**Programme:** ZOHO AUTOMATED INTEGRATION IMPLEMENTATION

## Secrets (Render env — never commit)

| Variable | Purpose |
|----------|---------|
| ZOHO_CLIENT_ID | OAuth app |
| ZOHO_CLIENT_SECRET | OAuth app |
| ZOHO_REFRESH_TOKEN | Long-lived refresh |
| ZOHO_*_WEBHOOK_SECRET | Per-integration HMAC |
| ZOHO_ORG_ID | Books org |

## Token lifecycle

1. Refresh token stored in env (not DB)
2. Access token cached in `zoho_oauth_tokens` per `ZOHO_ENVIRONMENT`
3. Refresh 5 min before expiry
4. `ZohoOAuthManager.invalidate()` clears cache on rotation

## Environment isolation

- `ZOHO_ENVIRONMENT=staging|production`
- Separate OAuth apps recommended per environment
- EU endpoints default: `zohoapis.eu`, `accounts.zoho.eu`

## PII

- Analytics: aggregate only (`pii.py` enforcement)
- Campaigns: email required for audience — DPIA required before production
- Audit logs: no full PII in webhook metadata

## Route security

- Admin routes: `admin_route_guard`
- Webhook routes: 404 when integration disabled (hide surface)
- Internal path prefix `/api/internal/integrations/zoho/`

## Rotation

1. Generate new refresh token in Zoho console
2. Update Render secret
3. Call OAuth invalidate or restart service
4. Verify via admin status endpoint
