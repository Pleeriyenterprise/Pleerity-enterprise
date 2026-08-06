# MongoDB Retention — Runtime Validation

**Audit ID:** `MONGODB-STORAGE-PREVENTION-VALIDATION-01` / Phase 5  
**Date:** 2026-08-06

---

## Dry-run (staging) — PASS

Executed `purge_aged_operational_telemetry(dry_run=True)` against `pleerity_staging`.

| Collection | Retention days | Matched | Deleted |
|------------|---------------:|--------:|--------:|
| `job_runs` | 90 | 0 | 0 |
| `operational_evidence_events` | 90 | 0 | 0 |
| `operational_evidence_executions` | 90 | 0 | 0 |
| `message_logs` | 180 | 0 | 0 |
| `reminder_evaluation_log` | 90 | **6,372** | 0 (dry-run) |
| `workflow_nudge_audit` | 90 | 0 | 0 |
| `workflow_recovery_audit` | 90 | 0 | 0 |

Flag `MONGO_OPERATIONAL_RETENTION_PURGE_ENABLED` was **off**; dry-run forced.

### Protected counts after dry-run (unchanged)

| Collection | Count |
|------------|------:|
| `audit_logs` | 191,429 |
| `clients` | 43 |
| `score_ledger_events` | 13,283 |
| `requirements` | 630 |

---

## Live run

**Not executed** in this phase.

Rationale: operating principle forbids additional deletions unless Phase 5 live is explicitly re-authorised with `--allow-retention-live`. Eligible live deletes would primarily hit aged `reminder_evaluation_log` (6,372), not Tier-1 collections (already empty).

Idempotency of double live pass: **unproven** until live enabled.

Deploy gap: retention purge is only invoked from OEP maintenance in local code — **not** on deployed SHA.

---

## Index / storage reclaim

Dry-run does not reclaim. Live reclaim for `reminder_evaluation_log` would be modest vs Flex budget. Major reclaim already achieved by prior Tier-1 remediation.

---

## Verdict

**`PASS_DRY_RUN`**. Live + idempotency + post-deploy maintenance job: **PENDING**.
