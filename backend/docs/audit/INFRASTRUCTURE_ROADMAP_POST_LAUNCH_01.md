# Infrastructure Roadmap (Post-Launch)

**Audit ID:** `PRODUCTION-READINESS-CLOSURE-01`  
**Mode:** Plans only — **not implemented** in this exercise.

---

## 1. Atlas staging / production cluster separation

| | |
|--|--|
| **Scope** | Move `pleerity_staging` and `pleerity_production` onto separate Atlas clusters (or dedicated Flex/Dedicated tiers). Update Render `MONGO_URL` per environment only. |
| **Benefits** | Removes shared 5 GB failure domain; staging growth cannot block production writes. |
| **Risks** | Cutover downtime; connection string mistakes; backup restore testing. |
| **Rollback** | Re-point env vars to previous shared URI; keep dual-read window if needed. |
| **Effort** | 2–4 engineer-days + Atlas provisioning lead time. |
| **Phase** | Next capacity planning cycle (P0 infra). |

## 2. Production retention enablement

| | |
|--|--|
| **Scope** | After staging live purge proof, enable `MONGO_OPERATIONAL_RETENTION_PURGE_ENABLED` on production with dry-run → bounded live batches; protect authoritative collections. |
| **Benefits** | Sustained operational telemetry footprint; reduces recurrence risk. |
| **Risks** | Over-deletion if policies wrong; clock/field mismatches. |
| **Rollback** | Disable flag immediately; restore from Atlas backup if needed. |
| **Effort** | 1–2 days including approval gates + monitoring. |
| **Phase** | After staging live retention approval + soak. |

## 3. Storage budgeting

| | |
|--|--|
| **Scope** | Define per-environment budgets, alert routing, and growth burn-rate dashboards from `mongo_storage_monitor` + Atlas metrics. |
| **Benefits** | Predictable headroom; earlier ops response than write-block. |
| **Risks** | Alert fatigue if thresholds noisy. |
| **Rollback** | Raise thresholds / disable non-critical alerts. |
| **Effort** | 1–3 days. |
| **Phase** | Parallel with cluster separation. |

## 4. Database lifecycle governance

| | |
|--|--|
| **Scope** | Codify collection authority classes, purge playbooks, index budgets, and change-control for new high-frequency writers. |
| **Benefits** | Prevents silent telemetry regression; auditable ops. |
| **Risks** | Process overhead if too rigid. |
| **Rollback** | Governance docs are additive; no runtime rollback required. |
| **Effort** | 3–5 days initial policy + owners. |
| **Phase** | Q-next platform reliability programme. |
