# MongoDB Retention Implementation

**Audit ID:** `MONGODB-STORAGE-REMEDIATION-AND-LIFECYCLE-GOVERNANCE-01`  
**Date:** 2026-08-06

---

## Policy table (operational telemetry)

| Collection | Purpose | Authority | Retention | Archive | Purge | Expected growth | TTL? |
|------------|---------|-----------|-----------|---------|-------|-----------------|------|
| `job_runs` | Job execution history | Operational | 60–90 days detail | Optional daily roll-up | Age delete via `operational_retention_purge` | High without idle-skip | No (job purge preferred) |
| `operational_evidence_events` | Derived correlation index | Derived | 30–90 days | Warm tier @ 90d then purge | Flagged purge | High (emit+backfill) | No |
| `operational_evidence_executions` | Story roots | Derived | Align with events | None | With events | Medium | No |
| `message_logs` | Delivery log | Operational | 90–180 days | None | Age purge | Medium | No |
| `reminder_evaluation_log` | Reminder eval | Operational | 90 days | None | Age purge | Medium | No |
| `workflow_*_audit` | Workflow telemetry | Operational | 90 days | None | Age purge | Medium | No |
| Queue collections | Work items | Temporary | Until done + short DLQ | None | Drain completed | Bounded | Prefer status cleanup |

## Authoritative — never TTL / never auto-purge

`audit_logs`, compliance decisions/evidence graph, `requirements`, `clients`, `consent_*`, `score_ledger_events`, GridFS evidence/packs, payments, users, properties, documents.

---

## Implementation

| Component | Behaviour |
|-----------|-----------|
| `services/operational_retention_purge.py` | Age-based `delete_many` in batches; protected blocklist; **dry-run unless** `MONGO_OPERATIONAL_RETENTION_PURGE_ENABLED` |
| OEP maintenance job | Warm tier (existing) + calls purge service |
| Idle persist skip | Prevents re-accumulation from 15s/30s/1m polls |

### Enablement

```text
# Staging first
MONGO_OPERATIONAL_RETENTION_PURGE_ENABLED=1
# Optional override limit for monitor
MONGO_STORAGE_LIMIT_BYTES=5368709120
```

Do **not** enable production purge until staging soak and a separate approval ticket.

---

## Warm tier vs delete

Existing `apply_warm_retention_tier` only marks events `warm` — does not free storage. Purge service is the reclaim path.
