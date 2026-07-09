# Phase 3 Implementation Summary

**Programme:** OPERATIONAL-EVIDENCE-TIMELINE-IMPLEMENTATION-02 — Phase 3  
**Date:** 2026-06-02

## Producers wired

| Boundary | Events |
|---|---|
| `risk_signal_regen_queue.enqueue_risk_signal_regen` (new insert only) | QUEUE_ITEM_CREATED (`category=risk`) |
| `risk_signal_regen_queue.run_risk_signal_regen_worker` | QUEUE_ITEM_CLAIMED, COMPLETED, FAILED, DEAD |

Correlation spine for risk regen: `risk-regen:{property_id}`.

## Historical backfill

- **Service:** `services/operational_evidence/backfill_service.py`
- **Sources:** `job_runs`, `incidents`, `message_logs`, `score_ledger_events`
- **Behaviour:** read-only on sources; `metadata.backfill=true`; confidence capped at 80 (`CONFIDENCE_INDIRECT`); skips rows already indexed by `(source_collection, source_id, event_type)`
- **Admin API:** `POST /api/admin/observability/evidence/backfill` with `{ days, limit_per_source, sources? }`

## Embedded UI

- **Component:** `frontend/src/components/admin/OperationalEvidencePanel.js`
- **Incidents page:** collapsible evidence panel per incident (lazy-loaded)
- **Automation Control Centre:** Evidence button opens modal with embedded panel (replaces navigation-only deep link)

## Validation

- **Script:** `backend/tmp_operational_evidence_timeline_validation_03.py`
- Writes `docs/audit/operational_evidence_timeline_validation_03/PHASE_3_VALIDATION_REPORT.json`

## Tests

- `test_backfill_skips_already_indexed`
- `test_backfill_emit_sets_metadata`
- `test_risk_regen_queue_created_emit`

## Next (Phase 4 — if planned)

- Scheduled backfill job registration (optional; currently admin API only)
- Annotation UI on embedded panels
- Cross-tenant portfolio evidence views
