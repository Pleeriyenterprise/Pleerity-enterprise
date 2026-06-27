# Operational Authority Assessment

**Programme:** OPERATIONAL-PRODUCTION-ACCEPTANCE-VALIDATION-01

For each admin operational indicator: source, calculation, runtime event, refresh, freshness, authority, validation method.

---

## Automation Control Centre

| Attribute | Detail |
|---|---|
| **Source** | `job_runs` collection |
| **API** | `GET /admin/observability/job-runs` |
| **Refresh** | On-demand per page load |
| **Authority** | **Yes** — direct Mongo read, no cache |
| **Validated** | HTTP 200; recent runs match scheduler activity |

---

## System Health

| Attribute | Detail |
|---|---|
| **Source** | `job_runs`, `scheduler_heartbeat`, `incidents`, `compliance_recalc_queue`, `job_schedule_registry` |
| **API** | `GET /admin/observability/health-summary` |
| **Calculation** | `build_health_summary_payload()` — per-job state machine + `_compute_overall_health` |
| **Refresh** | On-demand |
| **Freshness** | Heartbeat <5 min; job states from latest runs |
| **Authority** | **Yes** |
| **Validated** | 51/51 jobs; 16.4s latency; degraded signal matches open incidents |

---

## Platform Status (Control Centre)

| Attribute | Detail |
|---|---|
| **Source** | Health summary + security + revenue (owner) + engagement + workflow drift |
| **API** | `GET /admin/control-centre/snapshot` |
| **Scores** | Heuristic penalties documented in `scoring_notes` payload field |
| **Refresh** | On-demand |
| **Authority** | **Yes** (post `f2c10442`) |
| **Validated** | HTTP 200; scores present; platform_status `critical` aligns with P0/P1/P2 |

---

## Incident Management

| Attribute | Detail |
|---|---|
| **Source** | `incidents` collection via SLA watchdog + lifecycle service |
| **API** | `GET /admin/observability/incidents` |
| **Lifecycle** | OPEN → DEGRADED → RECOVERED → RESOLVED |
| **Authority** | **Yes** |
| **Validated** | Counts match health; fingerprint dedupe confirmed |

---

## Operational Alerts (email)

| Attribute | Detail |
|---|---|
| **Source** | `incident_lifecycle_service` + Postmark |
| **Trigger** | New incident, escalation, degraded transition, missing initial |
| **Authority** | **Mostly** — lifecycle fix deployed; 24h soak pending |
| **Validated** | No re-email ≥6h on sample unchanged P2 incidents |

---

## Telemetry / Health Scores

| Attribute | Detail |
|---|---|
| **Automation health** | 100 minus weighted penalties from health summary counts |
| **Job confidence** | Critical job state heuristic |
| **Security risk** | 7-day security dashboard aggregates |
| **Revenue health** | Owner-only; billing/stripe collections |
| **Authority** | **Yes** for automation/security; revenue owner-gated |
| **Validated** | Scores returned in Control Centre payload with breakdowns |

---

## Queues & Workers

| Attribute | Detail |
|---|---|
| **Recalc queue** | `compliance_recalc_queue` — depth metrics in health summary |
| **Workers** | In-process APScheduler; 51 jobs |
| **Authority** | **Yes** |
| **Validated** | 0 pending/dead/stuck; continuous worker success in job_runs |
