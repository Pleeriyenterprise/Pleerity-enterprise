# Watchlist — PRELAUNCH-AUTOMATION-LEVERAGE-FEASIBILITY-AUDIT-01

## Before any automation build

- Add **workflow timer** foundation (quote_pending_since, visit_pending_since, or timer collection)
- Add **automation reconciliation** job to suppress stale nudges
- Fix **job_schedule_registry** drift (`scheduled_admin_communications`, `work_order_schedule_reminders`)
- Extend **notification preferences** for escalation opt-out per event type

## Do not automate yet

- Auto-assign contractor
- Auto-approve quote / auto-confirm visit
- Auto-verify evidence or auto-link documents to requirements
- Auto-create work orders from risk signals (keep `AUTO_CREATE_WORK_ORDER_FOR_RISK_TYPES` empty until explicit programme)
- Unsupervised compliance remediation copy (legal/trust review required)

## Monitor after Phase 1

- Notification duplicate rate and throttle deferrals
- Nudge-to-action conversion (did user advance workflow?)
- False-positive rate (nudge sent after state already advanced)
- Support ticket themes related to "spam" or "wrong reminder"

## Dependencies on prior verified programmes

- Quote/visit workflow: `prelaunch_contractor_quote_visit_runtime_truth_verify_01` VERIFIED_OPERATIONALLY
- Contractor/tenant onboarding: invite activation repairs VERIFIED_OPERATIONALLY
- Document evidence authority: VERIFIED_OPERATIONALLY (auto-link still requires human confirm)
