# Notification bell — count vs list authority 01

Programme: `NOTIFICATION-BELL-AUTHORITY-DRIFT-01`

Collection: `in_app_notifications`.

Recipient authority: `portal_users.portal_user_id` passed as `recipient_id`.

## Before (production `13eca909` / develop prior to this fix)

| Filter | Unread count | List (`inbox_filter=all`) |
| --- | --- | --- |
| `recipient_id` | yes | yes |
| `is_read` | `False` only | not applied |
| dismissed | `$or` null / missing `dismissed_at` unpacked onto the query | same `$or` inside `$and` |
| legacy `dismissed: true` | still counted | still listed |
| `expires_at` | ignored | ignored |
| audience/role | none (recipient_id only) | none |
| pagination | full count | `to_list(max(limit*4, 400))` **then** Python sort **then** `[:limit]` |
| ordering | n/a | unread/severity/recency in process, **after** the 400 cap |

**Could a notification satisfy unread-count and be excluded from list?** Yes.

1. Unread document not among the first 400 unordered matches.
2. Dropdown `limit=30` after that window, if unread was never fetched.
3. Frontend treating `items=[]` (or a failed list) as “No notifications yet” while the count endpoint returned `1`.

## After (this implementation)

Shared helpers in `services/order_service.py`:

* `inbox_visibility_query(recipient_id)`
* `inbox_unread_query(recipient_id)`

| Filter | Unread count | List |
| --- | --- | --- |
| `recipient_id` | same | same |
| dismissed | `dismissed_at` null/missing **and** not `dismissed=true` | same |
| unread | `is_read` false / null / missing | unread filter uses the same; `all` does not require unread |
| sort | n/a | Mongo `is_read` ascending, `created_at` descending, **then** limit |
| `expires_at` | still ignored (both sides) | still ignored |

Client list JSON now includes `unread_count` from `get_unread_count` (not `len(items)`).

Admin list already returned `unread_count` separately; it now uses the same list/count helpers.

## Invariant

```text
unread_count
=
count of in_app_notifications the same recipient can retrieve
as unread under inbox_visibility_query
```

Pagination: badge may be `> limit`; dropdown shows latest unread-first page plus **View all**. Empty dropdown + badge > 0 is no longer an empty-inbox message.
