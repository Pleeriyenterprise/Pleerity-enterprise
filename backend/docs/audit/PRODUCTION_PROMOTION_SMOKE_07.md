# Production promotion smoke 07

**Programme:** `PRODUCTION-PROMOTION-EXECUTION-07`

## Public / frontend

| Check | Result |
| --- | --- |
| Homepage `/` | 200 |
| `/login` | 200 |
| `/login/admin` | 200 |
| `/admin`, `/admin/login`, `/portal/login` | 200 (SPA shell) |
| Bundle JS errors (fingerprint scan) | CC + capacity strings present; production API host only |
| Correct API host | `api.pleerityenterprise.co.uk` in `main.c9306ba7.js` |

## Authentication / RBAC

| Check | Result |
| --- | --- |
| Staging admin `prosper@yopmail.com` on production | **401** (DB isolation; expected) |
| Production admin login | **NOT_EXERCISED** — no `PROD_ADMIN_*` in the session environment |
| Representative customer login | **NOT_EXERCISED** — no production customer credentials used |
| Logout/session | **NOT_EXERCISED** (requires authenticated session) |

Do not treat missing production operator credentials as a code defect. Isolation probe passed.

## Admin / Commercial Controls (non-mutating)

Panel execute against a real customer was **not** performed. Deployment integrity is the frontend fingerprints plus CC unit tests. See `PRODUCTION_PROMOTION_COMMERCIAL_CONTROLS_SMOKE_07.md`.

## Mongo / scheduler

| Check | Result |
| --- | --- |
| Reads | `/api/version` and `/api/health` succeed after ready |
| Scheduler | `heartbeat_fresh` at 07:02Z and 07:20Z (age ~51s) |
| Capacity | shared cluster 54.19% `ok`, `writes_at_risk=false` at 07:24Z (staging health-summary scan of both DBs) |
| Capacity 503 on ready API | none after 06:53Z |

## Stripe / Postmark

| Check | Result |
| --- | --- |
| Live Stripe test event | **NOT_EXERCISED** (no production payment mutation) |
| Unnecessary customer email | **not sent** |
| Unit tests | Stripe webhook/mode tests in the promotion suite **passed**; Postmark orchestrator tests **failed** on pre-existing `resolve_greeting` NameError (present on pre-promotion `main` too) |

## HTTP during cutover

Deploy window only: two 502s (06:50Z), one 503 (06:53Z). No 5xx in 06:54–07:21Z (Render HTTP metrics + request log query). Instance count 1 throughout. Public pages remain 200 with bundle `main.c9306ba7.js`.
