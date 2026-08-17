# Phase A — Render Staging Configuration (P2)

**Programme:** ZOHO SANDBOX PILOT IMPLEMENTATION — PHASE A EXECUTION  
**Date:** 2026-07-10  
**Target:** Render staging web service (`pleerity-enterprise`)  
**Source of truth:** `services/integrations/zoho/config.py`, `credential_resolver.py`, `oauth_credential_registry.py`  
**Blueprint reference:** `render.staging.yaml` (flags only; secrets in dashboard)

---

## 1. Phase A activation sequence

| Step | Action |
|------|--------|
| 1 | Create Zoho sandbox OAuth Self Client (EU) |
| 2 | Store `ZOHO_CLIENT_ID` and `ZOHO_CLIENT_SECRET` in Render staging **secrets** |
| 3 | Set `ZOHO_INTEGRATION_ENABLED=true` in Render staging env |
| 4 | Redeploy staging |
| 5 | Validate via `GET /api/admin/integrations/zoho/status` |
| 6 | Run Phase A validation checklist (`PHASE_A_RUNTIME_VALIDATION.md`) |

Per-integration refresh tokens are **not required** for Phase A shell (no outbound API calls). Add at Phase B+ gates.

---

## 2. Environment variable matrix

### Required for Phase A

| Variable | Render type | Value | Consumed by |
|----------|-------------|-------|-------------|
| `ZOHO_INTEGRATION_ENABLED` | Env var | `true` | `config.py` — unlocks admin status + webhook surface |
| `ZOHO_ENVIRONMENT` | Env var | `staging` | `config.py` — OAuth cache namespace |
| `ZOHO_CLIENT_ID` | **Secret** | Sandbox Self Client ID | `credential_resolver.py` |
| `ZOHO_CLIENT_SECRET` | **Secret** | Sandbox Self Client secret | `credential_resolver.py` |
| `ZOHO_KILL_SWITCH` | Env var | `false` | `config.py` |

### Optional (defaults acceptable)

| Variable | Default | Purpose |
|----------|---------|---------|
| `ZOHO_API_BASE` | `https://www.zohoapis.eu` | Zoho API domain |
| `ZOHO_ACCOUNTS_URL` | `https://accounts.zoho.eu` | OAuth token endpoint |
| `ZOHO_CRM_MODULE` | `Leads` | CRM module name (Phase C) |

### Future phase (do not set for Phase A)

| Variable | Phase | Purpose |
|----------|-------|---------|
| `ZOHO_ANALYTICS_REFRESH_TOKEN` | B | Analytics OAuth |
| `ZOHO_CRM_REFRESH_TOKEN` | C | CRM OAuth |
| `ZOHO_CAMPAIGNS_REFRESH_TOKEN` | Campaigns pilot | Campaigns OAuth |
| `ZOHO_BOOKS_REFRESH_TOKEN` | Books pilot | Books OAuth |
| `ZOHO_WORKDRIVE_REFRESH_TOKEN` | WorkDrive pilot | WorkDrive OAuth |
| `ZOHO_ANALYTICS_WORKSPACE_ID` | B | Analytics target |
| `ZOHO_ORG_ID` | Books pilot | Books org |
| `ZOHO_WORKDRIVE_INTERNAL_FOLDER_ID` | WorkDrive pilot | Upload folder |
| `ZOHO_SIGN_WEBHOOK_SECRET` | Sign pilot | Webhook HMAC |
| `ZOHO_CAMPAIGNS_WEBHOOK_SECRET` | Campaigns pilot | Webhook HMAC |
| `ZOHO_CRM_WEBHOOK_SECRET` | CRM webhook test | Webhook HMAC |
| `ZOHO_BOOKS_WEBHOOK_SECRET` | Books webhook test | Webhook HMAC |
| `ZOHO_WEBHOOK_SECRET` | Optional fallback | Shared webhook HMAC fallback |

### Integration flags (Phase A — all remain `false`)

| Variable | Phase A value |
|----------|---------------|
| `ZOHO_ANALYTICS_SYNC_ENABLED` | `false` |
| `ZOHO_CRM_SYNC_ENABLED` | `false` |
| `ZOHO_CAMPAIGNS_SYNC_ENABLED` | `false` |
| `ZOHO_CAMPAIGNS_KIT_GAP_CONFIRMED` | `false` |
| `ZOHO_SIGN_SYNC_ENABLED` | `false` |
| `ZOHO_BOOKS_SYNC_ENABLED` | `false` |
| `ZOHO_WORKDRIVE_SYNC_ENABLED` | `false` |

### Deprecated (migration only — do not use as sole Phase A credential strategy)

| Variable | Status |
|----------|--------|
| `ZOHO_REFRESH_TOKEN` | Deprecated fallback — see `OAUTH_DEPRECATION_POLICY.md` |

---

## 3. `render.staging.yaml` alignment

Current blueprint (`render.staging.yaml` lines 86–107):

- Sets all Zoho flags to `false` ✓
- Sets `ZOHO_ENVIRONMENT=staging` ✓
- Documents OAuth secrets as dashboard-only ✓
- Does **not** commit secrets ✓

**Phase A change in Render dashboard only:** set `ZOHO_INTEGRATION_ENABLED=true` and add OAuth client secrets. Do not modify `render.production.yaml`.

---

## 4. Minimum Phase A Render configuration

```env
# Env vars (non-secret)
ZOHO_ENVIRONMENT=staging
ZOHO_INTEGRATION_ENABLED=true
ZOHO_KILL_SWITCH=false
ZOHO_ANALYTICS_SYNC_ENABLED=false
ZOHO_CRM_SYNC_ENABLED=false
ZOHO_CAMPAIGNS_SYNC_ENABLED=false
ZOHO_CAMPAIGNS_KIT_GAP_CONFIRMED=false
ZOHO_SIGN_SYNC_ENABLED=false
ZOHO_BOOKS_SYNC_ENABLED=false
ZOHO_WORKDRIVE_SYNC_ENABLED=false

# Secrets (Render dashboard)
ZOHO_CLIENT_ID=<sandbox-self-client-id>
ZOHO_CLIENT_SECRET=<sandbox-self-client-secret>
```

---

## 5. Post-deploy validation endpoints

| Endpoint | Auth | Expected Phase A |
|----------|------|------------------|
| `GET /api/health` | Public | `200` |
| `GET /api/admin/observability/health-summary` | Admin | `zoho_integration_health.overall_status: healthy` |
| `GET /api/admin/integrations/zoho/status` | Admin | `zoho_integration_enabled: true`, all integrations `false` |

---

## 6. Variables not consumed by code (documented elsewhere only)

| Variable | Note |
|----------|------|
| `ZOHO_INTEGRATION_LAYER_VERSION` | Python constant in `version.py` — not an env var |

---

## 7. Documentation cross-reference

| Document | Purpose |
|----------|---------|
| `docs/zoho_integration.env.example` | Full template |
| `ZOHO_OAUTH_ENVIRONMENT_VARIABLE_GUIDE.md` | Option B env reference |
| `OAUTH_CREDENTIAL_REGISTRY.md` | Per-integration registry |
| `ZOHO_SANDBOX_READINESS_REPORT.md` | Sandbox org prerequisites |
