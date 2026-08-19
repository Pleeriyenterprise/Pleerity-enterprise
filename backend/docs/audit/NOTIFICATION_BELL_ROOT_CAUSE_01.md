# Notification bell — root cause 01

Programme: `NOTIFICATION-BELL-AUTHORITY-DRIFT-01`

Production was not mutated. Main was not merged.

## Pilot symptom (production screenshot)

Customer: **Emmanuel Afolabi**, CRN `PLE-CVP-2026-000004`, `pleerityenterprise.co.uk/requirements?status=OVERDUE_OR_MISSING`.

```text
header bell unread indicator present
dropdown = No notifications yet
browser tab showed “1 new message”
```

Production HTML `<title>` is `Pleerity | AI-Driven Solutions & Compliance`. The tab label is not that static title; treat it as corroboration that the client believed something was unread, not as a second inbox authority.

## Reproduced

| Surface | Result |
| --- | --- |
| Production UI | **Yes** (pilot screenshot) |
| Production APIs as that user | Not called (no production customer session; no production Mongo from this workstation) |
| Local query/list predicates | **Yes** (unit tests) |
| Production frontend bundle `main.2f1c2452.js` | Same empty copy; independent list + unread-count URLs; no load-failure copy |

## Root cause

Primary (customer-visible):

```text
FRONTEND_LIST_FAILURE_MASKED_AS_EMPTY
```

The header dropdown rendered **“No notifications yet.”** whenever `!loading && items.length === 0`. It did not distinguish:

* successful empty inbox;
* successful list `[]` with `unread_count > 0`;
* list request failure (and `Promise.all` previously aborted the count apply too).

Production bundle still contained that empty copy and **did not** contain “couldn't load”.

Contributing (backend, can produce `count=1` with an empty/wrong page):

```text
PAGINATION_FILTER_ORDER_DEFECT
COUNT_LIST_QUERY_DRIFT
```

`get_unread_count` counted the full collection for `recipient_id + is_read: false + not dismissed`.

`list_inbox_notifications` fetched up to 400 unmatched-order documents, then sorted in Python, then sliced to `limit` (dropdown `limit=30`). An unread row could be omitted from that window. Count and list also built the dismissed predicate differently (`$or` unpacked vs `$and`). Legacy `dismissed=true` without `dismissed_at` was still counted.

Audience/privacy: list and count both key on `recipient_id` = authenticated `portal_user_id`. No cross-customer leak proven. Work-order fan-out may also write `recipient_id=email`; that is a same-customer address variant, not another tenant.

## Severity

```text
P1
```

A normal landlord can see a ghost unread indicator and cannot open the item from the same surface. Not P0: no cross-customer exposure proven.

## Pilot production record

```text
CURRENT_BUG_STATE
```

Identity from the screenshot (name + CRN). `client_id` / `portal_user_id` not retrieved: Atlas MCP has org AI access disabled; local `DB_NAME` is `pleerity_staging`, where the same CRN is a different fixture (Alexandra Chen) — not this pilot.

Do not delete production notification history in this exercise. After code promotion, re-read the account. If a stale row remains, use a separately governed reconciliation.
