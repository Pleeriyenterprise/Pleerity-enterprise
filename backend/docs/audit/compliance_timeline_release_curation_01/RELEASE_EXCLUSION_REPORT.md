# Release Exclusion Report

**Programme:** COMPLIANCE-TIMELINE-RELEASE-CURATION-01  
**Audited at:** 2026-06-02  
**Rule:** Read-only curation — nothing excluded from disk; this report defines what must **not** enter the Compliance Timeline release commit.

---

## Summary

| Category | Count | Action |
|---|---|---|
| Must exclude from release commit | **33** | Do not `git add` |
| Optional reference (separate commit or docs PR) | 3 | Not blocking |
| Unrelated audit JSON already satisfied on `develop` | 4 | Exclude |

---

## 1. Scratch scripts (`backend/tmp_*.py`) — 25 files

**Classification:** F (scratch)  
**Why exclude:** Ad-hoc staging probes, browser automation runners, E2E closure scripts, and one-off validation utilities. Not part of the product surface. Would pollute history and increase review burden. Many embed environment-specific assumptions and are not maintained as production code.

Examples:

- `tmp_e2e_*`, `tmp_kpi_browser_*`, `tmp_g1_api_convergence_validate.py`
- `tmp_prod_smoke_*`, `tmp_rc_go_no_go_validation.py`
- `tmp_supporting_linkage_staging_validation_01.py` (separate programme)

**Recommendation:** Keep local or move to a personal/scripts folder outside the release branch. Consider `.gitignore` pattern for `backend/tmp_*.py` in a separate hygiene PR (out of scope for this curation).

---

## 2. Cached validation downloads — 2 files

| File | Size concern | Why exclude |
|---|---|---|
| `backend/docs/audit/_staging_index.html` | Small | Downloaded artefact from release validation run |
| `backend/docs/audit/_staging_main.js` | ~5 MB | Full staging bundle snapshot; not source code |

These are evidence captures, not implementation. Committing multi-MB JS bundles bloats the repository.

---

## 3. E2E / ops runtime artefacts — 14+ paths

**Why exclude:** Belong to separate programmes (E2E blocker closure, ops runtime gates G1/G2/G4/G7), not Compliance Timeline.

| Pattern | Examples |
|---|---|
| `e2e_*` JSON/logs | `e2e_final_two_blockers_closure_01.json`, run logs |
| `ops_runtime_*` | stdout captures under `6fd5ac4c_d35a58ae` folders |
| `g1_probe_result.json` | Ops probe output |
| `e2e_text_bearing_fixtures/` | Generated PDF test fixtures |
| `generate_e2e_text_bearing_fixtures.py` | Fixture generator script |

---

## 4. Unrelated programme audits — 8 files

**Why exclude:** Different implementation IDs; some record work **already merged** to `develop` at `29fbe355`.

| File | Programme | Notes |
|---|---|---|
| `supporting_document_linkage_*` (3) | Supporting document linkage | Fix already on `main`/`develop` |
| `staging_frontend_backend_url_fix_01.json` | Staging URL fix | Merged via `2b51f7e8` |
| `production_promotion_execution_01.json` | Production promotion | Separate gate |
| `rc_production_go_no_go_validation_01.json` | RC validation | Separate gate |
| `final_blockers_frontend_deploy_and_extraction_fix_01.json` | E2E blockers | Separate programme |
| `frontend_deployment_and_extraction_rootcause_01.json` | Extraction root cause | Separate programme |

Including these would mix unrelated release narratives into the Compliance Timeline commit.

---

## 5. Future / experimental programme — 1 file

| File | Why exclude |
|---|---|
| `compliance_event_domain_model_audit_01.json` | Event ledger / Phase 3+ planning audit. Explicitly out of scope for Phase 1+2 release. |

---

## 6. Optional — include in docs-only follow-up, not code release

These are **programme lineage** documents. They may be committed in a separate “audit archive” PR but are not required for runtime:

- `compliance_timeline_domain_model_audit_01.json`
- `authoritative_date_lifecycle_architecture_audit_01.json`
- `renewal_semantics_and_date_provenance_audit_01.json`

---

## 7. Risk if exclusions are ignored

| Risk | Impact |
|---|---|
| `tmp_*` in release commit | Unreviewable scripts in production repo; security/review failure |
| `_staging_main.js` in commit | Repository bloat; accidental secret leakage surface |
| Mixed programme audits | Incorrect blame archaeology; failed release audit |
| Event ledger audit in Phase 1+2 commit | Implies scope creep into Phase 3 |

---

## Exclusion verification checklist (for committer)

Before any commit:

- [ ] `git status` shows **only** the 45 release files from `RELEASE_FILE_MATRIX.json`
- [ ] No `backend/tmp_*` staged
- [ ] No `_staging_*` under `docs/audit`
- [ ] No `e2e_*` or `ops_runtime_*` staged
- [ ] No supporting-document-linkage audit JSON staged
- [ ] `compliance_event_domain_model_audit_01.json` not staged

---

## `.gitignore` consideration (future, not this release)

Patterns worth adding in a hygiene task after release:

```
backend/tmp_*.py
backend/docs/audit/_staging_*
backend/docs/audit/**/*.run.log
```

Not executed in this curation exercise per constraints.
