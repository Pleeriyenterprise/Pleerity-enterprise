# Notification bell — error-state runtime 02

Programme: `NOTIFICATION-BELL-STAGING-UI-CERTIFICATION-02`

Staging API was not destabilised. Browser route intercept on the authenticated staging portal:

## List fails, count not intercepted

Dropdown copy:

```text
We couldn't load notifications.
Try again
```

`No notifications yet` was **not** shown.

Previously loaded items could still appear under the error copy (layout maps items even when `notifListError` is true). That is not an empty-inbox lie.

Retry control was present (`hasRetry = 1`).

## Count fails, list not the focus of this intercept

A short wait after aborting `unread-count` left the dropdown on `Loading…`. It did **not** show empty-inbox copy. Frontend unit tests already cover count-fail + list success.

## Automated

`ClientPortalLayout.notifications.test.js` and `InAppNotificationCenter.test.jsx`: list failure ≠ empty copy.
