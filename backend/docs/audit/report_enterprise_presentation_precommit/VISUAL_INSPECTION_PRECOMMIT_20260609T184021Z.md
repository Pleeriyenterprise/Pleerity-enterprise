# Audit Evidence Pack — Pre-commit Visual Inspection

**Run tag:** `20260609T184021Z`  
**Harness:** `backend/tmp_audit_evidence_pack_precommit_verify.py`  
**Artifact:** `AUDIT_PACK_PRECOMMIT_VERIFY_20260609T184021Z.json`

## Scenario coverage (local)

| Scenario | ZIP artifact | Governance | PDF pages (overview / summary / trail) |
|----------|--------------|------------|----------------------------------------|
| Compliant properties | `local_compliant_*.zip` | PASS | 2 / 4 / 2 |
| High-risk / overdue | `local_high_risk_overdue_*.zip` | PASS | 2 / 4 / 2 |
| Missing evidence | `local_missing_evidence_*.zip` | PASS | 2 / 4 / 2 |
| Missing delivery proof | `local_missing_delivery_proof_*.zip` | PASS | 2 / 4 / 2 |
| Large audit timeline (250 events) | `local_large_timeline_*.zip` | PASS | 2 / 3 / 4 |
| 100+ obligations stress | `local_obligations_100_plus_*.zip` | PASS | 2 / 5 / 4 |
| Large portfolio density (75 obligations) | `local_large_portfolio_*.zip` | PASS | 2 / 5 / 4 |
| Sparse / null metadata | `local_sparse_metadata_*.zip` | PASS | 2 / 3 / 2 |

## Staging probes

| Client | Result |
|--------|--------|
| Sophie calm | `403 PLAN_NOT_ELIGIBLE` — Solo plan cannot generate PDF audit packs |
| Partial B | `403 PLAN_NOT_ELIGIBLE` — same |
| Nancy ops (7 properties) | Generated + re-download byte-equal; **deployed backend lacks `audit_trail.pdf`** (old pack layout) |

## Governance & determinism

- All local scenarios: ZIP paths `00`–`07` present, sorted namelist, manifest ↔ checksums consistent.
- **Stored snapshot immutability:** re-download of same bytes = byte-equal; internal checksum verification passes.
- Fresh generations intentionally differ (`export_id` / `pack_id` UUIDs) — not a regression.

## Visual inspection checklist

### PASS (automated heuristics + text extraction)

- **PDF pagination:** Stress scenarios paginate matrix (5 summary pages) and audit trail (4 pages) without empty leading pages.
- **Table wrapping:** 110-obligation matrix renders across pages 2–4; column headers repeat with frozen-snapshot footer band.
- **Evidence matrix readability:** All required section markers present (`evidence matrix`, `executive summary`, `readiness`, `action priorit`, `frozen deterministic snapshot`, `intended use`, `scope and limitations`).
- **Footer/header consistency:** `Page N | Generated` footer band present on every page; grade line (`REGULATORY_SUBMISSION`) on each page.
- **Risk badge rendering:** Critical / High / Medium / Informational priority groupings present in high-risk and stress packs.
- **Long-text overflow:** 60-char obligation descriptions truncate in matrix column (expected PDF table behaviour); long address retained on cover/summary header.
- **100+ obligations:** No governance failures; matrix + action priorities complete.

### WATCH (manual print-preview recommended)

1. **Empty audit timeline (`sparse_metadata`):** `audit_trail.pdf` page 2 contains only Scope and Limitations — no timeline table when `timeline_count=0`. Not broken, but page 2 is disclosure-only; confirm acceptable for tribunal-facing empty-timeline exports.
2. **Tail pages:** Scope/limitations sometimes isolated on final summary page (e.g. 100+ obligations page 5). Content is complete; verify print margins in Acrobat/browser print preview.
3. **Matrix obligation column:** Very long descriptions show abbreviated/truncated text in cells — verify ellipsis/wrap is acceptable for regulator review at 75–110 rows.
4. **pypdf extraction artifacts:** Bullet characters may render as `` in text extraction only; confirm glyphs in actual PDF viewer.

### Staging deploy gap

- Local workspace includes `05_AUDIT_TIMELINE/audit_trail.pdf` and enterprise template PDFs.
- Staging Nancy pack still uses **legacy** `pack_overview.pdf` / `compliance_summary.pdf` (no matrix-first layout, no `audit_trail.pdf`).
- **Push to production/staging required** before staging visual parity.

## Readiness verdict

| Gate | Status |
|------|--------|
| Local governance | **PASS** |
| Local immutability (stored re-download) | **PASS** |
| PDF heuristic issues | **0** |
| Regulator-facing readability (automated) | **PASS** |
| Staging deploy parity | **BLOCKED** — deploy first |
| Commit (code only) | **READY** — pending your manual print-preview sign-off |
| Push | **NOT READY** — re-run staging probes after deploy |

## Recommended manual steps before commit/push

1. Open in PDF viewer (print preview 100%):
   - `local_obligations_100_plus_20260609T184021Z.zip` → `compliance_summary.pdf`
   - `local_large_timeline_20260609T184021Z.zip` → `audit_trail.pdf`
   - `local_sparse_metadata_20260609T184021Z.zip` → `audit_trail.pdf`
2. Confirm insurer/regulator/tribunal readability criteria subjectively.
3. After deploy: re-run `python tmp_audit_evidence_pack_precommit_verify.py` and confirm `staging_deploy_has_new_pdf: true` on Nancy ops.
