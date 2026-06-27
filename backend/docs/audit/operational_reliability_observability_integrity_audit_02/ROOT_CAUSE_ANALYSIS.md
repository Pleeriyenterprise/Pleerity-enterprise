# Root Cause Analysis — Audit 02

**Programme:** OPERATIONAL-RELIABILITY-OBSERVABILITY-INTEGRITY-AUDIT-02  
**Scope:** Staging runtime follow-up to Audit 01 remediations

---

## A. Health summary HTTP 500 after first deploy (`12ea3502`)

| Field | Detail |
|---|---|
| **Symptom** | `/admin/observability/health-summary` HTTP 500 at ~2s after `12ea3502` deploy |
| **Root cause** | Batch aggregation used `$sort` on all matching `job_runs` before `$group` — fails at staging collection scale |
| **Fix** | `02e71254` — `$top` per `job_name` with `finished_at` filter + `allowDiskUse` |
| **Result** | HTTP 200, 51 jobs, ~18s latency |

---

## B. Platform Status / Control Centre HTTP 500 (persistent)

| Field | Detail |
|---|---|
| **Symptom** | `/admin/control-centre/snapshot` HTTP 500 after ~28s |
| **Pre-audit** | Also failed at ~69s when health summary alone took ~55s |
| **Post health fix** | Still fails — **not solely health N+1** |
| **Likely contributors** | Chained collectors after `build_health_summary_payload()`: security dashboard, revenue block, workflow drift sample, work-order class mismatches |
| **Next step** | Render stack trace capture; isolate failing sub-collector (Audit 01 blocker P1) |

---

## C. Repeated operational emails (Audit 01 Issue)

| Field | Detail |
|---|---|
| **Symptom** | Same P2 incidents re-emailed each suppression window (~3600s) |
| **Root cause** | `_record_repeat` re-sent when `last_alert_email_at` age exceeded suppression and lifecycle was DEGRADED |
| **Fix** | Send only on escalation, OPEN→DEGRADED transition, or missing initial alert |
| **Runtime proof** | Pending 24h soak on staging |

---

## D. `delivery_unknown_stale` (20 rows)

| Field | Detail |
|---|---|
| **Symptom** | 20 reconciliation job runs with `outcome_metrics.delivery_unknown > 0` older than 6h window |
| **Sample jobs** | Mostly `daily_reminders` runs dating back several days |
| **Root cause (design)** | Messages marked SENT without Postmark DELIVERED webhook remain `unknown`; after stale window they count toward degraded health |
| **Not a false positive** | Health correctly reports degraded |
| **Action** | Verify webhook delivery for Postmark; run `delivery_reconciliation` job; inspect `message_logs` for sample run IDs in `RUNTIME_VALIDATION.json` |

---

## E. Open incidents after deploy

Transient P0/P1 incidents (`scheduled_admin_communications`, `risk_signal_regen_worker`, heartbeat stale) opened during deploy restart and may auto-recover on subsequent successful job runs. Persistent P2 incidents (`activation_reminder_processing`, `daily_reminders`, `subscription_ops_digest`) pre-date this deploy.
