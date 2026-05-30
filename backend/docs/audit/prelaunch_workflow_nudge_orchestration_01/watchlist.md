# PRELAUNCH-WORKFLOW-NUDGE-ORCHESTRATION-01 — Watchlist (post-closeout)

Programme closed **VERIFIED_OPERATIONALLY** on staging (`8cb2524f`).

## Minor follow-ups (non-blocking)

1. **Branded WORKFLOW_NUDGE email template** — nudges currently use `ADMIN_MANUAL` with human copy (consistent with visit/quote emails).
2. **Completion-proof / invoice timer hooks** — wire `on_work_order_completion_proof_pending` and `on_work_order_invoice_pending` at status transitions.
3. **Command Centre primary slim rows** — stall actions merge correctly in backend; primary slim payload may not always expose `primary_action_label` for every stall row (Today disclosure is authoritative for stall truth).
4. **Analytics** — `workflow_continued_after_nudge` / `abandonment_recovered` need product action-tracking hooks.

## Re-verification

Re-run `python tmp_prelaunch_workflow_nudge_orchestration_01_closeout.py` after material workflow changes.
