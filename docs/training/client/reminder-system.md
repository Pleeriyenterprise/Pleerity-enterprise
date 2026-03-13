# Client – Reminder System (Notifications) – Training Manual

## 1. Module name
**Reminder System** (Client view: Notification preferences and how reminders work)

## 2. Audience
**Client / end user.** Admins have a separate manual for monitoring and running the reminder job.

## 3. Purpose
Clients do **not** configure when reminders run (that is system-scheduled). They **do** control: (1) whether they receive **daily compliance reminders** (email and/or SMS), (2) email vs SMS preferences, and (3) other notification toggles (e.g. digests, marketing). This manual explains what reminders are, where to turn them on/off, and what to expect.

## 4. Where to find it in the UI
- **URL:** `/settings/notifications` (under Settings).
- **Navigation:** Sidebar → **Settings** → **Notifications**, or direct link to notification preferences.

## 5. What the user sees on the page
- **Sections:** Typically “Email notifications”, “SMS notifications”, and possibly “Reminders” or “Compliance reminders.”
- **Email:** Toggles for different notification types. Relevant for reminders: e.g. **Daily compliance reminders** (expiry reminders), **Monthly digest**, **Order/transactional** emails. Each can be on/off.
- **SMS:** Phone number field; verify with OTP. Toggles for **SMS reminders** (if plan supports). When SMS is on, compliance reminders may be sent by SMS in addition to or instead of email (implementation-specific).
- **Save:** Button to persist preferences. Backend: `GET/PUT` or `PATCH` on profile or notification-preferences API.
- **Help text (if any):** Short explanation that reminders are sent for expiring requirements and that they can turn them off here.

## 6. Step-by-step actions

| Action | What to click | What happens |
|--------|----------------|--------------|
| View preferences | Open Settings → Notifications | Current toggles and phone number load from API. |
| Turn daily reminders on/off | Toggle “Daily compliance reminders” or “Expiry reminders” | Save updates backend. When **on**, user may receive daily emails (and SMS if enabled) for requirements expiring in the configured window. When **off**, `daily_reminders` job skips this user. |
| Turn SMS on | Enter phone → Send verification code → Enter code → Verify | `POST /otp/send` (action verify_phone), then `POST /otp/verify`. On success, phone is verified; SMS toggles can be enabled. |
| Enable SMS reminders | Toggle “SMS reminders” or similar (after phone verified) | Save; future reminder job may send SMS in addition to email (if template and config support it). |
| Save all | Click Save | Preferences persisted; next reminder run respects new settings. |
| Turn reminders off | Turn “Daily compliance reminders” / “Expiry reminders” off → Save | User will not receive daily reminder emails (or SMS) for expiring items. They can still view due items on Dashboard and Compliance. |

## 7. What happens after each action
- **Save:** Backend stores preferences (e.g. `daily_reminder_enabled`, `expiry_reminders`, `sms_reminders`). No immediate email/SMS; next scheduled `daily_reminders` run (e.g. 09:00 UTC) uses the new settings.
- **Verify phone:** OTP sent; user enters code; backend marks phone verified. SMS options become available.
- **Turn off reminders:** Next run skips this user for reminder sends; they can re-enable anytime.

## 8. Status/outcome examples
- **Reminders on, email only:** User receives daily email when they have requirements expiring in the reminder window (e.g. next 30 days). No SMS unless they enable SMS and verify phone.
- **Reminders on, SMS enabled:** User may receive both email and SMS (or SMS only if configured that way). Depends on template and plan.
- **Reminders off:** No reminder emails/SMS for expiring items. Other emails (e.g. order confirmation) may still send per their toggles.
- **SMS verification failed:** Invalid code or expired OTP; user retries. If SMS service is unavailable (503), message may say “try again later.”
- **Phone not verified:** SMS reminder toggle may be disabled or greyed until phone is verified.

## 9. Common errors or confusing points
- **“I didn’t get a reminder”:** Check (1) Reminders are **on** in Settings → Notifications, (2) They have at least one requirement expiring in the window, (3) Email (and SMS if used) is correct and verified. Reminders run once per day (e.g. morning); they don’t send “right now” when they turn the toggle on.
- **“When do reminders send?”:** Not configurable by user; system runs daily (e.g. 09:00 UTC). Training: “Reminders are sent once per day; make sure your preferences are on if you want them.”
- **SMS not available:** Some plans or configs don’t support SMS; toggle may be hidden or show “unavailable.” Email reminders still work if enabled.
- **Two toggles:** “Daily compliance reminders” and “Expiry reminders” may be the same or separate (e.g. one for daily digest, one for expiry). Confirm in your build and train accordingly.

## 10. Current limitations or known gaps
- **Needs runtime confirmation:** Exact toggle labels (daily_reminder_enabled vs expiry_reminders) and whether both exist; whether SMS reminders are supported in your environment.
- No “preview” or “send test reminder” from client UI. User cannot see a log of “reminders sent to me” in the client portal.
- Reminder window (e.g. “next 30 days”) is typically server/config; not user-configurable in base implementation.
- Deduplication: one reminder per requirement/client/day; if user has multiple expiring items, they may get one email listing them (implementation-specific).

## 11. Notes for training staff
- “Reminders are automatic and daily. Clients only choose whether to receive them and by email or SMS.”
- “If a client says they didn’t get one, have them check Settings → Notifications and that they have something due in the next few weeks.”
- “Turning reminders off doesn’t remove due dates; they can still see what’s due on the Dashboard and Compliance page.”
- For admin-side monitoring (did the job run? delivery?), refer to admin Reminder System manual.

---

## Trainer walkthrough (5–10 minutes)

1. **Open Settings → Notifications** → show sections (Email, SMS).
2. **Point out “Daily compliance reminders” / “Expiry reminders”:** “This controls whether you get daily emails about expiring certificates and checks.”
3. **Toggle on/off and Save:** “If you turn it off, you won’t get those emails; you can still see what’s due on the Dashboard.”
4. **SMS (if available):** “To get SMS reminders, enter your phone, get the code, verify. Then you can turn on SMS reminders.”
5. **Set expectation:** “Reminders are sent once per day by the system; you can’t choose the time. Just leave the toggle on if you want them.”
6. **Q&A:** “I didn’t get a reminder” → check preferences are on, they have something due, and email/phone is correct.
