# Zoho OAuth Migration Plan (Stage O5)

**Programme:** ZOHO OAUTH ARCHITECTURE VALIDATION  
**Date:** 2026-07-10  
**Prerequisite:** Approval of Option B in `ZOHO_OAUTH_RECOMMENDATION.md`  
**Status:** **PLAN ONLY** — not implemented

---

## 1. Objective

Migrate from a single global refresh token to **per-Zoho-app refresh tokens** while:

- Preserving backward compatibility during transition
- Minimising staging/production disruption
- Keeping all integration flags default-disabled until phase gates
- Not changing SoR boundaries, webhook model, or kill switch behaviour

---

## 2. Scope of change

### In scope

| Area | Change |
|------|--------|
| `config.py` | Per-integration refresh token accessors with fallback |
| `oauth.py` | Parameterise manager by integration / app key |
| `client.py` | Pass `integration` to OAuth manager (already has `integration` param) |
| `operational_health.py` | Per-app OAuth health in snapshot |
| `config.py` `credentials_configured` | Per-integration or aggregate reporting |
| Tests | OAuth routing, fallback, skip behaviour |
| Env example + audit docs | Per-app refresh token vars |

### Out of scope

- Multiple OAuth clients (Option C)
- OAuth callback route implementation
- Feature flag defaults
- Scheduler cron wiring
- Production deployment
- Sign OAuth (not required)

---

## 3. Environment variable design

### 3.1 New variables (Render secrets, staging first)

| Variable | Zoho app | Required when |
|----------|----------|---------------|
| `ZOHO_CRM_REFRESH_TOKEN` | CRM | `ZOHO_CRM_SYNC_ENABLED=true` |
| `ZOHO_ANALYTICS_REFRESH_TOKEN` | Analytics | `ZOHO_ANALYTICS_SYNC_ENABLED=true` |
| `ZOHO_BOOKS_REFRESH_TOKEN` | Books | `ZOHO_BOOKS_SYNC_ENABLED=true` |
| `ZOHO_CAMPAIGNS_REFRESH_TOKEN` | Campaigns | `ZOHO_CAMPAIGNS_SYNC_ENABLED=true` |
| `ZOHO_WORKDRIVE_REFRESH_TOKEN` | WorkDrive | `ZOHO_WORKDRIVE_SYNC_ENABLED=true` |

### 3.2 Unchanged

| Variable | Notes |
|----------|-------|
| `ZOHO_CLIENT_ID` | Shared Self Client |
| `ZOHO_CLIENT_SECRET` | Shared Self Client |
| `ZOHO_REFRESH_TOKEN` | **Deprecated fallback** — see §3.3 |
| `ZOHO_ACCOUNTS_URL` | EU default |
| `ZOHO_API_BASE` | EU default |

### 3.3 Backward compatibility

During migration window:

```
resolve_refresh_token(integration):
    1. ZOHO_{INTEGRATION}_REFRESH_TOKEN if set
    2. Else ZOHO_REFRESH_TOKEN (legacy fallback)
    3. Else empty → no_credentials
```

**Deprecation:** After all environments use per-app tokens, log warning when legacy `ZOHO_REFRESH_TOKEN` is used for non-CRM integrations. Remove fallback in a later release once governance confirms.

---

## 4. Code changes (estimated)

| File | Change | Effort |
|------|--------|--------|
| `config.py` | `zoho_refresh_token_for(integration: str)`, `zoho_oauth_configured_for(integration)` | XS |
| `oauth.py` | `get_access_token(integration)`, per-integration `TOKEN_DOC_ID`, refresh resolver | S |
| `client.py` | Pass `integration` to `get_access_token(integration)` | XS |
| `service.py` | Use per-integration credential check instead of global trio | S |
| `operational_health.py` | OAuth subsection per app | S |
| `integration_status_snapshot()` | `oauth_by_integration` map | XS |
| `test_zoho_integration.py` | Per-app token routing tests | S |
| `test_zoho_operational_health.py` | Multi-token health tests | S |

**Total engineering estimate:** 2–4 days including review and staging validation.

---

## 5. Mongo cache migration

### Current

```
{ token_id: "zoho_oauth_access_token", environment: "staging", access_token, expires_at }
```

### Target

```
{ token_id: "zoho_oauth_access_token_crm", environment: "staging", ... }
{ token_id: "zoho_oauth_access_token_analytics", environment: "staging", ... }
...
```

**Migration:** No data migration required — old single-token cache documents expire naturally or can be deleted on deploy. Unique index `(token_id, environment)` already supports multiple documents.

---

## 6. Deployment impact

| Environment | Impact |
|-------------|--------|
| **Staging** | Add per-app refresh secrets when each phase starts; no change while flags off |
| **Production** | No change until production Zoho pilot approved |
| **Render blueprints** | No flag changes; secrets added via dashboard only |
| **Rolling deploy** | Backward compatible if only `ZOHO_REFRESH_TOKEN` present |

**Zero-downtime:** Yes — fallback preserves current behaviour until per-app secrets added.

---

## 7. Migration steps

### Step 0 — Governance (before code)

- [ ] Approve Option B (`ZOHO_OAUTH_RECOMMENDATION.md`)
- [ ] Execute sandbox tests T1–T5 (`ZOHO_OAUTH_SANDBOX_VALIDATION.md`)
- [ ] Update `ZOHO_SANDBOX_READINESS_REPORT.md` §3.2 (remove single multi-app token guidance)

### Step 1 — Implementation (develop)

- [x] Implement per-integration refresh token resolution + OAuth manager parameterisation
- [x] Extend operational health and admin `/status`
- [x] Add regression tests
- [x] Update `zoho_integration.env.example`
- [x] No flags enabled; no Render secret changes in commit

### Step 2 — Staging code deploy

- [ ] Merge to `develop`; verify staging converges (flags still off)
- [ ] Confirm legacy `ZOHO_REFRESH_TOKEN`-only behaviour unchanged if no new vars set

### Step 3 — Phase A (when approved)

- [ ] Add `ZOHO_CLIENT_ID`, `ZOHO_CLIENT_SECRET` to staging secrets
- [ ] Optionally add `ZOHO_CRM_REFRESH_TOKEN` with CRM-only scopes if testing refresh — **not required** for admin shell alone
- [ ] Enable `ZOHO_INTEGRATION_ENABLED=true` only

### Step 4 — Per-phase token minting

| Phase | Add Render secret | Scopes |
|-------|-------------------|--------|
| B | `ZOHO_ANALYTICS_REFRESH_TOKEN` | `ZohoAnalytics.data.create` |
| C | `ZOHO_CRM_REFRESH_TOKEN` | `ZohoCRM.modules.leads.CREATE,UPDATE` |
| Campaigns | `ZOHO_CAMPAIGNS_REFRESH_TOKEN` | `ZohoCampaigns.contact.CREATE-UPDATE` |
| Books | `ZOHO_BOOKS_REFRESH_TOKEN` | `ZohoBooks.accountants.CREATE` |
| WorkDrive | `ZOHO_WORKDRIVE_REFRESH_TOKEN` | `WorkDrive.files.CREATE` |

Mint each token via **separate** Self Client Generate Code invocation (one Zoho app per code).

### Step 5 — Deprecation

- [ ] After all active integrations use per-app tokens, document removal date for `ZOHO_REFRESH_TOKEN` fallback
- [ ] Remove fallback in a future controlled release (optional)

---

## 8. Regression risk

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Wrong token used for adapter | Medium | Unit tests per integration; explicit `integration` param in client |
| Legacy env breaks on deploy | Low | Fallback to `ZOHO_REFRESH_TOKEN` |
| Health false-positive `token_valid` | Medium | Per-app API probe optional in Phase B+ validation |
| Secret sprawl in Render | Medium | Document rotation runbook per app |
| Operator adds multi-app scope to one token | High (process) | Sandbox T1 + updated readiness docs |

**Overall regression risk:** **Low–Medium** with fallback and phased secret addition.

---

## 9. Rollback

| Scenario | Rollback |
|----------|----------|
| New code deployed, issues found | Revert commit; single-token behaviour restored |
| Per-app token misconfigured | Remove per-app secret; rely on legacy `ZOHO_REFRESH_TOKEN` during fallback window |
| Integration misbehaviour | Disable per-integration flag; kill switch if needed |

No Mongo schema rollback required.

---

## 10. Success criteria (post-migration)

- [ ] Each enabled integration uses its own refresh token
- [ ] CRM API success does not depend on Books token (and vice versa)
- [ ] Admin `/status` shows per-integration OAuth configuration
- [ ] Sandbox T5 (CRM-only) and per-app probes pass
- [ ] No production changes until explicit production pilot approval
- [ ] All Zoho flags remain off until respective phase gates

---

## 11. Approval checklist

| Approver | Decision | Date |
|----------|----------|------|
| Engineering | Option B implementation authorised | |
| Ops / Render | Per-app secret naming convention accepted | |
| Governance | Phased token minting aligned to pilot plan | |

**Implementation blocked until signed.**
