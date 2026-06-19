# TWIN-API-WEBHOOK-INTEGRATION-AUDIT-01

**Authority:** TWIN-API-WEBHOOK-INTEGRATION-AUDIT-01  
**Date:** 2026-06-19  
**Scope:** Audit only — no implementation  
**Goal:** Safest automatic path for CVP to receive Twin discoveries  
**Constraint:** Terminate at `TwinProvider.ingest_async()` — no LeadService, CRM, auto-import, outreach, nurture, or production enablement

**Related:** `TWIN_API_INTEGRATION_AUDIT.md`, `TWIN_WORKSPACE_SETUP_PACKAGE.md`, Stage W `TwinProvider`

---

## Executive conclusion

Twin webhooks are **run-lifecycle signals only**. They do **not** carry prospect export JSON. CVP must **always fetch run output separately** via the Twin REST API after receiving `run.completed` or `run.failed`.

**Safest automatic integration model:** **Webhook-triggered API pull** (hybrid trigger + fetch).

```
Twin POST run.completed / run.failed
        ↓
CVP Twin Ingestion Connector (new — orchestration only)
  1. Verify HMAC signature
  2. Idempotency gate (twin run_id)
  3. GET /v1/agents/{agent_id}/runs/{run_id}/events (paginated)
  4. Extract + validate export envelope
  5. DiscoveryRunService.create_run(provider=twin)
  6. TwinProvider.ingest_async(payload, IngestContext)
  7. DiscoveryRunService transition COMPLETED | FAILED | PARTIAL
        ↓
discovery_prospects (needs_review) — existing governance unchanged
```

**Not recommended:** Treating webhook body as ingest payload (it contains no `records[]`).  
**Not recommended:** Polling-only without webhooks (works but higher latency and API load).  
**Required fallback:** Manual JSON export path (Stage X) remains operational.

---

## 1. Authentication (Twin API keys)

| Item | Detail |
|------|--------|
| Header | `x-api-key: <secret>` on every Twin REST call |
| Base URL | `https://build.twin.so` |
| Key issuance | Twin dashboard or `POST /api/public/v1/access-api-keys` |
| Key rotation | Create new key → deploy → revoke old via `DELETE .../access-api-keys/{key_id}` |
| Scope | Full Twin account — not scoped to single agent |

**CVP connector uses API key only for outbound calls** (event fetch). Webhook endpoint does **not** use Twin API key — it uses webhook signing secret.

**Pre-flight:** `GET /v1/me` on deploy to validate key.

---

## 2. Webhook support (`run.completed`, `run.failed`)

### Registration (Twin side)

```http
POST /v1/agents/{agent_id}/webhooks
Content-Type: application/json
x-api-key: <TWIN_API_KEY>

{
  "url": "https://<cvp-staging>/api/internal/discovery/twin/webhooks",
  "events": ["run.completed", "run.failed"]
}
```

Response includes `webhook_id` and **`signing_secret` (once)**.

### Subscribed events for CVP

| Event | CVP action |
|-------|------------|
| `run.completed` | Fetch events → extract export → ingest if `outcome` is `success` or `partial` |
| `run.failed` | Record receipt; mark Discovery run FAILED; no ingest; alert ops |
| `run.started` | Optional — log only; do not ingest |
| `run.stopped` / `run.paused` | Ignore for ingest pipeline |

### Webhook payload (Twin → CVP)

```json
{
  "event": "run.completed",
  "timestamp": "2026-03-11T14:32:15Z",
  "data": {
    "run_id": "run_xyz789",
    "agent_id": "agent_abc123",
    "status": "completed",
    "outcome": "success",
    "finished_at": "2026-03-11T14:32:15Z"
  }
}
```

**No `records` array. No prospect fields.** Confirmed by [Twin REST API](https://docs.twin.so/rest-api) webhook documentation.

### Twin webhook retry policy

**Not documented** in Twin public docs. CVP must assume **at-least-once delivery** and implement idempotent webhook handling. Return `2xx` only after receipt is durably recorded.

---

## 3. Webhook signature verification

Twin delivers:

| Header | Value |
|--------|-------|
| `X-Cobb-Signature` | `sha256=<hex>` |
| `X-Cobb-Event` | e.g. `run.completed` |

**Algorithm:** `HMAC-SHA256(signing_secret, raw_request_body)` → prefix with `sha256=`

**CVP validation steps (in order):**

1. Read **raw body bytes** before JSON parse
2. Reject if `Content-Type` is not `application/json`
3. Load `TWIN_WEBHOOK_SIGNING_SECRET` for configured `agent_id` (or single-agent staging)
4. Compute expected signature; compare with `hmac.compare_digest` / `crypto.timingSafeEqual`
5. Verify `X-Cobb-Event` matches parsed `event` field
6. Verify `timestamp` within skew window (recommended ±300s)
7. Verify `data.agent_id` matches allowlisted agent(s)
8. Parse JSON only after signature passes

**On failure:** Return `401` — do not process, do not call Twin API, do not ingest.

---

## 4. Retrieving completed run output

### Step A — Confirm terminal state (optional but recommended)

```http
GET /v1/agents/{agent_id}/runs/{run_id}
```

Use when webhook arrives before Twin run record is fully consistent, or during reconciliation.

### Step B — Fetch run events (required)

```http
GET /v1/agents/{agent_id}/runs/{run_id}/events?limit=50&after_index=0
```

Paginate until no new events:

```
after_index = 0
loop:
  response = GET events(limit=50, after_index=after_index)
  accumulate events
  if empty or last page: break
  after_index = last_event.index
```

### Step C — Extract export JSON

The Pleerity Discovery Agent must emit a **terminal structured output** in run events matching `twin_export_schema.json`. Exact event type/key is **not documented by Twin** — must be captured from first real agent run.

**Extractor responsibilities:**

1. Scan events from highest index backward for export artifact
2. Accept shapes: `{ "records": [...] }` or full batch envelope
3. Validate against `twin_export_schema.json`
4. Strip prohibited fields (`lawful_basis`, `marketing_consent`, CRM IDs)
5. Set `export_id` = `exp-twin-{run_id}` if missing

**If no export found:** Mark Discovery run `FAILED`; store raw events in connector quarantine; do **not** call `ingest_async()` with empty payload.

---

## 5. Do run events contain export JSON?

| Source | Contains export JSON? |
|--------|----------------------|
| Webhook POST body | **No** — metadata only |
| `GET .../runs/{run_id}/events` | **Expected yes** — agent output embedded in event stream (schema TBD) |
| Dedicated export API | **Does not exist** |
| Manual file export | **Yes** — operator-provided JSON file |

**CVP must fetch separately** after every webhook. Webhook alone is insufficient for ingest.

**Validation gate:** Stage Y (see §10) blocked until one real Twin run's events are captured and export location documented.

---

## 6. Retry and idempotency

### Twin → CVP webhook retries

Assume duplicate deliveries. CVP returns `200` for already-processed `run_id` + `event` combinations.

### CVP webhook idempotency

**Receipt key:** `twin:{agent_id}:{run_id}:{event}`

**Recommended storage:** `discovery_twin_webhook_receipts` collection (connector-only):

```json
{
  "receipt_id": "DTR-...",
  "twin_agent_id": "agent_abc123",
  "twin_run_id": "run_xyz789",
  "event": "run.completed",
  "webhook_timestamp": "2026-03-11T14:32:15Z",
  "status": "processed|failed|skipped",
  "discovery_run_id": "DRUN-...",
  "processed_at": "...",
  "error_code": null
}
```

**Unique index:** `(twin_agent_id, twin_run_id, event)`

**Alternative (zero new collection):** Use `discovery_runs.file_name = "twin:{agent_id}:{run_id}"` with unique lookup before processing.

### CVP → Twin API retries

| Call | Retry |
|------|-------|
| `GET .../events` | Yes — exponential backoff, max 5, on 429/5xx |
| `GET .../runs/{id}` | Yes — same |
| Webhook processing | No — single orchestrated attempt per receipt; failures go to DLQ/reconciliation |

### Discovery ingest idempotency (existing)

`TwinProvider.ingest_async()` already handles:

- Per-row idempotency via `provider_reference` + `content_hash`
- Cross-run duplicates via `DiscoveryDuplicateService`
- Batch-internal duplicates via `seen_idempotency` set

**Connector must not re-ingest same Twin `run_id`:** gate at receipt layer before `create_run`.

### HTTP response policy

| Situation | HTTP | Rationale |
|-----------|------|-----------|
| Signature invalid | `401` | Twin may retry — acceptable |
| Unknown agent | `403` | Misconfiguration |
| Duplicate receipt | `200` | Stop Twin retries |
| Export extract failed | `200` + receipt `failed` | Prevent infinite retry; ops reconciles |
| Ingest success | `200` | Normal |
| Transient DB down | `503` | Allow Twin retry |

---

## 7. Secret storage

| Secret | Env var | Storage | Notes |
|--------|---------|---------|-------|
| Twin API key | `TWIN_API_KEY` | Secrets manager / `.env` staging only | Outbound Twin REST only |
| Webhook signing secret | `TWIN_WEBHOOK_SIGNING_SECRET` | Secrets manager | Per-agent; from webhook create response |
| Agent allowlist | `TWIN_DISCOVERY_AGENT_ID` | Config | Reject webhooks for other agents |
| Campaign binding | `TWIN_DISCOVERY_CAMPAIGN_ID` | Config | `IngestContext.discovery_campaign_id` |
| CVP internal auth | `DISCOVERY_TWIN_WEBHOOK_TOKEN` | Secrets manager | Optional `Authorization: Bearer` on CVP endpoint |
| Provider gate | `DISCOVERY_PROVIDER_TWIN_ENABLED` | Config | Default `false` |
| Connector gate | `DISCOVERY_TWIN_WEBHOOK_INGEST_ENABLED` | Config | **New** — separate from provider flag |
| Twin API base | `TWIN_API_BASE_URL` | Config | Default `https://build.twin.so` |
| Webhook skew | `TWIN_WEBHOOK_MAX_SKEW_SECONDS` | Config | Default `300` |

**Never:** Store secrets in Twin agent instructions, git, audit JSON exports, or `discovery_audit_logs` details.

**Rotation:** Webhook recreate → new signing secret → dual-verify window → disable old webhook.

---

## 8. Rate limits, pagination, failure handling

### Rate limits

Twin REST API **does not publish numeric rate limits**. CVP must:

- Use webhook-triggered pull (not tight polling loops)
- Back off on `429` with jitter (1s → 2s → 4s → 8s → 16s cap)
- Limit concurrent Twin API calls per agent (recommend 2)
- Log `Retry-After` header if present

### Pagination

| API | Parameters |
|-----|------------|
| Run events | `limit` (default use 50), `after_index` |
| Runs list | `page`, `page_size` (reconciliation backfill) |
| Agents | `cursor`, `limit` |

### Failure handling

| Failure | Handling |
|---------|----------|
| Twin API 401/403 | Alert; halt connector; check key |
| Twin API 404 on run | Receipt `failed`; no retry |
| Empty events | Receipt `failed`; quarantine |
| Schema validation fail | Receipt `failed`; raw events stored; no ingest |
| `ingest_async` partial reject | Discovery run → `PARTIAL`; job error details in `discovery_jobs` |
| `ingest_async` exception | Discovery run → `FAILED`; receipt `failed` |
| `run.failed` webhook | Receipt `skipped`; ops alert; no ingest |
| `outcome: fail` on completed | Same as failed — no ingest |
| Mongo unavailable | `503` to Twin; receipt not marked processed |

### Reconciliation job (recommended)

Scheduled staging job (not webhook):

```
GET /v1/agents/{agent_id}/runs?filter_status=finished&filter_started_after=...
For each run_id without receipt → process as webhook would
```

Covers missed webhooks and `503` responses.

---

## 9. Mapping Twin run output → `TwinProvider.ingest_async()`

### Existing adapter contract (Stage W)

Entry point:

```python
await TwinProvider().ingest_async(
    IngestSource(payload={"export_id": "...", "records": [...]}),
    IngestContext(
        discovery_run_id=discovery_run["discovery_run_id"],
        discovery_campaign_id=campaign_id,
        actor_id="twin-webhook-connector",
        actor_email="twin-ingest@pleerity.staging",
        lawful_basis=campaign.lawful_basis,  # from campaign — NOT Twin payload
    ),
)
```

### Pre-ingest requirements (`_validate_run_for_ingest`)

| Requirement | Connector action |
|-------------|------------------|
| `discovery_run_id` exists | `DiscoveryRunService.create_run()` first |
| Run `status` = `processing` | Create run defaults to PROCESSING ✓ |
| Run `provider` = `twin` | Set on `CreateRunRequest` |
| `campaign_id` matches context | Pass same `TWIN_DISCOVERY_CAMPAIGN_ID` |
| Provider enabled | Patch/check `is_provider_enabled("twin")` when flag on |

### Field mapping

Delegated entirely to `TwinProvider` — connector produces `twin_export_schema.json` shape only. See `twin_discovery_field_mapping.json`.

### Post-ingest

| Result | Action |
|--------|--------|
| `accepted_count > 0`, `rejected_count == 0` | `DiscoveryRunService` → `COMPLETED` |
| Both accepted and rejected | → `PARTIAL` |
| `accepted_count == 0` | → `FAILED` |
| Never | Call `DiscoveryImportService`, `LeadService`, or approval APIs |

### Linking Twin run ↔ Discovery run

Use `CreateRunRequest.file_name = f"twin:{agent_id}:{run_id}"` for traceability without schema migration.

---

## 10. Security boundaries

### Allowed call graph

```
Twin Webhook → CVP Connector Route
  → Twin REST (events fetch)
  → DiscoveryRunService
  → TwinProvider.ingest_async()
  → DiscoveryProspectService / DiscoveryJobService / DiscoveryAuditService
```

### Prohibited (hard)

| Prohibited | Enforced by |
|------------|-------------|
| `LeadService` | No import in connector module |
| CRM writes | No CRM imports |
| `DiscoveryImportService` | Connector must not import |
| `DiscoveryApprovalQueueService` | No auto-approve |
| Outreach / nurture | N/A — not in connector scope |
| Production enablement | Flags default false; staging host only |
| Auto-import | `DISCOVERY_AUTO_IMPORT_ON_APPROVE` irrelevant — connector stops at prospects |

### Endpoint exposure

| Environment | Exposure |
|-------------|----------|
| Staging | Internal route + optional IP allowlist |
| Production | **Disabled** until launch gate |

Recommended route: `POST /api/internal/discovery/twin/webhooks` — not in public OpenAPI; requires internal token.

### Data handling

- Raw Twin events: store in connector quarantine collection (TTL 30d) — not in prospect documents
- PII: standard Discovery retention/compliance applies after ingest
- Audit: only standard `PROSPECT_DISCOVERED` / `DUPLICATE_DETECTED` from adapter

---

## Deliverable A — Recommended integration model

**Model name:** Webhook-triggered event pull (WEP)

| Phase | Mode |
|-------|------|
| Now | Manual export (Stage X) |
| Stage Y | WEP in staging only |
| Production | WEP + manual fallback + reconciliation (launch gate) |

**Why safest:**
- Webhook minimizes polling and latency
- Separate fetch validates payload before ingest
- Existing `TwinProvider` unchanged
- Idempotent at webhook and prospect layers
- Failed extracts never touch CRM path

---

## Deliverable B — Required endpoints

### CVP (implement in Stage Y)

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `POST` | `/api/internal/discovery/twin/webhooks` | HMAC + optional Bearer | Receive Twin lifecycle events |
| `POST` | `/api/internal/discovery/twin/reconcile` | Internal admin token | Manual/backfill run processing |
| `GET` | `/api/internal/discovery/twin/health` | Internal | Key + agent + flag status |

### Twin (consume)

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/v1/agents/{agent_id}/webhooks` | Register CVP webhook |
| `GET` | `/v1/agents/{agent_id}/runs/{run_id}/events` | Fetch export |
| `GET` | `/v1/agents/{agent_id}/runs/{run_id}` | Status verify |
| `GET` | `/v1/me` | Key health check |
| `GET` | `/v1/agents/{agent_id}/runs` | Reconciliation |

---

## Deliverable C — Required environment variables

```bash
# Gates (all default false)
DISCOVERY_MODULE_ENABLED=false
DISCOVERY_PROVIDER_LAYER_ENABLED=false
DISCOVERY_PROVIDER_TWIN_ENABLED=false
DISCOVERY_TWIN_WEBHOOK_INGEST_ENABLED=false

# Twin credentials (secrets manager in staging)
TWIN_API_KEY=
TWIN_WEBHOOK_SIGNING_SECRET=
TWIN_API_BASE_URL=https://build.twin.so

# Binding
TWIN_DISCOVERY_AGENT_ID=
TWIN_DISCOVERY_CAMPAIGN_ID=

# CVP webhook hardening
DISCOVERY_TWIN_WEBHOOK_TOKEN=
TWIN_WEBHOOK_MAX_SKEW_SECONDS=300

# Connector actor attribution
TWIN_INGEST_ACTOR_ID=twin-webhook-connector
TWIN_INGEST_ACTOR_EMAIL=twin-ingest@pleerity.staging
```

---

## Deliverable D — Webhook payload validation plan

| Step | Check | Fail action |
|------|-------|-------------|
| W1 | HTTPS request | Reject |
| W2 | `DISCOVERY_TWIN_WEBHOOK_INGEST_ENABLED=true` | `404` (hidden) |
| W3 | Optional Bearer token | `401` |
| W4 | Raw body size ≤ 64KB | `413` |
| W5 | HMAC signature valid | `401` |
| W6 | `X-Cobb-Event` == body `event` | `400` |
| W7 | `timestamp` within skew | `400` |
| W8 | `data.agent_id` in allowlist | `403` |
| W9 | `data.run_id` present | `400` |
| W10 | `event` in `{run.completed, run.failed}` | `200` skip |
| W11 | Idempotency receipt check | `200` if duplicate |
| W12 | JSON schema for webhook envelope | `400` |

Post-validation: async task or inline fetch → export validation plan E1–E8.

| Step | Check | Fail action |
|------|-------|-------------|
| E1 | Twin API fetch events success | Receipt `failed` |
| E2 | Export extractor finds `records[]` | Receipt `failed` |
| E3 | `len(records) >= 1` | Receipt `failed` |
| E4 | JSON Schema `twin_export_schema.json` | Receipt `failed` |
| E5 | No prohibited fields | Strip + log warning |
| E6 | `create_run` success | Receipt `failed` |
| E7 | `ingest_async` success | Run `COMPLETED`/`PARTIAL` |
| E8 | Receipt `processed` persisted | — |

---

## Deliverable E — Idempotency plan

```
Layer 1: Webhook receipt (twin_agent_id + twin_run_id + event) — unique
Layer 2: Discovery run (file_name twin:{agent}:{run}) — lookup before create
Layer 3: TwinProvider batch (seen_idempotency keys)
Layer 4: DiscoveryDuplicateService (cross-campaign/run)
```

**Duplicate webhook:** Return `200`, log `idempotent_webhook_replay`.  
**Duplicate Twin run reprocessed:** Blocked at Layer 2.  
**Duplicate prospect in new Twin run:** Handled by Layer 4 → `DUPLICATE_DETECTED` audit.

---

## Deliverable F — Test plan

### Unit tests (no Twin network)

| Test | Assert |
|------|--------|
| Signature verify valid/invalid | 401 vs pass |
| Timestamp skew edge | reject stale |
| Webhook envelope parser | required fields |
| Export extractor | finds `records` in sample event fixture |
| Schema validator | rejects missing `twin_id` |
| Idempotency receipt | duplicate returns early |
| Mapping fixture → `IngestSource` | shape accepted by `_parse_twin_records` |
| Prohibited field strip | no `lawful_basis` in payload |

### Integration tests (staging, mocked Twin)

| Test | Assert |
|------|--------|
| Mock webhook → mock events API | `ingest_async` called once |
| Duplicate webhook delivery | single Discovery run |
| `run.failed` webhook | no prospects created |
| Invalid signature | no DB writes |
| Flag off | `404` |

### Integration tests (real Twin — optional flag)

`DISCOVERY_RUN_TWIN_WEBHOOK_E2E=1`

| Test | Assert |
|------|--------|
| Register webhook on staging agent | signing secret stored |
| Trigger `POST /runs` | webhook received |
| Full WEP path | prospects in `needs_review` |
| Stage X rerun | operational GREEN |

### Regression boundaries

| Test | Assert |
|------|--------|
| Connector import graph | no `LeadService` / `DiscoveryImportService` imports |
| Prospect status | all `needs_review` — none `imported` |
| Audit events | only `PROSPECT_DISCOVERED`, `DUPLICATE_DETECTED` |

---

## Deliverable G — Stage implementation prompt

Use as authority for **Stage Y — Twin Webhook Ingestion Connector** (staging only):

---

### STAGE-Y-TWIN-WEBHOOK-INGESTION-CONNECTOR-AUTHORITY-01

**Objective:** Implement webhook-triggered Twin discovery ingestion in staging, terminating at `TwinProvider.ingest_async()`.

**Branch:** `develop` only. No production. No auto-import. No outreach. No CRM writes.

**Prerequisites:**
- Stage W `TwinProvider` DONE
- Stage X manual export path validated (AMBER minimum)
- Real Twin agent run events captured and export extractor schema documented
- `TWIN_API_WEBHOOK_INTEGRATION_AUDIT-01` approved

**Scope — implement:**
1. `services/discovery/twin/twin_api_client.py` — authenticated REST client (events pagination, Problem Details errors, backoff)
2. `services/discovery/twin/twin_webhook_verifier.py` — HMAC-SHA256 verification
3. `services/discovery/twin/twin_run_event_extractor.py` — events → `{export_id, records[]}` per captured real-run schema
4. `services/discovery/twin/twin_ingestion_connector.py` — orchestration: receipt → fetch → validate → `create_run` → `ingest_async` → run status
5. `routes/discovery_twin_internal.py` — `POST /api/internal/discovery/twin/webhooks`, health, reconcile
6. `discovery_twin_webhook_receipts` collection + unique index
7. `discovery_config.py` — `DISCOVERY_TWIN_WEBHOOK_INGEST_ENABLED`
8. Tests per Deliverable F

**Scope — do NOT implement:**
- `LeadService`, `DiscoveryImportService`, `DiscoveryApprovalQueueService` calls
- Production route exposure
- Changes to `TwinProvider` mapping unless defect fix
- Auto-approve or auto-import

**Acceptance criteria:**
- Twin `run.completed` webhook triggers ingest without manual file
- Duplicate webhook delivery is idempotent
- `run.failed` creates receipt but zero prospects
- Invalid signature rejected with no ingest
- All prospects land in `needs_review`
- Flags default false; connector returns 404 when disabled
- Evidence JSON + markdown report in `docs/audit/discovery_phase_1_launch_01/`

**Runbook:**
1. Set staging env vars (Deliverable C)
2. Register Twin webhook pointing to staging CVP URL
3. Trigger Twin agent run
4. Verify receipt + discovery_run + prospects
5. Run boundary regression tests

---

## Architectural exception check

| Component | Change needed? |
|-----------|----------------|
| `TwinProvider` | No |
| `DiscoveryImportService` | No |
| `LeadService` | No |
| `DiscoveryRunDocument` | No (use `file_name` convention) |
| New connector module | Yes — orchestration only |

**No architectural exception** if connector terminates at `ingest_async()`.

---

## References

- [Twin REST API](https://docs.twin.so/rest-api)
- [Twin Triggers](https://docs.twin.so/triggers)
- `backend/services/discovery/providers/twin_provider.py`
- `backend/docs/audit/discovery_phase_1_launch_01/twin_workspace/twin_export_schema.json`
- `backend/docs/audit/discovery_phase_1_launch_01/twin_workspace/TWIN_API_INTEGRATION_AUDIT.md`
