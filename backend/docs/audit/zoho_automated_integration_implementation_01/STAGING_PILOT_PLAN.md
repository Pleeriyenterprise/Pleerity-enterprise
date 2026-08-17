# Zoho Integration — Staging Pilot Plan

**Programme:** ZOHO AUTOMATED INTEGRATION IMPLEMENTATION  
**Environment:** Staging only (`pleerity-api-staging`, sandbox Zoho org)  
**Date:** 2026-07-09  
**Prerequisite:** Commit deployed to `develop`; all flags **disabled** on deploy

---

## Deployment posture

| Control | Staging value |
|---------|---------------|
| `ZOHO_INTEGRATION_ENABLED` | `false` (until Phase A gate) |
| `ZOHO_KILL_SWITCH` | `false` |
| All per-integration flags | `false` |
| `ZOHO_ENVIRONMENT` | `staging` |
| OAuth credentials | **Sandbox Zoho org only** — Render secrets, not in git |
| Scheduler cron | **Not wired** — manual job trigger via admin |
| Production | **No changes** |

Explicit disabled defaults are documented in `render.staging.yaml` and `docs/zoho_integration.env.example`.

---

## Pilot phases

### Phase 0 — Deploy with layer dormant (Week 1)

**Objective:** Code on staging; zero Zoho activity.

| Step | Action | Owner |
|------|--------|-------|
| 0.1 | Merge commit to `develop`; verify Render auto-deploy | Engineering |
| 0.2 | Confirm env flags all `false` in Render dashboard | Ops |
| 0.3 | `GET /api/admin/integrations/zoho/status` → **404** (expected) | QA |
| 0.4 | Verify `/api/health` and existing staging smoke pass | QA |
| 0.5 | Confirm no `zoho_sync_runs` with status `running` | Ops |

**Exit:** Staging healthy; Zoho routes hidden; no sync activity.

---

### Phase A — Enable integration shell (Week 2)

**Objective:** Expose admin API; still no outbound sync.

| Step | Action |
|------|--------|
| A.1 | Create **sandbox** Zoho OAuth app (EU region) |
| A.2 | Store in Render **staging secrets only**: `ZOHO_CLIENT_ID`, `ZOHO_CLIENT_SECRET`, `ZOHO_REFRESH_TOKEN` |
| A.3 | Set `ZOHO_INTEGRATION_ENABLED=true` only |
| A.4 | Keep `ZOHO_ANALYTICS_SYNC_ENABLED=false`, `ZOHO_CRM_SYNC_ENABLED=false` |
| A.5 | Redeploy staging |
| A.6 | `GET /api/admin/integrations/zoho/status` → 200, all integrations `false` |

**Exit:** Admin visibility works; credentials configured; no sync jobs run.

---

### Phase B — Analytics pilot (Week 3)

**Objective:** First live integration — read-only aggregate export.

| Step | Action |
|------|--------|
| B.1 | Create Zoho Analytics workspace (sandbox); note `ZOHO_ANALYTICS_WORKSPACE_ID` |
| B.2 | Set `ZOHO_ANALYTICS_SYNC_ENABLED=true` |
| B.3 | Manual job: `POST /api/admin/jobs/run` → `zoho_analytics_export` |
| B.4 | Verify `zoho_sync_runs` record: status `success` or `skipped` (if workspace pending) |
| B.5 | Verify export payload has **no row-level PII** (aggregate counts only) |
| B.6 | Verify `audit_logs` contains `ZOHO_SYNC` entry |
| B.7 | Test kill switch: `ZOHO_KILL_SWITCH=true` → sync skipped → reset |

**Success criteria:**

- [ ] Aggregated metrics in export match staging Mongo counts (± timing)
- [ ] No email/phone in export payload
- [ ] Kill switch stops export within one deploy cycle
- [ ] No write path from Zoho to Pleerity

**Rollback:** Set `ZOHO_ANALYTICS_SYNC_ENABLED=false`; redeploy.

---

### Phase C — CRM one-way pilot (Week 4)

**Objective:** Pleerity → Zoho lead replica only.

| Prerequisite | Detail |
|--------------|--------|
| CRM custom fields | Create `Pleerity_Lead_ID`, `Pleerity_Client_ID`, etc. in sandbox CRM |
| Written approval | Sales/commercial sign-off per Stage ZA |

| Step | Action |
|------|--------|
| C.1 | Set `ZOHO_CRM_SYNC_ENABLED=true` |
| C.2 | Create test lead via staging public form or admin |
| C.3 | Manual job: `POST /api/admin/integrations/zoho/process-queue` or `zoho_sync_queue` job |
| C.4 | Verify Zoho sandbox Lead has matching `Pleerity_Lead_ID` |
| C.5 | Update lead stage in Pleerity admin → verify queue → Zoho updated |
| C.6 | Convert lead → verify `Pleerity_Client_ID` in Zoho |
| C.7 | POST test payload to `/api/internal/integrations/zoho/webhooks/crm` → must reject |

**Success criteria:**

- [ ] One-way sync only — Zoho never creates Pleerity leads
- [ ] `pleerity_lead_id` is external key in `zoho_external_keys`
- [ ] Inbound CRM webhook returns `crm_inbound_forbidden`
- [ ] Lead operations unaffected if Zoho API down (queue + dead-letter)

**Rollback:** Set `ZOHO_CRM_SYNC_ENABLED=false`; Pleerity CRM unchanged.

---

## Explicitly out of scope for this pilot

| Item | Reason |
|------|--------|
| Campaigns sync | Requires Kit gap confirmation |
| Books / WorkDrive sync | Programme B internal ops |
| Sign webhooks | After Analytics + CRM stable |
| Production deploy | Separate governance gate |
| Scheduler cron | Manual jobs only for pilot |
| Production Zoho credentials | Prohibited |

---

## Manual job reference

| Job ID | Purpose |
|--------|---------|
| `zoho_analytics_export` | Phase B |
| `zoho_sync_queue` | Phase C queue drain |
| Kill switch test | Any phase |

Trigger via existing admin job execution (`POST /api/admin/jobs/run`).

---

## Observability during pilot

| Check | Command / location |
|-------|-------------------|
| Flag snapshot | `GET /api/admin/integrations/zoho/status` |
| Sync history | `GET /api/admin/integrations/zoho/sync-runs` |
| Dead letters | Mongo `zoho_sync_dead_letter` |
| Audit trail | `audit_logs` where `metadata.action_type=ZOHO_SYNC` |

---

## Go / no-go for production

| Gate | Required |
|------|----------|
| Phase B Analytics complete | Yes |
| Phase C CRM complete | If sales demand confirmed |
| DPIA signed | Yes |
| P0 policies published | Yes |
| Kill switch tested | Yes |
| 48h staging soak with no authority violations | Yes |

**Production enablement is a separate programme** — not part of this staging pilot.

---

## Owners

| Role | Responsibility |
|------|----------------|
| Engineering lead | Deploy, flags, job execution |
| Ops | Render secrets, Mongo verification |
| QA | Exit criteria sign-off |
| DPO | PII review on Analytics export |
| Commercial | Phase C approval |

**Pilot status:** READY TO BEGIN AFTER DEPLOY (Phase 0)
