# Admin notification bell – why it might not show notifications

## How it works

- **Frontend:** `NotificationBell.jsx` in the admin layout calls:
  - `GET /api/admin/notifications/unread-count` (on load and every 30s)
  - `GET /api/admin/notifications/?limit=20` (when the dropdown is opened)
- **Auth:** Requests use `Authorization: Bearer <token>` with `localStorage.getItem('auth_token')` (same token as admin login).
- **Backend:** List and unread-count use `recipient_id` to filter: they resolve the current admin as `portal_user_id` or `user_id` from the JWT and query `in_app_notifications` where `recipient_id` equals that value.

So the bell only shows notifications whose **recipient_id** matches the **current admin’s id** (the one in the JWT: `portal_user_id` or `user_id`).

## Why you might not see any notifications

1. **No in-app notifications are being created**
   - Order events (new order, document ready, SLA warning, etc.) create in-app notifications only when `OrderNotificationService.notify_order_event()` is used (e.g. from workflow automation or webhooks). If your orders don’t go through that path, no order notifications are written.
   - Incidents create in-app notifications for all staff (role in ROLE_OWNER, ROLE_ADMIN, ROLE_SUPPORT) via `incident_service`.
   - “Client info received” creates one in-app notification when a client submits info; the admin is looked up with role in `["ROLE_ADMIN", "admin", "ROLE_OWNER"]` and status in `["active", "ACTIVE"]`; `recipient_id` is `portal_user_id` or `user_id`.

2. **recipient_id mismatch**
   - Notifications are stored with `recipient_id` set to the admin’s `portal_user_id` (or `user_id`) at **creation** time. The **bell** filters by the id from the **JWT** (`portal_user_id` or `user_id`). If those don’t match (e.g. different field used in DB vs token), the bell won’t show them.
   - All creators (order notification service, incident service, client_orders) now use `portal_user_id` or `user_id` from the same admin document so they match what the JWT carries.

3. **Wrong admin lookup when creating notifications**
   - Previously, “client info received” used `role: "admin"` and `status: "active"` and `admin["user_id"]`. In setups where `portal_users` use `ROLE_ADMIN` and `ACTIVE` and only have `portal_user_id`, that found no admin or used the wrong id. This has been fixed so the same role/status and id logic as the rest of the app is used.

4. **Auth token**
   - The bell uses `localStorage.getItem('auth_token')`. If the admin isn’t logged in or the token is missing/expired, requests return 401 and the bell shows no data.

## What was fixed

- **client_orders (client info received):** Admin lookup now uses `role` in `["ROLE_ADMIN", "admin", "ROLE_OWNER"]` and `status` in `["active", "ACTIVE"]`, and `recipient_id` is set to `admin.get("portal_user_id") or admin.get("user_id")` so it matches the JWT and the bell.
- **List response:** Notification list serialises `created_at` and `read_at` to ISO strings so the frontend always gets valid date strings.

## How to confirm the bell is working

1. **Check auth:** Log in as admin, open devtools → Application → Local Storage and confirm `auth_token` is set.
2. **Check API:** Open `GET /api/admin/notifications/unread-count` (e.g. in Network tab). It should return 200 and `{ "unread_count": 0 }` or a number; 401 means auth problem.
3. **Create a notification:** Trigger an event that creates an in-app notification (e.g. create an incident, or have a client submit info on an order, or trigger an order event that goes through `OrderNotificationService`). Then refresh or wait for the next poll and open the bell; the new notification should appear if `recipient_id` matches your admin’s `portal_user_id`/`user_id`.
