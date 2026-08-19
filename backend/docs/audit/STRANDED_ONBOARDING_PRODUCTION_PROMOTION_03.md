# Stranded onboarding — production promotion 03

Programme: `CHECKOUT-SUCCESS-ROUTE-FIX-AND-STRANDED-ONBOARDING-PRODUCTION-PROMOTION-03`

SO-01 remains `STRANDED_ONBOARDING_VERIFIED` on `7b2f83fd5fd77cf8a844fcd9b897ebc43f7fff50` (evidence `b3c2d76b`). See `STRANDED_ONBOARDING_E2E_CERTIFICATION_01.md`.

Commercial Controls remain `COMMERCIAL_CONTROLS_VERIFIED`. Scenario C (`allow_promotion_codes`) remains unsupported. This promotion did not reopen email-release authority or promo policy.

## Gate

Issued after staging runtime proof (`CHECKOUT_SUCCESS_ROUTE_RUNTIME_VALIDATION_03.md`) and focused regression (`STRANDED_ONBOARDING_FOCUSED_REGRESSION_03.md`):

```text
GO_FOR_STRANDED_ONBOARDING_PRODUCTION_PROMOTION
```

## Repository reconciliation (before merge)

| Item | Value |
| --- | --- |
| `origin/develop` HEAD at merge | `a803af04205710a3280322beeb7d6b5aa7aa2180` |
| `origin/main` HEAD pre-promotion | `b6b7ddf553482fa2797f317ce69296b21a494230` |
| Merge-base | `fb138ae5` |
| Fast-forward possible | **No** — `main` already had merge `b6b7ddf5` (production promotion 07) |
| Application commits promoted | Stranded Onboarding (`7b2f83fd` and predecessors), SO-01 evidence (`b3c2d76b`), checkout-success route (`583c4f9a`), staging proof docs (`a803af04`) |
| Unrelated working-tree dirt | Gallery PDFs, soak notes, tmp probes — **not committed**, **not merged** |
| Rollback SHA (production backend) | `b6b7ddf553482fa2797f317ce69296b21a494230` |
| Rollback frontend | Prior production Vercel deploy `pleerity-enterprise-ktjpvb37f` on project `pleerity-enterprise` |

No unverified application behaviour was mixed into the promotion candidate.

## Merge

| Item | Value |
| --- | --- |
| Strategy | `ort` merge commit (not fast-forward, **no conflicts**, **no force-push**) |
| Merge SHA | `1fcb5fbcdf99ded01a45fe2fcf1123587efd117d` |
| Parents | `b6b7ddf5` (main) + `a803af04` (develop) |
| Message | `chore(release): merge verified stranded-onboarding and checkout-success into main.` |
| Remote | `origin/main` updated `b6b7ddf5..1fcb5fbc` |

Worktree used for the merge: `C:\pleerity-workspace\ppe-07-main` (`main` is locked out of the primary `develop` worktree).

## Production backend

| Item | Value |
| --- | --- |
| Service | `pleerity-api-production` `srv-d8m59gmgvqtc73cmbu6g` |
| Deploy | `dep-da270tpsrm7s738h0mhg` **live** |
| `/api/version` | `commit_sha=1fcb5fbc…`, `environment=production` |
| Hosts verified | `https://api.pleerityenterprise.co.uk` and `https://pleerity-api-production.onrender.com` |
| Guard | `tier=production` `DB_NAME=pleerity_production` `STRIPE_MODE=live` |
| Staging secrets copied | **No** |

Scheduler heartbeat was stale for a few minutes during instance recycle (`last_heartbeat_at` frozen at `2026-08-18T14:48:06Z`, instance count 0 at 14:50–14:51). Heartbeat job ran successfully at `14:56:40Z`. Subsequent `/api/health` reports `heartbeat_fresh`, Mongo readiness `ready`, `degraded=false`.

One HTTP **502** at `14:51Z` during that recycle. No 5xx in Render HTTP metrics from `14:52Z` through the smoke window. Error-level app logs from `14:48Z`–`15:02Z`: none.

## Production frontend

| Item | Value |
| --- | --- |
| Project | **`pleerity-enterprise`** (not `9jjg`) |
| Customer domain | `https://pleerityenterprise.co.uk` |
| Deploy | `dpl_7aMvyBNxQX3mpFXC1CfuLJ2WLNDD` / `pleerity-enterprise-59iauw4f5` **Ready**, `target=production` |
| Bundle | `static/js/main.b993e884.js` |
| API host in bundle | `https://api.pleerityenterprise.co.uk` (40 refs) |
| Staging API host | **absent** (`pleerity-enterprise.onrender.com` count 0) |
| Stripe publishable | `pk_live_…` present; `STRIPE_MODE=live` on backend |
| Customer-entered promo | `allow_promotion_codes` **absent** from bundle |
| Recovery markers | `checkout-success-page`, `release_and_restart`, `preserve_existing`, `apply_selected` **present** |

## Non-blocking operational note

Staging project `pleerity-enterprise-9jjg` still has Git Production on `main`. After this `main` push, `pleerity-enterprise-9jjg.vercel.app` served a later 9jjg Production bundle (`main.b44d2ec1.js`) that still points at the **staging** API. Customer production is unaffected. Certified staging Preview `pybmokp1a` / `dpl_HEda8CLTXLqb4QMmNUL2zepoGKjT` remains available. Longer-term: stop Git Production-on-main for 9jjg.

## Smoke and observation

See `STRANDED_ONBOARDING_PRODUCTION_SMOKE_03.md`.

| Item | Value |
| --- | --- |
| Observation start | `2026-08-18T14:52:00Z` (instance count returned to 1) |
| Observation close | `2026-08-18T15:38:00Z` (~46 minutes) |
| Closing `/api/health` | `healthy`, readiness `ready`, scheduler `heartbeat_fresh` (`15:36:41Z`) |
| Closing `/api/version` | `1fcb5fbc…`, `environment=production` |
| HTTP 5xx after cutover | none (one **502** at `14:51Z` during instance recycle) |
| Error-level app logs | none |
| Bundle after observation | still `main.b993e884.js` |
| Success route after observation | still `/checkout/success?session_id=…` (200, not homepage) |
| P0/P1 attributable | none |

## Final verdict

```text
STRANDED_ONBOARDING_PRODUCTION_DEPLOYMENT_SUCCESSFUL_WITH_CONDITIONS
```

Condition: staging project `pleerity-enterprise-9jjg` Git Production remains on `main`. That alias hygiene does not affect customer production (`pleerity-enterprise` / `pleerityenterprise.co.uk`).
