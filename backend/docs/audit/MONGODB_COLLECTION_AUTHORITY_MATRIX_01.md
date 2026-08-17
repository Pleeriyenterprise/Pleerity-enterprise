# MongoDB Collection Authority Matrix

**Audit ID:** `MONGODB-STORAGE-ROOT-CAUSE-AND-CONTROLLED-CLEANUP-01`  
**Date:** 2026-08-06  
**Scope:** Both `pleerity_production` and `pleerity_staging` (same collection names; authority identical by code)

Legend:

| Class | Meaning |
|-------|---------|
| **A** Authoritative SoR | Source of truth for product/compliance/commerce |
| **D** Derived | Rebuildable index / projection |
| **O** Operational | Runtime ops telemetry; useful but not legal SoR |
| **T** Temporary / queue | Short-lived work items |
| **X** Test / fixture | Expected only in non-prod |

---

## Priority growth collections (incident focus)

| Collection | Class | Writers (code) | Readers | Recreated? | Cross-refs | Delete risk | Retention today | TTL? | Staging purge? |
|------------|-------|----------------|---------|------------|------------|-------------|-----------------|------|----------------|
| `operational_evidence_events` | **D** | `emit_service.emit_operational_evidence`; producers from job_runner, queues, notifications, incidents, scores; `backfill_service` | OEP query/story/portfolio APIs; Control Centre evidence UX | Yes — backfill + live emit | Points **to** source_collection/source_id; not required by those sources | Low for ops SoR; loses investigation UX history | Warm tier @ 90d (hide only) | **No** | **Yes (selective, aged)** |
| `operational_evidence_executions` | **D** | `_upsert_execution_summary` on emit | Story/tree roots | Yes — rebuilt as events emit | `root_execution_id` | Low | None | **No** | **Yes** with events |
| `operational_evidence_annotations` | **O** | Admin annotation APIs | OEP UI | No (manual) | event_id | Medium — admin notes lost | None | **No** | Export then purge if needed |
| `job_runs` | **O** | `job_run_service.start_job_run` / finish_* | Admin jobs UI, OEP backfill, health | No — historical | Referenced by OEP as source | Medium — ops history / SLA forensics; **not** payment/compliance SoR | None | **No** | **Yes (aged)**; keep recent N days |
| `job_run_failures` / failure detail (if present) | **O** | job_run finish failure paths | Admin | With job_runs | job_run_id | Medium | None | Check | With aged job_runs |

---

## Authoritative / protected families (do not purge without legal/product sign-off)

| Collection / family | Class | Notes | Staging reset safe? |
|---------------------|-------|-------|---------------------|
| `users`, auth/sessions, refresh tokens | **A** | Login; capacity errors → 500 | No full wipe without rebuild |
| `clients`, `properties`, `requirements`, applicability | **A** | Compliance core | Archive first |
| Evidence / documents / vault / classify / match collections | **A** | Compliance evidence SoR | **Protected** |
| `score_ledger_events`, score snapshots | **A**/**O** | Scoring authority / history | Protect; OEP only indexes |
| `audit_logs`, security events, admin action logs | **A**/**O** | Audit | **Protected** |
| Stripe / payments / invoices / entitlements / sponsorships | **A** | Commerce | **Protected** |
| Lifecycle / authority / governance rows | **A** | Commercial + client lifecycle | **Protected** |
| `incidents` | **O**/**A** hybrid | Ops SoR for incident lifecycle | Prefer retain; OEP is derived |
| `message_logs` / notification logs | **O** | Delivery evidence | Prefer retain aged selectively |
| Zoho / CRM integration state, tokens | **A** | Credentials + sync state | **Protected**; tokens sensitive |
| Orders / work orders / contractors | **A** | Ops + commercial | Archive before wipe |
| Legal content / published packs | **A** | Published content | Protect |

---

## Operational / queue / telemetry (candidates for bounded retention)

| Collection | Class | Expected retention (proposed) | Notes |
|------------|-------|-------------------------------|-------|
| `job_runs` | **O** | 30–90 days hot; archive optional | Bound urgently |
| `operational_evidence_*` | **D** | 14–90 days raw; roll-up summaries | Derived |
| Scheduler heartbeat / health snapshots | **O** | 7–30 days | Low value long-term |
| Compliance recalc queues | **T** | Until processed + short dead-letter | |
| Risk signal regen queues | **T** | Short | |
| Predictive insights / risk signal caches | **D** | Regenerable | Safe to purge staging |
| Temporary certification probe collections | **X** | Staging only | Prefer delete after export |

---

## Index ownership note

Indexes are created centrally in `database.py` `_create_indexes` on every connect. Both environments get the full set → **~900 indexes per DB**. Purging large collections reclaims index bytes as documents shrink; unused indexes should be reviewed separately (query-path audit) before dropping index definitions.

---

## Staging reset safety (matrix summary)

| Option | Safe? | Condition |
|--------|-------|-----------|
| A Drop & recreate entire `pleerity_staging` | **Not yet** | Requires archive of A-class + formal cert artefacts |
| B Selective purge OEP + aged job_runs | **Yes** | Dry-run report + allowlist + refuse production |
| C Archive then drop | **Yes** | After export of A-class / cert-only Mongo artefacts |
| D Retain staging as-is | Unblocks nothing | Cluster remains full |

See `MONGODB_STAGING_CLEANUP_PLAN_01.md`.
