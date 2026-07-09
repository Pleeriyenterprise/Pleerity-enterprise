# Phase 2 Implementation Summary

**Programme:** OPERATIONAL-EVIDENCE-TIMELINE-IMPLEMENTATION-02 — Phase 2  
**Date:** 2026-06-02

## Producers wired

| Boundary | Events |
|---|---|
| `compliance_recalc_queue.enqueue` | QUEUE_ITEM_CREATED (Phase 1) |
| `job_runner.run_compliance_recalc_worker` | QUEUE_ITEM_CLAIMED, COMPLETED, FAILED, DEAD |
| `score_ledger_service.log_score_change` | COMPLIANCE_SCORE_CHANGED, BECAME_VALID/NON_COMPLIANT, PORTFOLIO_RISK_* |
| `notification_orchestrator.send` / retry | NOTIFICATION_QUEUED, SENT, FAILED, RETRY_SCHEDULED |
| `evidence_review_audit.append_evidence_review_event` | EVIDENCE_APPROVED, EVIDENCE_REJECTED |
| `incident_lifecycle_service.try_transition_to_recovered` | INCIDENT_RECOVERED |
| `incident_lifecycle_service.try_auto_resolve_after_recovery` | INCIDENT_RESOLVED |

## UI deep links

- Incidents page: **View in Evidence Timeline** per incident
- Automation Control Centre: **Evidence** link per job last run

## API filters added

- `document_id` on timeline list endpoint

## Next (Phase 3)

- Embedded timeline panels
- Risk signal regen queue producers
- Historical backfill worker
- Staging E2E validation script
