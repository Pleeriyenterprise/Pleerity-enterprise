# Notification bell — multi-tab reconciliation 02

Programme: `NOTIFICATION-BELL-STAGING-UI-CERTIFICATION-02`

After mark-all on Tab A (`/settings/inbox`):

| Tab | Action | Badge |
| --- | --- | --- |
| A | mark all as read, then dashboard | `0` (no unread aria) |
| B | new browser context page → `/dashboard`, wait for load | `0` (no unread aria) |

No permanent ghost badge. A short stale window before Tab B’s own fetch is acceptable; Tab B converged on the same unread-count `0` as the API.

Reopen/poll (Scenario F): close dropdown, reopen, navigate to `/requirements`, return to `/dashboard`. Badge remained `0`.
