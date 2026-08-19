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
| `/api/version` | see `notification_bell_results_01.json` after deploy poll |
| `environment` | must be `staging` |
| health | must be ready |

## Runtime scenarios

Safe staging fixtures only. No production writes.

| Scenario | Result |
| --- | --- |
| A normal unread | pending deploy poll / fixture |
| A mark read | pending |
| B dismiss | pending |
| C list failure | **PASS locally** (frontend test: failure ≠ empty copy) |
| D multi-notification | pending (unit: mixed + limit) |

Scenario C cannot be forced on live staging without breaking the API; the frontend integration test is the designated proof.
