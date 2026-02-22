# Enterprise Reporting + Score Transparency – Gap Analysis

## Goal (task)
A) Evidence Readiness PDF (new report_service + POST /api/reports/generate).  
B) Score change tracking (score_change_log, delta, changed requirements; extend property API).  
C) Frontend: Property page delta + “View change history” modal; Reports page Generate PDF + list past reports; replace Compliant/Non-compliant wording.  
D) Tests: PDF generation, score delta, no regression.

## Current state

| Area | Location | Behaviour |
|------|----------|-----------|
| PDF reports | reporting_service.py, professional_reports.py, routes/reports.py | Compliance summary, requirements, audit PDFs via GET with format=pdf; plan-gated (reports_pdf). No “Evidence Readiness” report; no POST /api/reports/generate with scope. |
| Score persist | compliance_scoring_service.recalculate_and_persist | Writes property_compliance_score_history; audit log has delta; no score_change_log collection; no “changed requirements” snapshot. |
| Property API | portfolio: GET /properties/{id}/compliance-detail; client: get_compliance_score_explanation(property_id) | compliance-detail returns property_score, risk_level, matrix, kpis; no score_delta, score_change_summary, last_updated_at. |
| Frontend Property | PropertyDetailPage.js | Score card shows score + risk; no delta indicator, no “View change history” modal. |
| Frontend Reports | ReportsPage.js | Client-side jsPDF for some PDFs; available reports list, schedules; no dedicated “Generate Evidence Readiness PDF” or “list past reports” (stored). |
| Wording | Multiple pages | “Compliant”, “Non-compliant”, “Fully Compliant” in dashboard, admin, tenant, reports. |

## Conflicts and safest option

1. **New report vs existing**  
   Task: new report_service.py + Evidence Readiness PDF with specific sections. Existing: reporting_service + professional_reports with different report types. **Choice:** Add report_service.py for Evidence Readiness only; add POST /api/reports/generate (scope=portfolio|property, property_id optional). Keep existing GET report routes and plan gating; gate new endpoint by same reports_pdf where applicable.

2. **score_change_log vs property_compliance_score_history**  
   Task: persist to score_change_log with delta and changed requirements. **Choice:** Add score_change_log collection; write from recalculate_and_persist (after computing delta and, if available, diff of score_breakdown/status). Keep existing history + audit unchanged.

3. **Property API response**  
   Task: include score_delta, score_change_summary, last_updated_at. **Choice:** Extend GET /api/portfolio/properties/{id}/compliance-detail (and any client property score endpoint used by Property page) to add these fields from property + latest score_change_log or history.

4. **Frontend “past reports”**  
   Task: list past reports, download links. **Choice:** Implement only if backend stores report runs (e.g. report_generations or similar). If not in scope, add “Generate PDF” button that calls POST /api/reports/generate and returns download; “list past reports” can be deferred or implemented with a simple in-memory/DB store for report metadata.

5. **Wording replacement**  
   Task: replace “Compliant/Non-compliant” with evidence readiness / risk level / missing or expired evidence. **Choice:** Replace in key user-facing places (Property detail, Dashboard score card, Reports page summary). Leave admin/tenant wording for a follow-up where needed; avoid broad find-replace to prevent breaking copy.

## Implementation summary

- **A)** report_service.py: Evidence Readiness PDF (cover, executive summary, portfolio table, property detail matrix, methodology, audit snapshot 30d, disclaimer). POST /api/reports/generate with body { scope, property_id? }, return PDF file.
- **B)** In recalculate_and_persist: load previous score and score_breakdown; compute delta; diff requirement keys status → changed_requirements; insert score_change_log. Extend compliance-detail (and client property score) response with score_delta, score_change_summary, last_updated_at.
- **C)** Property page: below score card show delta (green/red), short explanation, “View change history” modal (data from new API or history endpoint). Reports page: “Generate Evidence Readiness PDF” button calling new endpoint; optional list of past reports if backend supports it. Wording: replace targeted Compliant/Non-compliant with evidence readiness / risk / missing or expired evidence.
- **D)** Tests: PDF generation (report_service), score delta and score_change_log (recalculate_and_persist); ensure no regression to provisioning/billing.
