# Commercial Controls — E2E runtime certification 03

**Audit ID:** `COMMERCIAL-CONTROLS-RUNTIME-CERTIFICATION-COMPLETION-03`  
**Date:** 2026-08-15  
**Runtime SHA:** `7c77391a5ee65f0a85372d9c462448c270b6b066` (docs-only on implementation `02533d50`; behaviour identical)  
**Production:** untouched (`89217062`)  
**Main:** not merged

Evidence JSON: `backend/docs/audit/commercial_controls_e2e_results_03.json`  
Follow-up: `backend/docs/audit/commercial_controls_e2e_followup_03.json`

## Final verdict

```text
COMMERCIAL_CONTROLS_INCOMPLETE
```

Not `VERIFIED`: ACTIVE Suspend Billing never applied `pause_collection` on a live Stripe subscription; `PLAN_UNRESOLVED` had no staging fixture; invoice-void-during-pause was not live-invoiced.

Not `BLOCKED_STAGING_CREDENTIALS` / `BLOCKED_STAGING_AUTH_LOCK`: preflight **200** / `ROLE_ADMIN`.

Not solely `BLOCKED_EXTERNAL_PROVIDER`: Stripe missing-subscription errors blocked the ACTIVE pause column, but `PLAN_UNRESOLVED` and UI circuit-breaker findings are platform-side.

Suspend Billing **authority was not changed**. Staging Stripe IDs are absent from the connected Stripe account; execute failed closed.

## Preflight / deployment

- Login 200, `ROLE_ADMIN`, eligible for step-up (`STEP_UP_REQUIRED` on execute without token).
- Staging environment, expected frontend alias and `commercial-step-up-modal-host`.
- Production SHA unchanged.

## Matrix

Control | UI | Step-up | API | DB | Authority | Access | Stripe | Email | Audit | Expiry | Refresh | Verdict
--- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | ---
Grant grace period | PASS | PASS | PASS | PASS | PASS | PASS | n/a | accepted; Gmail bounced | PASS | revoked not natural | API PASS | **PASS** (email delivery bounce)
Sponsored access | code-host | PASS | PASS | PASS | PASS | PASS | n/a | accepted | PASS | revoked | API PASS | **PASS**
Retention extension | code-host | PASS | PASS | PASS | PASS | PASS | n/a | accepted | PASS | revoked | API PASS | **PASS**
Waive onboarding fee | code-host | PASS | PASS | PASS | PASS | PASS (no ENABLED overlay change required) | n/a | skipped (unchecked) | PASS | revoked | API PASS | **PASS**
Recovery compensation | code-host | PASS | PASS | PASS | PASS | PASS | n/a | accepted | PASS | revoked | API PASS | **PASS**
Restrict entitlement | code-host | PASS | PASS | PASS | PASS | PASS (effective restricted) | n/a | accepted | PASS | revoked | API PASS | **PASS**
Suspend billing ACTIVE | host present | PASS | FAIL 502 | no persist | reject-closed | unchanged | **STRIPE_PAUSE_FAILED** missing sub | not sent | `commercial_rejected` | n/a | n/a | **FAIL** (fixture/Stripe object)
Suspend billing CANCELLED | host present | PASS | PASS | PASS | PASS | CANCELLED + effective ENABLED + PLAN_3_PRO | already_non_collecting | **DELIVERED** | granted + expired | **PASS** | API PASS | **PASS**

No required column is marked PASS from unit tests alone.

## Failure atomicity

| Case | Result |
| --- | --- |
| Missing/short reason | 422 |
| Missing confirmation | 403 |
| Invalid duration (31d grace) | 400 `VALIDATION_FAILED` |
| Unauthenticated execute | 401 |
| Duplicate exception | not proven on ACTIVE suspend (first execute failed, so second grace succeeded — later revoked) |
| `PLAN_UNRESOLVED` | no plan-less fixture in 150+ scanned clients |
| Stripe rejection | 502 `STRIPE_PAUSE_FAILED`; no overlay; audited |
| Postmark failure | not injected; Gmail bounce observed after accept |
| Mongo failure | not safely injectable |
| Stale frontend | alias still `main.c8b6a433.js` with host fingerprint |
| Timeout | executes 3–10s; 60s hang not generated |
| UI circuit | 403 `STEP_UP_REQUIRED` counted as circuit failure; cancel+retry paused 90s |

## Mongo soak

Interrupted 15 August 2026. Duration not carried forward. Production promotion still subject to the separate Mongo stability condition.

## What would be required to re-open VERIFIED

1. A staging Stripe subscription that `Subscription.retrieve` accepts; then ACTIVE `pause_collection.behavior=void` plus expiry resume.
2. Optional live invoice during pause (or accept Stripe void contract as a documented condition).
3. A `PLAN_UNRESOLVED` fixture (no resolvable plan) proving reject without Solo default.
4. UI circuit must not treat `STEP_UP_REQUIRED` as a 403 failure (change requires a separate approved fix — not done here).
