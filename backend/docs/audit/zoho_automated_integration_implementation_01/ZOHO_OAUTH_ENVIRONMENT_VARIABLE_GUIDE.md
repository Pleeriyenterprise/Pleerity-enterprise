# Zoho OAuth — Environment Variable Guide (Option B)

**Programme:** ZOHO OAUTH ARCHITECTURE IMPLEMENTATION  
**Architecture:** Option B — Shared OAuth Client, Per-Integration Refresh Tokens

---

## Shared OAuth client (all integrations)

| Variable | Required | Purpose |
|----------|----------|---------|
| `ZOHO_CLIENT_ID` | Yes (when OAuth used) | Shared Zoho Self Client ID |
| `ZOHO_CLIENT_SECRET` | Yes (when OAuth used) | Shared Zoho Self Client secret |
| `ZOHO_ACCOUNTS_URL` | No | OAuth token endpoint base (default `https://accounts.zoho.eu`) |
| `ZOHO_API_BASE` | No | Zoho API base (default `https://www.zohoapis.eu`) |
| `ZOHO_ENVIRONMENT` | No | `staging` or `production` — isolates Mongo access-token cache |

---

## Per-integration refresh tokens

Each Zoho business application requires its **own** refresh token. One refresh token cannot authorise multiple Zoho products.

| Variable | Integration | Phase |
|----------|-------------|-------|
| `ZOHO_ANALYTICS_REFRESH_TOKEN` | Analytics | Phase B |
| `ZOHO_CRM_REFRESH_TOKEN` | CRM | Phase C |
| `ZOHO_CAMPAIGNS_REFRESH_TOKEN` | Campaigns | Campaigns pilot |
| `ZOHO_BOOKS_REFRESH_TOKEN` | Books | Books pilot |
| `ZOHO_WORKDRIVE_REFRESH_TOKEN` | WorkDrive | WorkDrive pilot |

**Sign** does not require an OAuth refresh token (webhook-only).

---

## Deprecated (migration only)

| Variable | Status | Notes |
|----------|--------|-------|
| `ZOHO_REFRESH_TOKEN` | **Deprecated** | Legacy fallback during migration. See `OAUTH_DEPRECATION_POLICY.md`. Will be removed before first production Zoho rollout. |

Resolution order at runtime:

1. `ZOHO_{INTEGRATION}_REFRESH_TOKEN`
2. `ZOHO_REFRESH_TOKEN` (legacy, with runtime warnings for non-CRM integrations)
3. No credentials → `no_credentials` skip

---

## Access token cache (MongoDB — not env)

Per-integration cache identifiers in collection `zoho_oauth_tokens`:

| Integration | `token_id` |
|-------------|------------|
| CRM | `zoho_oauth_access_token_crm` |
| Analytics | `zoho_oauth_access_token_analytics` |
| Books | `zoho_oauth_access_token_books` |
| Campaigns | `zoho_oauth_access_token_campaigns` |
| WorkDrive | `zoho_oauth_access_token_workdrive` |

Each document is keyed by `(token_id, environment)`. No Mongo schema migration required.

---

## Source of truth

Runtime accessors: `services/integrations/zoho/config.py`, `credential_resolver.py`, `oauth_credential_registry.py`

Example template: `docs/zoho_integration.env.example`
