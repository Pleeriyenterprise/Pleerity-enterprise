# Notification bell — staging certification 01

Programme: `NOTIFICATION-BELL-AUTHORITY-DRIFT-01`

Do not merge `main`. Do not deploy production from this programme.

## Local proof (before/with commit)

| Suite | Result |
| --- | --- |
| `tests/test_in_app_notification_inbox_authority_01.py` | 9 passed |
| ClientPortalLayout notifications + InAppNotificationCenter | 8 passed |

## Staging deploy

Recorded after push of the implementation SHA. Backend expected host: `https://pleerity-enterprise.onrender.com`. Frontend staging is not customer production (`pleerity-enterprise-9jjg` only).

| Check | Result |
| --- | --- |
| `/api/version` | `a5d71332` / `environment=staging` |
| health | recovered to `healthy` / `ready` after recycle 502/503 |

## Runtime scenarios

Safe staging fixtures only. No production writes.

| Scenario | Result |
| --- | --- |
| A normal unread | **PASS** on staging Mongo predicates (`unread=1`, `visible=1`); live portal session **not** run |
| A mark read | **PASS** on staging Mongo (`unread=0` after `is_read=true`) |
| B dismiss | **PASS** on staging Mongo (`unread=0`; dismissed row excluded from visibility) |
| C list failure | **PASS locally** (frontend test: failure ≠ empty copy) |
| D multi-notification | **PASS** on staging Mongo (`unread=3`, `visible=4` with one already-read row) |

Staging test recipient `nb01-inbox-cert-user` was inserted then **deleted**. Scenario C cannot be forced on live staging without breaking the API.

Safe to promote only after a staging (or impersonation) portal session confirms badge, dropdown, and `/settings/inbox` agree — **not** authorised in this programme.
