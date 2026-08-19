# Customer communication — notification volume observation 04

Programme: `CUSTOMER-COMMUNICATION-PRODUCTION-PROMOTION-GATE-04`

Invariant:

```text
one eligible requirement per governed reminder window
→ at most one customer reminder per recipient
```

Not:

```text
one client per day → one email
```

Intentional increase from batch-level to item-level messages is expected. Runaway duplication is not.

## Scheduler

| Job | Id | Schedule | Registered on new instance |
| --- | --- | --- | --- |
| Daily Compliance Reminders | `daily_reminders` | 09:00 UTC | `2026-08-19T07:49:02Z` |
| Subscription lifecycle & renewal reminders | `subscription_lifecycle` | 09:15 UTC | `2026-08-19T07:49:03Z` |

`misfire_grace_time=300`, `coalesce=True`, `max_instances=1`.

## Observation before 09:00 UTC

Deploy completed ~07:44Z. Health recovered ~07:53Z.

No `daily_reminders` scheduled execution is expected before 09:00 UTC. No reminder fan-out, job-run explosion, or Postmark customer-message spike was observed in `07:41Z`–`07:56Z`.

The only Postmark success in that window was `INTERNAL_ALERT` to `i***@pleerityenterprise.co.uk` for the recycle heartbeat-stale operator incident. That is not a customer reminder.

| Metric | Pre-09:00 window |
| --- | --- |
| daily reminder evaluations | 0 (job not yet due) |
| eligible requirements | n/a |
| messages attempted | 0 customer reminders |
| messages sent | 0 customer reminders |
| messages suppressed by cooldown | n/a |
| messages suppressed by preferences | n/a |
| provider failures | none in error logs |

## Observation through 09:27 UTC

Health observation lasted **07:53Z–09:27Z** (~94 minutes). `/api/health` remained `healthy` / `ready` / `heartbeat_fresh` on both API hosts, including after the 09:00 and 09:15 cron slots. Last heartbeat sampled: `2026-08-19T09:27:02Z`.

Render MCP log access dropped after ~08:01Z (`mcp_auth` timeout; subsequent `list_logs` connection timeouts). Cron **send counts were therefore not retrieved from application logs** in this session.

| Metric | 09:00 / 09:15 window |
| --- | --- |
| daily reminder evaluations | NOT_RETRIEVED (Render MCP outage) |
| eligible requirements | NOT_RETRIEVED |
| messages attempted | NOT_RETRIEVED |
| messages sent | NOT_RETRIEVED |
| messages suppressed by cooldown | NOT_RETRIEVED |
| messages suppressed by preferences | NOT_RETRIEVED |
| provider failures | none visible via `/api/health`; error-level logs none through `07:55Z` |
| scheduler continuity through cron slots | PASS (`heartbeat_fresh` at 09:07, 09:19, 09:27) |

This is an observation-completeness limitation, not a measured amplification defect. Jobs were registered before 09:00 (`daily_reminders`, `subscription_lifecycle`) with `coalesce=True` and `max_instances=1`.

Alert rule remains: if later log review shows send counts exceeding eligible-requirement counts unexpectedly, treat as amplification defect and evaluate rollback.
