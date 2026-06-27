# Regression Validation Report

**Programme:** COMPLIANCE-TIMELINE-PHASE-1-AND-2-RELEASE-VALIDATION-01  
**Validated at:** 2026-06-02

## Verdict: **LOCAL PASS — staging regression status UNKNOWN**

Automated regression suites pass on the **local uncommitted** working tree. Staging at `29fbe355` does not include the programme, so staging-specific regressions from the migration cannot be observed yet.

---

## Known regression targets

| Regression | Local evidence | Staging |
|---|---|---|
| SATISFIED_UNVERIFIED displayed to customers | Not re-tested in timeline suite; lifecycle tests pass separately | **Unknown** |
| Review pending shown for Class A | Not in timeline test scope | **Unknown** |
| Supporting documents altering timeline authority | **PASS** — `test_supporting_document_does_not_alter_timeline_authority` | Not deployed |
| Estimated dates presented as verified | **PASS** — `test_warning_days_due_date_is_estimated_not_authoritative`, `test_verified_authority_beats_stale_estimate` | Not deployed |
| `warning_days` presented as renewal truth | **PASS** — estimate label excludes "renewal" | Not deployed |
| Conflicting dates across UI | **BLOCKED** — no staging UI session | N/A |
| Conflicting wording across reports | **LOCAL PASS** — consumer migration tests | Not deployed |
| Frontend runtime errors | Bundle serves; Phase 2 symbols absent on staging | No Phase 2 to break |
| API contract regressions | Enrich additive fields local; legacy `due_date` preserved | Staging lacks new fields |

---

## Test execution summary (local)

```
test_compliance_timeline.py                          21 passed
test_compliance_timeline_consumer_migration.py       10 passed
test_client_requirement_lifecycle.py                 (included in combined run)
test_supporting_evidence_linkage_fix_01.py           (included in combined run)
Combined timeline + regression                       53 passed
frontend complianceTimelinePresentation.test.js       4 passed
```

---

## Supporting evidence linkage (prior release guard)

Deployed staging includes `29fbe355` supporting document linkage fix (separate from Compliance Timeline). Local timeline tests explicitly guard against supporting documents overriding authority expiry — **PASS** locally.

---

## Frontend regression

Staging bundle `main.67a36506.js`:

- Does not include Phase 2 presentation helpers → **no new frontend regression from programme on staging**
- Prior staging issues (KPI strip, API URL routing) documented in separate audit artefacts — out of scope unless they block timeline validation login

---

## Required post-deploy regression pass

1. Authenticated staging smoke across Requirements, Property, Today, Reports
2. Compare timeline labels for 3+ requirement IDs
3. Re-run full backend timeline + consumer migration CI suite on deployed SHA
4. Browser console check on property dashboard and requirements list

**Release gate:** all local regressions must pass **on deployed SHA**, not only on working tree.
