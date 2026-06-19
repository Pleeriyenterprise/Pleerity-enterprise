# TWIN-API-INTEGRATION-AUDIT-01

**Authority:** TWIN-API-INTEGRATION-AUDIT-01  
**Date:** 2026-06-19  
**Scope:** Audit only — no implementation  
**Constraint:** Twin integration must terminate at `TwinProvider.ingest_async()`  
**CVP state:** Stage W adapter complete; no Twin HTTP routes; `DISCOVERY_PROVIDER_TWIN_ENABLED` defaults `false`

---

## Executive summary

Twin exposes a mature **agent/run management REST API** and **run-lifecycle webhooks**, but **does not expose a first-class prospect export API**. Prospect batches must be obtained via **manual export**, **parsing run events**, or an **agent-initiated HTTP POST** to a CVP ingest endpoint (future).

| Option | Verdict |
|--------|---------|
| A. Manual Export | **Required for Phase 1** (Stage X, operational validation) |
| B. API Pull | **Required component** (run status + event extraction) |
| C. Webhook Push | **Insufficient alone** (lifecycle metadata only, no prospect payload) |
| D. Hybrid | **Recommended target architecture** |

**Recommendation:** **D — Hybrid**  
`run.completed` webhook → API pull run events → normalize to `twin_export_schema.json` → `TwinProvider.ingest_async()`

Manual export remains the fallback and audit baseline until event extraction is proven stable.

---

## 1. Twin REST API review

**Base URL:** `https://build.twin.so`  
**OpenAPI:** `https://build.twin.so/openapi.json`  
**Docs:** [Twin REST API](https://docs.twin.so/rest-api)

### 1.1 Authentication

| Aspect | Detail |
|--------|--------|
| Method | API key header on every request |
| Header | `x-api-key: YOUR_API_KEY` |
| Key creation | Twin dashboard or `POST /api/public/v1/access-api-keys` |
| Key lifecycle | List, create (full key returned once), revoke |
| Identity | `GET /v1/me` → `user_id` |

**CVP implications:**
- Store key in secrets manager (`TWIN_API_KEY`), never in repo or agent instructions
- Use separate staging vs production keys
- Revoke on compromise; rotate on schedule
- API key grants full Twin account scope — treat as tier-0 secret

### 1.2 Agent APIs

| Endpoint | Purpose |
|----------|---------|
| `GET /v1/agents` | List agents (cursor + limit pagination, workspace filter) |
| `POST /v1/agents` | Create agent |
| `GET /v1/agents/{agent_id}` | Agent detail, deployment state |
| `DELETE /v1/agents/{agent_id}` | Delete agent + run data |
| `GET /v1/agents/{agent_id}/instructions` | Read system prompt |
| `PUT /v1/agents/{agent_id}/instructions` | Update prompt (versioned) |
| `POST /v1/agents/{agent_id}/move` | Move between workspaces |

**Workspaces:** `GET/POST/PUT/DELETE /v1/workspaces`

**CVP use:** Pleerity Discovery Agent is created/deployed in a dedicated staging workspace. CVP does **not** need to create agents via API for Phase 1 — workspace setup is manual per `TWIN_WORKSPACE_SETUP_PACKAGE.md`. API read access supports health checks and deployment verification.

### 1.3 Run APIs

| Endpoint | Purpose |
|----------|---------|
| `GET /v1/agents/{agent_id}/runs` | List runs (page, page_size, status/date filters) |
| `POST /v1/agents/{agent_id}/runs` | Start run (`run_mode`: `build` \| `run`) |
| `POST /v1/agents/{agent_id}/runs/{run_id}/cancel` | Cancel (idempotent) |
| `DELETE /v1/agents/{agent_id}/runs/{run_id}` | Delete run |
| `GET /v1/agents/{agent_id}/runs/{run_id}/events` | **Run event stream** (limit, after_index) |

**Schedules:** cron via `GET/PUT/DELETE /v1/agents/{agent_id}/schedule` (+ pause/resume)

**CVP use:**
- Trigger discovery runs programmatically (`run_mode: run` only — never `build` in production path)
- Poll run status until `finished` / `completed`
- **Extract prospect JSON from run events** — this is the de facto “export API”

**Gap:** Event payload schema for prospect output is **not documented** as a stable export contract. Must be validated against real Pleerity Discovery Agent runs before automating.

### 1.4 Export APIs

**Finding: No dedicated export endpoint exists.**

Twin REST API does not include:
- `GET /exports`
- `GET /runs/{id}/artifacts`
- `GET /runs/{id}/output`

Prospect data delivery options:

| Method | Mechanism |
|--------|-----------|
| Manual | Operator copies/downloads agent JSON output (Stage X path) |
| Run events | Parse terminal events from `/events` for structured JSON |
| Agent HTTP tool | Agent POSTs batch to CVP endpoint per instructions (custom) |
| Twin integrations | Google Sheets etc. — **not recommended** (extra boundary, no Discovery mapping) |

### 1.5 Webhook support

**Registration:** `POST /v1/agents/{agent_id}/webhooks`  
**Management:** list, get, patch, delete per agent

| Event | When fired |
|-------|------------|
| `run.started` | Run begins |
| `run.completed` | Run finishes (success, partial, fail) |
| `run.failed` | Policy error |
| `run.stopped` | User stopped |
| `run.paused` | User pause or 15+ min agent pause |

**Payload:** `{ event, timestamp, data: { run_id, agent_id, status, outcome?, finished_at? } }`  
**Does NOT include prospect records.**

**Verification:**
- Headers: `X-Cobb-Signature` (`sha256=...`), `X-Cobb-Event`
- `HMAC-SHA256(signing_secret, raw_body)` compared with timing-safe equality
- `signing_secret` returned once at webhook creation

**CVP use:** Webhooks signal **when to pull**, not **what to ingest**. Suitable for async orchestration only.

**Note:** Twin “custom webhooks” in [Triggers](https://docs.twin.so/triggers) are **inbound to Twin** (trigger agents), not outbound prospect delivery.

### 1.6 Rate limits

**Finding: No numeric REST API rate limits documented.**

Twin docs reference rate limiting in the context of **web/browser automation** during agent runs, not API quota headers. CVP must assume:
- Undocumented limits may exist (429 responses possible)
- Implement exponential backoff + jitter on all Twin API calls
- Avoid tight polling loops on `/events`
- Confirm limits with Twin support before production scale

### 1.7 Pagination

| API | Model |
|-----|-------|
| Agents | Cursor + `limit` |
| Runs | `page` + `page_size` (default 100) |
| Run events | `limit` + `after_index` (cursor by event index) |
| Instructions history | `limit` |

**CVP pattern for event extraction:**
```
after_index = 0
loop:
  GET /events?limit=50&after_index={after_index}
  parse events; append prospect candidates
  if no more events: break
  after_index = last_event.index
```

### 1.8 Error handling

**Format:** RFC 9457 Problem Details (`application/problem+json`)

```json
{
  "type": "about:blank",
  "title": "Not Found",
  "status": 404,
  "detail": "Description of what went wrong"
}
```

**CVP handling requirements (future integration service):**
| Status | Action |
|--------|--------|
| 401 / 403 | Alert, halt, check API key |
| 404 | Run/agent deleted — mark job failed, no retry |
| 409 / conflict | Log, idempotent retry policy |
| 429 | Backoff per rate-limit policy |
| 5xx | Retry with cap (3–5 attempts) |
| Parse errors on events | Quarantine batch, manual review, do not partial-ingest unvalidated JSON |

---

## 2. Integration options assessment

### A. Manual Export

**Flow:**
```
Twin Agent Run → Operator exports JSON file → Stage X / ops ingest script → TwinProvider.ingest_async()
```

| Pros | Cons |
|------|------|
| Lowest risk; matches Stage X | Not scalable |
| Human QA gate before ingest | Latency |
| No Twin API dependency for ingest | Operator error |
| Already validated (contract cohort + script path) | No real-time discovery |

**Verdict:** **Mandatory for Phase 1** and permanent fallback.

---

### B. API Pull

**Flow:**
```
Scheduler or manual trigger → POST /runs → poll GET /runs → GET /events → normalize → ingest_async()
```

| Pros | Cons |
|------|------|
| Fully programmatic | No export API — event parsing required |
| No inbound CVP webhook attack surface | Polling cost/latency if no webhook |
| Deterministic retry | Event schema stability unknown |

**Verdict:** **Required building block** for automation.

---

### C. Webhook Push

**Flow:**
```
Twin POST run.completed → CVP handler → ???
```

| Pros | Cons |
|------|------|
| Efficient run completion signal | **No prospect payload in webhook** |
| Reduces status polling | Still requires API pull for data |
| Signed deliveries | Misleading name — not “prospect push” |

**Verdict:** **Useful as trigger only**, not as standalone integration. Not sufficient alone.

---

### D. Hybrid (recommended)

**Flow:**
```
┌─────────────────────────────────────────────────────────────────┐
│ Twin Platform                                                    │
│  Schedule / POST /runs → Pleerity Discovery Agent executes      │
│  run.completed webhook ─────────────────────────────┐           │
└────────────────────────────────────────────────────│───────────┘
                                                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ CVP Twin Integration Layer (future — NOT LeadService/CRM)       │
│  1. Verify X-Cobb-Signature                                      │
│  2. Idempotency check on run_id                                  │
│  3. GET /runs/{run_id}/events (paginated)                        │
│  4. Extract + validate records[] per twin_export_schema.json     │
│  5. DiscoveryRunService.create_run(provider=twin)                │
│  6. TwinProvider.ingest_async(payload, IngestContext)  ◄─ STOP  │
└─────────────────────────────────────────────────────────────────┘
                                                     │
                                                     ▼
                              discovery_prospects → Review → Import (existing)
```

**Manual export path remains parallel** for Stage X, debugging, and disaster recovery.

---

## 3. Recommended architecture

### Layer model

| Layer | Responsibility | CVP status |
|-------|----------------|------------|
| L0 Twin Platform | Discovery agent execution | External |
| L1 Integration orchestrator | Webhook verify, run tracking, event pull, normalize | **Not built** |
| L2 Discovery provider | `TwinProvider.ingest_async()` | **Built (Stage W)** |
| L3 Discovery Foundation | Review, compliance, import, lifecycle | **Built** |

### Hard boundary (non-negotiable)

```
Twin API / Webhook / File
        ↓
[L1 Integration — optional future]
        ↓
TwinProvider.ingest_async()  ← TERMINATION POINT
        ↓
discovery_prospects only
```

**L1 must never call:**
- `LeadService`
- `DiscoveryImportService`
- `DiscoveryApprovalQueueService`
- CRM models or routes

### Phased rollout

| Phase | Mode | Gate |
|-------|------|------|
| X (now) | Manual export + validation script | Real Twin export, Stage X GREEN |
| X+1 | Hybrid (webhook + event pull) in staging | Event schema proven on 3+ runs |
| Production | Hybrid + manual fallback | Launch gate, `DISCOVERY_PROVIDER_TWIN_ENABLED` |

### Future components (design only — do not implement in this audit)

| Component | Role |
|-----------|------|
| `TwinApiClient` | Authenticated REST wrapper, pagination, Problem Details parsing |
| `TwinWebhookReceiver` | `POST /api/internal/discovery/twin/webhooks` — signature verify only |
| `TwinRunEventExtractor` | Parse events → `{ export_id, records[] }` |
| `TwinIngestOrchestrator` | Create run + `ingest_async()`; job state in `discovery_jobs` |
| `twin_ingest_dlq` | Failed normalizations quarantined for ops review |

**Flag gating:** `DISCOVERY_PROVIDER_TWIN_ENABLED` + new `DISCOVERY_TWIN_API_INGEST_ENABLED` (recommended separate flag for API path vs manual).

---

## 4. Required endpoints

### Twin platform (consume)

| Priority | Method | Endpoint | Purpose |
|----------|--------|----------|---------|
| P0 | `POST` | `/v1/agents/{agent_id}/runs` | Start discovery run |
| P0 | `GET` | `/v1/agents/{agent_id}/runs/{run_id}` | Confirm terminal status |
| P0 | `GET` | `/v1/agents/{agent_id}/runs/{run_id}/events` | Extract prospect JSON |
| P0 | `POST` | `/v1/agents/{agent_id}/webhooks` | Register `run.completed`, `run.failed` |
| P1 | `GET` | `/v1/agents/{agent_id}` | Deployment health |
| P1 | `GET` | `/v1/me` | Key validation |
| P2 | `GET` | `/v1/agents/{agent_id}/runs` | Reconciliation / backfill |
| P2 | `PUT` | `/v1/agents/{agent_id}/schedule` | Scheduled discovery (if ops-approved) |

### CVP (expose — future, staging only)

| Priority | Method | Endpoint | Purpose |
|----------|--------|----------|---------|
| P0 | `POST` | `/api/internal/discovery/twin/webhooks` | Receive Twin run lifecycle events |
| P1 | `POST` | `/api/internal/discovery/twin/ingest` | Optional: agent-direct batch POST (HMAC + IP allowlist) |
| P1 | `POST` | `/api/internal/discovery/twin/runs/{run_id}/pull` | Manual ops backfill trigger |

All CVP endpoints must:
- Call only `TwinProvider.ingest_async()` after normalization
- Require internal auth (service token or mTLS)
- Be disabled when `DISCOVERY_PROVIDER_TWIN_ENABLED=false`
- Log to `discovery_audit_logs` via existing adapter audit path only

**No public/unauthenticated Twin ingest route.**

---

## 5. Security model

### Credential management

| Secret | Storage | Rotation |
|--------|---------|----------|
| `TWIN_API_KEY` | Secrets manager / env (staging) | Quarterly or on staff change |
| Twin webhook `signing_secret` | Secrets manager per agent | On webhook recreate |
| CVP internal ingest token | Secrets manager | Independent rotation |

### Webhook security

1. HTTPS only in production (Twin allows HTTP — reject in CVP config)
2. Verify `X-Cobb-Signature` on raw body before JSON parse
3. Idempotency key: `twin:webhook:{event}:{run_id}`
4. Reject replay: check `timestamp` within skew window (e.g. 5 min)
5. Rate limit inbound webhook endpoint per source IP

### API client security

- Timeout: 30s connect, 120s read for event pagination
- Retry only idempotent GETs and verified webhook processing
- No API key in logs, audit details, or error responses
- Egress allowlist to `build.twin.so` only

### Data security

- Prospect PII in transit: TLS end-to-end
- Twin export JSON at rest: staging audit directory access-controlled
- Agent must not output consent fields (per agent spec)
- Lawful basis applied from Discovery campaign `IngestContext`, not Twin payload

### Authorization model

```
Twin API Key        → Twin account (agent/run management only)
CVP Internal Token  → Twin integration endpoints (ingest orchestration only)
Discovery Campaign  → lawful_basis for IngestContext
Human Reviewer      → approval (unchanged)
```

---

## 6. Mapping model

**Authoritative mapping:** `twin_workspace/twin_discovery_field_mapping.json`  
**Schema:** `twin_workspace/twin_export_schema.json`  
**Adapter:** `TwinProvider.map_to_canonical()` + `_split_twin_fields()`

### Integration layer responsibilities

| Step | Owner |
|------|-------|
| Twin event → export envelope | L1 Extractor (future) |
| Export envelope → `IngestSource.payload` | L1 Orchestrator |
| Row validation + canonical map | `TwinProvider.validate()` / `map_to_canonical()` |
| Twin-only fields → raw payload | `TwinProvider` (existing) |
| Prospect persistence | `DiscoveryProspectService` (existing) |

### Normalization rules

1. Output must be `{ "export_id": "...", "records": [ ... ] }` before `ingest_async()`
2. `export_id` = `run_id` or `exp-{run_id}` for traceability
3. Each record requires `twin_id`, `company_name`, `source_url`, `confidence_score`, `country`
4. Strip `lawful_basis`, `marketing_consent`, CRM IDs if agent mis-emits
5. `provider_id` is implicit (`twin`) — set by adapter, not payload

### Idempotency

| Key | Source |
|-----|--------|
| Webhook processing | `run_id` + event type |
| Prospect ingest | `TwinProvider.idempotency_key()` → provider_reference + content_hash |
| Re-run same export file | Duplicate detection via existing `DiscoveryDuplicateService` |

---

## 7. Risk assessment

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| No stable export API | **High** | Certain | Manual fallback; prove event extraction on real runs; version-pin extractor |
| Run event schema changes | **High** | Medium | Contract tests against sample events; extractor version field |
| Undocumented API rate limits | Medium | Medium | Backoff; webhook-triggered pull not poll; ask Twin for quotas |
| Webhook without payload → missed pull | Medium | Low | Reconciliation job: `GET /runs?filter_status=finished` backfill |
| Agent output format drift | **High** | Medium | JSON schema validation pre-ingest; reject batch on schema fail |
| API key compromise | **High** | Low | Scoped keys, rotation, audit `last_used_at`, IP monitoring |
| Ingest endpoint bypasses review | **High** | Low | `ingest_async()` only creates `needs_review` — no import path in L1 |
| Browser automation fragility | Medium | High | Agent instructions: API-first; public sources only |
| Cost overrun (Twin credits) | Medium | Medium | `run_mode: run` only; schedule governance; cost tracking in `part_i` |
| False positive prospect quality | Medium | Medium | Confidence ≥ 50 export rule; human review unchanged |
| Architectural exception pressure | **High** | Low | Terminate at `ingest_async()` — already proven Stage W/X |

### Architectural exception check

| System | Modification required? |
|--------|------------------------|
| `TwinProvider` | No — payload contract already defined |
| `DiscoveryImportService` | No |
| `LeadService` | No |
| `DiscoveryApprovalQueueService` | No |
| Compliance / lifecycle / metrics | No |
| New L1 integration layer | Yes — **orchestration only**, not governance |

**No architectural exception** if L1 respects termination at `TwinProvider.ingest_async()`.

---

## 8. Decision matrix

| Criterion | Manual | API Pull | Webhook Push | Hybrid |
|-----------|--------|----------|--------------|--------|
| Stage X readiness | ✅ Now | ⚠️ Needs event proof | ❌ No payload | ⚠️ After event proof |
| Operational scale | ❌ | ✅ | ⚠️ Trigger only | ✅ |
| Security surface | ✅ Minimal | ✅ Outbound only | ⚠️ Inbound | ⚠️ Inbound + outbound |
| Discovery boundary | ✅ | ✅ | ✅ if + pull | ✅ |
| Auditability | ✅ | ✅ | ✅ | ✅ |
| Twin API gaps | ✅ Bypasses | ⚠️ Event parsing | ❌ Incomplete | ⚠️ Managed |

**Winner: D — Hybrid** with **A — Manual Export** as Phase 1 and permanent fallback.

---

## 9. Immediate actions (no implementation)

1. Complete Stage X with **manual real Twin export** per `STAGE_X_RERUN_CHECKLIST.md`
2. Run Pleerity Discovery Agent once; capture full **run events** payload for schema analysis
3. Confirm with Twin whether a stable structured output / artifact API is planned
4. Request documented API rate limits and webhook retry policy
5. Only after event schema is proven: design L1 orchestrator PR (separate authority)

---

## 10. References

- [Twin REST API](https://docs.twin.so/rest-api)
- [Twin Triggers](https://docs.twin.so/triggers)
- `backend/services/discovery/providers/twin_provider.py`
- `backend/docs/audit/discovery_phase_1_launch_01/twin_workspace/TWIN_WORKSPACE_SETUP_PACKAGE.md`
- `backend/docs/audit/discovery_phase_1_launch_01/twin_workspace/twin_discovery_field_mapping.json`
- `backend/docs/audit/discovery_phase_1_launch_01/STAGE_X_TWIN_STAGING_REPORT.md`
