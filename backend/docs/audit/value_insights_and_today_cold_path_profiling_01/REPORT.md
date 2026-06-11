# VALUE-INSIGHTS-AND-TODAY-COLD-PATH-PROFILING-01

**Run:** `20260611T194409Z`  
**Fixture:** Nancy (`6fd5ac4c-3fd4-4112-ade7-156977deb49f`)  
**Classification:** `PROJECTION_COST_DRIFT` + `UNIFIED_TASKS_COLD_PATH_COST`  
**Method:** Staging HTTP cold/warm + local service decomposition against staging Mongo (profiling harness only; no production code changes)

## Executive summary

Phase 1 removed frontend over-fetching. **Remaining cold-path cost is backend projection work**, not raw Mongo query latency.

| Endpoint | HTTP cold | HTTP warm | Local decomposed dominant |
|----------|-----------|-----------|---------------------------|
| `GET /client/value-insights` | **57.7s** | 25.1s | `vi.unified_tasks_digest` **18.2s** |
| `GET /today/items` | **41.9s** | **10.5s** (`cache_hit: true`) | `today.unified_tasks` **22.8s** |

Local timings are lower than HTTP cold (Render worker + full entitlements path + network). Mongo `explain()` samples for Nancy are sub-second per query; **enrichment and unified-task assembly dominate**.

---

## A. Value insights — deep trace

### Authority chain (`client_value_insights_service.get_value_insights`)

1. `plan_registry.get_client_entitlements` (HTTP server path)
2. `properties.count_documents`
3. **`calculate_compliance_score`** → loads all requirements, `enrich_requirements_for_client`, projects stats, loads all documents
4. `documents.count` ×2, `work_orders.count`
5. **`get_unified_tasks_digest`** → calls **`get_unified_tasks_for_client(raw_limit=60)`** full rebuild for `urgent_count` / `upcoming_count` only

### Stage timings (local cold, Nancy)

| Stage | ms | Notes |
|-------|-----|-------|
| `vi.unified_tasks_digest` | **18,183** | `cache_hit: false`; 136 urgent / 10 upcoming |
| `vi.compliance_score.calculate` | **12,712** | 43 requirements enriched; score 38 |
| `vi.entitlements` | 206 | Harness used DB fallback (Stripe env absent locally) |
| Count queries | ~260 | properties, documents, work_orders |

**Dominant bottleneck:** `vi.unified_tasks_digest` — full unified tasks rebuild for monetisation counts.

**Top internal operations:** unified_tasks digest → compliance_score calculate → (everything else &lt;0.3s each).

See `value_insights_execution_trace.json`.

---

## B. Today items — deep trace

### Pipeline (route `GET /today/items`)

`get_unified_tasks_for_client(surface_profile=today)` ∥ `list_rent_attention_tasks` → `build_today_payload_from_unified` → stall enrichment → recovery enrichment → `merge_rent_into_today_payload`

### Stage timings (local cold, Nancy)

| Stage | ms | in → out |
|-------|-----|----------|
| **`today.unified_tasks`** | **22,783** | limit 50 → 6 task refs; 120 urgent in summary |
| `ut.freshness_block` | 9,515 | portfolio/risk/automation freshness probes |
| `today.recovery_enrichment` | 5,151 | operational recovery merge |
| `ut.priority_stream` | 4,233 | 231 priority actions |
| `ut.canonical_requirement_guard` | 2,503 | 231 → 213 tasks |
| `ut.stale_suppression_and_dedupe` | 1,520 | 213 tasks |
| `today.projection` | 23 | payload build |
| `today.rent_attention` | 179 | 12 rent tasks |

**Dominant bottleneck:** **`get_unified_tasks_for_client`** (`today.unified_tasks`), driven by freshness block + recovery enrichment + priority stream enrichment — not the today projection layer.

HTTP warm pass: **10.5s** with `freshness.cache_hit: true` (45s TTL) — confirms cache helps but cold miss remains costly.

See `today_items_execution_trace.json`.

---

## C. Cache audit

| Layer | TTL | value-insights | today/items |
|-------|-----|----------------|-------------|
| `operational_surface_cache` (in-process, per worker) | 45s | Not used by endpoint | Used via `get_unified_tasks_for_client` |
| HTTP response `freshness` | — | No cache fields | Warm: `cache_hit: true` |

- **Bypass:** `bypass_cache` exists on service layer only; not exposed on `GET /today/items`.
- **Worker-local:** Render multi-worker → repeat cold rebuilds across instances.
- **Invalidation:** `invalidate_client_operational_surfaces` on compliance-outcome mutations.

See `cache_usage_audit.json`.

---

## D. Duplicate work audit

| Duplication | Classification |
|-------------|----------------|
| value-insights rebuilds unified_tasks for 2 integers | `DUPLICATE_WORK_DRIFT` |
| value-insights runs full `calculate_compliance_score` for overdue/expiring stats | `DUPLICATE_WORK_DRIFT` |
| today + value-insights + dashboard each invoke priority stream / unified tasks independently | `DUPLICATE_WORK_DRIFT` |
| `enrich_requirements_for_client` in both compliance_score and priority_stream | `PROJECTION_COST_DRIFT` |

See `duplicate_projection_audit.json`.

---

## E. Database audit

Nancy fixture (79 requirements, 7 properties, 106 open WOs): **no full-collection scans** in sampled queries; `executionTimeMillis` ≤11ms per explain.

| Query | examined | returned | wall ms |
|-------|----------|----------|---------|
| compliance_score all requirements | 79 | 79 | 286 |
| priority_stream gap requirements | 79 | 78 | 135 |
| open work_orders | 106 | 106 | 183 |

**Conclusion:** slowness is **Python enrichment / aggregation / multi-service orchestration**, not missing indexes at Nancy scale. Classification: `DATABASE_COST_DRIFT` secondary only.

See `database_cost_audit.json`.

---

## F. Optimisation opportunities (not implemented)

Ranked by expected gain × safety:

| # | Opportunity | Est. gain | Risk | Category |
|---|-------------|-----------|------|----------|
| 1 | Derive value_insights counts from cached digest / CC summary | **18s** | LOW | cache |
| 2 | Value insights stats from persisted headline / compliance-summary slice | **13s** | MEDIUM | projection |
| 3 | Defer or cache `ut.freshness_block` + narrow recovery enrichment on today profile | **10–15s** | MEDIUM | projection |
| 4 | Portal snapshot (C1) | **45s** cross-nav | HIGH | architecture |
| 5 | Shared Redis operational cache | **35s** warm repeat | HIGH | cache |

See `optimisation_opportunities.json`.

**Estimated cold-path reduction if #1–#3 implemented (non-overlapping):** ~**25–35s** on value-insights + today local paths; HTTP gains depend on Render worker colocation.

---

## Decisions enabled (no implementation in this programme)

1. **Dominant value-insights bottleneck:** `get_unified_tasks_digest` full rebuild (`PROJECTION_COST_DRIFT` + `DUPLICATE_WORK_DRIFT`).
2. **Dominant today/items bottleneck:** `get_unified_tasks_for_client` assembly (`UNIFIED_TASKS_COLD_PATH_COST`), especially freshness + recovery + priority stream.
3. **Top three opportunities:** digest reuse for value-insights; headline stats instead of full score calc; trim today-profile freshness/recovery work.
4. **Portal snapshot:** **Still justified** as architecture play after targeted fixes — root cause is repeated cross-endpoint projections, not frontend wiring.
5. **P2 (remove CC from Today gate):** unchanged priority — today/items itself remains ~40s cold.

---

## Artifacts

| File | Purpose |
|------|---------|
| `value_insights_execution_trace.json` | Stage trace + HTTP cold/warm |
| `today_items_execution_trace.json` | Pipeline stages + HTTP cold/warm |
| `cache_usage_audit.json` | TTL and hit behaviour |
| `duplicate_projection_audit.json` | Cross-surface duplication |
| `database_cost_audit.json` | explain() samples |
| `optimisation_opportunities.json` | Ranked opportunities |
| `classifications.json` | Drift taxonomy |
| `watchlist.md` | Follow-ups |

**Re-run:** `python value_insights_and_today_cold_path_profiling_01_execute.py`

**No production code changes.**
