# Dependency Completeness Report

**Programme:** COMPLIANCE-TIMELINE-RELEASE-CURATION-01  
**Audited at:** 2026-06-02

## Verdict: **COMPLETE locally — one governance artefact missing**

All runtime dependencies for Phase 1 and Phase 2 are present in the working tree. No missing implementation file blocks a release candidate commit.

---

## Dependency graph

```
compliance_timeline.py (Phase 1 calculator)
        │
        ▼
requirement_truth.py enrich ──► timeline_primary_* + compliance_timeline on API rows
        │
        ▼
compliance_timeline_presentation.py (Phase 2 helpers)
        │
        ├──► build_date_presentation_from_timeline (requirement_truth date_label)
        ├──► Backend consumers (reports, email, calendar, score drivers, jobs display)
        └──► complianceTimelinePresentation.js ──► Frontend pages/components/utils
```

---

## Phase 1 dependencies

| Dependency | Required by | Present | Path |
|---|---|---|---|
| Timeline calculator | Enrich, all consumers via ensure/build | **Yes** | `backend/services/compliance_timeline.py` |
| Enrich integration | Client API, reports input | **Yes** | `backend/services/requirement_truth.py` |
| Timeline unit tests | CI gate | **Yes** | `backend/tests/test_compliance_timeline.py` |
| Evidence authority inputs | Calculator | **Yes** | Pre-existing (`requirement_evidence_authority.py`) |
| Lifecycle semantics resolver | Calculator (read-only) | **Yes** | Pre-existing (`lifecycle_semantics_resolver.py`) |
| CER structured fields | Assessment/declaration families | **Yes** | Pre-existing (`compliance_evidence_record_service.py`) |

**Phase 1 missing:** None in working tree.

---

## Phase 2 dependencies

| Dependency | Required by | Present | Path |
|---|---|---|---|
| Presentation layer | All Phase 2 backend + FE | **Yes** | `compliance_timeline_presentation.py` |
| FE presentation utility | 6 frontend consumers | **Yes** | `complianceTimelinePresentation.js` |
| Report human language | Operational/executive reports | **Yes** | `report_human_language_v1.py` |
| Monthly digest assembly | Digest PDF rows | **Yes** | `monthly_digest_assembly_service.py` |
| Requirements operational | PDF/CSV/email rows | **Yes** | `report_requirements_operational.py` |
| PDF/matrix templates | Compliance summary PDF | **Yes** | `report_pdf_templates.py` |
| Executive summary | Matrix humanization | **Yes** | `report_compliance_summary_executive.py` |
| Score PDF + CSV | Driver export surfaces | **Yes** | `pdf_report_builder.py`, `routes/reports.py` |
| Compliance pack | Audit evidence pack | **Yes** | `compliance_pack.py` |
| Professional reports | Expiry schedule PDF | **Yes** | `professional_reports.py` |
| Calendar service | Client calendar events | **Yes** | `client_calendar_timeline_service.py` |
| Scheduled email digest | Email wording | **Yes** | `scheduled_report_digest.py` |
| Jobs reminder display | Email body (not scheduling) | **Yes** | `jobs.py` |
| Score drivers API | Compliance score page | **Yes** | `compliance_score.py` |
| Frontend pages/modals | Customer UI | **Yes** | 6 files (see RELEASE_FILE_MATRIX) |
| Consumer migration tests | CI gate | **Yes** | `test_compliance_timeline_consumer_migration.py` |
| Updated report tests | Regression gate | **Yes** | `test_report_human_language_v1.py`, `test_report_requirements_operational.py` |
| FE unit tests | CI gate | **Yes** | `complianceTimelinePresentation.test.js` |

**Phase 2 missing:** None in working tree.

---

## Intentionally out of scope (not missing)

| Component | Reason |
|---|---|
| Scoring math timeline migration | Documented Phase 3+ optional programme |
| `CUSTOMER_STATUS_PROJECTOR_V2_MODE` | Explicitly disabled |
| Event ledger | Phase 3+ |
| Database migrations | Programme is additive projection only |
| `ClientDashboard.js` confirmed_expiry banners | Workflow heuristics, not date presentation |

---

## Cross-layer coupling checks

| Check | Result |
|---|---|
| Phase 2 imports Phase 1 service | **Pass** — presentation calls `build_compliance_timeline` |
| Phase 2 FE assumes API enrich fields | **Pass** — enrich adds all six timeline fields |
| Reports call presentation without circular imports | **Pass** — one-way dependency |
| Reminder scheduling still uses `get_effective_expiry_date` | **Pass** — `jobs.py` unchanged for scheduling anchor |
| No Phase 3 / S2 projector code in tree | **Pass** — none detected |

---

## Governance dependencies

| Artefact | Status |
|---|---|
| Phase 1 closure JSON | Present (untracked) |
| Phase 2 closure JSON | Present (untracked) |
| Consumer inventory matrix | Present (untracked) |
| Release validation pack | Present (untracked) |
| **COMPLIANCE_TIMELINE master tracker** | **MISSING — must be created before commit** |
| Update to REQUIREMENT_LIFECYCLE master tracker | Not required (separate programme) |

---

## Test coverage dependency closure

| Suite | Covers | Local result |
|---|---|---|
| `test_compliance_timeline.py` | Calculator + all families | 21 passed |
| `test_compliance_timeline_consumer_migration.py` | Consumer alignment | 10 passed |
| Report test updates | Report wording regressions | Pass (in combined run) |
| FE presentation tests | Frontend helpers | 4 passed |

**Conclusion:** Implementation dependency graph is closed. Governance tracker is the only missing non-code dependency.
