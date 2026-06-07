# Watchlist — Today UI + score count semantics closeout

- **Deploy frontend fix:** `/today` still crashes on staging (`CVP_ErrorBoundary`) until bundle with `filterInboxTasksForOperationalActionability` deploys. Re-run `python scripts/today_ui_and_score_count_semantics_closeout_01_execute.py` after deploy.
- **Deploy backend semantics:** `visible_requirement_count`, updated `lifecycle_satisfied_count`, and `grouping_note` require backend deploy before staging API reflects 10/10 lifecycle satisfied.
- **Dashboard error boundary:** Harness flagged dashboard error boundary during impersonated session — verify after deploy (may be transient auth).
- **Score grouping note:** Appears when `visible_requirement_count > score_tracked_requirement_count`; confirm on Compliance Score page post-deploy.
