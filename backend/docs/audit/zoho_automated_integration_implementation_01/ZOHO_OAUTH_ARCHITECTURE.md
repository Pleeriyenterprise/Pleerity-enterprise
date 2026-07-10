# Zoho OAuth Architecture (Option B — Implemented)

**Programme:** ZOHO OAUTH ARCHITECTURE IMPLEMENTATION  
**Status:** Implemented on `develop`  
**Decision:** Approved Option B (`ZOHO_OAUTH_RECOMMENDATION.md`)

---

## 1. Architecture summary

| Component | Responsibility |
|-----------|----------------|
| **Adapter** | Business sync logic; calls `ZohoHttpClient` with `integration` |
| **Credential Resolver** | Determines which refresh token belongs to each integration |
| **OAuth Manager** | Access token cache + refresh against Zoho OAuth |
| **Mongo `zoho_oauth_tokens`** | Per-integration access token cache per environment |

The Credential Resolver performs **no OAuth operations**. The OAuth Manager does **not** choose refresh tokens directly.

---

## 2. Runtime flow

```
Adapter
  → ZohoHttpClient.request(integration="crm", ...)
    → resolve_oauth_credentials("crm")
    → ZohoOAuthManager.get_access_token("crm")
      → Mongo cache: token_id="zoho_oauth_access_token_crm"
      → POST {ZOHO_ACCOUNTS_URL}/oauth/v2/token (refresh)
    → Authorization: Zoho-oauthtoken {access_token}
```

---

## 3. Shared vs per-integration credentials

| Credential | Scope |
|------------|-------|
| `ZOHO_CLIENT_ID` | Shared across all integrations |
| `ZOHO_CLIENT_SECRET` | Shared across all integrations |
| `ZOHO_*_REFRESH_TOKEN` | One per Zoho business application |
| Access token cache | One Mongo document per integration per environment |

---

## 4. Credential resolution order

```
1. ZOHO_{INTEGRATION}_REFRESH_TOKEN
2. ZOHO_REFRESH_TOKEN (deprecated legacy fallback)
3. No credentials
```

Legacy fallback emits runtime warnings for integrations other than CRM (approved migration scenario). See `OAUTH_DEPRECATION_POLICY.md`.

---

## 5. Code map

| Module | Path |
|--------|------|
| Credential registry | `services/integrations/zoho/oauth_credential_registry.py` |
| Credential resolver | `services/integrations/zoho/credential_resolver.py` |
| OAuth manager | `services/integrations/zoho/oauth.py` |
| HTTP client | `services/integrations/zoho/client.py` |
| Config accessors | `services/integrations/zoho/config.py` |
| Operational health | `services/integrations/zoho/operational_health.py` |

---

## 6. Observability

OAuth health is exposed per integration via:

- `GET /api/admin/integrations/zoho/status` → `oauth_by_integration`, `operational_snapshot.oauth.by_integration`
- Platform health summary → `zoho_integration_health.oauth_integrations_configured`

No secrets are exposed. See `OAUTH_CREDENTIAL_REGISTRY.md` for registry fields.

---

## 7. Boundaries preserved

- Feature flags and kill switch unchanged
- Pleerity remains System of Record
- Sign remains webhook-only (no OAuth refresh token)
- No production/staging config changes in this implementation commit
- No integration flags enabled

---

## 8. Post-implementation

After staging validation with per-integration refresh tokens, **no further OAuth architecture redesign** is required before Phase A and subsequent Zoho integration pilots.
