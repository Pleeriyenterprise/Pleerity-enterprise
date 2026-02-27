# Why am I not receiving notifications? (Troubleshooting)

Your notification toggles are all ON, but you're not receiving any. Here are the **exact conditions** under which each notification is sent and what to check.

---

## 1. Preferences are saved correctly

- **Frontend:** Settings → Notifications → toggles and "Send reminders before certificates expire" (e.g. 1 day) → **Save**.
- **Backend:** Preferences are stored in `notification_preferences` by `client_id` (from your logged-in portal user). If you didn’t click Save after changing toggles, the server still has the old values.
- **Check:** Reload the Notifications page and confirm the toggles still show as you expect. If they reset, the save may have failed (check browser network tab for `PUT /api/profile/notifications`).

---

## 2. Expiry reminders (daily)

**When they’re sent:** A **scheduled job** runs daily and sends an email only if you have at least one requirement that is:

- **Overdue** (past due date), or  
- **Expiring within the reminder window** you chose (e.g. “1 day” = due today or tomorrow).

**So you get no reminder if:**

- You have **no requirements** (no certificates/items tracked), or  
- Every requirement is **more than 1 day away** from its due date (e.g. you set “1 day” and nothing expires today or tomorrow).

**Also required:**

- Your **subscription_status** is `ACTIVE` and **entitlement_status** is `ENABLED` (or unset).
- **Daily reminders** toggle is ON (you have this).
- Not in **Quiet hours** (yours are OFF).
- The client record has an **email**: `client.email` or `client.contact_email` must be set; otherwise the job skips sending and logs “no recipient”.

**Practical check:**  
If “Send reminders before certificates expire” is set to **1 day**, try changing it to **30 days** and wait for the next daily job run. If you have any requirement expiring in the next 30 days, you should get one reminder email (assuming the rest above is OK).

---

## 3. Compliance status alerts (GREEN → AMBER → RED)

**When they’re sent:** A job runs **twice per day** and only sends an email when a **property’s compliance status gets worse** than the last time we notified you (e.g. GREEN → AMBER or AMBER → RED).

**So you get no alert if:**

- No property’s status has **degraded** since the last notification (e.g. everything stays GREEN, or already RED and we already notified).
- You’re in **Quiet hours** (you have them OFF).

**Check:** Have any of your properties actually moved to AMBER or RED recently? If not, no email is expected.

---

## 4. Monthly digest

**When it’s sent:** **Once per month**, on the **1st of the month at 10:00 UTC**, to clients who have the Monthly Digest toggle ON.

**So you get nothing if:**

- It’s not the 1st (or the job hasn’t run yet that day).
- The client has no **email** (`client.email` or `client.contact_email`).

---

## 5. Document updates

**When they’re sent:** When something in the system triggers a “document update” event (e.g. AI extraction applied to an uploaded document). The code checks the **Document updates** preference before sending.

**So you get nothing if:**

- No such event has happened (e.g. no recent uploads/processing that trigger the notification).
- **Document updates** is OFF (yours is ON).

---

## 6. SMS (urgent alerts)

You have **“Urgent Alerts Only”** ON: SMS is sent only when there are **overdue** items in the daily reminder, or (depending on implementation) for the most critical alerts. If there are no overdue items and no RED status change, **no SMS is sent** even though the main SMS toggle is ON.

---

## 7. Email delivery (backend)

For **any** email to be delivered:

- **POSTMARK_SERVER_TOKEN** must be set and valid (Postmark is used for email).
- The client must have **email** or **contact_email** set.
- No global throttling or provider errors (check **message_logs** and any audit events like `EMAIL_SKIPPED_NO_RECIPIENT`, `NOTIFICATION_PROVIDER_NOT_CONFIGURED`).

An admin can:

- Confirm the client document has `email` or `contact_email`.
- Check **message_logs** for your `client_id` to see if sends were attempted and with what status.
- Confirm the daily reminder and compliance check jobs are running (scheduler / logs).

---

## Summary table

| Notification type   | Trigger condition                                      | Why you might get nothing                    |
|--------------------|--------------------------------------------------------|---------------------------------------------|
| Expiry reminders   | ≥1 requirement overdue or expiring within reminder window | No requirements, or none in window (e.g. 1 day) |
| Status alerts      | Property status got worse (e.g. GREEN→RED)            | No status degradation                       |
| Monthly digest    | 1st of month, 10:00 UTC                                | Not the 1st, or no client email             |
| Document updates   | Document event (e.g. AI extraction)                    | No such event                               |
| SMS                | Urgent only: overdue / critical                        | No overdue items, no RED change             |

**Most likely in your case:** With **“1 day”** for reminders, you only get an email when something expires **today or tomorrow** (or is overdue). If all your certificates are further out, the system correctly sends **no** reminder. Try **30 days** to see a reminder sooner, and ensure the client has a valid email and preferences are saved.
