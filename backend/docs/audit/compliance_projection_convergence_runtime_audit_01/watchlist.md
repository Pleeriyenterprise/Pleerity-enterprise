# Watchlist — Today UI + score count post-deploy closeout

- **Today hero drift:** API `urgent_count=0` but browser elevates a file-review task as "Do this next" with Needs action 1. Investigate `pickPrimaryExecutionTask` / in_progress elevation vs assurance filter for issue-linked review tasks.
- **Score pipeline scope:** Score API `visible_requirement_count=8` while Requirements registry shows 10 visible rows. Dashboard quick actions already show "10 active in Requirements" vs "8 score-tracked obligations" — align Compliance Score page/API to same 10/8 split with `grouping_note`.
- **Grouping note absent:** `grouping_note` only emits when `visible > score_tracked`; score pipeline must source visible count from full registry (10) not deduped portal rows (8).
- **Harness impersonation:** Browser sessions require `role: ROLE_CLIENT_ADMIN` in localStorage user blob.
- **Re-run after fix:** `python scripts/today_ui_and_score_count_post_deploy_closeout_01_execute.py`
