# MongoDB incident stability 06

**Programme:** `MONGODB-24H-SOAK-CLOSURE-AND-PROMOTION-GATE-06`  
**Source:** `GET /api/admin/observability/incidents` (paginated; 1,138 listed) plus health-summary open counts.  
**Window:** incidents with `created_at` ≥ `2026-08-15T21:19:51Z`.

## Headline

| Check | Result |
| --- | --- |
| Open P0/P1 now | **0** |
| Open incidents now | **2** (both P2, both pre-soak) |
| New P0 during soak after scheduler recovery | **none** |
| New P1 during soak after scheduler recovery | **none** |
| False storage / Atlas / write-block incident | **none** |
| False scheduler incident remaining open | **none** |
| Stale RECOVERING contradicting current runtime | **none** |
| `overall_health` | `degraded` (matches 2 open non-P0/P1 + delivery-unknown stale), not an incident-engine lie |

## Soak-window creations (n=5)

All five are **RESOLVED**. Four were raised in the **documented post-deploy recovery** (21:24–21:25Z), before scheduler recovered at 21:26:36Z. One P2 was raised at 22:00Z and later resolved.

| Created (UTC) | Severity | Title | Job | Lifecycle |
| --- | --- | --- | --- | --- |
| 2026-08-15T21:24:56Z | P1 | Scheduler heartbeat stale | — | RESOLVED |
| 2026-08-15T21:25:03Z | P0 | Job risk_signal_regen_worker missed SLA | risk_signal_regen_worker | RESOLVED |
| 2026-08-15T21:25:07Z | P0 | Job notification_retry_worker missed SLA | notification_retry_worker | RESOLVED |
| 2026-08-15T21:25:14Z | P0 | Job scheduled_admin_communications missed SLA | scheduled_admin_communications | RESOLVED |
| 2026-08-15T22:00:32Z | P2 | Job work_order_schedule_reminders missed SLA | work_order_schedule_reminders | RESOLVED |

These P0/P1 are the expected SLA/heartbeat flaps from the soak-starting Render restart (`fb138ae5` live at 21:19:51Z). They progressed to RESOLVED. They do **not** remain as RECOVERING/RECOVERED against a currently healthy heartbeat.

After `2026-08-15T21:26:36Z`, **no new P0 or P1** was created for the rest of the 32h window.

## Soak-window counts

By severity (created in window):

| Severity | Count | Blocking now? |
| --- | ---: | --- |
| P0 | 3 | No — all RESOLVED |
| P1 | 1 | No — RESOLVED |
| P2 | 1 | No — RESOLVED |

By lifecycle (created in window):

| Lifecycle | Count |
| --- | ---: |
| RESOLVED | 5 |
| RECOVERING | 0 |
| RECOVERED | 0 |
| OPEN / DEGRADED (in-window) | 0 |

## Open incidents at close (not created in this soak)

| Created | Severity | Status | Lifecycle | Title |
| --- | --- | --- | --- | --- |
| 2026-08-09T09:10:20Z | P2 | open | RECOVERED | Job daily_reminders last run was degraded |
| 2026-08-06T21:10:19Z | P2 | open | DEGRADED | Delivery unknown unresolved |

Both pre-date this soak. `daily_reminders` had 1 degraded run in the last 24h (`finished_at` 2026-08-16T09:02:27Z) — consistent with a lingering P2, not a scheduler outage. Delivery-unknown matches health-summary `delivery_unknown_stale: 20` (non-blocking observability).

The RECOVERED-but-`status=open` `daily_reminders` row is **lifecycle residue**, not a contradiction of current `/api/health` (scheduler `heartbeat_fresh`). It is not P0/P1. Do not treat as launch-blocking. Do not auto-resolve in this exercise.

No remaining incident claims storage pressure or a stale scheduler while runtime is healthy.

## Catalogue (all listed incidents, historical)

| Dimension | Counts |
| --- | --- |
| Severity | P0 372, P1 390, P2 376 |
| Status | resolved 1,136; open 2 |
| Lifecycle | RESOLVED 757, RECOVERED 1, DEGRADED 1, unknown 379 |

The large historical P0/P1 totals are **closed catalogue debt**, not live soak failures. `lifecycle=unknown` is missing `lifecycle_state` on older rows.

## Incident verdict

```text
INCIDENTS = PASS_WITH_CONDITION
```

Conditions: two historic P2s remain open; deploy-window P0/P1 existed and fully resolved. No new launch-blocking incident emerged after scheduler recovery.
