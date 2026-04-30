# Published Registry Client-Truth Source Audit

This inventory classifies requirement generation and consumption paths for the migration to published-registry client truth.

## Source Classification

- **Client-facing active obligation**
  - `backend/services/requirement_client_runtime_surface.py`
  - `filter_requirement_rows_for_client_runtime_surfaces()`
  - `project_requirement_row_client_runtime()`
- **Internal fallback**
  - `backend/services/compliance_requirement_registry.py`
  - `backend/services/requirement_catalog.py`
- **Migration compatibility**
  - `backend/services/provisioning.py` (`requirement_generation_source=requirement_rules`)
  - `backend/services/compliance_governed_rules_service.py`
- **Historical/audit only**
  - Persisted legacy rows in `requirements` with linked entities (`documents`, `work_orders`, `reminder_item_state`, `invoices`)
- **Test fixture only**
  - Direct seeded requirement rows in backend tests that bypass planner/published registry

## Downstream Consumers Audited

- Scoring: `backend/services/compliance_score.py`, `backend/services/compliance_scoring_service.py`
- Reminders: `backend/services/reminder_truth_service.py`
- Gap stream and priority: `backend/services/compliance_gap_sync.py`, `backend/services/client_priority_stream.py`, `backend/services/unified_tasks_service.py`, `backend/services/command_center_service.py`
- Reporting and digest: `backend/services/reporting_service.py`, `backend/services/professional_reports.py`, `backend/services/monthly_digest_assembly_service.py`

## Migration Policy

- New/active client-visible obligations must have active published registry eligibility.
- Legacy rows without published eligibility are retained as:
  - `mapped_readonly` / `unmapped_readonly` when linked history exists
  - `hidden_deprecated` when no linked history exists
- No hard deletion of historical rows in this migration.

