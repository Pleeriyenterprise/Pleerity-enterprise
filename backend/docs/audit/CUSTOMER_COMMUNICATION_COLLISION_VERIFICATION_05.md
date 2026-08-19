# COMPLIANCE_ALERT collision verification 05

## Product roles (confirmed against code)

| Signal | Role |
| --- | --- |
| Daily / lifecycle reminder | Time-based **action** reminder: one eligible requirement → one requirement-specific email |
| COMPLIANCE_ALERT | Property **dashboard state-change** (degradation GREEN→AMBER/RED etc.) |
| MONTHLY_DIGEST | Intentional multi-item monthly summary |

COMPLIANCE_ALERT was not disabled.

## Same-day collision

When daily reminders are enabled and **exactly one** requirement id explains the degradation, the daily reminder already owns that customer intent. Sending COMPLIANCE_ALERT the same day is a duplicate.

When **multiple** requirements contribute, or the contributing set is unknown, the property-level status email remains distinct.

When daily reminders are off, COMPLIANCE_ALERT still sends (it is then the only customer signal).

## Suppression contract

`should_suppress_compliance_alert_for_property(contributing_requirement_ids, daily_reminders_enabled)`

* daily off → do not suppress
* one contributing id + daily on → suppress **email**
* 0 or 2+ ids → do not suppress

Suppressed properties still update `compliance_status` / `last_notified_status` and still fire webhooks.

`daily_reminders_enabled` = `expiry_reminders` AND `daily_reminder_enabled` (default true).

## Tests

Unit: `test_should_suppress_single_requirement_when_daily_reminders_enabled` and multi/unknown cases.

Expected: distinct purposes may coexist; materially duplicate messages for the same single requirement on the same day may not.
