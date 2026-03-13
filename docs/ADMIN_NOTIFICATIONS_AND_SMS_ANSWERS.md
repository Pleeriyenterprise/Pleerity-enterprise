# Admin notifications and SMS – implementation and verification

## 1. Are all admin notifications implemented and enforced?

**Implemented:** Yes. The system has:

- **Admin Notification Preferences** stored in `portal_users.notification_preferences` (email_enabled, sms_enabled, in_app_enabled, notification_email, notification_phone).
- **Order Notification Service** (`order_notification_service.py`) that sends Email, SMS, and in-app for order events. It loads all admins via `_get_admin_preferences()` and, for each admin, respects:
  - `prefs.get("email_enabled", True)` before sending email
  - `prefs.get("sms_enabled", False)` and `admin_phone` before sending SMS
  - `prefs.get("in_app_enabled", True)` before creating in-app notifications

**Event types** that trigger notifications (and whether email/SMS are used by default in code):

| Event                         | Email (config) | SMS (config) | In-app |
|------------------------------|----------------|-------------|--------|
| New Order                    | Yes            | No          | Yes    |
| Document Ready for Review    | Yes            | No          | Yes    |
| Client Input Required        | No             | No          | Yes    |
| Order Delivered              | No             | No          | Yes    |
| Delivery Failed              | Yes            | Yes         | Yes    |
| Order Failed                 | Yes            | Yes         | Yes    |
| SLA Warning                  | Yes            | No          | Yes    |
| SLA Breach                   | Yes            | No          | Yes    |

So: **channel-level enforcement (email/SMS/in-app on or off) is implemented and enforced** for the order-notification path that uses `OrderNotificationService`.

**Caveats:**

- **Event-level toggles:** The UI note is correct: there are no per-event toggles stored per admin. The backend uses a fixed `EVENT_CONFIG` per event (email_enabled/sms_enabled). So “all events are enabled for your selected channels” is accurate: if email is ON, you get email for every event that has `email_enabled: True` in config; you cannot turn off “New Orders” email only.
- **Legacy path:** `order_service.notify_admin_of_state()` is still used when an order transitions to certain states (e.g. INTERNAL_REVIEW, FAILED, DELIVERY_FAILED). That path uses a single admin from `portal_users` (role=admin) and does **not** read `notification_preferences`. So for those transitions, admin channel preferences are **not** enforced; the other path (workflow automation → `OrderNotificationService`) **does** enforce them.
- **Role/lookup consistency:** Admin preferences are looked up by `user_id` and `role: "admin"`. Elsewhere the app uses `portal_user_id` and `role: "ROLE_ADMIN"`. If the JWT or DB use `portal_user_id` / `ROLE_ADMIN`, the preferences lookup or the “get all admins” query can miss admins. Fixing this is recommended (see below).

---

## 2. Email and SMS end-to-end for admin and users

**Admin**

- **Email:** Sent via `NotificationOrchestrator` (template `ORDER_NOTIFICATION`). Requires `POSTMARK_SERVER_TOKEN`. Admin preferences (email_enabled, notification_email) are respected when using `OrderNotificationService`.
- **SMS:** Sent via `NotificationOrchestrator` (template `ADMIN_MANUAL_SMS`). Requires `SMS_ENABLED=true`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, and either `TWILIO_MESSAGING_SERVICE_SID` or `TWILIO_PHONE_NUMBER`. Only sent when the event has `sms_enabled: True` in `EVENT_CONFIG` and the admin has `sms_enabled: True` and a `notification_phone`.

**Users (clients)**

- **Email:** Reminders (e.g. daily expiry, compliance) go through `NotificationOrchestrator`; client `notification_preferences` (e.g. daily_reminder_enabled, quiet_hours) are respected in `jobs.py`.
- **SMS:** Reminders can be sent as SMS when the plan allows `sms_reminders` and client preferences have SMS enabled; same orchestrator and Twilio. OTP uses the same orchestrator with template `OTP_CODE_SMS`.

So both admin and user email/SMS are implemented and run through the same orchestrator; enforcement is via preferences (and plan for client SMS).

---

## 3. Why OTP/SMS might be failing

OTP is sent only via `NotificationOrchestrator` (template `OTP_CODE_SMS`). If sending fails, the API returns **503** with `code: "SMS_UNAVAILABLE"`.

**Common causes:**

1. **SMS not enabled:** `SMS_ENABLED` is not set to `"true"` (case-insensitive). The orchestrator then marks the message as `BLOCKED_PROVIDER_NOT_CONFIGURED` and does not call Twilio.
2. **Twilio not configured:** Missing or wrong `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, or both `TWILIO_MESSAGING_SERVICE_SID` and `TWILIO_PHONE_NUMBER`. The code requires either a messaging service SID or a from number.
3. **Twilio API error:** Invalid number, account issue, or rate limit. The error is written to `message_logs` (status `FAILED`, `error_message`).

**What to check:**

- Env: `SMS_ENABLED=true`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, and either `TWILIO_MESSAGING_SERVICE_SID` or `TWILIO_PHONE_NUMBER`.
- `message_logs` for the OTP attempt: `template_key = "OTP_CODE_SMS"`, then check `status` and `error_message`.
- Admin → **Notification Health** (e.g. `/admin/notification-health` and “recent” logs) to see recent SMS outcomes.

---

## 4. How to confirm SMS configuration works (apart from OTP)

- **Clients:** Use **Send test SMS** on the client notification preferences flow. That calls `POST /api/sms/test-send` (client auth, verified phone). It uses the same orchestrator and Twilio as OTP, so if test-send works, SMS config is fine for that path (and OTP should use the same config).
- **Admins:** Use **Send test SMS** on the Admin Notification Preferences page (when SMS is enabled and a notification phone is set). This calls `POST /api/admin/notifications/test-sms` and sends one SMS via the same orchestrator/Twilio as OTP and order notifications. If it succeeds, SMS configuration is working for admin. You can also use **Notification Health** (Admin → Notification Health → recent logs, filter by `channel: "SMS"`) to inspect status and errors.

---

## 5. Recommended code fixes

1. **Admin preferences lookup:** Use the same identifier and role as the rest of the app:
   - Resolve admin id as `current_user.get("portal_user_id") or current_user.get("user_id")` when getting/updating preferences.
   - When querying `portal_users`, use a query that matches your actual data (e.g. `portal_user_id` and/or `user_id`, and role `"ROLE_ADMIN"` or `"admin"` consistently). That way the same admin who sees the Preferences page is the one whose preferences are saved and used for order notifications.
2. **Order notification “get all admins”:** Ensure the role filter matches how admin users are stored (e.g. include both `"ROLE_ADMIN"` and `"admin"` if needed), so all admins receive order notifications when their preferences allow it.
3. **Legacy `notify_admin_of_state`:** Either remove it and rely on `OrderNotificationService` for those transitions, or make it load admin(s) and respect `notification_preferences` (email_enabled, sms_enabled, notification_phone) so behaviour is consistent.

After these, admin notification preferences will be consistently enforced and SMS/OTP issues can be debugged using env, `message_logs`, and (for clients) the test-send button.
