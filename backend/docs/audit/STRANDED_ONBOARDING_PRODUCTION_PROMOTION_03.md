# Stranded onboarding — production promotion 03

Programme: `CHECKOUT-SUCCESS-ROUTE-FIX-AND-STRANDED-ONBOARDING-PRODUCTION-PROMOTION-03`

Gate issued after staging proof:

```text
GO_FOR_STRANDED_ONBOARDING_PRODUCTION_PROMOTION
```

SO-01 remains `STRANDED_ONBOARDING_VERIFIED`. Commercial Controls remain `COMMERCIAL_CONTROLS_VERIFIED`. Scenario C remains unsupported.

## Repository reconciliation (before merge)

| Item | Value |
| --- | --- |
| `origin/develop` HEAD | `583c4f9a90e78fb83baf3c9f60b57bf17c9ab5b2` |
| `origin/main` HEAD | `b6b7ddf553482fa2797f317ce69296b21a494230` |
| Merge-base | `fb138ae5` |
| Fast-forward possible | **No** — `main` has merge commit `b6b7ddf5` (production promotion 07) not on `develop` |
| Application commits on develop not on main | `177996e6` (docs), `7f3ba4fc` … `7b2f83fd` (stranded onboarding), `b3c2d76b` (SO-01 evidence), `583c4f9a` (checkout-success route) |
| Unrelated working-tree dirt | Gallery PDFs, soak notes, tmp probes — **not committed**, **not merged** |
| Rollback SHA (production backend pre-promotion) | `b6b7ddf553482fa2797f317ce69296b21a494230` |
| Rollback frontend | Production Vercel project `pleerity-enterprise` bundle serving `b6b7ddf5` / prior production alias |

No unverified application behaviour was mixed into the promotion candidate.

## Merge

Prefer merge commit (not force-push). Record merge SHA in the results JSON after the merge completes.

## Production backend

Deploy only the certified stranded-onboarding + checkout-success source. Verify `/api/version` `environment=production`, health, scheduler heartbeat, Mongo connectivity. Do not copy staging secrets.

## Production frontend

Project **`pleerity-enterprise`** (not `9jjg`). Confirm production API host, Stripe publishable key, checkout-success route, recovery panel markers, no staging API host, production alias serves the new bundle.
