# Watchlist

- Classification: **PARTIAL** (fix committed; browser re-verify after Vercel deploy)
- Root cause: `ClientTasksPage` called `setPayload(todayHit)` instead of `setPayload(todayHit.data)` — Dashboard already unwrapped correctly.
- Property detail: header bypassed `getPropertyDisplayName`; compliance-detail omitted address fields (now fixed backend + frontend).
- API `/today/items` returns 40 open items (24 urgent + 8 upcoming + 8 in progress) for nancy@yopmail.com — not empty.
- `bucket_continuation` caps visible rows; disclosure banner added on Today page.
- Value insights “Urgent inbox items” is urgent-only; Dashboard Today KPI = urgent + upcoming + in-progress.
- Re-run `tmp_prelaunch_inbox_dashboard_property_truth_repair_01.py` after deploy → target **VERIFIED_OPERATIONALLY**.
