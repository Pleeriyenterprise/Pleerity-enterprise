# POST-SUBMISSION-EVIDENCE-UX-FIX-P0 — Staging Validation

**Date:** 2026-06-15  
**Commit:** `4e4a4fe312ef4cc9ec1385f9d9ac592a51be37b7` (`develop`)  
**Verdict:** **GO** (staging validation complete for deployable surfaces; see coverage gaps)

---

## Deployments confirmed

| Surface | URL | Status |
|---------|-----|--------|
| Backend (staging) | `https://pleerity-enterprise.onrender.com/api` | **OK** — `commit_sha` matches `4e4a4fe3`, `environment: staging` |
| Frontend (staging alias) | `https://pleerity-enterprise-9jjg.vercel.app` | **OK** — bundle `main.d8bbd86e.js`; markers `showHeroPrimary`, `Not provided`, staging API URL present |
| Production | Not in scope | `main` not merged; no production API writes |

Frontend alias updated via preview prebuilt deploy (`dpl_2FV7x4hwaDMHEeh4M8QTmSux9xjG`) → `pleerity-enterprise-9jjg.vercel.app`.

---

## Automated harness (`post_submission_evidence_ux_fix_p0_staging_validate.py`)

**Result:** GO — 0 failures  
**Artifact:** `STAGING_VALIDATION_P0.json`

### Requirement-family matrix (staging data)

| Family | Property | Result |
|--------|----------|--------|
| legionella | Nancy primary | PASS — verified view → intel submission URL; reopen prefill 6 fields; no false upload warning |
| gas_safety | Nancy primary | PASS — verified; documents URL (has authoritative doc) |
| eicr | Nancy primary | PASS — expiry_confirmation_required; no false upload warning |
| epc | Nancy primary | PASS — escalation_review; modal warning is review semantics (not upload false-positive) |
| hmo | Nancy primary | PASS |
| smoke_heat_co | — | **not_on_property** (Nancy + solo fixture) |
| pat | — | **not_on_property** (occupation_contract false-positive excluded) |
| tenancy | — | **not_on_property** |
| rent_smart_wales | — | **not_on_property** |
| lead_testing | — | **not_on_property** |

### P0 check coverage (API-side)

| Check | API harness | Notes |
|-------|-------------|-------|
| False `uploaded_not_verified` | Verified | All captured rows |
| Verified view routing (structured CER) | Verified | Legionella → `open=intel&focus=submission` |
| Reopen prefill | Verified | Legionella 6-field prefill |
| PAT document route | N/A on Nancy | No PAT requirement on fixture properties |
| Single Update CTA (hero suppressed) | Bundle-only | `showHeroPrimary` confirmed in `main.d8bbd86e.js` on 9jjg |
| Display hygiene (`Not provided`) | Bundle-only | String present in deployed bundle |

---

## Evidence authority convergence repro

**Script:** `evidence_authority_convergence_repro_01_execute.py`  
**Classification:** `none_observed_on_staging_sample`  
**Artifact:** `backend/docs/audit/evidence_authority_convergence_repro_01/`

---

## Regression tests (local, at `4e4a4fe3`)

| Suite | Result |
|-------|--------|
| Backend P0 + cognition + CER + authority convergence | **37 passed** (30 cognition/CER/P0 + 7 authority convergence) |
| Frontend P0 (authoritativeEvidenceView, modal context, display hygiene, documentEvidenceAuthority) | **29 passed** |

---

## Constraints honoured

- No production data writes
- No registry changes
- No staging repair/backfill
- `main` not merged

---

## Coverage gaps (manual E2E still recommended before prod)

1. **Smoke/heat**, **PAT**, **tenancy**, **Rent Smart Wales**, **lead testing** — no matching requirements on Nancy primary or solo fixture; validate on a property that carries those obligations.
2. **Duplicate Update CTA** and **display hygiene** — API harness cannot assert UI; bundle markers + prior unit tests only.
3. **Browser E2E** — not run in this pass; API + bundle verification only.

---

## GO / NO-GO summary

| Gate | Verdict |
|------|---------|
| Staging backend at P0 SHA | **GO** |
| Staging frontend (9jjg) at P0 bundle | **GO** |
| API behavioural matrix (available families) | **GO** |
| Full 10-family runtime E2E on staging | **PARTIAL** — 5 families lack fixture data |
| Merge to `main` / production promotion | **Recommend GO for merge** after team accepts coverage gaps above; no blockers observed on tested surfaces |

---

## Harness script fixes (uncommitted)

`backend/scripts/post_submission_evidence_ux_fix_p0_staging_validate.py` — property merge bug, PAT false-positive filter, frontend-only hero CTA check documented.
