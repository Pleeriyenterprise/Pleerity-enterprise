# Report Presentation Authority — Production Promotion

**Outcome:** `REPORT_PRESENTATION_AUTHORITY_PRODUCTION_PROMOTION_SUCCESSFUL`  
**Generated:** 2026-07-02T13:40:49+00:00  
**Branch promoted:** `main` (scoped cherry-pick; **no** develop merge)

---

## Promotion lineage

| Order | develop SHA | main SHA | Subject |
|------:|-------------|----------|---------|
| 1 | `73594124` | `12abdf99` | Audit pack technical-language cleanup + `report_presentation/` module |
| 2 | `36fec1cb` | `f3094759` | Report Presentation Authority wiring |
| 3 | `a361ade4` | `80c9d25e` | Gallery validation evidence refresh |

**Main before:** `8d368c2c` (rollback anchor)  
**Main after:** `80c9d25e`  
**Promotion method:** Scoped cherry-pick only — no unrelated develop commits included.

Cherry-pick order follows dependency (`73594124` → `36fec1cb` → `a361ade4`).

---

## Pre-flight

| Check | Result |
|-------|--------|
| Approved commits only | **Pass** — 3 commits, RPA programme scope |
| Unrelated develop work excluded | **Pass** — no merge of develop |
| Config / Render / Vercel changes | **Pass** — none in promotion diff |
| Database migrations | **Pass** — none |
| API contract changes | **Pass** — presentation layer only |
| Local WIP excluded | **Pass** — unrelated `email_layout.py` stashed; tmp/probe scripts not promoted |

---

## Deployment

| Surface | URL | Deployed artefact |
|---------|-----|-------------------|
| Backend (Render) | https://api.pleerityenterprise.co.uk | `80c9d25e2dbbaada22bdd8c24c62baac008e5b23` |
| Frontend (Vercel) | https://pleerityenterprise.co.uk | `main.ccfc03f2.js` (sha256 `a8580189…`) |

Backend `/api/version` aligned to promoted SHA after Render rollover (~2 min). Brief 502/503 during deploy; post-deploy health **healthy**.

---

## Smoke validation

| Probe | Result |
|-------|--------|
| API health | `healthy` / `production` / readiness ready |
| Homepage | HTTP 200 |
| Reports (unauthenticated) | HTTP 401 (expected) |
| Dashboard (unauthenticated) | HTTP 401 (expected) |
| Frontend prod API in bundle | **Yes** |
| Staging API in bundle | **No** |

---

## Regression validation

| Suite | Result |
|-------|--------|
| `test_report_presentation_authority.py` | Pass |
| `test_report_pdf_templates.py` | Pass |
| `test_report_evidence_readiness_operational.py` | Pass |
| **Total** | **33 passed** |

Report calculations, scoring, lifecycle, evidence determination, and report APIs unchanged (presentation layer only).

---

## Gallery & technical language

| Check | Result |
|-------|--------|
| Gallery validation (promoted `main`) | **114/114 COMPLETE** |
| Engineering terms in executive body | **None** (gallery script) |
| Technical appendix forensic detail | **Preserved** |
| Executive summaries early | **Pass** |
| Business chronology | **Pass** |

---

## Production report PDF validation

**Status:** Cross-referenced to gallery validation on promoted commit.

Authenticated live PDF generation was **not** run (no `PRODUCTION_SMOKE_*` credentials in environment). RPA is server-side PDF presentation; gallery validation on the promoted tree is the authoritative report artefact check.

---

## Known limitations

1. No authenticated end-to-end production PDF download in this session.
2. Frontend bundle not modified by RPA — expected; PDF presentation is backend-generated.
3. Deploy rollover produced transient 502/503 — resolved before final smoke.

---

## Rollback

If regression detected: revert `main` to `8d368c2c` and redeploy Render/Vercel to prior production deployment.

---

## Evidence

- `REPORT_PRESENTATION_AUTHORITY_PRODUCTION_PROMOTION.json`
- Gallery reference: `backend/docs/audit/report_presentation_gallery_validation_01/`
