# MongoDB Storage Monitoring — Validation

**Audit ID:** `MONGODB-STORAGE-PREVENTION-VALIDATION-01` / Phase 2  
**Date:** 2026-08-06

---

## Unit classification (PASS)

| Usage % | Level | Pass |
|--------:|-------|:----:|
| 10 | ok | ✓ |
| 60 | warning | ✓ |
| 75 | attention | ✓ |
| 85 | critical | ✓ |
| 90 | platform_alert | ✓ |
| 95 | emergency | ✓ |

Incident severity contract in `mongo_storage_monitor.maybe_raise_storage_incident`:

| Level | Severity |
|-------|----------|
| critical (≥85) | P2 |
| platform_alert (≥90) | P1 |
| emergency (≥95) | P0 |

Duplicate suppression designed via fingerprint `atlas_flex_storage_pressure` / source `mongo_storage_capacity`.

---

## Live dashboard / incident exercise

| Check | Result |
|-------|--------|
| Monitor job on staging | **BLOCKED_NOT_DEPLOYED** |
| System Health `mongo_storage` field | **Absent on deployed build** |
| Control Centre platform alert | **Absent on deployed build** |
| Incident create/resolve lifecycle | **Not exercised live** (would leave stale state without deployed resolve path + would not test production code) |
| Stale alert cleanup | N/A — no live simulation performed |

---

## Verdict

**`PASS_UNIT` / `BLOCKED_NOT_DEPLOYED` for operational surfaces.**

Post-deploy required: run `mongo_storage_capacity_monitor`, temporarily lower `MONGO_STORAGE_LIMIT_BYTES` to cross bands (or inject snapshot), prove Health + Control Centre + incident upsert, then restore limit and resolve/auto-resolve incident so no stale P0/P1 remains.
