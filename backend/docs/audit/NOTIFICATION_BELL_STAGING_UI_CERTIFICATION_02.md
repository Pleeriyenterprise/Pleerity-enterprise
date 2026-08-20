# Notification bell — staging UI certification 02

Programme: `NOTIFICATION-BELL-STAGING-UI-CERTIFICATION-02`  
Parent: `NOTIFICATION-BELL-AUTHORITY-DRIFT-01`

Do not merge `main`. Do not deploy customer production.

## Preflight

| Check | Result |
| --- | --- |
| Implementation SHA | `a5d71332663952870f69555f3725df4f24f68eef` |
| Staging `/api/version` | `c2cc9b3c1bd1f752043a58eb1395498e2c5e76f1` / `environment=staging` |
| Docs-only descendant | `c2cc9b3c` changes only `NOTIFICATION_BELL_STAGING_CERTIFICATION_01.md` and `notification_bell_results_01.json` vs `a5d71332`. Behavioural source match. |
| Health | `healthy` / `ready` / `heartbeat_fresh` at session start |
| Frontend before alias | `main.3f8006ed.js` — **missing** list-failure copy (Git Production-on-main bundle) |
| Frontend after alias | `pleerity-enterprise-9jjg.vercel.app` → preview `dpl_7Bs7GLA87iB46zbA3RQTiHsuEgjK` (`a5d71332`) bundle `main.7389bb0f.js` containing `We couldn't load notifications.` and `View all notifications` |
| Production API | unchanged `13eca909` / `environment=production` |

Staging alias update was **frontend routing only** on project `pleerity-enterprise-9jjg`. Customer host `pleerityenterprise.co.uk` was not changed.

## Authenticated fixture

Safe staging yopmail client, not the production pilot.

| Field | Value |
| --- | --- |
| Name | Elena Rodriguez |
| Email domain | yopmail.com |
| `client_id` | `b8705b33-c380-461e-89f4-9eba727ea00a` |
| `portal_user_id` | `70b7d6cf-7a7c-47e5-8592-69adc1930561` |
| Role | `ROLE_CLIENT_ADMIN` |
| CRN | `PLE-CVP-2026-000038` |
| Access | Admin impersonation in the staging portal (audited). Not a tenant. |

Baseline before fixtures: unread-count `0`, list `[]` (HTTP 200).

Inbox rows were created with the same document contract as `create_in_app_notification` (no public “create notification” client API). Tagged `metadata.programme=NB02-INBOX-CERT`.

## Scenario results

| Scenario | Result |
| --- | --- |
| A one unread | **PASS** — count API `1`; badge `1`; dropdown showed `NOTIF-D583065A`; centre All/Unread/Compliance showed the same title |
| B open/mark read | **PASS** — click opened `/requirements`; count API `0`; item remained under All; Unread empty; survived reload |
| C dismiss unread | **PASS** on `NOTIF-4079BC96` — dismiss POST `200`; badge `0`; dropdown no longer showed C2. First C row (`NOTIF-4E7BA0E1`) was marked read by an earlier icon-name click; not used as dismiss proof |
| D multi | **PASS** — badge `3`; Unread showed the three D titles; All header `3 unread`; after waits All retained read leftovers plus unread |
| E mark all | **PASS** — `POST .../read-all` `200`; header “You are up to date”; Unread empty; All still listed D+A items as read; count API `0` |
| F reopen/nav | **PASS** — close/reopen dropdown and dashboard↔requirements left badge `0` |
| G multi-tab | **PASS** — second tab dashboard badge `[]` (unread `0`) after mark-all |
| H list failure | **PASS** — list `500` intercept: dropdown showed “We couldn't load notifications” + Try again; **not** “No notifications yet”. Retry control present. Count-fail intercept left loading on a short wait; unit tests cover count-fail + list success |
| I centre filters | **PASS** — All / Unread / Compliance agreed with count. Billing/System correctly showed “not shown in this view” while header unread remained |
| CTA | **PASS** — internal `/requirements` |

## Privacy

Queries used the impersonated `portal_user_id` only. No other customer’s titles appeared in Elena’s inbox.

## Production non-touch

| Check | Result |
| --- | --- |
| Production API SHA | `13eca909` (unchanged) |
| `origin/main` | `13eca909` (unchanged) |
| Production Mongo | not mutated |
| Pilot Emmanuel / CRN `PLE-CVP-2026-000004` | not opened, not marked, not dismissed |

## Verdict

`NOTIFICATION_BELL_VERIFIED_WITH_LEGACY_DATA_CONDITION`
