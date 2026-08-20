# Notification bell — pilot follow-up 02

Programme: `NOTIFICATION-BELL-STAGING-UI-CERTIFICATION-02`  
Parent investigation: `NOTIFICATION_BELL_PILOT_ACCOUNT_ASSESSMENT_01.md`

## Production pilot

| Field | Value |
| --- | --- |
| Name | Emmanuel Afolabi |
| CRN | `PLE-CVP-2026-000004` |
| This exercise | **read-only, not opened** |
| Mark read / dismiss / delete / Mongo patch | **not performed** |

Production API remained `13eca909`. Atlas MCP still cannot read production Mongo. No production session as this user.

## Classification

Exact ghost row for the pilot:

```text
UNKNOWN_UNTIL_PRODUCTION_READ
```

Programme 01 customer-visible causes (count/list drift, pagination-before-filter, list failure masked as empty) are fixed in `a5d71332`. Whether Emmanuel’s current badge is a leftover legacy document cannot be proven without a production read of `in_app_notifications`.

After production promotion of this SHA:

```text
LEGACY_DATA_RECONCILIATION_REQUIRED
```

if a read-only query still finds unread rows that fail the new visibility predicate (or a stale denormalized count). Do not silently delete production history. Do not repair only this user.

## Staging fixture vs pilot

Staging CRN `PLE-CVP-2026-000038` (Elena Rodriguez, yopmail) is **not** the production pilot. Staging CRN `000004` must not be treated as Emmanuel.
