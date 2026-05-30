# PRELAUNCH-WORKFLOW-NUDGE-ORCHESTRATION-01 — Watchlist

## Post-deploy (required for VERIFIED_OPERATIONALLY)

1. **Deploy to staging/production** — re-run `tmp_prelaunch_workflow_nudge_orchestration_01.py` and confirm `workflow_stall_disclosure` on Today payload.
2. **Admin job smoke** — trigger `workflow_nudge_processing`; confirm `workflow_nudge_metrics` row and no duplicate same-day sends.
3. **Browser scenarios** — quote abandonment, visit delay, activation delay, evidence review delay, overdue requirement (7 scenarios from programme Part 10).
4. **Command Centre** — confirm stalled WO appears with continuation CTA label (e.g. "Review contractor quote").

## Implementation gaps (small)

5. **Evidence upload timer hook** — wire `on_evidence_uploaded` in `routes/documents.py` perform_client_document_upload and contractor evidence upload routes.
6. **Completion proof / invoice timers** — wire `on_work_order_completion_proof_pending` and `on_work_order_invoice_pending` at status/invoice transitions.
7. **Branded WORKFLOW_NUDGE template** — currently uses `ADMIN_MANUAL` with human copy (consistent with visit/quote emails).

## Operational

8. **Backfill canonical timers** — legacy jobs rely on `assigned_at` / `quote_submitted_at` fallback until next transition.
9. **Analytics** — `workflow_continued_after_nudge` / `abandonment_recovered` metrics need action-tracking follow-up.
