# Discovery Feature Flags Governance

```yaml
---
Status: ACTIVE
Authority Level: TIER_1
Related:
  - docs/launch/DISCOVERY_PHASE_1_LAUNCH_GATE.md
  - docs/DISCOVERY_FOUNDATION_ARCHITECTURE.md
Last Review: 2026-06-02
---

```

## 1. Rule

**All discovery flags default `false` in production** until `DISCOVERY_PHASE_1_LAUNCH_GATE.md` GO sign-off.

Staging may enable flags for validation only after Tracker Stage W prerequisites met.

Develop: flags may be enabled locally for implementation testing.

---

## 2. Phase 1 flags

| Flag | Env var | Default | Purpose |
|------|---------|---------|---------|
| `DISCOVERY_MODULE_ENABLED` | `DISCOVERY_MODULE_ENABLED` | `false` | Master gate — all discovery routes return 404 when false |
| `DISCOVERY_PROVIDER_LAYER_ENABLED` | `DISCOVERY_PROVIDER_LAYER_ENABLED` | `false` | Enables provider protocol + registry |
| `DISCOVERY_CSV_IMPORT_ENABLED` | `DISCOVERY_CSV_IMPORT_ENABLED` | `false` | CSV upload endpoint |
| `DISCOVERY_PROVIDER_CSV_ENABLED` | `DISCOVERY_PROVIDER_CSV_ENABLED` | `false` | CSV provider adapter |
| `DISCOVERY_AUTO_IMPORT_ON_APPROVE` | `DISCOVERY_AUTO_IMPORT_ON_APPROVE` | `true` | When module enabled: approve triggers import (still via DiscoveryImportService) |

**Flag dependency chain:**

```
DISCOVERY_MODULE_ENABLED
  └── DISCOVERY_PROVIDER_LAYER_ENABLED
        └── DISCOVERY_PROVIDER_CSV_ENABLED
              └── DISCOVERY_CSV_IMPORT_ENABLED
```

Manual import follows `DISCOVERY_MODULE_ENABLED` + `DISCOVERY_PROVIDER_LAYER_ENABLED` (no separate flag Phase 1).

---

## 3. Reserved Phase 2 flags (must remain false in Phase 1)

| Flag | Default | Provider |
|------|---------|----------|
| `DISCOVERY_PROVIDER_TWIN_ENABLED` | `false` | Twin orchestration ingest |
| `DISCOVERY_PROVIDER_APOLLO_ENABLED` | `false` | Apollo API |
| `DISCOVERY_PROVIDER_CLAY_ENABLED` | `false` | Clay table sync |
| `DISCOVERY_PROVIDER_INTERNAL_CRAWLER_ENABLED` | `false` | Internal web crawler |

Enabling any Phase 2 flag requires:

1. ADR amendment
2. Compliance sign-off (transfer basis for US providers)
3. Updated anti-lock-in checklist
4. New launch gate or Phase 2 gate

---

## 4. Operational flags (optional)

| Flag | Default | Purpose |
|------|---------|---------|
| `DISCOVERY_RETENTION_SWEEP_ENABLED` | `false` | Daily retention job |
| `DISCOVERY_SUPPRESSION_BLOCK_MODE` | `false` | `true` = block import on suppression hit; `false` = flag only |

---

## 5. Implementation location

- Read from `os.environ` with helper `discovery_config.py`
- Expose read-only status on `GET /api/admin/discovery/config` (admin only)
- Register in ops feature flag UI if platform pattern requires (audited `FEATURE_FLAG_CHANGED`)

---

## 6. Rollback

1. Set `DISCOVERY_MODULE_ENABLED=false` — immediate 404 on all discovery endpoints
2. No data mutation on rollback
3. Existing prospects/leads unchanged
4. Verify: legacy CSV import remains 410/redirect

---

## 7. Launch gate linkage

Production enablement order:

1. `DISCOVERY_MODULE_ENABLED=true`
2. `DISCOVERY_PROVIDER_LAYER_ENABLED=true`
3. `DISCOVERY_PROVIDER_CSV_ENABLED=true`
4. `DISCOVERY_CSV_IMPORT_ENABLED=true`

**NO-GO** if any Phase 2 provider flag is `true` during Phase 1 launch.
