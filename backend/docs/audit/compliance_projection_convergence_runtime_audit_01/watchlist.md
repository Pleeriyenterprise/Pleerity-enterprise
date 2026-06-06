# Watchlist — assurance post-deploy closeout

- **Today page error boundary:** Browser `/today` route crashes with `CVP_ErrorBoundary` under impersonated session while other routes load. Investigate client-side Today render after assurance filter changes.
- **lifecycle_satisfied_count scope:** Stats report 8 (score-tracked/alias scope) while Requirements page shows 10/10 satisfied. Confirm UI labels always cite Requirements page for lifecycle truth and score page for score-tracked scope.
- **Gap engine MISSING_EVIDENCE (5 LOW):** Informational only; monitor that these do not resurface as operational Today urgency after Today fix.
- **Re-run closeout** after Today browser fix: `python scripts/compliance_assurance_actionability_post_deploy_closeout_01_execute.py`
