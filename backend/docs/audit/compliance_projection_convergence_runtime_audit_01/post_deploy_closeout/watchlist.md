# Watchlist — post-deploy closeout

- **Score aggregation count drift:** Requirements API reports 10/10 lifecycle valid; compliance-score and dashboard impact show **8 valid / 8 compliant**. Investigate which 2 requirements are excluded from score `total_requirements` and whether that exclusion is intentional.
- **Dashboard compliance_summary drift:** `compliant: 6` vs `total_requirements: 10` in API snapshot — reconcile dashboard summary builder with `is_requirement_satisfied` authority.
- **Today assurance surfacing:** API `urgent_count=0` but UI shows **Needs action: 1** and **DO THIS NEXT** for document-review assurance tasks. Confirm whether assurance items should remain in operational inbox header counts or move to informational assurance notices only.
- **Quick actions / score recommendations:** Four HIGH-priority assurance cards (FIRE_DETECTION self-recorded, GAS_SAFETY review) remain. Dashboard subtext distinguishes assurance confidence; score page does not. Align labeling and priority with non-operational assurance semantics.
- **93/100 score:** Likely intentional assurance-confidence cap (not a legal breach). Verify copy clearly states compliance obligations are met while confidence score is sub-100; confirm 100/100 remains achievable after assurance verification completes.
