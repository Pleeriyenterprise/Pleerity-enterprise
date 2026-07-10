# OAuth Regression Test Results

**Programme:** ZOHO OAUTH ARCHITECTURE IMPLEMENTATION — Option B  
**Date:** 2026-07-10  
**Environment:** Local development (no live Zoho credentials)

---

## Command

```bash
cd backend
python -m pytest tests/integrations/zoho/ -q --tb=short
```

---

## Result

| Metric | Value |
|--------|-------|
| **Total tests** | 37 |
| **Passed** | 37 |
| **Failed** | 0 |
| **Duration** | ~1.1s |

**Verdict:** PASS

---

## OAuth-specific test coverage

| Test | Area | Result |
|------|------|--------|
| `test_registry_contains_all_oauth_integrations` | Credential registry | PASS |
| `test_credential_resolver_prefers_per_integration_token` | Resolver priority | PASS |
| `test_credential_resolver_legacy_fallback` | Legacy fallback | PASS |
| `test_credential_resolver_no_credentials` | No credentials path | PASS |
| `test_legacy_warning_for_non_crm_integration` | Migration warnings | PASS |
| `test_no_legacy_warning_for_crm_migration` | Approved CRM migration | PASS |
| `test_zoho_oauth_configured_for_per_integration` | Config accessors | PASS |
| `test_integration_status_snapshot_oauth_by_integration` | Status endpoint data | PASS |
| `test_oauth_cache_isolation_per_integration` | Per-integration Mongo cache | PASS |
| `test_operational_snapshot_per_integration_oauth` | Operational health | PASS |
| `test_http_client_passes_integration_to_oauth_manager` | Client → OAuth routing | PASS |

---

## Existing suite regression

All pre-existing Zoho integration tests passed unchanged, including:

- Feature flag defaults
- Kill switch behaviour
- PII minimisation
- CRM authority boundaries
- Webhook HMAC verification (CRM, Books)
- Sync dead-letter on failure
- Operational health platform hooks
- Analytics export versioning

---

## Not tested (requires live credentials)

| Test | Reason |
|------|--------|
| Live Zoho OAuth refresh (T1–T5) | No Render OAuth secrets in validation environment |
| Staging deploy convergence | Out of scope for code implementation |

Live sandbox validation remains per `ZOHO_OAUTH_SANDBOX_VALIDATION.md` when credentials are available.

---

## Evidence file

Test run captured during implementation on 2026-07-10. Re-run before staging deploy:

```bash
python -m pytest tests/integrations/zoho/ -q
```
