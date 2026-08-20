# Notification bell — frontend failure states 01

Programme: `NOTIFICATION-BELL-AUTHORITY-DRIFT-01`

## Header dropdown (`ClientPortalLayout`)

| Condition | Before | After |
| --- | --- | --- |
| list ok, count ok, items present | items | HAS_ITEMS |
| list ok, count 0, items [] | “No notifications yet.” | EMPTY |
| list ok, count > 0, items [] | “No notifications yet.” | unread-not-shown + View all (not empty) |
| list fail, count ok | `Promise.all` catch; empty copy if items still [] | LOAD_FAILED + Try again; badge may remain |
| list fail, count fail | catch; empty if never loaded | LOAD_FAILED |
| count fail, list ok | `Promise.all` catch (both dropped) | items shown; badge may stay previous |

Required states: `LOADING` / `EMPTY` / `HAS_ITEMS` / `LOAD_FAILED`.

## Notification centre

| Condition | Before | After |
| --- | --- | --- |
| list throw | `setItems([])` then “No notifications” | “We couldn't load notifications.” + Try again |
| unread_count > 0 and items [] | “No notifications” | distinct copy (not empty inbox) |

## Production bundle (`main.2f1c2452.js`)

Confirmed the old empty-state string and `/profile/in-app-notifications/unread-count`. No load-failure string. Frontend staging/production still need this bundle after develop deploy.
