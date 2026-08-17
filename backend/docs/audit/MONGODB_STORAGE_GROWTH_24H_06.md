# MongoDB storage growth — 24h soak 06

**Programme:** `MONGODB-24H-SOAK-CLOSURE-AND-PROMOTION-GATE-06`  
**Cluster monitor:** `GET /api/admin/observability/health-summary` → `mongo_storage`  
**No cleanup or purge was performed.**

## Cluster utilisation

Limit remains Atlas Flex **5 GiB** (`5368709120` bytes). Monitor scans both `pleerity_staging` and `pleerity_production` on the shared cluster.

| Snapshot | When (UTC) | Used bytes | Usage | Level | Writes at risk |
| --- | --- | ---: | ---: | --- | --- |
| Soak-adjacent start (05) | 2026-08-15T21:13:38Z | 2,854,065,854 | **53.16%** | `ok` | false |
| Soak end (06) | 2026-08-17T06:05:37Z | 2,906,243,948 | **54.13%** | `ok` | false |

No hourly storage series was recorded during this window. Intermediate authority is the 05 start snapshot plus this close snapshot. No later 05 capture exists after the preservation-push restart.

## Growth

Elapsed from storage start snapshot: **32.87 hours** (1.370 days).  
Elapsed from soak baseline `2026-08-15T21:19:51Z`: **32.76 hours**.

| Metric | Value |
| --- | --- |
| Absolute growth | **+52,178,094 bytes** (49.76 MiB) |
| Percentage-point growth | **+0.97 pp** (53.16 → 54.13) |
| Relative growth of used bytes | **+1.83%** |
| Estimated daily growth | **~38.1 MB/day** (~36.3 MiB/day) |
| Headroom to 85% critical | ~1.66 GB ≈ **~43 days** at this rate |
| Headroom to 90% write-risk | ~1.93 GB ≈ **~50 days** at this rate |

Growth is linear and small relative to the 5 GiB budget. It is consistent with continued staging workload (scheduled jobs, SoR collections, OEP from genuine runs), not a return to write-block.

## Writes and capacity events

| Check | Result |
| --- | --- |
| Monitor `available` | true |
| Monitor `level` | `ok` (warning threshold is 60%) |
| `writes_at_risk` | false |
| `incident_recommended` | false |
| Write-block event in soak | **none** |
| `DATABASE_CAPACITY_EXCEEDED` incident in soak | **none** (storage-like titles on first incident page: empty) |
| Capacity monitor job | `mongo_storage_capacity_monitor` last success `2026-08-17T06:00:02Z`; **131** `job_runs` in-window (~4h cadence) |

## Per-database split at soak end

| Database | Data | Index | Objects | Collections |
| --- | ---: | ---: | ---: | ---: |
| `pleerity_staging` | 744,300,875 | 245,075,968 | 858,616 | 266 |
| `pleerity_production` | 1,416,581,665 | 500,285,440 | 1,390,825 | 224 |

Staging data+index ≈ **989 MB**. Production on the same cluster ≈ **1.92 GB**. Shared Flex remains a **roadmap** blast-radius item, not a new soak defect.

This exercise did not mutate `pleerity_production`.

## Watched collections (staging only, read-only collStats)

Compare with the 6 Aug partial soak (`incident_closure_soak_snapshot_01.json`). That window is **not** this soak; it is a scale reference only.

| Collection | 6 Aug ~18:32Z | 17 Aug 06:10Z | Soak-window new docs | Size+index now |
| --- | ---: | ---: | ---: | ---: |
| `job_runs` | 331 | **30,266** | **+3,902** | 21.4 MB |
| `operational_evidence_events` | 1,042 | **91,717** | **+12,564** (`occurred_at`) | 241.6 MB |
| `operational_evidence_executions` | 19 | **36** | 0 on `created_at` (bounded lifetime +17 since 6 Aug) | 0.13 MB |
| `job_poll_heartbeats` | 5 (upsert) | **5** (upsert) | 0 new docs | 1.5 KB |

Pre-remediation `job_runs` was **~1.94M / ~1.4 GB**. Current `job_runs` is **30,266 / ~15 MB data** — two orders of magnitude below that failure mode.

## Is OEP a new runaway?

`operational_evidence_events` is now the largest staging collection (it was not on 6 Aug; `audit_logs` led then). Absolute count rose from ~1k to ~92k across **~11 days of staging**, not 32 hours alone.

Soak-window OEP rate: 12,564 / 1.365 d ≈ **9,200 events/day**. The 6 Aug partial window was ~262 events/hour (~6,300/day). Same order of magnitude. Idle-skip poll heartbeats remain **5 upserts**, so 15s/30s/1m idle ticks are **not** inserting a document per poll.

This is **not** the pre-remediation telemetry explosion. It **is** a reason to keep live retention on the post-launch roadmap rather than treat OEP as a launch blocker. Do not purge in this exercise.

## Top staging collections by size+index (soak end)

| Collection | Count | Size+index |
| --- | ---: | ---: |
| operational_evidence_events | 91,717 | 241.6 MB |
| audit_logs | 232,241 | 149.5 MB |
| message_logs | 23,737 | 123.2 MB |
| security_events | 129,699 | 78.0 MB |
| compliance_decisions | 16,188 | 44.6 MB |
| compliance_evidence_nodes | 32,374 | 42.0 MB |
| job_runs | 30,266 | 21.4 MB |

SoR/ops collections remain large; `job_runs` is no longer in the storage-danger class.

## Capacity verdict

```text
MONGODB_CAPACITY = PASS_WITH_CONDITION
```

Condition: shared Atlas Flex (staging + production) and live retention not enabled. Growth during the soak was controlled; writes remained available; monitor stayed `ok`.
