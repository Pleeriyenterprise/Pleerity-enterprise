# Notification bell — pilot account assessment 01

Programme: `NOTIFICATION-BELL-AUTHORITY-DRIFT-01`

Production data was **not** mutated.

## Identity (screenshot, not guessed IDs)

| Field | Value |
| --- | --- |
| Display name | Emmanuel Afolabi |
| CRN | `PLE-CVP-2026-000004` |
| Role (UI) | client portal (Requirements, not admin chrome) |
| Host | `pleerityenterprise.co.uk` |

`client_id` / `portal_user_id` / live API JSON: **not retrieved**.

## Why records were not dumped

* MongoDB Atlas MCP: organization AI client access disabled.
* Workstation `.env` `DB_NAME=pleerity_staging`. The same CRN there is **Alexandra Chen** — a staging fixture clash, **not** the production pilot. That database was not used to infer the pilot’s notifications.

## Preferences / HTTP

Not captured (no production session). Do not invent.

## Classification

```text
CURRENT_BUG_STATE
```

The screenshot is the unread-badge vs empty-dropdown inconsistency on the live customer frontend. After the code fix is promoted, re-inspect this account **read-only**. If an unread row exists and is listable, the UI defect is closed. If count remains 1 with no retrievable row, schedule a **separate** reconciliation — do not silently delete history in this programme.
