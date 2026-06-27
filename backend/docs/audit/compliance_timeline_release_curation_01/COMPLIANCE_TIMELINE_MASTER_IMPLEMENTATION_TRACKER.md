# Compliance Timeline — Master Implementation Tracker

**Programme:** COMPLIANCE-TIMELINE (Phase 1 Current Truth + Phase 2 Consumer Migration)  
**Authority:** `compliance_timeline_current_truth_implementation_01.json`, `compliance_timeline_phase_2_consumer_migration_01.json`  
**Maintained:** Compliance Timeline workstream  
**Last updated:** 2026-06-02 (release candidate commit — pending SHAs)

---

## Programme status

| Phase | Scope | Implementation | Committed | Pushed develop | Staging deploy | Production |
|---|---|---|---|---|---|---|
| **Phase 1** | Current Truth — calculator, projection, enrich fields | **Complete (local)** | Pending | Pending | **Not deployed** | **Blocked** |
| **Phase 2** | Consumer migration — UI, reports, email, calendar | **Complete (local)** | Pending | Pending | **Not deployed** | **Blocked** |
| **Phase 3** | Scoring alignment, legacy field retirement, event ledger (optional) | **Not started** | — | — | — | **Blocked** |

---

## Release boundary

**In scope (this release):**

- `backend/services/compliance_timeline.py` — authoritative projection calculator
- `backend/services/compliance_timeline_presentation.py` — consumer presentation helpers
- `requirement_truth.py` enrich integration + `date_label` delegation
- Backend consumers: reports, digest, email, calendar, score drivers, audit pack, reminders (display only)
- Frontend consumers: Requirements, Property, Score, Admin, modal, widgets, operating hub
- Tests: `test_compliance_timeline.py`, `test_compliance_timeline_consumer_migration.py`, report + FE tests
- Governance: closure JSON, consumer inventory, release validation pack, release curation pack

**Explicitly out of scope:**

- Event ledger / `compliance_event_domain_model_audit_01`
- `CUSTOMER_STATUS_PROJECTOR_V2_MODE` activation
- Database migrations or repair scripts
- Scoring engine math migration (Phase 3 optional)
- Production promotion

---

## Commit plan

| Commit | Message | Contents |
|---|---|---|
| 1 | `feat(compliance): add authoritative timeline projection` | Calculator, Phase 1 tests, Phase 1 closure JSON |
| 2 | `feat(compliance): migrate date consumers to compliance timeline` | Presentation layer, enrich wiring, all consumers, tests, governance packs, this tracker |

**Base commit:** `29fbe355` — supporting document linkage fix (already on develop/main)

---

## Phase 1 — Current Truth

| Deliverable | Path | Status |
|---|---|---|
| Timeline service | `backend/services/compliance_timeline.py` | Release candidate |
| Enrich integration | `backend/services/requirement_truth.py` | Commit 2 |
| Unit tests (21) | `backend/tests/test_compliance_timeline.py` | Release candidate |
| Closure artefact | `backend/docs/audit/compliance_timeline_current_truth_implementation_01.json` | Commit 1 |

**Additive API fields:** `compliance_timeline`, `timeline_primary_date`, `timeline_primary_date_label`, `timeline_primary_date_confidence`, `timeline_primary_date_source`, `timeline_primary_date_concept`

---

## Phase 2 — Consumer Migration

| Surface | Path | Status |
|---|---|---|
| Presentation layer | `compliance_timeline_presentation.py` | Release candidate |
| Frontend utility | `frontend/src/utils/complianceTimelinePresentation.js` | Release candidate |
| Requirements / Property / Score / Admin | `frontend/src/pages/*.js` | Release candidate |
| Modal / hub / widgets | `frontend/src/components/**`, `utils/**` | Release candidate |
| Reports / digest / email / calendar | `backend/services/report_*.py`, `jobs.py`, etc. | Release candidate |
| Consumer tests | `test_compliance_timeline_consumer_migration.py` | Release candidate |
| Closure artefact | `compliance_timeline_phase_2_consumer_migration_01.json` | Commit 2 |
| Consumer inventory | `CONSUMER_INVENTORY_MATRIX.json` | Commit 2 |

---

## Test gates (pre-commit)

| Suite | Expected |
|---|---|
| `test_compliance_timeline.py` | 21 passed |
| `test_compliance_timeline_consumer_migration.py` | 10 passed |
| `test_supporting_evidence_linkage_fix_01.py` | Pass |
| `test_client_requirement_lifecycle.py` | Pass |
| `test_report_human_language_v1.py` | Pass |
| `test_report_requirements_operational.py` | Pass |
| `complianceTimelinePresentation.test.js` | 4 passed |

---

## Known exclusions (must not enter release commit)

- `backend/tmp_*.py` (25 scratch scripts)
- `backend/docs/audit/_staging_*` (cached bundle downloads)
- E2E / ops runtime captures (`e2e_*`, `ops_runtime_*`)
- Supporting-document-linkage audits (already on develop)
- Event ledger audit JSON
- Optional upstream audits (domain model, renewal semantics) — separate docs PR if needed

See `compliance_timeline_release_curation_01/RELEASE_EXCLUSION_REPORT.md`.

---

## Remaining Phase 3 work (not in this release)

1. Scoring engine math — optional migration to timeline attention anchors
2. `ClientDashboard.js` onboarding banners — replace `confirmed_expiry_date` heuristics with lifecycle semantics
3. Legacy field retirement (`due_date` presentation-only removal)
4. Event ledger programme (separate governance)
5. Persisted timeline hash / drift detection (optional)

---

## Staging validation — **REQUIRED before main**

After push to `origin/develop` and staging deploy:

1. Re-run `COMPLIANCE-TIMELINE-PHASE-1-AND-2-RELEASE-VALIDATION-01`
2. Authenticated timeline payload sampling on enriched requirements
3. Cross-surface consistency for ≥3 requirement IDs
4. Family spot-check on staging data
5. Performance p95 vs baseline

**Staging deploy:** Not executed in this task.  
**Release validation status:** Pending post-deploy.

---

## Production promotion — **BLOCKED**

Production promotion remains **NO-GO** until:

- [ ] Release commits on `origin/develop`
- [ ] Staging backend + frontend deployed from merge SHA (aligned)
- [ ] Release validation pack passes on staging
- [ ] `PRODUCTION_READINESS_DECISION.md` superseded with GO or GO WITH CONDITIONS
- [ ] No merge to `main` until above complete

---

## Merge / deploy SHAs (populate after events)

| Event | SHA | Date |
|---|---|---|
| Phase 1 commit | _pending_ | |
| Phase 2 commit | _pending_ | |
| `origin/develop` tip after push | _pending_ | |
| Staging backend deploy | _pending_ | |
| Staging frontend deploy | _pending_ | |
| Release validation verdict | _pending_ | |

---

## Related artefacts

| Document | Location |
|---|---|
| Release curation pack | `compliance_timeline_release_curation_01/` |
| Release validation pack | `compliance_timeline_release_validation_01/` |
| Consumer inventory | `CONSUMER_INVENTORY_MATRIX.json` |
| Phase 1 closure | `compliance_timeline_current_truth_implementation_01.json` |
| Phase 2 closure | `compliance_timeline_phase_2_consumer_migration_01.json` |
