# REQUIREMENT-AUTHORITY-PRODUCTION-PROMOTION-01

**Verdict:** **`PRODUCTION_PROMOTION_SUCCESSFUL`**
**Run:** 20260630T153435Z
**Programme:** RAOD authority fixes + requirement reconciliation (archive-only)

---

## Executive summary

Validated Requirement Authority and Reconciliation work was **scoped-promoted** from `develop` (`5063280b`) to `main` using **cherry-pick of four commits only**. A full `develop` → `main` merge was **rejected** because `develop` is 24 commits ahead of `main`, including unvalidated CEG/CIE/OEP programmes outside this gate.

Production deploy completed. `/api/version` reports promoted SHA `3c87941c`. Production smoke checks pass. Production reconciliation **execute was not run**. Production dry-run was **skipped** locally (operator credentials target `pleerity_staging` only).

---

## Source and promotion SHAs

| Field | SHA |
|-------|-----|
| Validated develop head | `5063280b5eea5ae0f41a6faaa0bad326724e75e3` |
| `main` before promotion | `9755ccfa09d444821d0fee38dcf8e35248da187c` |
| `main` after promotion | `3c87941ceb87d5830a3e356bc98aeef311b70628` |
| Production deployed SHA | `3c87941ceb87d5830a3e356bc98aeef311b70628` |

### Promotion strategy

**Cherry-pick (scoped)** — preserves identical patches to develop validation commits; avoids 20 out-of-scope commits on `develop` (CEG, CIE, OEP, etc.).

| develop | main | Message |
|---------|------|---------|
| `0b1887a2` | `bdda2c8d` | fix(requirements): align onboarding authority and runtime risk semantics |
| `6f20d5cc` | `18fa6a22` | docs(requirements): add post-deploy staging validation evidence |
| `c93a014b` | `54ef956b` | fix(requirements): add authority reconciliation for alias duplicates |
| `5063280b` | `3c87941c` | docs(requirements): add post-reconciliation staging validation evidence |

---

## Pre-flight checks

| Check | Result |
|-------|--------|
| Branch: promotion executed from clean `main` checkout | PASS |
| develop contains `0b1887a2`, `6f20d5cc`, `c93a014b`, `5063280b` | PASS |
| Full develop→main merge would include out-of-scope work | **BLOCKED** — 20 extra commits; scoped cherry-pick used instead |
| lifecycle_kpi_gates.py excluded (stashed, not promoted) | PASS |
| test_lifecycle_kpis_p5_s3_authority_regression.py excluded | PASS |
| Unrelated tmp scripts excluded | PASS |
| Staging API version ≥ `c93a014b` | PASS — staging at `5063280b` |
| Staging validation evidence | PASS — `STAGING_VALIDATION_ACCEPTED`, `duplicate_active_groups_staging: 0`, `authority_superseded_rows_staging: 27`, `reconcile_required_before_production: false` |

---

## Files included (20 paths)

- `backend/routes/portal.py`
- `backend/services/provisioning.py`
- `backend/services/requirement_client_runtime_surface.py`
- `backend/services/risk_signal_service.py`
- `backend/services/requirement_authority_reconciliation_governance.py`
- `backend/services/requirement_authority_reconciliation_service.py`
- `backend/scripts/requirement_authority_reconciliation_01.py`
- `backend/tests/test_requirement_authority_onboarding_drift_01.py`
- `backend/tests/test_requirement_authority_reconciliation_01.py`
- `backend/tmp_requirement_authority_staging_validation_01.py`
- `backend/docs/audit/requirement_authority_onboarding_drift_01/*` (4 files)
- `backend/docs/audit/requirement_reconciliation_authority_01/*` (6 files)

## Files explicitly excluded

- `backend/services/lifecycle_kpi_gates.py`
- `backend/tests/test_lifecycle_kpis_p5_s3_authority_regression.py`
- All CEG / CIE / OEP commits on develop (not cherry-picked)
- All unrelated tmp scripts and audit artefacts
- `render.production.yaml`, `render.staging.yaml`, `render.yaml` — **unchanged**

---

## Production environment verification

| Check | Result |
|-------|--------|
| `/api/version` environment | `production` |
| `/api/health` environment | `production` |
| Render manifest DB_NAME (production) | `pleerity_production` (unchanged) |
| Render manifest STRIPE_MODE (production) | `live` (unchanged) |
| Frontend bundle uses prod API | PASS — `api.pleerityenterprise.co.uk` |
| Frontend bundle references staging API | PASS — absent |
| Local operator DB | `pleerity_staging` (isolated from production) |
| Production env vars modified | **NO** |

---

## Production smoke results

| Check | Result |
|-------|--------|
| API health | **200** — healthy |
| `/api/version` SHA | **3c87941c** |
| Homepage | **200** |
| Setup-status endpoint reachable | **400** without client_id (expected) |
| Requirements API unauthenticated | **401** |
| Dashboard API unauthenticated | **401** |
| Local RAOD pytest (17 tests) | **PASS** |

### Deferred (non-blocking)

- **Setup-status semantic fields on live production client** — requires production pilot `client_id` / portal JWT (credentials not in operator environment).
- **EICR PENDING-only shadow on production Mongo** — requires production DB read access.
- **Runtime superseded-row dedupe on production data** — code deployed; Mongo shadow not run locally.

---

## Production reconciliation

| Step | Status |
|------|--------|
| Execute reconciliation | **NOT RUN** (per policy) |
| Dry-run | **SKIPPED** — local `DB_NAME=pleerity_staging`; production Mongo credentials unavailable locally |

**Recommendation:** Before any production execute approval, run from a secure operator shell with `pleerity_production` credentials:

```bash
cd backend
python scripts/requirement_authority_reconciliation_01.py --dry-run
```

Review `duplicate_active_groups`, `records_to_archive`, affected families, and client/property counts. **Stop and report** if duplicates found; do not execute without explicit approval.

Staging reference (already executed): 27 rows archived, 26 groups, idempotency pass.

---

## Remaining risks

1. **Production Mongo duplicate state unknown** until production dry-run completes.
2. **Authenticated production requirement surfaces** not probed (no pilot credentials).
3. **develop/main divergence** — `develop` remains 20 commits ahead with out-of-scope work; future promotions need scoped gates.

---

## Rollback recommendation

If regression detected: redeploy `main` to previous SHA `9755ccfa` via Render manual rollback. Reconciliation archives are non-destructive; rollback does not auto-revert Mongo supersede metadata (no deletes were performed on staging or production).

---

## Acceptance

| Criterion | Met |
|-----------|-----|
| main receives only validated RAOD programme | YES (scoped cherry-pick) |
| Production deploy completes | YES |
| Production `/api/version` confirms promoted SHA | YES |
| Production smoke checks pass | YES |
| Production DB isolation verified (manifest + API labels) | YES |
| Requirement semantic code deployed | YES (portal.py in promotion) |
| No unrelated files included | YES |
| Evidence written | YES |

**Final recommendation:** `PRODUCTION_PROMOTION_SUCCESSFUL` — proceed to **production dry-run** when operator credentials available; **do not execute** reconciliation without explicit approval.
