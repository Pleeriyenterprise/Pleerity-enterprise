# REQUIREMENT-RECONCILIATION-AUTHORITY-01

**Programme:** REQUIREMENT-RECONCILIATION-AUTHORITY-01  
**Branch:** `develop` only  
**Verdict:** Implementation complete — staging dry-run validated; execute on staging before production  
**Date:** 2026-06-30  
**Production:** Not touched. Not merged to `main`.

---

## Executive summary

RAOD-01 fixed **runtime authority** (alias dedupe, risk semantics, count disclosure). Staging validation confirmed **27 legacy duplicate active rows** across **26 alias-family groups** still exist in `pleerity_staging` Mongo while runtime surfaces already show one row per obligation.

This programme adds an **idempotent, non-destructive reconciliation service** that:

- Detects active duplicate rows sharing an alias family on the same `(client_id, property_id)`
- Selects the canonical survivor using the same precedence as `requirement_client_runtime_surface` dedupe
- Archives superseded rows via `registry_metadata.lifecycle.status = superseded` + `authority_reconciliation` block
- Preserves document IDs, status, applicability, and all historical fields on archived rows
- Writes audit log entries per archived row

**No documents are deleted.**

---

## Governance basis

| Document / module | Role |
|-------------------|------|
| `backend/docs/COMPLIANCE_CLIENT_STATUS_AUTHORITY.md` | KPI/runtime authority chain; archived metadata excluded from surfaces |
| `backend/docs/audit/requirement_authority_onboarding_drift_01/*` | RAOD-01 audit; reconcile required before production |
| `services/requirement_client_runtime_surface.py` | Alias families + dedupe rank (source of truth for survivor selection) |
| `services/requirement_action_resolver.py` | Wales `occupation_contract` → `wales_occupation_contract` alias in Wales context |
| `services/requirement_materialization_service.py` | Prior pattern: `reconciled_obsolete` without delete (NOT_REQUIRED path — distinct from alias supersede) |

Canonical selection order (mirrors runtime dedupe):

1. Published-enriched registry metadata  
2. Evidence / tracking present  
3. Recency (`updated_at`)  
4. Catalog slug preference per alias family  
5. Jurisdiction fit (e.g. penalize `wales_occupation_contract` on non-Wales properties)

---

## Implementation

| Component | Path |
|-----------|------|
| Governance constants | `services/requirement_authority_reconciliation_governance.py` |
| Reconciliation service | `services/requirement_authority_reconciliation_service.py` |
| CLI runner (`--dry-run`, `--execute`, `--idempotency-check`) | `scripts/requirement_authority_reconciliation_01.py` |
| Regression tests | `tests/test_requirement_authority_reconciliation_01.py` |

### Archive metadata (per superseded row)

```json
{
  "registry_metadata": {
    "lifecycle": { "status": "superseded" },
    "lifecycle_status": "superseded",
    "authority_reconciliation": {
      "archive_reason": "superseded_alias_duplicate",
      "archive_source": "REQUIREMENT-RECONCILIATION-AUTHORITY-01",
      "canonical_requirement_id": "<winner>",
      "canonical_requirement_code": "<code>",
      "alias_family": "<family>",
      "reconciled_at": "<iso>",
      "reconciled_by": "<actor>",
      "previous_lifecycle": "<prior>",
      "new_lifecycle": "superseded",
      "reconciliation_version": "1"
    }
  }
}
```

Audit action: `REQUIREMENTS_EVALUATED` with `reason_code=AUTHORITY_ALIAS_RECONCILE`.

---

## Staging dry-run (pleerity_staging)

```bash
cd backend
python scripts/requirement_authority_reconciliation_01.py --dry-run
```

| Metric | Before | After (simulated) |
|--------|--------|-------------------|
| Total requirement rows | 613 | 613 |
| Active alias-family rows | 161 | 134 |
| Duplicate active groups | 26 | 0 |
| Rows to archive | — | 27 |

Families observed: `wales_occupation_contract_alias_family`, `hmo_fire_risk_alias_family`, `fire_detection_alias_family`, `tenancy_deposit_alias_family`, `right_to_rent_alias_family`.

Evidence: `REQUIREMENT_RECONCILIATION.json`, `REQUIREMENT_RECONCILIATION_REPORT.md`

---

## Tests

```bash
python -m pytest tests/test_requirement_authority_reconciliation_01.py -v
python -m pytest tests/test_requirement_authority_onboarding_drift_01.py -v
```

**16/16 passed** (11 reconciliation + 5 RAOD regression).

Coverage includes: single/multiple duplicate families, Wales vs England jurisdiction, dry-run (no writes), execute + audit, idempotent second run, already-superseded skip, no-duplicate dataset, large portfolio scan, runtime filter count unchanged after reconcile.

---

## Production readiness recommendation

| Step | Status |
|------|--------|
| Dry-run on staging | Done |
| Execute on staging with `--execute --idempotency-check` | **Required before production** |
| Verify HTTP/runtime counts unchanged post-execute | Required |
| Production execute during controlled window | After staging execute + sign-off |
| Merge to `main` | Not until staging execute validated |

**Safe to execute on staging** — reconciliation aligns Mongo with runtime authority already deployed in RAOD-01 (`0b1887a2`). Runtime behaviour should remain unchanged because archived rows were already excluded by alias dedupe or will match dedupe output.

**Do not run on production** until staging execute + idempotency check passes.

---

## Commands reference

```bash
# Analysis only (no writes)
python scripts/requirement_authority_reconciliation_01.py --dry-run

# Single client
python scripts/requirement_authority_reconciliation_01.py --dry-run --client-id <uuid>

# Apply archives + verify idempotency
python scripts/requirement_authority_reconciliation_01.py --execute --idempotency-check
```
