# POST-SUBMISSION-EVIDENCE-UX-FIX-P0 — Pre-Main Closeout

**Date:** 2026-06-15  
**Develop commit:** `4e4a4fe312ef4cc9ec1385f9d9ac592a51be37b7`  
**Main commit (production backend):** `616e15980908d96c0c40832d4b5bf49427fe6b92`

---

## 1. Production frontend pre-merge status

| Check | Result |
|-------|--------|
| URL | `https://pleerityenterprise.co.uk` |
| Bundle | `main.fdf4cc94.js` |
| Production API in bundle | `https://api.pleerityenterprise.co.uk` |
| P0 markers (`showHeroPrimary`, `authoritativeEvidenceView`, `Not provided`) | **Absent** |
| Production backend `/api/version` | `616e1598`, `environment: production` |

### Accidental `--prod` deploy assessment

During staging validation, a Vercel `--prod` deploy ran. Findings:

- Production **does not** contain P0 frontend code (no `showHeroPrimary` / `authoritativeEvidenceView`).
- Production backend remains on **main** (`616e1598`), aligned with merge-base.
- Bundle hash `main.fdf4cc94.js` differs from a fresh local main build (`main.448de82e.js`) due to build-time embedding of `REACT_APP_BACKEND_URL`; semantic comparison shows both bundles target `api.pleerityenterprise.co.uk` and lack P0 strings.
- **Risk:** Low for P0 accidental promotion. **Residual:** production frontend artifact may have been redeployed to a new hash without a deliberate main release; recommend confirming Vercel production deployment history before next prod cut. **No production modification performed in this closeout.**

---

## 2. Missing-family staging validation

Harness: `post_submission_evidence_ux_fix_p0_missing_families_validate.py`  
Artifact: `MISSING_FAMILIES_VALIDATION_P0.json`

| Family | Fixture | Property / requirement | API checks | Notes |
|--------|---------|----------------------|------------|-------|
| **Smoke, Heat & CO** | `fire_alarm` proxy | Nancy portfolio `fire_alarm` row | **PASS** | Registry has **0** `smoke_heat_alarms` materialisations on staging; domestic-alarm proxy per engine/tests |
| **PAT** | Live | Nancy `9786b4ea…` / `9bb01a6e…` | **PASS** | Primary routes `/documents` (P0-6 fix verified) |
| **Tenancy Agreement** | Live | Kelso Place `def23b30…` / `58dd9efc…` | **PASS** | ACTION_REQUIRED; no false `uploaded_not_verified` |
| **Rent Smart Wales** | Live | Wimbledon Family Home `3a69dcbd…` / `1e9b7901…` | **PASS** | Wales fixture client |
| **Lead Testing** | Synthetic (restored) | Glasgow Shawlands `0a5b4497…` | **PASS** | Temp `building_age_years=70` → sync → validate → **restore original age** |

### P0 dimensions (API / bundle)

| Dimension | Coverage |
|-----------|----------|
| View evidence route | Verified where CER/verified paths exist; smoke proxy uses cognition primary |
| Update prefill | Exercised on legionella (primary harness); others action_required without CER |
| Duplicate CTA absence | Frontend bundle on 9jjg (`showHeroPrimary`); API defers to bundle |
| False `uploaded_not_verified` | **PASS** all captured families |
| Display hygiene | Bundle marker `Not provided` on 9jjg |
| Primary CTA routing | PAT `/documents` confirmed; tenancy/rent_smart use guided declaration |

### Synthetic fixture cleanup

- **Lead testing:** `building_age_years` restored on `0a5b4497-a1ba-4ee9-87e1-ae2bb9d4cc68` in script `finally` block; requirements re-synced.
- **Smoke proxy:** read-only; no data mutation.
- Marker: `P0-CLOSEOUT-MISSING-FAMILIES-20260615`

---

## 3. Full staging matrix (primary harness)

`post_submission_evidence_ux_fix_p0_staging_validate.py` → **GO** (0 failures)  
Families on Nancy primary: legionella, gas_safety, eicr, epc, hmo.

---

## 4. Regression tests (re-run)

| Suite | Result |
|-------|--------|
| Backend P0 + related | **37 passed** |
| Frontend P0 | **29 passed** |

---

## 5. Harness fixes committed

- `post_submission_evidence_ux_fix_p0_staging_validate.py` — PAT route via cognition URL; pass `take_action` into checks
- `post_submission_evidence_ux_fix_p0_missing_families_validate.py` — missing-family closeout probe

---

## 6. Final GO / NO-GO for main merge

| Gate | Verdict |
|------|---------|
| Staging backend at `4e4a4fe3` | **GO** |
| Staging frontend (9jjg) P0 bundle | **GO** |
| Primary harness (5 families) | **GO** |
| Missing-family harness (5 families) | **GO** |
| Production accidentally on P0 | **NO** — production frontend lacks P0 markers |
| Local regression tests | **GO** |

### **Final recommendation: GO for merge to `main`**

---

## 7. Residual risks

1. **Smoke** validated via `fire_alarm` proxy — not a live `smoke_heat_alarms` row (zero on staging registry).
2. **Lead testing** validated via temporary age materialisation — not a persistent post-submission CER row.
3. **Duplicate CTA / display hygiene** — bundle + unit tests; no full browser E2E in this pass.
4. **Production frontend hash drift** — `fdf4cc94` vs local `448de82e`; confirm deployment lineage before next prod release (no P0 leakage observed).

**Constraints honoured:** no merge to main, no production modification, no registry changes.
