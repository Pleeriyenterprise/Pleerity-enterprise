# Customer communication — production deployment 04

Programme: `CUSTOMER-COMMUNICATION-PRODUCTION-PROMOTION-GATE-04`

## Backend

| Item | Value |
| --- | --- |
| Service | `pleerity-api-production` `srv-d8m59gmgvqtc73cmbu6g` |
| Workspace | `tea-d6889rnpm1nc738ucl8g` |
| Branch | `main` |
| `autoDeploy` | yes |
| Root dir | `backend` |
| Deploy | `dep-da2lsdqd0e5s73fuu0j0` **live** |
| Intended commit | `626f35de80ca71dd03b4782552126213cab414b4` |
| Build | succeeded (`build_in_progress` → `live` at `2026-08-19T07:44:20Z`) |
| Instance | `srv-d8m59gmgvqtc73cmbu6g-zqmg7` after recycle from `zq69m` |
| Guard | `tier=production` `DB_NAME=pleerity_production` `STRIPE_MODE=live` |
| Mongo | `Connected to MongoDB: pleerity_production` at `07:44:12Z`; job store `pleerity_production.scheduled_jobs` |
| Scheduler | rebound `07:49:02Z`–`07:49:15Z`; jobs include Daily Compliance Reminders and Subscription lifecycle & renewal reminders |
| `/api/version` | `626f35de…` / `environment=production` on both `https://api.pleerityenterprise.co.uk` and `https://pleerity-api-production.onrender.com` |
| Staging secrets copied | **No** |

## Governed startup

A brief recycle window is expected.

| Time (UTC) | Observation |
| --- | --- |
| 07:41:43 | Deploy `dep-da2lsdqd0e5s73fuu0j0` started |
| 07:43:23 | Previous instance scheduler stopped; Mongo connection closed |
| 07:43:58 | New instance `uvicorn` start |
| 07:44:11 | Application startup complete; deploy marked live |
| 07:44:12 | Mongo connected |
| 07:44:48 | `/api/version` already reports `626f35de` |
| 07:44:56 | `/api/health` **503** (startup) |
| 07:46 | Render HTTP metrics: 2×503, 1×502 |
| 07:47:27 | `/api/health` 200; readiness still `post_db_initialization` |
| 07:49 | Scheduler jobs added (including daily reminders + subscription lifecycle) |
| 07:50:14 | Transient P1 incident `Scheduler heartbeat stale` (`6a856036eb413d81cff75bf4`) — recycle residue |
| 07:50:16 | Internal alert email via Postmark to `i***@pleerityenterprise.co.uk` (`INTERNAL_ALERT`) — operator alert, not a customer communication send |
| 07:51:02 | First new-instance scheduler heartbeat success |
| 07:53:02 | Heartbeat fresh; `/api/health` `healthy` / `ready` / `heartbeat_fresh` |

Do not treat the recycle 503/502 or the heartbeat-stale P1 as a communication regression. Same pattern as stranded-onboarding promotion 03.

## Frontend

**Not deployed.**

| Item | Value |
| --- | --- |
| Reason | No frontend files in `origin/main...origin/develop` |
| Customer project | `pleerity-enterprise` (not `pleerity-enterprise-9jjg`) |
| Customer domain | `https://pleerityenterprise.co.uk` |
| Bundle at promotion | `static/js/main.b993e884.js` (unchanged vs pre-promotion) |
| Public routes smoked | `/`, `/login`, `/login/admin` all HTTP 200 |
| `pleerity-enterprise-9jjg` | **not deployed** as customer production |

## Stripe webhook route (production)

Unsigned `POST https://api.pleerityenterprise.co.uk/api/webhooks/stripe` returns **400 Invalid webhook signature**. The promoted handler is mounted. No live customer event was manufactured.
