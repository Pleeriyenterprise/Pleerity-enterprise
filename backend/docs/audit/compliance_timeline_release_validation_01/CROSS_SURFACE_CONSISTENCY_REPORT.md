# Cross-Surface Consistency Report

**Programme:** COMPLIANCE-TIMELINE-PHASE-1-AND-2-RELEASE-VALIDATION-01  
**Validated at:** 2026-06-02

## Verdict: **BLOCKED on staging — LOCAL PASS on automated cross-surface tests**

Cross-surface validation requires the same enriched requirement object to produce identical timeline-derived presentation across all consumers. Staging cannot be validated because the programme is not deployed and no authenticated API session was available.

---

## Surfaces in scope

| Surface | Staging | Local automated evidence |
|---|---|---|
| Requirements list | **NOT TESTED** | Migrated in `RequirementsPage.js` — not deployed |
| Requirement modal | **NOT TESTED** | `RequirementIntelligenceModal.js` — not deployed |
| Property matrix | **NOT TESTED** | `PropertyDetailPage.js` — not deployed |
| Property detail | **NOT TESTED** | Same |
| Operating Hub | **NOT TESTED** | `PropertyOperatingHub.jsx` — not deployed |
| Calendar | **NOT TESTED** | `client_calendar_timeline_service.py` — not deployed |
| Monthly Digest | **NOT TESTED** | `monthly_digest_assembly_service.py` — not deployed |
| Audit Evidence Pack | **NOT TESTED** | `compliance_pack.py` — not deployed |
| Compliance Summary | **NOT TESTED** | `report_compliance_summary_executive.py` — not deployed |
| Scheduled email preview | **NOT TESTED** | `scheduled_report_digest.py` — not deployed |
| Compliance score drivers | **NOT TESTED** | `ComplianceScorePage.js` + `compliance_score.py` — not deployed |

---

## Local cross-surface consistency (same requirement object)

Executed via `test_compliance_timeline_consumer_migration.py` on local working tree:

| Check | Result |
|---|---|
| `enrich_requirement_dict` → `date_label` == `timeline_primary_date_label` | **PASS** |
| `timeline_report_date_display(enriched)` == `timeline_primary_date_label` | **PASS** |
| `human_operational_renewal_date(enriched)` == timeline label | **PASS** |
| Matrix `expiry_display` contains timeline wording ("Certificate expires") | **PASS** |
| Calendar event date == timeline `primary_date` | **PASS** |
| Estimated system due never labelled "renewal" in report display | **PASS** |

**Interpretation:** For a single verified Gas Safety fixture, enrich API label, report renewal column, matrix expiry display, and calendar anchor align on the same timeline projection locally.

---

## Staging blockers

1. Backend at `29fbe355` does not enrich requirements with timeline fields
2. Frontend bundle lacks `getTimelineDateLabel` / Phase 2 presentation helpers
3. No staging login session used — cannot compare live requirement IDs across UI and reports

---

## Required re-validation after deploy

For each of ≥3 real requirement IDs on staging (covering certificate, assessment, declaration families):

1. Fetch enriched requirement via client API
2. Capture `timeline_primary_date_label`, confidence, concept
3. Compare to Requirements list, property matrix, modal, calendar event title/date, digest PDF row, audit pack line, summary report cell, scheduled email preview
4. Assert zero divergence in date, wording, confidence, concept, estimated vs verified state

**Pass criterion:** all surfaces identical per requirement ID.

---

## Independent date reinterpretation

On staging: **cannot confirm** — legacy consumers still active at `29fbe355`.  
Locally: Phase 2 migrations present in working tree; automated tests pass for delegated presentation paths.
