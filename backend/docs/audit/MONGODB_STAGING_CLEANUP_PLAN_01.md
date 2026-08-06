# MongoDB Staging Cleanup Plan

**Audit ID:** `MONGODB-STORAGE-ROOT-CAUSE-AND-CONTROLLED-CLEANUP-01`  
**Date:** 2026-08-06  
**Status:** Plan only — **no deletes until explicit approval**

---

## Verdict for staging options

| Option | Recommendation |
|--------|----------------|
| **A** Drop & recreate `pleerity_staging` | **Defer** → treat as `STAGING_REQUIRES_ARCHIVE_BEFORE_CLEANUP` |
| **B** Selective purge | **Preferred first step** → aligns with final verdict `SAFE_TO_PURGE_STAGING_SELECTIVELY` |
| **C** Archive then drop | Acceptable if product wants clean staging after B or instead of B |
| **D** Retain | Does not resolve Flex 5 GB write block |

---

## Why selective purge first

1. Staging (~2.60 GB) is larger than production (~1.42 GB) on the **same** Flex cluster.  
2. Largest reclaim is expected from derived OEP + aged `job_runs` (same growth pattern as production Atlas top-3).  
3. Full drop risks destroying staging-only seed data, Zoho sync state, test tenants used for demos, and any formal certification artefacts still only in Mongo.  
4. Many certification programmes already wrote **markdown/JSON under `backend/docs/audit/`** — OEP/job_runs history is largely re-derivable telemetry, not the formal evidence pack itself.

---

## Formal evidence that must be preserved *outside Mongo* before any full drop (Option A/C)

Export or confirm already archived:

| Artefact class | Why | Likely location today |
|----------------|-----|------------------------|
| Zoho CRM / integration certification packs | Formal programme evidence | `docs/audit/**` + any Mongo cert run rows |
| CIE / compliance intelligence validation reports | Formal | `docs/audit/**` |
| Commercial entitlement / lifecycle cert outputs | Formal | `docs/audit/**` |
| OEP certification / timeline verification reports | Formal (docs) vs raw events (DB) | Prefer docs; DB events are derived |
| Staging owner/admin credentials seed notes | Ops continuity | Secrets managers / runbooks — not DB dumps in git |
| Stripe test-mode linkage / webhook secrets | Ops | Env secrets — not Mongo purge target |
| Sample tenant property/requirement fixtures used for demos | Product demos | Export JSON if unique to staging |

**Protected until proven disposable:** payment records, authority/governance rows, audit_logs, vault evidence, user PII, Zoho tokens.

---

## Proposed deletion set (staging only — for approval)

### Tier 1 — Immediate reclaim (recommended)

| Collection | Predicate (proposed) | Reason | Exclusion |
|------------|----------------------|--------|-----------|
| `operational_evidence_events` | `occurred_at` / `recorded_at` older than **14 days** (or all if product accepts) | Derived; unbounded; largest data+index | Keep annotations linkage if needed; prefer delete events first |
| `operational_evidence_executions` | Orphaned or all matching purged event roots; or **all** if events fully rebuilt later | Derived registry | None critical |
| `operational_evidence_annotations` | Optional: export then delete with events | Admin notes | Export CSV/JSON first |
| `job_runs` | `created_at` older than **30 days** | Ops log; not compliance SoR | Keep last 30d for staging debug |

### Tier 2 — Secondary (only after Tier 1 dry-run)

| Collection | Predicate | Reason |
|------------|-----------|--------|
| Regenerable insight/cache collections | All staging | Derived |
| Dead queue items older than 7d | Aged | Temporary |
| Explicit `tmp_` / probe collections if any | All | Test-only |

### Explicitly out of scope (this incident)

- Any operation against `pleerity_production`
- Drop of entire staging database without archive checklist complete
- Deletion of users, clients, properties, requirements, evidence, payments, audit_logs, entitlements

---

## Report-only cleanup utility (design — do not implement until approved)

**Proposed path:** `backend/scripts/mongodb_controlled_cleanup_01.py` (or `tools/`)

### Hard requirements

| Control | Spec |
|---------|------|
| Default mode | `--dry-run` (default **true**) |
| Env allowlist | `--environment staging` only |
| DB allowlist | `--db-name pleerity_staging` only |
| Production refuse | Abort if `DB_NAME == pleerity_production` or env == production |
| Execution | Deletes only if `--execute-deletes YES_I_APPROVED_STAGING_PURGE` (exact string) |
| Batches | `--batch-size` default 500–1000; max cap |
| Checkpoint | Write `mongodb_cleanup_checkpoint_01.json` with last `_id` / timestamp |
| Output | Counts, min/max dates, estimated data bytes (collStats), estimated index bytes, sample `_id`/`event_id`/`job_run_id`, reason codes, protected exclusions |
| Before/after | `collStats` snapshot to `mongodb_cleanup_evidence_*.json` |
| Logging | Structured JSON lines; no secrets |

### Dry-run report fields (per collection)

```json
{
  "collection": "operational_evidence_events",
  "match_count": 0,
  "date_range": {"min": null, "max": null},
  "estimated_storage_bytes": null,
  "estimated_index_bytes": null,
  "sample_ids": [],
  "reason": "derived_oep_unbounded_retention",
  "protected_excluded_count": 0,
  "would_delete": true
}
```

---

## Expected reclaim (order-of-magnitude — confirm with dry-run `collStats`)

| Target | Staging hypothesis |
|--------|--------------------|
| OEP events + indexes | Likely **largest** share of staging 2.60 GB |
| Aged job_runs | Secondary large reclaim |
| Combined effect | Aim to free **>1 GB** cluster headroom so production writes resume |

Exact bytes **must** come from dry-run against live staging (not estimated here as authoritative).

---

## Execution sequence (when approved)

1. Snapshot Atlas metrics (logical size, index size) — screenshot/export.  
2. Run utility dry-run → attach report to approval ticket.  
3. Product/ops approve deletion set.  
4. Run with execute flag during maintenance window.  
5. Confirm writes unblocked; admin login recovers.  
6. Enable retention/TTL prevention (see `MONGODB_RETENTION_POLICY_01.md`).  
7. Schedule cluster separation project.

---

## Confirmation

No cleanup executed in this phase. Production untouched.
