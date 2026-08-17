# OAuth Credential Registry

**Programme:** ZOHO OAUTH ARCHITECTURE IMPLEMENTATION  
**Source:** `services/integrations/zoho/oauth_credential_registry.py`

---

## Registry purpose

The OAuth Credential Registry is a configuration-driven catalogue of every Zoho OAuth integration. It describes how credentials are resolved; it does not store secrets.

Admin visibility: `registry_snapshot()` exposed via operational health (`oauth.credential_registry`) and `integration_status_snapshot()`.

---

## Record fields

| Field | Description |
|-------|-------------|
| `integration` | Integration key (`crm`, `analytics`, …) |
| `oauth_client` | `shared` — one Self Client for all integrations |
| `refresh_token_source` | Env var name for per-integration refresh token |
| `expected_scope` | Scope string required when minting that integration's refresh token |
| `oauth_endpoint` | Resolved `ZOHO_ACCOUNTS_URL` at runtime |
| `api_endpoint` | Resolved `ZOHO_API_BASE` at runtime |
| `environment` | `staging` or `production` (`ZOHO_ENVIRONMENT`) |
| `cache_identifier` | Mongo `token_id` for access token cache |
| `feature_flag` | Integration enablement flag env var |
| `current_status` | `enabled` or `disabled` based on feature flag |
| `requires_oauth` | `false` for Sign (webhook-only) |

---

## OAuth integrations

| Integration | Refresh token env | Cache identifier | Expected scope |
|-------------|-------------------|------------------|----------------|
| analytics | `ZOHO_ANALYTICS_REFRESH_TOKEN` | `zoho_oauth_access_token_analytics` | `ZohoAnalytics.data.create` |
| crm | `ZOHO_CRM_REFRESH_TOKEN` | `zoho_oauth_access_token_crm` | `ZohoCRM.modules.leads.CREATE,ZohoCRM.modules.leads.UPDATE,ZohoCRM.modules.leads.READ` |
| campaigns | `ZOHO_CAMPAIGNS_REFRESH_TOKEN` | `zoho_oauth_access_token_campaigns` | `ZohoCampaigns.contact.CREATE-UPDATE` |
| books | `ZOHO_BOOKS_REFRESH_TOKEN` | `zoho_oauth_access_token_books` | `ZohoBooks.accountants.CREATE` |
| workdrive | `ZOHO_WORKDRIVE_REFRESH_TOKEN` | `zoho_oauth_access_token_workdrive` | `WorkDrive.files.CREATE` |

---

## Non-OAuth integrations

| Integration | OAuth | Notes |
|-------------|-------|-------|
| sign | No | Webhook HMAC verification only |

---

## Shared OAuth client env vars

| Variable | Purpose |
|----------|---------|
| `ZOHO_CLIENT_ID` | Shared client ID |
| `ZOHO_CLIENT_SECRET` | Shared client secret |

---

## Legacy fallback (deprecated)

| Variable | Status |
|----------|--------|
| `ZOHO_REFRESH_TOKEN` | Deprecated — see `OAUTH_DEPRECATION_POLICY.md` |

Legacy cache identifier `zoho_oauth_access_token` is no longer written by the OAuth manager. Existing documents expire naturally.

---

## Runtime API

```python
from services.integrations.zoho.oauth_credential_registry import (
    get_oauth_integration_record,
    oauth_integrations,
    registry_snapshot,
)
from services.integrations.zoho.credential_resolver import resolve_oauth_credentials
```

`resolve_oauth_credentials(integration)` returns resolved credentials including `refresh_token_source` (`per_integration`, `legacy`, `none`).
