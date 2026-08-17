# Zoho Security and Token Management

**Programme:** ZOHO AUTOMATED INTEGRATION IMPLEMENTATION  
**OAuth architecture:** Option B (shared client, per-integration refresh tokens)

## Secrets (Render env — never commit)

| Variable | Purpose |
|----------|---------|
| ZOHO_CLIENT_ID | Shared OAuth Self Client |
| ZOHO_CLIENT_SECRET | Shared OAuth Self Client |
| ZOHO_ANALYTICS_REFRESH_TOKEN | Analytics refresh token |
| ZOHO_CRM_REFRESH_TOKEN | CRM refresh token |
| ZOHO_CAMPAIGNS_REFRESH_TOKEN | Campaigns refresh token |
| ZOHO_BOOKS_REFRESH_TOKEN | Books refresh token |
| ZOHO_WORKDRIVE_REFRESH_TOKEN | WorkDrive refresh token |
| ZOHO_REFRESH_TOKEN | **Deprecated** — legacy migration fallback only |
| ZOHO_*_WEBHOOK_SECRET | Per-integration HMAC |
| ZOHO_ORG_ID | Books org |

**Important:** One refresh token cannot authorise multiple Zoho business applications. Mint separate tokens per integration with integration-specific scopes. See `OAUTH_CREDENTIAL_REGISTRY.md`.

## Token lifecycle

1. Per-integration refresh tokens stored in env (not DB)
2. Access tokens cached in `zoho_oauth_tokens` per integration per `ZOHO_ENVIRONMENT`
3. Cache identifiers: `zoho_oauth_access_token_{crm,analytics,books,campaigns,workdrive}`
4. Refresh 5 min before expiry
5. `ZohoOAuthManager.invalidate(integration)` clears per-integration cache on rotation

## Credential resolution

1. `ZOHO_{INTEGRATION}_REFRESH_TOKEN`
2. Legacy `ZOHO_REFRESH_TOKEN` (deprecated — see `OAUTH_DEPRECATION_POLICY.md`)
3. No credentials → sync skipped with `no_credentials`

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

1. Generate new refresh token in Zoho API Console for the specific integration
2. Update Render secret (`ZOHO_{INTEGRATION}_REFRESH_TOKEN`)
3. Call `ZohoOAuthManager.invalidate(integration)` or restart service
4. Verify via admin status endpoint (`oauth.by_integration`)
