# Notification bell — runtime authority matrix 02

Programme: `NOTIFICATION-BELL-STAGING-UI-CERTIFICATION-02`  
Fixture: Elena Rodriguez / CRN `PLE-CVP-2026-000038` / staging impersonation.

| State | Count API | List API | Badge | Dropdown | Notification Centre | Verdict |
| --- | ---: | ---: | ---: | --- | --- | --- |
| 1 unread | 1 | 1 item `NOTIF-D583065A` | 1 | same item | All + Unread + Compliance same item | PASS |
| read | 0 | 1 visible (read) | 0 | same item remains | All has item; Unread empty | PASS |
| dismissed unread | 0 | C2 absent | 0 | C2 absent | C2 absent after dismiss POST 200 | PASS |
| 3 unread + leftover read | 3 | 3 unread + prior read rows | 3 | three D titles (after load) | Unread 3; All header 3 unread | PASS |
| mark all | 0 | 5 visible read (A, C, 3×D) | 0 | five titles, no unread badge | All retains; Unread empty | PASS |
| list failure | count still available | list 500 | not converted to empty inbox | “We couldn't load notifications” + Try again; **not** “No notifications yet” | not used for this intercept | PASS |

Notes:

- Dropdown `limit=30` never hid the single unread item.
- Unread count is the full unread query, not `items.length`.
- Category filter with `badge > 0` and zero items in Billing/System is valid.
