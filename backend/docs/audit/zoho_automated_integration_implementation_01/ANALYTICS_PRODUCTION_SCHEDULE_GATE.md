# ANALYTICS_PRODUCTION_SCHEDULE_GATE

**Phase:** `PHASE_B_ANALYTICS_SCHEDULED_OPERATION_01`  
**Date:** 2026-07-14  
**Status:** **CLOSED — DO NOT ENABLE**

---

## Current state

| Control | Staging | Production |
|---|---|---|
| `zoho_analytics_export` cron registration | Allowed only when `ENVIRONMENT`/`ENV` == `staging` | **Blocked** by `zoho_analytics_schedule_registration_allowed()` |
| Force production schedule via code path | N/A | No production branch registers the job |
| Ops enablement | Pending live validation + 3 daily cycles | **Not recommended** |

---

## Enablement recommendation (future only)

Do **not** wire or enable the production schedule until **all** of the following are true:

1. Staging checklist in `ANALYTICS_STAGING_SCHEDULE_VALIDATION.md` fully PASS.
2. Staging completes **at least three consecutive daily scheduled cycles successfully** (real 02:15 UTC runs or equivalent scheduled instrumentation — not force-fabricated Zoho success).
3. No open actionable Analytics incident policy for ≥7 days after those three cycles (operator judgment).
4. Explicit owner change control: production `ENVIRONMENT` gate flip + code change that allows production registration (separate PR; not this phase).
5. Production flags remain off until cutover: `ZOHO_ANALYTICS_SYNC_ENABLED` and OAuth credentials reviewed for production org/workspace/view.
6. Duplicate-period guard, dead-letter replay, kill switch, and SoR boundaries reconfirmed on production config.

---

## Explicit non-goals of this phase

- No production cron registration.
- No other Zoho product schedules (CRM, Books, Campaigns, etc.).
- No change to Pleerity System of Record / Stripe billing authority.

---

## Recommendation summary

**Defer production schedule enablement.** Revisit only after three consecutive successful staging daily cycles and a dedicated production change request referencing this gate document.
