# MongoDB Retention & Storage Prevention Policy

**Audit ID:** `MONGODB-STORAGE-ROOT-CAUSE-AND-CONTROLLED-CLEANUP-01`  
**Date:** 2026-08-06  
**Status:** Design proposal (implementation gated on approval)

---

## Principles

1. Authoritative compliance, payment, audit, and authority records are **never** TTL’d without a governed legal retention schedule.  
2. Derived / operational telemetry must be **bounded**.  
3. Retention actions must be auditable (job_run + before/after stats).  
4. Storage headroom alerts fire **before** Atlas write blocks.  
5. Staging and production must not share a Flex 5 GB failure domain long-term.

---

## 1. TTL / governed retention (proposed)

| Collection | Policy | Mechanism | Notes |
|------------|--------|-----------|-------|
| `operational_evidence_events` | Keep **hot 30d**, **warm 31–90d** (optional hide), **delete >90d** (or archive to cold object store) | Prefer scheduled delete job with dry-run; optional TTL index on `recorded_at` **only after** product accepts loss of old timelines | Today: warm tier only — **insufficient** |
| `operational_evidence_executions` | Delete when no events remain or age >90d | Cascade job after event purge | Derived |
| `operational_evidence_annotations` | Retain with events or export before purge | Manual/export | Low volume |
| `job_runs` | Retain **60–90d** detail; optional roll-up daily aggregates beyond that | TTL on `created_at` **or** nightly purge job | Keep failure samples longer if needed |
| Scheduler heartbeat / ephemeral health | **7–14d** | TTL | |
| Queue dead letters | **14–30d** | Purge job | |

**Do not TTL:** evidence vault, requirements, clients/properties, payments, entitlements, audit_logs, score_ledger (unless separate legal schedule).

---

## 2. Roll-up strategy

Where full raw history is unnecessary:

| Source | Roll-up | Cadence |
|--------|---------|---------|
| `job_runs` | Daily per-`job_name` counts: success/degraded/failed, p50/p95 duration | Nightly |
| OEP events | Daily counts by `category`, `event_type`, `severity`, `customer_impact.classification` | Nightly |
| Incidents | Keep authoritative incident docs; OEP copies expire | — |

Store roll-ups in small collections (e.g. `ops_telemetry_daily`) with months of history at negligible size.

---

## 3. Duplicate prevention & idempotency

| Path | Current | Proposed |
|------|---------|----------|
| Live OEP emit | Always new `event_id` UUID | Keep for true distinct runtime events; add optional idempotency key `(source_collection, source_id, event_type, occurred_at_bucket)` for high-churn producers if duplicates observed |
| OEP backfill | `_already_indexed` check | Retain; ensure maintenance job cannot unbounded-amplify |
| `job_runs` | One row per execution | Correct — reduce frequency of no-op jobs instead of deduping |
| No-op jobs | Many jobs still create run + 2 OEP events when “nothing changed” | Emit **lightweight** outcome or skip OEP for empty success where product allows |

---

## 4. Index hygiene

1. Audit query paths for `operational_evidence_events` (timeline, chain, story, portfolio).  
2. Drop unused compound indexes after 30d `hidden`/`$indexStats` review in non-prod.  
3. Prefer fewer covering indexes; Flex pays for every index byte.  
4. Avoid creating full index set on throwaway local DBs that share Atlas (never share Atlas for local).

---

## 5. Database growth alerts

| Signal | Threshold (proposed) | Action |
|--------|----------------------|--------|
| Atlas logical data+index | 60% / 75% / 90% of plan limit | Pager + incident |
| Collection size top-N | OEP or job_runs > configured GB | Create incident |
| Write error `AtlasError` / space quota | Any | Incident **P1**; API returns **503** with capacity code |
| Index count growth | >N new indexes/week | Eng review |

Surface in:

- System Health  
- Platform Status  
- Control Centre storage card (new read-only metric from Atlas Admin API or periodic `dbStats`/`collStats` sampler)

---

## 6. Safe 503 handling for capacity failures

When Mongo write fails with space/quota class errors:

1. Do **not** return opaque 500 for login if capacity is detected — return **503** `SERVICE_UNAVAILABLE` with `code=DATABASE_CAPACITY_EXCEEDED`.  
2. Skip non-critical writes (telemetry) rather than failing auth when possible (session write may still require capacity — prefer reclaim).  
3. Open/update platform incident automatically.  
4. Emit metric `mongo_capacity_blocked_total`.

---

## 7. Separate Atlas projects / clusters

| Recommendation | Rationale |
|----------------|-----------|
| **Staging and production on separate clusters (or projects)** | Prevents staging validation from blocking production writes |
| Minimum: production on dedicated tier with headroom; staging on separate Flex/M10 | Incident root cause is shared 5 GB |
| Local/dev: local Mongo or ephemeral containers — **never** shared Atlas Flex | Script defaults already favour staging name — dangerous with shared URI |

---

## 8. Maintenance job evolution

Replace “backfill + warm tier only” with:

1. Backfill (bounded lookback).  
2. Warm tier (optional).  
3. **Delete or archive** aged derived events.  
4. Compact/roll-up job_runs.  
5. Emit storage stats to health.

Feature-flag all delete behaviour; dry-run first in staging.

---

## Implementation gating

No retention deletes or TTL indexes are applied in this audit phase. Require explicit approval tickets per environment.
