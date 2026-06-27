# Business Event Catalogue

Business domain events correlate with infrastructure events via shared `correlation_id` / `root_execution_id`.

## Compliance & requirements

| event_type | Category | Typical evidence source |
|---|---|---|
| COMPLIANCE_BECAME_VALID | compliance | score_ledger_events |
| COMPLIANCE_BECAME_NON_COMPLIANT | compliance | score_ledger_events |
| COMPLIANCE_SCORE_CHANGED | compliance | score_ledger_events |
| REQUIREMENT_CREATED | workflow | audit_logs |
| REQUIREMENT_REMOVED | workflow | audit_logs |
| REQUIREMENT_EXPIRED | compliance | job_runs (expiry jobs) |

## Evidence

| event_type | Category | Source |
|---|---|---|
| EVIDENCE_UPLOADED | evidence | audit_logs / documents |
| EVIDENCE_APPROVED | evidence | evidence_review_events |
| EVIDENCE_REJECTED | evidence | evidence_review_events |

## Risk & portfolio

| event_type | Category | Source |
|---|---|---|
| PORTFOLIO_RISK_INCREASED | risk | score_ledger / risk signals |
| PORTFOLIO_RISK_DECREASED | risk | score_ledger / risk signals |

## Reminders & notifications

| event_type | Category | Source |
|---|---|---|
| REMINDER_GENERATED | reminder | job_runs |
| REMINDER_COMPLETED | reminder | job_runs |
| NOTIFICATION_* | notification | message_logs |

## Work orders & inspections

| event_type | Category | Source |
|---|---|---|
| WORK_ORDER_OPENED | workflow | maintenance work orders |
| WORK_ORDER_COMPLETED | workflow | maintenance work orders |
| INSPECTION_SCHEDULED | compliance | compliance execution |
| INSPECTION_COMPLETED | compliance | compliance execution |

## Phase 2 wiring

Each business event uses `emit_operational_evidence()` at the authoritative write boundary with `caused_by_event_id` linking to triggering infrastructure event when known.

Constants: `services/operational_evidence/constants.py` → `BUSINESS_EVENT_TYPES`
