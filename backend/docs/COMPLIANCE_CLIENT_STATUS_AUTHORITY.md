# Client compliance status authority

## Canonical projection

All **client-facing** compliance counts, overdue logic, score `stats`, Command Centre `compliance_status_summary` requirement KPIs, catalog matrix row status (when catalog is used), and requirement reports MUST derive from:

1. `filter_requirement_rows_for_client_runtime_surfaces` — runtime eligibility (planner, jurisdiction, visibility gates, dedupe).
2. `project_requirement_row_client_runtime` — per-row **status**, **due_date** (ISO from effective expiry), **evidence_state** (authority when synced, else legacy).
3. `client_portal_surface_visible_row` — exclude rows with `client_surface_visible is False` from **portal KPI aggregates** (counts shown on dashboard, compliance score stats, Command Centre, reports).

Aggregated counts MUST use `compute_client_portal_requirement_stats` on the list from steps 1–3.

## Allowed status strings (projected)

| Status | Meaning |
|--------|---------|
| `COMPLIANT` | Satisfied / verified current (includes authority-mapped verified current). |
| `VALID` | Legacy alias for satisfied row; treated like `COMPLIANT` in KPI counts. |
| `PENDING` | Required but evidence missing or not confirmed; counts toward **missing_evidence**. |
| `MISSING` | Explicit missing evidence; counts toward **missing_evidence**. |
| `EXPIRING_SOON` | Within expiring-soon policy window. |
| `OVERDUE` | Past effective expiry or authority-mapped overdue. |
| `EXPIRED` | Legacy or matrix label for expired certificate; **KPI overdue** treats `EXPIRED` like `OVERDUE`. |
| `NOT_REQUIRED` / `NOT_APPLICABLE` | Excluded from required KPI buckets when not in runtime set. |

`ACTION_REQUIRED`, `MISSING_EVIDENCE`, `NEEDS_CONFIRMATION` may appear on **score driver / matrix display** strings; they are presentation aliases, not separate Mongo requirement statuses. Canonical storage/projection for counts remains the table above.

Do **not** re-interpret overdue via ad hoc calendar on raw `PENDING` for KPI totals; use the projected status.

## Headline portfolio score vs catalog matrix

- **`GET /client/compliance-score` `score`, `grade`, `color`, `message`:** Averaged **persisted** per-property scores from `compliance_scoring_service` / recalc jobs (same portal-projected requirement universe as of last recalc).
- **`catalog_portfolio_view` (when catalog is populated):** Alternate **catalog-weighted** portfolio score and presentation fields only. It must **not** replace headline `score` / `stats` — consumers choose explicitly if they display the catalog lens.

## Surface Matrix

| Surface / endpoint | Source service / function | Classification | Status authority used | Can diverge from KPI truth by design? | Allowed reason for divergence |
|---|---|---|---|---|---|
| Properties page (`/properties`, via `GET /api/client/dashboard`) | `routes/client.py:get_dashboard` | `KPI-authoritative` | `filter_requirement_rows_for_client_runtime_surfaces` + `project_requirement_row_client_runtime` + `client_portal_surface_visible_row`; property badge from projected statuses | No | N/A |
| Dashboard KPI cards (`/app/dashboard`) | `routes/client.py:get_dashboard`, `services/compliance_score.py:calculate_compliance_score` | `KPI-authoritative` | `calculate_compliance_score.stats` (portal-projected requirement counts) | No | N/A |
| Compliance score page (`GET /api/client/compliance-score`) | `services/compliance_score.py:calculate_compliance_score` | `KPI-authoritative` | `compute_client_portal_requirement_stats` over projected + portal-visible rows | No | N/A |
| Score drivers block (`drivers` in compliance score payload) | `services/compliance_score.py:calculate_compliance_score` | `KPI-authoritative` | Same projected row set as score `stats`; display aliases allowed | No | N/A |
| Actions to improve score (`recommendations`, `top_next_actions`) | `services/compliance_score.py:calculate_compliance_score` | `KPI-authoritative` | Derived from persisted per-property scoring outputs + projected requirement context | No | N/A |
| Requirements page (`GET /api/client/requirements`) | `routes/client.py` requirements route + runtime filter/enrichment | `KPI-authoritative` | Runtime filter + projected status semantics (`project_requirement_row_client_runtime`) | No | N/A |
| Property compliance tab (`GET /api/portfolio/properties/{property_id}/compliance-detail`) | `routes/portfolio.py`, `services/catalog_compliance.py:get_property_compliance_detail` | `KPI-authoritative` | Catalog matrix rows now projected (`project_requirement_row_client_runtime`) before KPI/status use | No | N/A |
| Command Centre (`GET /api/client/command-center`) | `services/command_center_service.py:get_command_center_bundle` | `KPI-authoritative` for compliance counts; `operational task flow` for task/risk streams | Compliance counts come only from `calculate_compliance_score.stats` (`compliance_counts_authority`) | Yes (task/risk streams only) | Urgent task/risk lists are operational prioritisation, not KPI aggregates |
| Today page (`/today`) | `services/today_projection_service.py:build_today_payload_from_unified` + unified tasks | `operational task flow` | Unified task pipeline; requirement CTAs from canonical `take_action` contract | Yes | Inbox visibility/actions and prioritisation are operational workflow controls, not KPI truth |
| Reports: compliance summary (`GET /api/reports/compliance-summary`) | `services/reporting_service.py:generate_compliance_summary_report` | `audit/reporting view` (KPI-aligned) | Projected + portal-visible rows + `compute_client_portal_requirement_stats` | No | N/A |
| Reports: requirements export (`GET /api/reports/requirements`) | `services/reporting_service.py:generate_requirements_report` | `audit/reporting view` (KPI-aligned) | Per-row `project_requirement_row_client_runtime` on runtime-filtered set | No | N/A |
| Professional compliance summary PDF (`GET /api/reports/professional/compliance-summary`) | `services/professional_reports.py:generate_compliance_summary_pdf` | `audit/reporting view` (KPI-aligned summary) | Summary requirement counts use projected + portal-visible + stats helper | No | N/A |
| Professional expiry schedule PDF | `services/professional_reports.py:generate_expiry_schedule_pdf` | `calendar/schedule view` | Calendar urgency (`get_effective_expiry_date`, schedule status) | Yes | Explicitly schedule-only by design; not canonical KPI aggregation |
| Monthly digest (email/PDF model) | `services/monthly_digest_assembly_service.py:assemble_monthly_digest_payload` | `audit/reporting view` with mixed sections | Headline counts from `calculate_compliance_score.stats`; requirement rows from projected + portal-visible set | Yes (limited sections) | Includes operational sections (jobs/activity/recommendations) alongside KPI-aligned compliance summary |
| Portfolio compliance summary (`GET /api/portfolio/compliance-summary`) | `routes/portfolio.py`, `services/catalog_compliance.py:get_portfolio_compliance_from_catalog` | `audit/reporting view` (client-visible portfolio lens) | Legacy path uses projected status; catalog path uses projected row status for matrix/KPIs | Yes (headline score lens) | Catalog portfolio score is an alternate lens (`catalog_portfolio_view` pattern), not the canonical headline score source |
| Value insights card metrics | `services/client_value_insights_service.py:get_value_insights` | `audit/reporting view` (advisory) | Pulls compliance counts from `calculate_compliance_score.stats` | Yes | Advisory/upgrade narrative may combine KPI counts with commercial heuristics |

## Interpretation Rules

- `KPI-authoritative` surfaces MUST compute compliance counts/status from:
  1. `filter_requirement_rows_for_client_runtime_surfaces`
  2. `project_requirement_row_client_runtime`
  3. `client_portal_surface_visible_row`
  4. `compute_client_portal_requirement_stats`
- `operational task flow` surfaces (Today / task streams) MAY display requirement-linked tasks and canonical CTAs, but MUST NOT be used as a replacement aggregate for compliance KPI counts.
- Optional API **`propagation_notice`** on document mutations is **not** a status authority — when displayed on client vault flows, it explains **temporary** backbone/queue deferral only; requirement rows and headline score semantics remain per projection + scoring services.
- `calendar/schedule view` surfaces MAY use calendar urgency semantics (`remaining`, `overdue`, `expiring`) for planning outputs; they MUST be labeled schedule-only and MUST NOT be represented as KPI-truth totals.
- `audit/reporting view` surfaces SHOULD mirror KPI-authoritative counts unless the output is explicitly labeled as alternate lens or schedule view.
- Allowed divergence must be explicit in payload copy/labels (for example: `catalog_portfolio_view` note, expiry schedule disclaimer).

## Anti-patterns (disallowed)

- Frontend `Math.max` across portfolio summary, tasks, and score for the same KPI.
- Catalog-only `status` on enriched rows without projection (catalog matrix must apply projection for KPIs).
- Report-only `_runtime_status` helpers that diverge from `project_requirement_row_client_runtime`.

## Related code

- `services/requirement_client_runtime_surface.py` — projection, visibility, `compute_client_portal_requirement_stats`.
- `services/compliance_score.py` — `stats` and drivers from portal projected rows.
- `services/command_center_service.py` — `compliance_status_summary` requirement fields from `calculate_compliance_score`.
- `services/kpi_authority_projection_contract.py` — **L-002 CI guard**: registered KPI-authoritative modules must reference filter+project (or delegate only via `calculate_compliance_score` without raw requirement queries). See `tests/test_kpi_authority_projection_contract.py`.
- `GET /api/admin/compliance-truth/clients/{client_id}/explain` — admin explain payload.

## Client mental model & workspace orientation (presentation only)

Client-facing **page intros, empty states, and footnotes** that distinguish **Dashboard (portfolio KPIs)**, **Today (operational inbox)**, **Command Center (portfolio triage)**, **Requirements (tracked obligations)**, **Documents (evidence vault)**, and **stored scores vs uploads** are **non-authoritative**. They MUST NOT contradict this matrix, imply instant score finality, or substitute for requirement rows or `calculate_compliance_score` outputs. Canonical copy module: `frontend/src/utils/workspaceOrientationCopy.js` (governed alongside `PRESENTATION_LANGUAGE_GOVERNANCE.md`).

## Not applicable (NOT_REQUIRED) — portal governance

Catalog mark (`POST /api/client/properties/{property_id}/requirements/mark-not-applicable` and `POST /api/properties/{property_id}/requirements/mark-not-applicable`) and requirement-id mark (`POST /api/requirements/{requirement_id}/mark-not-applicable`) align on: preset category (`not_required_reason` / `reason_code`), mandatory **free-text audit reason** (minimum length, trimmed), **`sync_requirement_evidence_authority`**, **`create_audit_log`** with `event: mark_not_applicable` (catalog adds `path: property_catalog`), and **async** `enqueue_compliance_recalc` (no synchronous score rewrite).

`PATCH /api/properties/{property_id}/requirements/{requirement_id}` with `applicability: NOT_REQUIRED` requires the same preset plus `not_applicable_audit_reason`. When applicability is set to **`REQUIRED`** or **`UNKNOWN`**, stale N/A row metadata (`not_required_reason`, `not_applicable_audit_reason`) is cleared with **`$unset`** on the requirement document; historical audit log rows are not deleted.

`POST /api/requirements/{requirement_id}/reopen` restores tracked participation with the same authority sync + enqueue pattern; audit metadata includes `prior_applicability` for operational review.
