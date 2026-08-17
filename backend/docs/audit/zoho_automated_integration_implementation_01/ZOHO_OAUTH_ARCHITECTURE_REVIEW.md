# Zoho OAuth Architecture Review (Stage O1)

**Programme:** ZOHO OAUTH ARCHITECTURE VALIDATION  
**Date:** 2026-07-10  
**Scope:** Analysis only — no implementation changes  
**Codebase reference:** `af0b74fd` (`develop`)

---

## 1. Executive summary

The Pleerity Zoho integration uses a **single global OAuth credential set** and a **single access-token cache** for all outbound API integrations. Authentication is implemented in `ZohoOAuthManager` and consumed exclusively through `ZohoHttpClient`. There is **no per-integration token routing**, **no scope validation at runtime**, and **no storage of refresh-token lineage or Zoho app identity**.

This design is internally consistent but assumes one refresh token authorises all Zoho product APIs called by the adapters.

---

## 2. Components reviewed

| Component | Path | Role |
|-----------|------|------|
| `ZohoOAuthManager` | `services/integrations/zoho/oauth.py` | Refresh + cache access tokens |
| `ZohoHttpClient` | `services/integrations/zoho/client.py` | Attach bearer token to all API calls |
| Config accessors | `services/integrations/zoho/config.py` | Read `ZOHO_CLIENT_*`, `ZOHO_REFRESH_TOKEN` |
| Adapters | `services/integrations/zoho/adapters/*.py` | Product API calls (except Sign) |
| Sync service | `services/integrations/zoho/service.py` | Credential gate before adapter execution |
| Operational health | `services/integrations/zoho/operational_health.py` | OAuth cache visibility |
| Mongo indexes | `database.py` | `zoho_oauth_tokens` unique on `(token_id, environment)` |

---

## 3. Environment variables (OAuth-related)

| Variable | Storage | Consumed by | Notes |
|----------|---------|-------------|-------|
| `ZOHO_CLIENT_ID` | Render secret | `oauth.py` refresh | Single client for all apps |
| `ZOHO_CLIENT_SECRET` | Render secret | `oauth.py` refresh | Single client for all apps |
| `ZOHO_REFRESH_TOKEN` | Render secret | `oauth.py` refresh | Single refresh token for all apps |
| `ZOHO_ACCOUNTS_URL` | Env (default `https://accounts.zoho.eu`) | Token refresh endpoint | EU default |
| `ZOHO_API_BASE` | Env (default `https://www.zohoapis.eu`) | All API requests | Fixed base for all products |
| `ZOHO_ENVIRONMENT` | Env | Token cache namespace | `staging` \| `production` |

No per-integration OAuth env vars exist today.

---

## 4. Authentication flow (as implemented)

### 4.1 Credential gate

```python
def zoho_credentials_configured() -> bool:
    return bool(zoho_client_id() and zoho_client_secret() and zoho_refresh_token())
```

Used by:

- `ZohoOAuthManager.get_access_token()` — returns `None` if incomplete
- `ZohoIntegrationService.run_sync()` — skips outbound sync (except `sign`) with `no_credentials`
- Admin `/status` — exposes `credentials_configured: true/false`

**Sign integration** does not call Zoho APIs; it is exempt from the credential gate in `service.py`.

### 4.2 Access token resolution

```
Adapter → zoho_http_client.request()
       → zoho_oauth_manager.get_access_token()
           1. zoho_credentials_configured()?
           2. Mongo cache hit (token_id=zoho_oauth_access_token, environment=ZOHO_ENVIRONMENT)?
              - Valid if expires_at > now + 300s buffer
           3. Else POST {ZOHO_ACCOUNTS_URL}/oauth/v2/token
              grant_type=refresh_token
              client_id, client_secret, refresh_token from env
           4. Store access_token + expires_at in Mongo
       → Authorization: Zoho-oauthtoken {access_token}
       → {ZOHO_API_BASE}{path}
```

### 4.3 Refresh request (exact parameters)

From `oauth.py`:

| Parameter | Source |
|-----------|--------|
| `grant_type` | `refresh_token` (fixed) |
| `refresh_token` | `ZOHO_REFRESH_TOKEN` |
| `client_id` | `ZOHO_CLIENT_ID` |
| `client_secret` | `ZOHO_CLIENT_SECRET` |

**Not sent:** `scope`, `redirect_uri`, product/app identifier.

**Not persisted from refresh response:** `api_domain` (response includes it; code ignores it and uses `ZOHO_API_BASE` instead).

### 4.4 Token cache (MongoDB)

| Field | Value |
|-------|-------|
| Collection | `zoho_oauth_tokens` |
| Document key | `token_id: "zoho_oauth_access_token"` + `environment` |
| Stored fields | `access_token`, `expires_at`, `updated_at` |
| Index | Unique compound `(token_id, environment)` |

**Implication:** Only **one** cached access token exists per Pleerity environment (`staging` / `production`), shared across CRM, Analytics, Books, Campaigns, and WorkDrive.

### 4.5 Invalidation

`ZohoOAuthManager.invalidate()` deletes the Mongo cache document for the current `zoho_environment()`. It does **not** revoke the refresh token at Zoho (`oauth/v2/token/revoke` is not called).

---

## 5. Adapter → API surface (OAuth consumers)

All outbound integrations share the same token via `zoho_http_client`:

| Integration | OAuth required | API paths (relative to `ZOHO_API_BASE`) |
|-------------|----------------|----------------------------------------|
| **crm** | Yes | `POST /crm/v6/{module}`, `PUT /crm/v6/{module}/{id}` |
| **analytics** | Yes | `POST /analytics/v2/workspaces/{id}/data` |
| **books** | Yes | `POST /books/v3/journals?organization_id={org}` |
| **campaigns** | Yes | `POST /campaigns/v1.1/addlistsubscribersinbulk`, `POST /campaigns/v1.1/suppresssubscribers` |
| **workdrive** | Yes | `POST /workdrive/api/v1/upload` |
| **sign** | No | Webhook-only; no `zoho_http_client` usage |

Each maps to a **distinct Zoho business application** in OAuth scope nomenclature (`ZohoCRM`, `ZohoAnalytics`, `ZohoBooks`, `ZohoCampaigns`, `WorkDrive`).

---

## 6. Operational visibility

`operational_health._oauth_health()` reads the single Mongo cache document and reports:

- `configured` — env trio present
- `token_cached` — Mongo doc exists
- `token_valid` — `expires_at` within buffer

It does **not** verify token usability against each Zoho product API.

---

## 7. Architectural characteristics

| Characteristic | Current state |
|----------------|---------------|
| OAuth clients | 1 (`ZOHO_CLIENT_ID`) |
| Refresh tokens | 1 (`ZOHO_REFRESH_TOKEN`) |
| Access token caches | 1 per `ZOHO_ENVIRONMENT` |
| Per-integration auth | None |
| Runtime scope enforcement | None |
| Token refresh scope parameter | None |
| Multi-DC `api_domain` handling | Ignored; fixed EU base URL |
| Incremental scope enhancement | Not implemented |

---

## 8. Internal consistency

The implementation is **self-consistent**: every adapter that needs OAuth calls the same manager and HTTP client. There are no code paths that expect per-app refresh tokens.

The open question is **external validity** against Zoho's OAuth platform rules — addressed in `ZOHO_OAUTH_COMPATIBILITY_REPORT.md`.

---

## 9. Documentation alignment note

`ZOHO_SANDBOX_READINESS_REPORT.md` §3.2 suggests generating one refresh token with the **union of scopes** across CRM, Analytics, Books, Campaigns, and WorkDrive. That guidance assumes multi-app scope bundling is permitted. This architecture review does not assume that; compatibility is validated separately.
