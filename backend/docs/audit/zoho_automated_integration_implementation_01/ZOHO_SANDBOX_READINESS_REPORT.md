# Zoho Sandbox Readiness Report

**Programme:** ZOHO AUTOMATED INTEGRATION IMPLEMENTATION  
**Document type:** Pre–Phase A readiness checklist (documentation only)  
**Date:** 2026-07-09  
**Staging API base:** `https://pleerity-enterprise.onrender.com/api`  
**Current staging commit:** `0edb7607` (Phase 0 evidence + integration layer)  
**Status:** **NOT READY FOR PHASE A** until items in §13 are complete and signed off

---

## Executive summary

Phase 0 is complete: the integration layer is deployed on staging with all flags **disabled**. Before anyone sets `ZOHO_INTEGRATION_ENABLED=true`, the Zoho **sandbox org**, **OAuth app**, **Render staging secrets**, and **integration-specific Zoho configuration** described below must exist.

This document lists exactly what must be created or configured. It does **not** authorise enabling flags, adding secrets, running sync jobs, or wiring scheduler cron.

**Authority unchanged:** Pleerity remains customer SoR; Stripe remains payment authority. Zoho is a downstream replica/export target only.

---

## 1. Scope and phasing

| Phase | What becomes active | Flags enabled (in order) |
|-------|---------------------|--------------------------|
| **Phase A** | Admin visibility + OAuth shell | `ZOHO_INTEGRATION_ENABLED=true` only |
| **Phase B** | Analytics read-only export | + `ZOHO_ANALYTICS_SYNC_ENABLED=true` |
| **Phase C** | CRM one-way replica | + `ZOHO_CRM_SYNC_ENABLED=true` |
| **Later** | Sign, Campaigns, Books, WorkDrive | Per-integration flags (see §8–11) |

**Out of scope for initial sandbox pilot:** production OAuth, scheduler cron wiring, production Zoho org credentials.

---

## 2. Zoho sandbox org prerequisites

Create or confirm a **dedicated Zoho One sandbox org** isolated from production Pleerity Ltd operations.

| Requirement | Detail |
|-------------|--------|
| Data centre | **EU** — must match backend defaults (`accounts.zoho.eu`, `www.zohoapis.eu`) |
| Org type | Sandbox / developer sandbox linked to Zoho One trial or partner sandbox |
| Isolation | No production customer PII copied into sandbox without DPIA approval |
| Products enabled | CRM, Analytics, Campaigns (if testing), Sign, Books, WorkDrive — only those needed for planned pilot phases |
| Admin access | At least one Zoho sandbox admin for OAuth app creation, custom fields, webhooks, workspace setup |
| Pleerity staging admin | At least one Pleerity staging admin user (for `GET /api/admin/integrations/zoho/status`) |

**Reference:** `STAGING_PILOT_PLAN.md`, `ZOHO_SECURITY_AND_TOKEN_MANAGEMENT.md`

---

## 3. OAuth app setup

The backend uses a **server-side refresh-token flow only**. Runtime token refresh is handled by `ZohoOAuthManager` (`services/integrations/zoho/oauth.py`); there is **no Pleerity OAuth callback route** in the codebase.

### 3.1 Create the OAuth client

| Step | Action |
|------|--------|
| 1 | Log in to [Zoho API Console (EU)](https://api-console.zoho.eu/) with the sandbox org admin |
| 2 | Create a **Server-based Application** (confidential client) |
| 3 | Name suggestion: `Pleerity Enterprise Staging Integration` |
| 4 | Associate with the **sandbox org only** |
| 5 | Record **Client ID** and **Client Secret** — store in Render staging secrets only (§4) |

### 3.2 Required OAuth scopes (per integration — Option B)

Under **Option B** (implemented), each Zoho business application requires its **own refresh token** minted with **only** the scopes needed for that integration. Do **not** attempt to authorise CRM, Analytics, Books, Campaigns, and WorkDrive from a single refresh token.

| Integration | Refresh token env | Minimum scopes |
|-------------|-------------------|----------------|
| Analytics (Phase B) | `ZOHO_ANALYTICS_REFRESH_TOKEN` | `ZohoAnalytics.data.create` |
| CRM (Phase C) | `ZOHO_CRM_REFRESH_TOKEN` | `ZohoCRM.modules.leads.CREATE`, `ZohoCRM.modules.leads.UPDATE` |
| Campaigns | `ZOHO_CAMPAIGNS_REFRESH_TOKEN` | `ZohoCampaigns.contact.CREATE-UPDATE` |
| Books | `ZOHO_BOOKS_REFRESH_TOKEN` | `ZohoBooks.accountants.CREATE` |
| WorkDrive | `ZOHO_WORKDRIVE_REFRESH_TOKEN` | `WorkDrive.files.CREATE` |
| Sign | *(none)* | Webhook-only — no OAuth refresh token |

**Phase A minimum:** Client ID + secret only; per-integration refresh tokens optional until API calls are needed.

**Governance note:** Prefer module-scoped CRM scopes over `ZohoCRM.modules.ALL`. Do not request Desk, Mail, or unrelated Zoho scopes.

**Reference:** `OAUTH_CREDENTIAL_REGISTRY.md`, `ZOHO_OAUTH_ARCHITECTURE.md`

### 3.3 Redirect URIs

Redirect URIs are required **only for the one-time refresh-token authorisation** (not for ongoing runtime).

| URI | Purpose |
|-----|---------|
| `https://www.zoho.eu/oauthredirect` | Zoho default — acceptable for Self Client / server app token generation |
| `http://localhost:8080/oauth/callback` | Optional — local one-time token generation by engineering |

**Do not** expose a public Pleerity OAuth callback unless a future authorised-code flow is explicitly designed. Current implementation uses per-integration refresh tokens in environment; no callback handler exists.

### 3.4 Generate refresh tokens (one-time, out of band, per integration)

| Step | Action |
|------|--------|
| 1 | In Zoho API Console, use **Generate Code** / Self Client flow with scopes for **one** integration only |
| 2 | Exchange authorisation code for tokens via `POST https://accounts.zoho.eu/oauth/v2/token` |
| 3 | Store the **refresh token** in the matching Render staging secret (e.g. `ZOHO_CRM_REFRESH_TOKEN`) |
| 4 | Repeat for each integration at its phase gate |
| 5 | Verify access token refresh succeeds **before** enabling the integration flag |

**Legacy migration:** `ZOHO_REFRESH_TOKEN` remains supported as a deprecated fallback during migration. See `OAUTH_DEPRECATION_POLICY.md`. Prefer per-integration tokens.

**Token storage:** Refresh tokens in Render env (not MongoDB). Access tokens cached in MongoDB collection `zoho_oauth_tokens` per integration per `ZOHO_ENVIRONMENT` (e.g. `zoho_oauth_access_token_crm`).

---

## 4. Render staging secrets and env (backend)

### 4.1 Secrets — set in Render dashboard only (never commit)

| Variable | Phase needed | Purpose |
|----------|--------------|---------|
| `ZOHO_CLIENT_ID` | **Phase A** | Shared OAuth app client ID |
| `ZOHO_CLIENT_SECRET` | **Phase A** | Shared OAuth app client secret |
| `ZOHO_ANALYTICS_REFRESH_TOKEN` | Phase B | Analytics refresh token |
| `ZOHO_CRM_REFRESH_TOKEN` | Phase C | CRM refresh token |
| `ZOHO_CAMPAIGNS_REFRESH_TOKEN` | Campaigns pilot | Campaigns refresh token |
| `ZOHO_BOOKS_REFRESH_TOKEN` | Books pilot | Books refresh token |
| `ZOHO_WORKDRIVE_REFRESH_TOKEN` | WorkDrive pilot | WorkDrive refresh token |
| `ZOHO_REFRESH_TOKEN` | **Deprecated** | Legacy migration fallback only |
| `ZOHO_ANALYTICS_WORKSPACE_ID` | Phase B | Target Analytics workspace |
| `ZOHO_ORG_ID` | Books pilot | Zoho Books organisation ID |
| `ZOHO_WORKDRIVE_INTERNAL_FOLDER_ID` | WorkDrive pilot | Target internal archive folder |
| `ZOHO_SIGN_WEBHOOK_SECRET` | Sign webhook pilot | HMAC verification (`X-Zoho-Signature`) |
| `ZOHO_CAMPAIGNS_WEBHOOK_SECRET` | Campaigns webhook pilot | HMAC verification |
| `ZOHO_CRM_WEBHOOK_SECRET` | CRM webhook test | HMAC verification (inbound always rejected) |
| `ZOHO_BOOKS_WEBHOOK_SECRET` | Books webhook registration | HMAC verification (inbound always rejected) |
| `ZOHO_WEBHOOK_SECRET` | Optional fallback | Used if per-integration secret unset |

**Source:** `docs/zoho_integration.env.example`, `services/integrations/zoho/config.py`

### 4.2 Non-secret env — already declared in `render.staging.yaml`

These must remain **`false`** until the corresponding pilot gate:

| Variable | Current staging value | Notes |
|----------|----------------------|-------|
| `ZOHO_ENVIRONMENT` | `staging` | Drives token namespace |
| `ZOHO_INTEGRATION_ENABLED` | `false` | Master gate — Phase A only |
| `ZOHO_KILL_SWITCH` | `false` | Emergency stop |
| `ZOHO_ANALYTICS_SYNC_ENABLED` | `false` | Phase B |
| `ZOHO_CRM_SYNC_ENABLED` | `false` | Phase C |
| `ZOHO_CAMPAIGNS_SYNC_ENABLED` | `false` | Requires Kit gap flag |
| `ZOHO_CAMPAIGNS_KIT_GAP_CONFIRMED` | `false` | **Mandatory** for Campaigns sync |
| `ZOHO_SIGN_SYNC_ENABLED` | `false` | Sign webhook processing |
| `ZOHO_BOOKS_SYNC_ENABLED` | `false` | Programme B / later |
| `ZOHO_WORKDRIVE_SYNC_ENABLED` | `false` | Programme B / later |
| `ZOHO_API_BASE` | default `https://www.zohoapis.eu` | Override only if org region differs |
| `ZOHO_ACCOUNTS_URL` | default `https://accounts.zoho.eu` | Override only if org region differs |
| `ZOHO_CRM_MODULE` | default `Leads` | CRM module name |

---

## 5. Zoho CRM custom fields (Phase C prerequisite)

Create custom fields on the **Leads** module in sandbox CRM before enabling `ZOHO_CRM_SYNC_ENABLED`.

**Source:** `services/integrations/zoho/registry.py` (`CRM_FIELD_MAP`)

| Zoho field (API name) | Type | Required | Maps from Pleerity | Notes |
|-----------------------|------|----------|-------------------|-------|
| `Pleerity_Lead_ID` | Single Line | **Yes** | `lead_id` | **External key** — upsert identity |
| `Pleerity_Client_ID` | Single Line | Yes | `client_id` | Set post-conversion |
| `Pleerity_Status` | Single Line | Yes | `status` | Read replica |
| `Pleerity_Service_Interest` | Single Line | Recommended | `service_interest` | |
| `Pleerity_Created_At` | DateTime | Recommended | `created_at` | |
| `Pleerity_Updated_At` | DateTime | Recommended | `updated_at` | |
| `Lead_Score` | Number | Recommended | `lead_score` | Use CRM custom field if not standard |
| `Email` | Email | Standard | `email` | |
| `First_Name` | Text | Standard | `first_name` | |
| `Last_Name` | Text | Standard | `last_name` | |
| `Phone` | Phone | Standard | `phone` | |
| `Lead_Status` | Picklist | Standard | `stage` | Align picklist values with Pleerity stages |
| `Lead_Source` | Picklist | Standard | `source_platform` | |

**Inbound authority:** Zoho must **never** write back `lead_id`, `email`, `stage`, `status`, `client_id`, `lead_score`, `converted_at`. Inbound CRM webhooks are always rejected (`crm_inbound_forbidden`).

**Layout:** Add Pleerity fields to a dedicated section on the Lead layout for sandbox QA visibility.

---

## 6. Zoho Analytics workspace requirements (Phase B prerequisite)

| Requirement | Detail |
|-------------|--------|
| Workspace | Create sandbox Analytics workspace; record **Workspace ID** → `ZOHO_ANALYTICS_WORKSPACE_ID` |
| Data model | Table(s) accepting **aggregated daily** import via API append |
| Export fields | Must accept payload shaped by `build_analytics_export()` — no row-level PII |

**Expected aggregate columns** (`ANALYTICS_EXPORT_METRICS` + builder output):

| Field | Description |
|-------|-------------|
| `period_start` | ISO8601 UTC start |
| `period_end` | ISO8601 UTC end |
| `leads_created_count` | Count in period |
| `leads_converted_count` | Count in period |
| `total_leads_count` | Snapshot total |
| `conversion_rate_pct` | Derived percentage |
| `active_subscriptions_count` | From `client_billing` |
| `mrr_summary_gbp` | Aggregated MRR — no per-customer rows |
| `support_tickets_open_count` | Aggregate |
| `support_tickets_closed_count` | Aggregate in period |
| `export_type` | Constant `aggregated_daily` |

**API behaviour:** `POST /analytics/v2/workspaces/{workspace_id}/data` with `import_type: append`. If workspace ID is unset, export is built locally and sync status is `skipped` — not a successful live pilot.

**DPO review:** Confirm export contains **no email, phone, name, or address** before Phase B go-live.

---

## 7. Webhook URLs and signing / HMAC requirements

Webhooks are **flag-gated** (`ZOHO_INTEGRATION_ENABLED=false` → routes return **404**). Routes use prefix `/api/internal/integrations/zoho/webhooks/`.

**Staging base URL:** `https://pleerity-enterprise.onrender.com`

| Integration | Pleerity endpoint | Zoho sandbox webhook URL to register |
|-------------|-------------------|--------------------------------------|
| Sign | `POST /api/internal/integrations/zoho/webhooks/sign` | `https://pleerity-enterprise.onrender.com/api/internal/integrations/zoho/webhooks/sign` |
| Campaigns | `POST /api/internal/integrations/zoho/webhooks/campaigns` | `https://pleerity-enterprise.onrender.com/api/internal/integrations/zoho/webhooks/campaigns` |
| CRM | `POST /api/internal/integrations/zoho/webhooks/crm` | `https://pleerity-enterprise.onrender.com/api/internal/integrations/zoho/webhooks/crm` |
| Books | `POST /api/internal/integrations/zoho/webhooks/books` | `https://pleerity-enterprise.onrender.com/api/internal/integrations/zoho/webhooks/books` |

### 7.1 HMAC verification

| Item | Specification |
|------|---------------|
| Algorithm | HMAC-SHA256 over **raw request body** |
| Header | `X-Zoho-Signature` |
| Secret resolution | `ZOHO_{INTEGRATION}_WEBHOOK_SECRET` → fallback `ZOHO_WEBHOOK_SECRET` (Sign, Campaigns, CRM, **Books**) |
| Signature format | Hex digest; implementation strips optional `sha256=` prefix |
| Missing secret | **401** `webhook_secret_not_configured` |
| Invalid signature | **401** `invalid_signature` |

**Source:** `services/integrations/zoho/webhooks/verifier.py`, `ZOHO_WEBHOOK_POLICY.md`

### 7.2 Allowed inbound actions

| Webhook | When integration flag on | Pleerity action |
|---------|--------------------------|-----------------|
| Sign `document.completed` | `ZOHO_SIGN_SYNC_ENABLED=true` | Audit metadata via Sign adapter |
| Campaigns unsubscribe | `ZOHO_CAMPAIGNS_SYNC_ENABLED=true` **and** `ZOHO_CAMPAIGNS_KIT_GAP_CONFIRMED=true` | Update `newsletter_subscribers`, `leads.followup_status` |
| CRM any | Always rejected | `crm_inbound_forbidden` |
| Books any | Always rejected | `books_inbound_forbidden` |

**Network:** Ensure Zoho sandbox can reach the staging public URL. No IP allowlist is implemented in code.

---

## 8. Books export setup (Programme B / later pilot)

| Requirement | Detail |
|-------------|--------|
| Purpose | Internal finance summary export — **not** customer billing SoR |
| Org ID | Record Zoho Books org ID → `ZOHO_ORG_ID` |
| Chart of accounts | Map journal line types to Pleerity Ltd recognition accounts (finance owner) |
| Export content | `build_books_export()` — `subscription_revenue_summary` line from aggregated Stripe/MRR data |
| Line types (registry) | `stripe_payout`, `stripe_fee`, `subscription_revenue_summary`, `refund_summary` |
| API | `POST /books/v3/journals?organization_id={ZOHO_ORG_ID}` |
| Inbound | **Forbidden** — Books webhook always rejected |
| Flag | `ZOHO_BOOKS_SYNC_ENABLED=true` (requires master + Books flag) |

**Authority:** Stripe + `client_billing` remain payment SoR. Books is read-only downstream for Pleerity Ltd reporting.

---

## 9. Campaigns prerequisites (conditional — not in initial pilot)

Campaigns sync is **blocked** unless **both** flags are true:

- `ZOHO_CAMPAIGNS_SYNC_ENABLED=true`
- `ZOHO_CAMPAIGNS_KIT_GAP_CONFIRMED=true`

| Requirement | Detail |
|-------------|--------|
| Business gate | Written confirmation that Zoho Campaigns + Marketing Automation Kit gap is understood and accepted |
| Zoho list | Mailing list / topic configured for sandbox bulk subscriber import |
| Audience source | Pleerity `newsletter_subscribers` where `marketing_consent != false` |
| Suppression source | Opt-outs from `newsletter_subscribers` and `leads` with `followup_status: opted_out` |
| Export fields | `email`, `marketing_consent`, `subscribed_at`, `source` (email only sent in bulk API) |
| Webhook | Unsubscribe events → §7 Campaigns endpoint |
| DPIA | Required before production audience export |

**Manual jobs (when enabled):** `zoho_campaigns_export` — not cron-wired in pilot.

---

## 10. Sign webhook setup (after Analytics + CRM stable)

| Requirement | Detail |
|-------------|--------|
| Flag | `ZOHO_SIGN_SYNC_ENABLED=true` |
| Webhook secret | `ZOHO_SIGN_WEBHOOK_SECRET` in Render |
| Zoho Sign config | Register completion webhook → §7 Sign URL |
| Payload fields | `request_id`, `document_name`, `category` / `document_category`, `completed_at`, `document_url`, `business_record_id` |

**Allowed document categories:** `vendor`, `partnership`, `employment`, `nda`, `b2b_agreement`, `internal`

**Forbidden categories:** `subscription_clickwrap`, `compliance_evidence`, `customer_agreement`, `requirement_evidence`

Sign completions create **audit metadata only** — not customer compliance evidence storage.

---

## 11. WorkDrive folder / archive requirements (Programme B / later)

| Requirement | Detail |
|-------------|--------|
| Folder | Create sandbox folder e.g. `Pleerity-Internal-Archive-Staging` |
| Folder ID | → `ZOHO_WORKDRIVE_INTERNAL_FOLDER_ID` |
| Flag | `ZOHO_WORKDRIVE_SYNC_ENABLED=true` |
| Operation | `archive_document` uploads via WorkDrive API |

**Allowed categories:** `internal`, `vendor`, `hr`, `governance`, `b2b_signed`, `finance`

**Forbidden categories:** `compliance_evidence`, `customer_vault`, `requirement_evidence`, `property_evidence`

Customer compliance documents must **never** be archived to WorkDrive via this integration.

---

## 12. Test users and test data needed

### 12.1 Pleerity staging

| Asset | Purpose |
|-------|---------|
| Staging admin user | Authenticate to `GET /api/admin/integrations/zoho/status`, manual sync, job trigger |
| 3–5 test leads | CRM one-way pilot — varied stages, one convertible to client |
| 2+ `newsletter_subscribers` | Campaigns audience/suppression (if tested) — include one opted-out |
| Active + inactive billing rows | Analytics/Books aggregate validation (staging Mongo) |
| Support tickets (open + closed) | Analytics aggregate counts |

**Lead test pattern (Phase C):**

1. Create lead via staging public form or admin → note `lead_id`
2. Update stage in Pleerity admin
3. Convert lead → verify `client_id` populated
4. Confirm queue entry in `zoho_sync_queue` after CRM flag on
5. Confirm mapping in `zoho_external_keys` (`integration: crm`, Pleerity `lead_id` → Zoho record ID)

### 12.2 Zoho sandbox

| Asset | Purpose |
|-------|---------|
| Sandbox CRM user | Visual verification of Lead replica |
| Sandbox admin | OAuth, fields, webhooks, Analytics workspace |
| Test Sign request (optional) | B2B template in allowed category |
| Books org (optional) | Journal posting verification |

**Do not** copy production customer records into sandbox without anonymisation and DPIA approval.

---

## 13. Validation checklist before enabling the first flag

Complete **all Phase A items** before setting `ZOHO_INTEGRATION_ENABLED=true`. Do not enable per-integration flags until their phase prerequisites are done.

### 13.1 Governance (required)

- [ ] Stage Z / Stage ZA adoption blueprint reviewed by engineering lead
- [ ] P0 governance policies published (MDM, SoR, sync, conflict, security)
- [ ] DPIA signed for platform → Zoho PII export (required before production; recommended before sandbox CRM/Campaigns)
- [ ] Written commercial sign-off for CRM pilot (Phase C) — if proceeding beyond Analytics
- [ ] Legal/marketing copy corrected — no false “Zoho integrated” claims in production-facing materials

### 13.2 Zoho sandbox org (required)

- [ ] Dedicated sandbox org provisioned (EU data centre)
- [ ] Sandbox isolated from production Zoho One org
- [ ] CRM Leads module accessible
- [ ] Analytics workspace created (before Phase B)

### 13.3 OAuth (Phase A gate)

- [ ] Server-based OAuth app created in Zoho API Console (EU)
- [ ] Per-integration scopes selected at each phase gate (see §3.2)
- [ ] Per-integration refresh tokens generated and stored in Render staging secrets
- [ ] `ZOHO_CLIENT_ID`, `ZOHO_CLIENT_SECRET` set in Render **staging only**
- [ ] Per-integration refresh tokens set before enabling each integration flag
- [ ] Token refresh verified via admin status (`oauth.by_integration` shows `credentials_configured: true`)
- [ ] No OAuth credentials committed to git
- [ ] `ZOHO_REFRESH_TOKEN` not used as sole production credential (deprecated)

### 13.4 Render / staging posture (required)

- [ ] Staging deploy SHA current (`0edb7607` or later on `develop`)
- [ ] `GET /api/health` → healthy
- [ ] All `ZOHO_*` flags confirmed `false` in Render dashboard
- [ ] `ZOHO_ENVIRONMENT=staging`
- [ ] Production unchanged — production SHA still pinned to pre-integration release
- [ ] No scheduler cron entries for `zoho_*` jobs in `server.py`

### 13.5 Phase A enablement check (first flag only)

After §13.1–13.4 complete:

- [ ] Set `ZOHO_INTEGRATION_ENABLED=true` **only**
- [ ] Keep all per-integration flags `false`
- [ ] Redeploy staging
- [ ] `GET /api/admin/integrations/zoho/status` → **200**, `credentials_configured: true`, all integrations `false`
- [ ] Webhook URLs still require auth/signature — CRM test without signature → 401 (not open)
- [ ] **Do not** run `zoho_analytics_export`, `zoho_sync_queue`, or other sync jobs yet

### 13.6 Phase B additional checks (Analytics)

- [ ] `ZOHO_ANALYTICS_WORKSPACE_ID` set in Render
- [ ] Analytics table schema matches §6 aggregate fields
- [ ] DPO sign-off on aggregate export sample (no PII)
- [ ] Then enable `ZOHO_ANALYTICS_SYNC_ENABLED=true`
- [ ] Manual job only: `POST /api/admin/jobs/run` → `zoho_analytics_export`
- [ ] Verify `zoho_sync_runs` + `audit_logs` (`ZOHO_SYNC`)
- [ ] Kill switch test: `ZOHO_KILL_SWITCH=true` → sync skipped → reset

### 13.7 Phase C additional checks (CRM)

- [ ] All CRM custom fields from §5 created in sandbox
- [ ] Commercial written approval obtained
- [ ] Test leads prepared in staging Mongo (§12)
- [ ] Then enable `ZOHO_CRM_SYNC_ENABLED=true`
- [ ] Manual queue processing only
- [ ] Inbound CRM webhook test → `crm_inbound_forbidden`

---

## 14. Explicit prohibitions (until separately authorised)

| Action | Status |
|--------|--------|
| Enable `ZOHO_INTEGRATION_ENABLED` without §13 complete | **Prohibited** |
| Add Render secrets to production | **Prohibited** |
| Enable any per-integration flag during Phase A | **Prohibited** |
| Wire `zoho_*` jobs to `scheduler.add_job` | **Prohibited** in pilot |
| Run sync jobs before corresponding phase gate | **Prohibited** |
| Copy production PII to sandbox | **Prohibited** without DPIA |
| Two-way CRM sync | **Prohibited** by architecture |

---

## 15. Reference map

| Topic | Source in repo |
|-------|----------------|
| Env variables | `docs/zoho_integration.env.example`, `render.staging.yaml` |
| Field mappings | `services/integrations/zoho/registry.py`, `ZOHO_FIELD_MAPPING_REGISTRY.md` |
| Webhook policy | `ZOHO_WEBHOOK_POLICY.md`, `routes/integrations/zoho/webhooks.py` |
| Security / tokens | `ZOHO_SECURITY_AND_TOKEN_MANAGEMENT.md` |
| Staging pilot phases | `STAGING_PILOT_PLAN.md` |
| SoR boundaries | `SYSTEM_OF_RECORD_BOUNDARIES.md` |
| Phase 0 evidence | `PHASE_0_STAGING_VALIDATION_REPORT.md` |

---

## 16. Sign-off

| Role | Sandbox readiness confirmed | Date |
|------|----------------------------|------|
| Engineering lead | ☐ | |
| Ops (Render secrets) | ☐ | |
| Commercial (CRM demand) | ☐ | |
| DPO (PII export) | ☐ | |

**Next authorised step after sign-off:** Phase A — enable `ZOHO_INTEGRATION_ENABLED=true` only, with sandbox OAuth credentials in Render staging secrets. No sync jobs. No cron. No production changes.

---

*Document only. No code, flags, secrets, cron, or sync jobs were modified to produce this report.*
