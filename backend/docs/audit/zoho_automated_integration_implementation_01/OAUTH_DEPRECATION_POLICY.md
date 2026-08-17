# OAuth Deprecation Policy — `ZOHO_REFRESH_TOKEN`

**Programme:** ZOHO OAUTH ARCHITECTURE IMPLEMENTATION  
**Effective:** 2026-07-10  
**Status:** Active during migration window

---

## 1. Deprecated variable

| Variable | Replacement |
|----------|-------------|
| `ZOHO_REFRESH_TOKEN` | `ZOHO_CRM_REFRESH_TOKEN`, `ZOHO_ANALYTICS_REFRESH_TOKEN`, `ZOHO_BOOKS_REFRESH_TOKEN`, `ZOHO_CAMPAIGNS_REFRESH_TOKEN`, `ZOHO_WORKDRIVE_REFRESH_TOKEN` |

The legacy variable exists **only** to support backward-compatible migration. It must **not** become a permanent implementation detail.

---

## 2. Migration window

| Milestone | Target |
|-----------|--------|
| Code implementation | Complete (Option B on `develop`) |
| Staging validation | Before Phase B/C API pilots |
| Per-integration secrets in Render staging | Added at each phase gate (not in code commit) |
| Legacy fallback removal | **Before first production Zoho rollout** |
| Production cut-off | `ZOHO_REFRESH_TOKEN` must not be present in production Render secrets |

---

## 3. Warning behaviour

| Scenario | Behaviour |
|----------|-----------|
| Per-integration token set | No legacy warning |
| Legacy used for **CRM** only | No warning (approved migration scenario) |
| Legacy used for Analytics, Books, Campaigns, WorkDrive | **Runtime WARNING** logged once per integration per process |
| Legacy used after per-integration token also set | Per-integration token wins; no legacy path |

Log message format:

```
Zoho OAuth: integration '{name}' is using deprecated legacy ZOHO_REFRESH_TOKEN.
Set ZOHO_{INTEGRATION}_REFRESH_TOKEN before production Zoho rollout.
Legacy fallback will be removed.
```

---

## 4. Removal milestone

| Gate | Requirement |
|------|-------------|
| **Code removal** | After all active environments use per-integration tokens and governance signs off |
| **Documentation** | Update env example and sandbox readiness to remove legacy references |
| **Production cut-off** | Hard requirement — production deploy blocked if `ZOHO_REFRESH_TOKEN` is the only refresh source |

Estimated removal: immediately after staging sandbox validation (T1–T5) confirms per-integration tokens for all pilot integrations.

---

## 5. Rollback approach

If a per-integration token is misconfigured during migration:

1. Remove the incorrect `ZOHO_{INTEGRATION}_REFRESH_TOKEN` from Render
2. Temporarily rely on `ZOHO_REFRESH_TOKEN` **only for CRM** during the fallback window
3. Fix token in Zoho API Console and re-add per-integration secret
4. Call `ZohoOAuthManager.invalidate(integration)` or restart service to clear cache

**Do not** rely on legacy fallback for multi-integration production operation.

---

## 6. Governance sign-off required before removal

- [ ] All pilot integrations have dedicated refresh tokens in staging
- [ ] Operational health shows `refresh_token_source: per_integration` for active integrations
- [ ] No legacy warnings in staging logs for enabled integrations
- [ ] Production promotion checklist updated

---

## 7. Implementation reference

Resolver: `services/integrations/zoho/credential_resolver.py`  
Approved migration integrations: `crm` only
