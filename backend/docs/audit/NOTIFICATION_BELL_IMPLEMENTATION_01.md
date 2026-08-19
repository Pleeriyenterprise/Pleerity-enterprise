# Notification bell — implementation 01

Programme: `NOTIFICATION-BELL-AUTHORITY-DRIFT-01`

## Backend

`backend/services/order_service.py`

* Canonical `inbox_visibility_query` / `inbox_unread_query`.
* List sorts in Mongo (`is_read`, `created_at`) before `limit`.
* Count uses `inbox_unread_query` (includes missing `is_read`; excludes `dismissed=true`).
* Mark-all-read uses the unread query.
* Mark-read matches visibility (not dismissed).

`backend/routes/profile.py`

* `GET /profile/in-app-notifications` returns `{ items, unread_count }`.
* `unread_count` is `get_unread_count`, not `len(items)`.

## Frontend

`ClientPortalLayout.jsx`

* `Promise.allSettled` so count can apply when list fails.
* States: loading / error / unread-not-shown / empty / items.
* Empty copy only when list succeeded, items empty, and `unread_count === 0`.
* Retry on list failure.
* After mark-read, reload list+count.

`InAppNotificationCenter.jsx`

* List failure no longer `setItems([])`.
* Error copy: “We couldn't load notifications.”
* Empty + unread_count > 0 is not “No notifications”.

## Not changed

Email notifications, global preference documents, Commercial Controls, customer-communication cleanup, production data.

## Tests

* `backend/tests/test_in_app_notification_inbox_authority_01.py` — 9 passed.
* `frontend/src/components/ClientPortalLayout.notifications.test.js`
* `frontend/src/components/notifications/InAppNotificationCenter.test.jsx`
* Frontend matching pattern: 8 passed.
