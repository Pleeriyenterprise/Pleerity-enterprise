# Watchlist — PRELAUNCH-TODAY-EXECUTION-WORKSPACE-01

- **Classification:** VERIFIED_OPERATIONALLY (closed 2026-05-29)
- **Blockers:** none

## Closed with deploy fixes

Runtime regressions from `9b82ec25` closeout blocked `/today` until:

- `41475c8b` — restore `useGuidedEvidenceModal` import
- `8eaec170` — restore `RequirementIntelligenceModal` import
- `9ec37bce` — define `TaskCard` `propertyLine` / `cognitionEntity`
- `38c022a2` — list cognition chips fall back to server `take_action` / `business_actions` labels

Live bundle: `main.82e79739.js` (successor to pre-closeout stale bundle).

## Remaining watch (non-blocking)

- **Dashboard Today KPI drilldown:** browser capture did not resolve `[data-testid="executive-kpi-row"]` Today count (`dashboard_today_kpi: null`); API open sum is 40 — confirm dashboard card selector on next dashboard UX pass.
- **Continuation samples:** API urgent rows for Nancy lack `operational_continuation` / `take_action` on first work-order samples; hero and chips use `business_actions` authority for rent/work-order rows.
- **Command Centre scope delta:** CC urgent digest (68) vs Today visible open (40) is expected — Today caps buckets; `today-bucket-continuation-notice` discloses overflow (202 total continuation).
- **Requirements cognition on non-linked tasks:** Today pool is work orders / rent / issues without `requirement_id`; full `operational_cognition.list_guidance` appears when requirement-linked tasks surface.

## Invariants (do not revert)

- Today uses `requirementsOperational` (`projection=full`) — never `projection=list` for workspace rows.
- Today = execution queue; Command Centre = ranked portfolio triage (counts may differ with disclosure).
