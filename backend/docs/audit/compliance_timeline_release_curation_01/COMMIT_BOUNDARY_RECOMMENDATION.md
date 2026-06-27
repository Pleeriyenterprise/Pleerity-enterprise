# Commit Boundary Recommendation

**Programme:** COMPLIANCE-TIMELINE-RELEASE-CURATION-01  
**Audited at:** 2026-06-02

## Recommendation: **Option B — two commits, one pull request**

Use **two sequential commits** on a single feature branch, merged to `develop` via **one PR**:

1. **Commit 1 — Phase 1 (Current Truth)**
2. **Commit 2 — Phase 2 (Consumer Migration)** + governance pack

Deploy staging only after **both** commits are on `develop` (single deploy SHA containing the full programme).

---

## Options considered

### Option A — Single commit

| Pros | Cons |
|---|---|
| Zero hunk-splitting risk | Phase 1 and Phase 2 history collapsed |
| Atomic deploy by definition | Harder to audit phase boundaries later |
| Simplest committer workflow | Does not mirror two-phase programme governance |

### Option B — Two commits (recommended)

| Pros | Cons |
|---|---|
| Clear audit trail matching programme phases | Requires careful staging of `requirement_truth.py` |
| Easier rollback reasoning per phase | Phase 2 commit is non-runnable alone until deployed together |
| Aligns with closure artefacts (Phase 1 JSON, Phase 2 JSON) | Slightly more committer discipline |

### Option C — Two PRs

**Not recommended.** Phase 2 depends on Phase 1 enrich fields; merging Phase 2 PR before Phase 1 would break consumers. Single PR eliminates intermediate broken `develop` states.

---

## Proposed commit boundaries

### Commit 1 — `feat(compliance-timeline): Phase 1 current truth projection`

| Include | Exclude |
|---|---|
| `backend/services/compliance_timeline.py` | All Phase 2 consumer files |
| `backend/tests/test_compliance_timeline.py` | Presentation layer |
| `requirement_truth.py` — **enrich block only** (lines adding `build_compliance_timeline` + timeline fields + `build_date_presentation_from_timeline` for date_label) | `build_date_presentation` early-return delegation (Phase 2) |
| `compliance_timeline_current_truth_implementation_01.json` | Phase 2 audit JSON |

**Note:** At commit time, use `git add -p backend/services/requirement_truth.py` to stage only the enrich hunk block inside `enrich_requirement_dict`. Do **not** stage the `build_date_presentation` delegation hunk in Commit 1.

### Commit 2 — `feat(compliance-timeline): Phase 2 consumer migration`

| Include |
|---|
| `compliance_timeline_presentation.py` |
| All backend/frontend consumer files (22 modified + 2 new FE files) |
| Consumer + report tests |
| `build_date_presentation` delegation hunk in `requirement_truth.py` |
| `CONSUMER_INVENTORY_MATRIX.json` |
| `compliance_timeline_phase_2_consumer_migration_01.json` |
| `compliance_timeline_release_validation_01/` (10 files) |
| `compliance_timeline_release_curation_01/` (7 files) |
| **New:** `COMPLIANCE_TIMELINE_MASTER_IMPLEMENTATION_TRACKER.md` |

Optional in Commit 2 or separate docs commit:

- `compliance_timeline_domain_model_audit_01.json`
- Upstream architecture audit JSON references

---

## Coherence checks

| Risk | Mitigation |
|---|---|
| Unrelated fixes mixed in | Working tree contains **only** timeline programme in modified tracked files — **pass** |
| Partially completed work | Phase 1+2 implementation complete; tests pass — **pass** |
| Phase 3 / event ledger | `compliance_event_domain_model_audit_01.json` excluded — **pass** |
| Abandoned code | All `tmp_*` excluded — **pass** |
| Experimental code | No experimental flags enabled — **pass** |
| Future S2 projector | Not present in diff — **pass** |

---

## Fallback: Option A if hunk-split fails

If `git add -p` on `requirement_truth.py` proves error-prone during commit prep, **fall back to Option A** (single commit):

```
feat(compliance-timeline): Phase 1 current truth and Phase 2 consumer migration
```

Single commit is acceptable for release integrity when the alternative risks partial staging. Document in PR body that both phases ship atomically.

---

## PR structure

```
branch: feature/compliance-timeline-phase-1-2
target: develop
commits: 2 (or 1 if fallback)
title: feat(compliance-timeline): current truth projection and consumer migration
body:
  - Phase 1 summary + test count
  - Phase 2 consumer inventory reference
  - Exclusion attestation (no tmp_*)
  - Staging deploy + re-run RELEASE-VALIDATION-01 required before production
```

**Do not merge to `main` until staging release validation passes.**

---

## Justification summary

Two commits preserve **long-term programme traceability** (matching Phase 1 and Phase 2 closure artefacts and governance) while a **single PR** prevents broken intermediate states on `develop`. The only file spanning both phases is `requirement_truth.py`, which is splittable at commit time with patch staging. If that split is too fragile, single commit remains a valid release-safe alternative.
