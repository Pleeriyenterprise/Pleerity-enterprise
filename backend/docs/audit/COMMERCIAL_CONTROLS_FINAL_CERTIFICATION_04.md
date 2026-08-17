# Commercial Controls — final certification 04

**Programme:** `COMMERCIAL-CONTROLS-RUNTIME-CERTIFICATION-CLOSURE-04`  
**Date:** 2026-08-15  
**Staging runtime SHA:** `7c77391a5ee65f0a85372d9c462448c270b6b066`  
**Behavioural implementation SHA:** `02533d50faafc114292ab1cba56c2a283df01664`  
**Circuit-fix commit (local `develop`, not pushed):** `f88ce26d6711e881fc20cdae148ac8bff4b2f9cb`  
**Production / `main`:** `89217062481b4eb858a8b530ec90c83de067a4be`

Architecture was not reopened. Suspend Billing authority was not redesigned. `main` was not merged. Production was not deployed.

Prior evidence 01–03 is preserved, not duplicated. 03 verdict was `COMMERCIAL_CONTROLS_INCOMPLETE`.

## Final verdict

```text
COMMERCIAL_CONTROLS_VERIFIED
```

Not `BLOCKED_BY_STAGING_STRIPE_RECONCILIATION_DRIFT` — missing `sub_*` objects were isolated stale fixtures.  
Not `BLOCKED_BY_SUSPEND_BILLING_FINANCIAL_SEMANTICS` — live pause/resume matched the intended void-pause outcome.  
Not `BLOCKED_BY_EXTERNAL_PROVIDER`.  
Not `INCOMPLETE` — required runtime columns for all eight matrix rows are evidenced.

## Why VERIFIED (03 blockers closed)

1. **ACTIVE Stripe fixture** — current test subscription on lere (`sub_1Tr2…`) accepted `pause_collection.behavior=void`.
2. **`PLAN_UNRESOLVED`** — disposable fixture, 409, no Stripe/exception/email mutation, archived.
3. **Circuit** — `STEP_UP_REQUIRED` excluded from failure counts; UI cancel + immediate retry (two 403s, no 90s pause); genuine 403s still trip the breaker (unit test).

## Certification matrix

Control | UI | Step-up | API | DB | Authority | Access | Stripe | Email | Audit | Expiry | Refresh | Verdict
--- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | ---
Grant grace period | host + 03 UI | PASS | 04 smoke 200 | PASS (03+04) | PASS | ENABLED | n/a | 03 sent / bounce noted | granted | revoked 04 | API | **PASS**
Suspend billing ACTIVE | submit + modal + cancel/retry | PASS | PASS 200 | exception then expired | pause then resume | ENABLED / PLAN_2_PORTFOLIO | `pause_collection` void | **DELIVERED** + inbox | granted + `commercial_expired` | **PASS** | panel | **PASS**
Suspend billing CANCELLED | 03 host | PASS 03 | PASS 03 | PASS 03 | already_non_collecting | CANCELLED + effective ENABLED + PLAN_3_PRO | no recreate | **DELIVERED** 03 | granted + expired 03 | **PASS** 03 | API 03 | **PASS** (preserved)
Sponsored access | host + 03 | PASS | 04 smoke 200 | PASS | PASS | ENABLED | n/a | 03 sent | granted | revoked 04 | API | **PASS**
Retention extension | host + 03 | PASS | 04 smoke 200 | PASS | PASS | ENABLED | n/a | 03 sent | granted | revoked 04 | API | **PASS**
Waive onboarding fee | host + 03 | PASS | 04 smoke 200 | PASS | PASS (no recurring waive) | unchanged overlay | n/a | 03 skipped | granted | revoked 04 | API | **PASS**
Recovery compensation | host + 03 | PASS | 04 smoke 200 | PASS | PASS | ENABLED | n/a | 03 sent | granted | revoked 04 | API | **PASS**
Restrict entitlement | host + 03 | PASS | 04 smoke 200 | PASS | PASS | restricted then revoked | n/a | 03 sent | granted | revoked 04 | API | **PASS**

ACTIVE and CANCELLED Suspend Billing are separate rows. Their Stripe consequences differ.

Phase 12 sanity after the circuit change used the governed API smoke harness on nancy (non-Stripe controls), each execute 200 after step-up, then revoke. 03 detailed UI/API evidence is retained.

## Documented observations (non-blocking)

- In-pause invoice **generation** was not live (next cycle 8 Sep). Void-on-create remains Stripe contract; resume did not invoice immediately; period end unchanged.
- Billing GET may lag `pause_collection` null during an active pause; execute `stripe_pause` and webhooks are authority.
- Circuit fix lives on local `develop` (`f88ce26d`) and the staging **frontend alias** only. It is not on `origin/develop` / staging backend, so Render auto-deploy did not restart the API.
- Mongo soak interruption from earlier on 15 Aug 2026 is **not** reset by this exercise. This exercise did not redeploy the backend.

## Production non-touch (reconfirmed 2026-08-15T20:58Z)

| Check | Result |
| --- | --- |
| `origin/main` | `89217062481b4eb858a8b530ec90c83de067a4be` |
| Production API | `89217062…`, `environment=production` |
| Production frontend | `https://pleerityenterprise.co.uk` bundle `main.eac95fab.js`; no `cc-step-up-circuit-fix-04` |
| Staging API | `7c77391a…`, `environment=staging` |
| Staging frontend | `https://pleerity-enterprise-9jjg.vercel.app` bundle `main.7fd31560.js` |
| Production Stripe | not touched |
| Production Postmark recipient | not used |
| Production Mongo | not written |
| Production deploy | none |

## 04 pack

- `COMMERCIAL_CONTROLS_STRIPE_FIXTURE_INTEGRITY_04.md`
- `COMMERCIAL_CONTROLS_STEP_UP_CIRCUIT_FIX_04.md`
- `COMMERCIAL_CONTROLS_ACTIVE_SUSPEND_RUNTIME_04.md`
- `COMMERCIAL_CONTROLS_STRIPE_VOID_SEMANTICS_04.md`
- `COMMERCIAL_CONTROLS_PLAN_UNRESOLVED_RUNTIME_04.md`
- `COMMERCIAL_CONTROLS_POSTMARK_ACTIVE_SUSPEND_04.md`
- `commercial_controls_final_results_04.json`
