# MongoDB Top-20 Storage Ranking (Production + Staging)

**Audit ID:** `MONGODB-STORAGE-ROOT-CAUSE-AND-CONTROLLED-CLEANUP-01` (extension)  
**Date:** 2026-08-06  
**Mode:** Read-only (`collStats` only — **no deletes**)  
**Metric:** `size` (logical document bytes) + `totalIndexSize`  
**Source snapshots:**  
- `mongodb_collstats_pleerity_production_01.json`  
- `mongodb_collstats_pleerity_staging_01.json`

**Cluster totals (sum of all collections, same metric):**

| Database | Collections | Total size+indexes |
|----------|-------------|--------------------|
| `pleerity_production` | 224 | **1.92 GB** (1,915,228,493 B) |
| `pleerity_staging` | 264 | **3.45 GB** (3,453,474,384 B) |
| **Combined** | — | **~5.37 GB** (explains Flex 5 GB write block) |

**Authority classes:** A = authoritative · D = derived · O = operational · T = temporary · X = test-only

**Recoverable estimate:** logical `size + totalIndexSize` if that collection were fully purged (WiredTiger may reclaim disk asynchronously; Atlas logical/index accounting is what hits Flex limits). Aged-only purge would reclaim less — noted where relevant.

---

## Production — Top 20 by size + indexes

| Rank | Collection | Docs | Data | Indexes | **Total** | Class | Auto-recreated? | Recoverable if purged | Recommended retention |
|------|------------|------|------|---------|-----------|-------|-----------------|----------------------|------------------------|
| 1 | `operational_evidence_events` | 495,814 | 886.1 MB | 336.0 MB | **1,222.0 MB** | **D** | Yes (live emit + backfill) | **~1,222 MB** (full); aged 90d+ still majority | Hot 30d / delete or archive >90d |
| 2 | `job_runs` | 611,973 | 382.6 MB | 111.1 MB | **493.7 MB** | **O** | Yes (every instrumented job) | **~494 MB** full; keep 30–60d → large fraction | 60–90 days detail |
| 3 | `operational_evidence_executions` | 245,147 | 122.7 MB | 27.0 MB | **149.7 MB** | **D** | Yes (upsert on emit) | **~150 MB** with events | Align with OEP events |
| 4 | `security_events` | 16,162 | 5.5 MB | 5.2 MB | **10.7 MB** | **O**/A-adjacent | Yes (auth/security paths) | Low priority; protect login/security forensics | 180–365 days |
| 5 | `message_logs` | 1,370 | 6.4 MB | 0.7 MB | **7.1 MB** | **O** | Yes (notification sends) | Small; delivery forensics | 90–180 days |
| 6 | `audit_logs` | 5,375 | 3.0 MB | 1.1 MB | **4.1 MB** | **A** | Yes (audited actions) | **Do not purge** without legal schedule | Per compliance policy (multi-year typical) |
| 7 | `reminder_evaluation_log` | 1,918 | 1.1 MB | 0.5 MB | **1.6 MB** | **O** | Yes (reminder job) | ~1.6 MB | 30–90 days |
| 8 | `score_ledger_events` | 1,033 | 0.9 MB | 0.4 MB | **1.2 MB** | **A** | Yes (score authority) | **Protected** | Legal/product score history |
| 9 | `lead_events` | 1,222 | 0.5 MB | 0.7 MB | **1.2 MB** | **O** | Yes (lead funnel) | Small | 180 days / marketing policy |
| 10 | `compliance_recalc_queue` | 1,013 | 0.7 MB | 0.3 MB | **1.0 MB** | **T** | Yes (enqueue worker) | ~1.0 MB if drained/aged | Processed + 7–14d DLQ |
| 11 | `property_compliance_score_history` | 1,043 | 0.5 MB | 0.3 MB | **0.8 MB** | **O**/D | Yes (snapshots/history) | Small | 1–2 years or roll-up |
| 12 | `requirements` | 110 | 0.3 MB | 0.5 MB | **0.8 MB** | **A** | Seeded/managed | **Do not purge** | Permanent product data |
| 13 | `incidents` | 132 | 0.4 MB | 0.3 MB | **0.7 MB** | **O**/A | Yes (incident lifecycle) | Protect recent; archive old | 1–2 years ops |
| 14 | `order_files.chunks` | 6 | 0.6 MB | 0.1 MB | **0.6 MB** | **A** | With orders (GridFS) | **Protected** | With order retention |
| 15 | `score_events` | 1,047 | 0.5 MB | 0.2 MB | **0.6 MB** | **O**/D | Yes | Small | Align with score history |
| 16 | `clients` | 6 | 0.04 MB | 0.6 MB | **0.6 MB** | **A** | No (tenant SoR) | **Do not purge** (index-heavy empty-ish) | Permanent |
| 17 | `consent_events` | 342 | 0.2 MB | 0.3 MB | **0.6 MB** | **A** | Yes (consent trail) | **Protected** | Legal retention |
| 18 | `score_change_log` | 1,043 | 0.4 MB | 0.1 MB | **0.5 MB** | **O**/D | Yes | Small | 90–365 days |
| 19 | `consent_state` | 314 | 0.1 MB | 0.3 MB | **0.5 MB** | **A** | Yes (current consent) | **Protected** | Permanent while subject exists |
| 20 | `work_orders` | 1 | ~0 MB | 0.4 MB | **0.4 MB** | **A** | No | **Do not purge** (indexes dominate) | Permanent product data |

### Production concentration

| Slice | Total | Share of DB |
|-------|-------|-------------|
| Ranks 1–3 (OEP + job_runs) | **1,865.5 MB** | **~97.4%** |
| Ranks 4–20 | **~34 MB** | **~1.8%** |

Production reclaim outside ranks 1–3 is negligible for the Flex incident.

---

## Staging — Top 20 by size + indexes

| Rank | Collection | Docs | Data | Indexes | **Total** | Class | Auto-recreated? | Recoverable if purged | Recommended retention |
|------|------------|------|------|---------|-----------|-------|-----------------|----------------------|------------------------|
| 1 | `job_runs` | 1,937,891 | 1,083.6 MB | 322.1 MB | **1,405.7 MB** | **O** | Yes | **~1,406 MB** full; >30d purge recovers most | 30 days on staging |
| 2 | `operational_evidence_events` | 543,702 | 999.1 MB | 360.4 MB | **1,359.5 MB** | **D** | Yes | **~1,360 MB** | 14–30 days on staging |
| 3 | `audit_logs` | 191,429 | 97.8 MB | 26.1 MB | **123.9 MB** | **A** | Yes | Archive before any purge; **not** Tier-1 | Keep / export then age |
| 4 | `operational_evidence_executions` | 150,211 | 75.2 MB | 17.7 MB | **92.9 MB** | **D** | Yes | **~93 MB** with events | Align with OEP |
| 5 | `message_logs` | 17,111 | 82.8 MB | 4.6 MB | **87.4 MB** | **O** | Yes | ~87 MB if aged purge OK | 30–90 days staging |
| 6 | `security_events` | 127,732 | 43.6 MB | 33.6 MB | **77.2 MB** | **O**/A-adjacent | Yes | Prefer retain or export; secondary reclaim | 90–180 days staging |
| 7 | `lead_events` | 43,161 | 19.2 MB | 14.3 MB | **33.5 MB** | **O** | Yes | ~33 MB | 90 days staging |
| 8 | `compliance_decisions` | 10,824 | 24.5 MB | 5.1 MB | **29.5 MB** | **A** | Materialised by engine | **Protected** unless fixture-only proven | Product retention |
| 9 | `compliance_evidence_nodes` | 21,646 | 17.2 MB | 10.7 MB | **27.9 MB** | **A**/D hybrid | Materialised | Treat as **protected** evidence graph | Product retention |
| 10 | `compliance_decision_snapshots` | 10,823 | 21.9 MB | 4.8 MB | **26.7 MB** | **A** | With decisions | **Protected** | Product retention |
| 11 | `compliance_evidence_edges` | 10,823 | 10.3 MB | 7.7 MB | **18.0 MB** | **A**/D hybrid | Materialised | **Protected** | Product retention |
| 12 | `workflow_nudge_audit` | 43,444 | 16.0 MB | 0.7 MB | **16.7 MB** | **O** | Yes | ~17 MB | 30–90 days |
| 13 | `score_ledger_events` | 13,283 | 11.7 MB | 4.0 MB | **15.7 MB** | **A** | Yes | **Protected** | Score authority |
| 14 | `reminder_evaluation_log` | 18,283 | 10.4 MB | 2.8 MB | **13.2 MB** | **O** | Yes | ~13 MB | 30 days staging |
| 15 | `compliance_recalc_queue` | 12,983 | 7.8 MB | 1.7 MB | **9.5 MB** | **T** | Yes | ~9.5 MB | Drain + 7d |
| 16 | `workflow_recovery_audit` | 26,591 | 8.7 MB | 0.5 MB | **9.2 MB** | **O** | Yes | ~9 MB | 30–90 days |
| 17 | `property_compliance_score_history` | 13,550 | 6.9 MB | 2.1 MB | **9.0 MB** | **O**/D | Yes | Small | 90–365 days |
| 18 | `compliance_audit_packs.chunks` | 65 | 7.9 MB | 0.1 MB | **8.0 MB** | **A** | On pack generate (GridFS) | Export packs before purge | Keep pack artefacts |
| 19 | `score_events` | 12,889 | 5.7 MB | 0.8 MB | **6.4 MB** | **O**/D | Yes | ~6 MB | Align with scores |
| 20 | `score_change_log` | 13,534 | 5.8 MB | 0.3 MB | **6.1 MB** | **O**/D | Yes | ~6 MB | 90 days staging |

### Staging concentration

| Slice | Total | Share of DB |
|-------|-------|-------------|
| Ranks 1–2 (`job_runs` + OEP events) | **2,765.2 MB** | **~80.1%** |
| Ranks 1–4 (+ executions + audit_logs) | **2,982.0 MB** | **~86.3%** |
| Compliance decision/evidence cluster (8–11) | **~102 MB** | **~3.0%** — **do not treat as disposable telemetry** |

---

## Cross-environment comparison (same collections)

| Collection | Prod total | Staging total | Staging / Prod |
|------------|------------|---------------|----------------|
| `job_runs` | 493.7 MB | **1,405.7 MB** | **2.8×** (1.94M vs 612k docs) |
| `operational_evidence_events` | 1,222.0 MB | 1,359.5 MB | 1.1× |
| `operational_evidence_executions` | 149.7 MB | 92.9 MB | 0.6× |
| `audit_logs` | 4.1 MB | **123.9 MB** | **30×** |
| `security_events` | 10.7 MB | **77.2 MB** | **7×** |
| `message_logs` | 7.1 MB | **87.4 MB** | **12×** |

Staging inflation is dominated by **job_runs** volume (certification / long-running schedulers / test load), then OEP, then audit/security/message amplification.

---

## Classification quick reference (top offenders)

| Class | Collections in top ranks | Purge posture |
|-------|--------------------------|---------------|
| **Derived (D)** | `operational_evidence_events`, `operational_evidence_executions` | Highest reclaim; safe after dry-run on **staging** |
| **Operational (O)** | `job_runs`, `message_logs`, reminder/workflow logs, lead_events | High reclaim if aged; keep short window |
| **Temporary (T)** | `compliance_recalc_queue` | Safe to drain/age |
| **Authoritative (A)** | `audit_logs`, score ledger, compliance decisions/nodes/edges/snapshots, requirements, clients, consent, GridFS packs/orders | **No emergency purge**; archive first if ever cleaned |
| **Test-only (X)** | None in either top 20 under that name | — |

---

## Recommended reclaim priority (still no deletes)

1. **Staging** `job_runs` + `operational_evidence_events` + `operational_evidence_executions` → **~2.86 GB** logical if fully purged (Tier-1).  
2. **Staging** aged `message_logs` / workflow audit logs → secondary (~100 MB class).  
3. **Do not** include staging `audit_logs`, compliance decision/evidence graph, or GridFS packs in Tier-1.  
4. **Production:** same Tier-1 classes only after staging frees the cluster and retention is implemented — not in this report’s execution scope.

---

## Method notes

- Ranking uses MongoDB `collStats.size + collStats.totalIndexSize` (matches Atlas “logical data + indexes” style accounting better than `storageSize` alone).  
- `storageSize` is lower due to compression; Flex limit tracking follows logical/index accounting used in the incident.  
- No documents were deleted; no indexes dropped; no Atlas settings changed.
