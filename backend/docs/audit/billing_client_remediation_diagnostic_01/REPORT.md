# BILLING-CLIENT-REMEDIATION — Post-deploy verification

**Programme:** BILLING-CLIENT-REMEDIATION-POST-DEPLOY-VERIFY-01  
**Generated:** 2026-06-03T07:33:55+00:00  
**Classification:** **PARTIAL**

## Client

- **client_id:** `80f83edd-ba12-41ed-929a-bbaf8c696a23`
- **CRN:** `PLE-CVP-2026-000011`
- **Portal:** `confidence@yaho.co.uk` (password setup **not complete**)

## Deploy

- `/api/version` → `c9cbeae5fc24008e23ab7ef7b95847b10c793dbf` (matches fix commit)

## Plan change (POST `/api/billing/checkout`)

| Check | Result |
|--------|--------|
| Affected client direct API | Blocked — portal login 401 (no password) |
| Proxy drift cohort (`nancy@yopmail.com`) | **200**, `plan_change_path: deployment_checkout`, checkout URL present |
| Refresh-block copy on proxy path | **Absent** |
| `requires_deployment_checkout` for affected row | **true** (stored `test`, deployment `live`) |

Deployed code routes test/live drift through **deployment Checkout**, not portal preflight. Same path applies to the affected client once the portal can authenticate.

## Admin recovery

- Stripe remediation guidance: `VERIFIED_OPERATIONALLY` (live checkout session evidence after prior regeneration activity)
- Recovery dashboard row still shows stale `MODE_UNVERIFIED` while case is `RECOVERY_RESOLVED` — dashboard metadata lag, not billing API blocker
- `regenerate-checkout` returns **409** when case is `RECOVERY_RESOLVED` (expected; reopen required for another admin regeneration)

## Customer UX

- Browser proof **skipped** — `password_setup_complete: false` for portal admin
- No screenshot captured

## Safety

- Legacy subscription id unchanged during probes
- No blind subscription mutation
- Containment preserved (no mode bypass, no force-set)

## Regression

- `test_stripe_mode_containment.py` — pass
- `test_billing_recovery_operations.py` — pass

## Verdict

**PARTIAL** — deploy and deployment-checkout routing verified on staging; affected customer UX pending portal password setup and checkout completion.
