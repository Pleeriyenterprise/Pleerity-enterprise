# OAuth Implementation Changelog

**Programme:** ZOHO OAUTH ARCHITECTURE IMPLEMENTATION — Option B  
**Date:** 2026-07-10

---

## Summary

Implemented approved Option B OAuth architecture: shared OAuth client with per-integration refresh tokens, credential resolver, per-integration access token cache, operational health extensions, and backward-compatible legacy fallback.

---

## New modules

| File | Purpose |
|------|---------|
| `services/integrations/zoho/oauth_credential_registry.py` | Configuration-driven OAuth integration registry |
| `services/integrations/zoho/credential_resolver.py` | Per-integration credential resolution (no OAuth ops) |
| `tests/integrations/zoho/test_zoho_oauth.py` | OAuth Option B regression tests |

---

## Modified modules

| File | Change |
|------|--------|
| `services/integrations/zoho/oauth.py` | `get_access_token(integration)`; per-integration Mongo cache; auth failure tracking |
| `services/integrations/zoho/client.py` | Passes `integration` to OAuth manager |
| `services/integrations/zoho/config.py` | `zoho_refresh_token_for`, `zoho_oauth_configured_for`, `oauth_by_integration` in status snapshot |
| `services/integrations/zoho/service.py` | Per-integration credential gate |
| `services/integrations/zoho/operational_health.py` | Per-integration OAuth health + registry in snapshot |
| `tests/integrations/zoho/test_zoho_integration.py` | Analytics sync test uses per-integration token |
| `docs/zoho_integration.env.example` | Per-integration refresh token placeholders |

---

## Documentation

| Document | Action |
|----------|--------|
| `ZOHO_OAUTH_ARCHITECTURE.md` | Created — implemented architecture |
| `ZOHO_OAUTH_ENVIRONMENT_VARIABLE_GUIDE.md` | Created — env var reference |
| `OAUTH_DEPRECATION_POLICY.md` | Created — `ZOHO_REFRESH_TOKEN` deprecation |
| `OAUTH_CREDENTIAL_REGISTRY.md` | Created — registry reference |
| `OAUTH_IMPLEMENTATION_REPORT.md` | Created — implementation summary |
| `OAUTH_REGRESSION_TEST_RESULTS.md` | Created — test evidence |
| `ZOHO_SANDBOX_READINESS_REPORT.md` | Updated §3.2, §3.4, §4.1 |
| `ZOHO_SECURITY_AND_TOKEN_MANAGEMENT.md` | Updated for Option B |
| `ZOHO_OAUTH_MIGRATION_PLAN.md` | Step 1 marked complete |

---

## Behavioural changes

| Before | After |
|--------|-------|
| Single `ZOHO_REFRESH_TOKEN` for all APIs | Per-integration refresh tokens with legacy fallback |
| Single Mongo cache `zoho_oauth_access_token` | Per-integration cache `zoho_oauth_access_token_{integration}` |
| Global `zoho_credentials_configured()` gate on sync | `zoho_oauth_configured_for(integration)` gate |
| Single OAuth health block | `oauth.by_integration` per integration |

---

## Not changed (per constraints)

- No integration flags enabled
- No Render secrets added
- No production or staging configuration modified
- Phase A not started
- `ZOHO_REFRESH_TOKEN` not removed (deprecated fallback retained)
- No OAuth tokens generated

---

## Migration notes

Deploy is backward compatible: environments with only `ZOHO_REFRESH_TOKEN` continue to work (CRM without warning; other integrations with deprecation warnings). Add per-integration secrets at each phase gate.
